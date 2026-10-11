import numpy as np
import pytest

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis import analyze
from speech_analysis.clarity import classify_clarity, clarity_score
from speech_analysis.emotion import StubEmotion
from speech_analysis.fillers import split_by_fillers
from speech_analysis.recognition import OnnxRecognizer, StubRecognizer
from speech_analysis.segments import build_segments
from talkmate.services.recommendation_service import build_recommendation, find_issues

from .conftest import SR, upload, voice
from .test_analysis import FakeOnnxModel


def test_score_follows_calibration_points():
    assert clarity_score([1.0, 1.0]) == pytest.approx(98)
    assert clarity_score([0.985]) == pytest.approx(95)
    assert clarity_score([0.95]) == pytest.approx(86)
    assert clarity_score([0.905]) == pytest.approx(75)
    assert clarity_score([0.84]) == pytest.approx(40)
    assert clarity_score([0.0]) == 0


def test_score_is_monotonic_and_uses_mean():
    scores = [clarity_score([p]) for p in np.linspace(0, 1, 60)]
    assert all(a <= b for a, b in zip(scores, scores[1:]))
    assert clarity_score([1.0, 0.9]) == pytest.approx(clarity_score([0.95]))


def test_score_without_probabilities_is_none():
    assert clarity_score([]) is None
    assert clarity_score([None, None]) is None
    assert clarity_score([None, 0.95]) == pytest.approx(86)


def test_levels():
    assert classify_clarity(95, T) == "clear"
    assert classify_clarity(88, T) == "clear"
    assert classify_clarity(87.9, T) == "medium"
    assert classify_clarity(75, T) == "medium"
    assert classify_clarity(74.9, T) == "unclear"
    assert classify_clarity(None, T) is None
    assert classify_clarity(80, dict(T, clarity_unclear=85)) == "unclear"


def test_unclear_words_are_marked_and_filler_wins():
    text = "Ну, сегодня расскажу проекте."
    parts = split_by_fillers(text, unclear=[(4, 11), (0, 2)])
    assert "".join(p["text"] for p in parts) == text
    assert [(p["text"], p["filler"], p["unclear"]) for p in parts] == [
        ("Ну", True, False), (", ", False, False), ("сегодня", False, True), (" расскажу проекте.", False, False),
    ]


def test_segment_clarity_and_unclear_words():
    # Первая фраза произнесена чётко, во второй модель почти не узнала одно слово.
    tokens = [("Добрый", 0.0, 0.99), (" день", 0.5, 0.99), (" всем", 1.0, 0.98), (" коллегам", 1.5, 0.99), (".", 2.5, 0.99),
              (" Сегодня", 3.0, 0.9), (" рас", 3.5, 0.3), ("скажу", 3.8, 0.8), (" про", 4.5, 0.85), (" проект", 5.0, 0.9), (".", 6.0, 0.9)]
    first, second = build_segments(tokens, 7.0, T)
    assert first["clarity"] >= 95 and first["clarity_level"] == "clear"
    assert not any(p["unclear"] for p in first["parts"])
    assert second["clarity"] < 75 and second["clarity_level"] == "unclear"
    assert [p["text"] for p in second["parts"] if p["unclear"]] == ["расскажу"]


def test_segments_without_probabilities_have_no_clarity():
    segment = build_segments([("раз", 0.0), (" два", 1.0), (" три", 2.0), (" четыре", 3.0)], 4.0, T)[0]
    assert segment["clarity"] is None and segment["clarity_level"] is None
    assert not any(p["unclear"] for p in segment["parts"])


def test_onnx_recognizer_passes_model_confidence(monkeypatch):
    model = FakeOnnxModel(replies=[([" При", "вет", " мир"], [0.0, 0.2, 0.6])])
    monkeypatch.setitem(OnnxRecognizer._models, "conf-model", model)
    original = model.recognize

    def with_logprobs(waveform, sample_rate):
        result = original(waveform, sample_rate)
        result.logprobs = [np.log(0.9), np.log(0.5), 0.0]
        return result

    monkeypatch.setattr(model, "recognize", with_logprobs)
    recognizer = OnnxRecognizer("conf-model")
    detailed = recognizer.recognize_detailed(voice(duration=1.0))
    assert [(piece, time) for piece, time, _ in detailed] == [(" При", 0.0), ("вет", 0.2), (" мир", 0.6)]
    assert [round(p, 2) for _, _, p in detailed] == [0.9, 0.5, 1.0]
    assert recognizer.recognize_timed(voice(duration=1.0)) == []      # ответы модели в тесте закончились


class ConfidentRecognizer:
    """Распознаватель с заданной уверенностью: имитирует чёткую и невнятную речь."""

    def __init__(self, probability):
        self.probability = probability

    def recognize_detailed(self, samples):
        words = "добрый день коллеги сегодня я расскажу о нашем проекте подробно".split()
        step = len(samples) / SR / len(words)
        return [((" " if i else "") + w, i * step, self.probability) for i, w in enumerate(words)]


def test_pipeline_reports_clarity(make_wav):
    clear = analyze(make_wav(duration=6.0), T, ConfidentRecognizer(0.99), StubEmotion())
    mumbled = analyze(make_wav(duration=6.0), T, ConfidentRecognizer(0.86), StubEmotion())
    assert clear.clarity > 95 and clear.clarity_level == "clear"
    assert mumbled.clarity < 60 and mumbled.clarity_level == "unclear"
    unknown = analyze(make_wav(duration=6.0), T, StubRecognizer("добрый день коллеги сегодня"), StubEmotion())
    assert unknown.clarity is None and unknown.clarity_level is None


def test_recommendation_mentions_unclear_speech(make_wav):
    mumbled = analyze(make_wav(duration=6.0, amplitude=0.15, f0=110.0, f0_end=220.0), T, ConfidentRecognizer(0.86), StubEmotion())
    assert "unclear" in find_issues(mumbled, T)
    assert "говорить чётче" in build_recommendation(mumbled, T)[1]
    clear = analyze(make_wav(duration=6.0, amplitude=0.15, f0=110.0, f0_end=220.0), T, ConfidentRecognizer(0.99), StubEmotion())
    assert "unclear" not in find_issues(clear, T)


def test_api_returns_clarity_and_keeps_it_in_stats(tmp_path, make_wav):
    from talkmate import create_app
    from talkmate.config import Config

    from .conftest import auth, register

    config = Config(DATABASE_URL="sqlite://", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40,
                    ADMIN_EMAIL="admin@test.ru", ADMIN_PASSWORD="adminpass")
    app = create_app(config, recognizer=ConfidentRecognizer(0.95), emotion_backend=StubEmotion())
    client = app.test_client()
    headers = auth(register(client)["token"])
    body = upload(client, headers, make_wav(duration=6.0)).get_json()
    assert body["feedback"]["clarity"] == 86 and body["feedback"]["clarity_level"] == "medium"
    assert body["segments"][0]["clarity"] == 86
    stats = client.get("/api/stats", headers=headers).get_json()
    assert stats["points"][0]["clarity"] == 86
    assert stats["thresholds"]["clarity_unclear"] == 75 and stats["thresholds"]["clarity_clear"] == 88

    # Администратор поднял планку: та же запись теперь считается невнятной.
    admin = auth(client.post("/api/auth/login", json={"email": "admin@test.ru", "password": "adminpass"}).get_json()["token"])
    assert client.put("/api/admin/thresholds", headers=admin, json={"clarity_unclear": 90, "clarity_clear": 95}).status_code == 200
    assert upload(client, headers, make_wav(duration=6.0)).get_json()["feedback"]["clarity_level"] == "unclear"
    assert client.put("/api/admin/thresholds", headers=admin, json={"clarity_unclear": 96}).status_code == 400


def test_api_clarity_is_null_when_recognizer_gives_no_confidence(client, user, make_wav):
    body = upload(client, user["headers"], make_wav()).get_json()
    assert body["feedback"]["clarity"] is None and body["feedback"]["clarity_level"] is None
