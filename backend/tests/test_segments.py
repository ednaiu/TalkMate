import numpy as np
import pytest

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis import analyze
from speech_analysis.emotion import StubEmotion
from speech_analysis.recognition import StubRecognizer, spread_evenly
from speech_analysis.segments import build_segments

from .conftest import SR, auth, register, upload, voice


def timed(*phrases):
    """Собирает кусочки с временем из фраз вида (текст, начало, конец): слова фразы идут равномерно."""
    tokens = []
    for text, start, end in phrases:
        words = text.split()
        step = (end - start) / len(words)
        for i, word in enumerate(words):
            tokens.append(((" " if tokens else "") + word, start + i * step))
    return tokens


def test_sentences_become_segments_with_their_own_rate():
    tokens = timed(
        ("Добрый день, уважаемые коллеги, начнём.", 0.0, 4.0),                        # 5 слов за 4 с: 75 слов/мин
        ("Сегодня я очень быстро расскажу вам обо всём что мы успели сделать за этот год.", 4.0, 8.0),  # 15 слов за 4 с: 225
        ("Теперь можно выдохнуть и обсудить вопросы.", 8.0, 11.0),
    )
    segments = build_segments(tokens, duration=11.0, thresholds=T)
    assert [s["text"] for s in segments] == [
        "Добрый день, уважаемые коллеги, начнём.",
        "Сегодня я очень быстро расскажу вам обо всём что мы успели сделать за этот год.",
        "Теперь можно выдохнуть и обсудить вопросы.",
    ]
    assert [(s["start"], s["end"]) for s in segments] == [(0.0, 4.0), (4.0, 8.0), (8.0, 11.0)]
    assert [s["rate"] for s in segments] == [75, 225, 120]
    assert [s["rate_status"] for s in segments] == ["slow", "fast", "normal"]


def test_short_sentences_are_merged():
    tokens = timed(("Так.", 0.0, 0.5), ("Да.", 0.5, 1.0), ("Сегодня мы говорим о подготовке к выступлению перед залом.", 1.0, 5.0),
                   ("Спасибо.", 5.0, 5.5))
    segments = build_segments(tokens, duration=6.0, thresholds=T)
    assert len(segments) == 1
    assert segments[0]["text"].startswith("Так. Да. Сегодня") and segments[0]["text"].endswith("Спасибо.")
    assert segments[0]["start"] == 0.0 and segments[0]["end"] == 5.6


def test_text_without_punctuation_splits_on_pauses():
    tokens = timed(("добрый день уважаемые коллеги начнём встречу", 0.0, 3.5), ("сегодня расскажу о нашем новом проекте подробно", 6.0, 9.5))
    segments = build_segments(tokens, duration=10.0, thresholds=T)
    assert [s["text"] for s in segments] == ["добрый день уважаемые коллеги начнём встречу", "сегодня расскажу о нашем новом проекте подробно"]
    # Пауза между фразами входит в первую: шесть слов за шесть секунд.
    assert segments[0]["rate"] == 60 and segments[0]["rate_status"] == "slow"


def test_very_long_sentence_is_cut():
    tokens = timed((" ".join(["слово"] * 80) + ".", 0.0, 40.0))
    segments = build_segments(tokens, duration=40.0, thresholds=T)
    assert len(segments) >= 2
    assert all(s["end"] - s["start"] <= 16.0 for s in segments)
    assert sum(len(s["text"].split()) for s in segments) == 80


def test_fillers_are_marked_inside_segments():
    tokens = timed(("Ну, вот сегодня я, как бы, расскажу о проекте.", 0.0, 4.0))
    parts = build_segments(tokens, duration=4.0, thresholds=T)[0]["parts"]
    assert "".join(p["text"] for p in parts) == "Ну, вот сегодня я, как бы, расскажу о проекте."
    assert [p["text"] for p in parts if p["filler"]] == ["Ну", "вот", "как бы"]


def test_emotion_is_judged_per_segment_and_skipped_for_short_ones():
    tokens = timed(("Первая фраза звучит совершенно спокойно и ровно.", 0.0, 4.0), ("А вторая фраза звучит уже заметно иначе, да.", 4.0, 8.0))
    samples = np.concatenate([np.full(4 * SR, 0.1, dtype=np.float32), np.full(4 * SR, 0.9, dtype=np.float32)])
    seen = []

    def emotion(chunk):
        seen.append(len(chunk))
        return "sadness" if chunk.mean() > 0.5 else "neutral"

    segments = build_segments(tokens, 8.0, T, samples=samples, sample_rate=SR, emotion=emotion)
    assert [s["emotion"] for s in segments] == ["neutral", "sadness"]
    assert seen == [4 * SR, 4 * SR]

    short = build_segments(timed(("Раз два три четыре.", 0.0, 1.2)), 1.5, T, samples=samples, sample_rate=SR, emotion=emotion)
    assert short[0]["emotion"] is None


def test_empty_text_gives_no_segments():
    assert build_segments([], 5.0, T) == []
    assert build_segments([(" ", 0.0)], 5.0, T) == []


def test_numbers_count_as_spoken_words_in_segment_rate():
    tokens = timed(("В 2024 году мы выросли в 22 раза.", 0.0, 6.0))
    # В, две тысячи двадцать четыре, году, мы, выросли, в, двадцать два, раза: 12 произнесённых слов, а не 8 токенов.
    # Фраза кончается через 0,6 с после начала последнего слова, то есть длится 5,85 с.
    assert build_segments(tokens, 6.0, T)[0]["rate"] == round(12 / (5.85 / 60))


def test_spread_evenly():
    assert spread_evenly("раз два три", 6.0) == [("раз", 0.0), (" два", 2.0), (" три", 4.0)]
    assert spread_evenly("", 6.0) == []


def test_pipeline_returns_segments(make_wav):
    text = "Добрый день, коллеги. Ну, вот сегодня я расскажу о нашем проекте подробно и не спеша."
    result = analyze(make_wav(duration=8.0), T, StubRecognizer(text), StubEmotion("neutral"))
    assert "".join(s["text"] for s in result.segments).replace(" ", "") == text.replace(" ", "")
    assert all(s["emotion"] == "neutral" for s in result.segments)
    assert [p["text"] for s in result.segments for p in s["parts"] if p["filler"]] == ["Ну", "вот"]


def test_api_returns_and_keeps_segments(client, user, make_wav, recognizer):
    recognizer.text = "Добрый день, коллеги. Ну, вот сегодня я расскажу о нашем проекте подробно и не спеша."
    created = upload(client, user["headers"], make_wav(duration=8.0)).get_json()
    assert created["segments"] and {"start", "end", "text", "rate", "rate_status", "emotion", "parts"} <= set(created["segments"][0])
    again = client.get(f"/api/speeches/{created['id']}", headers=user["headers"]).get_json()
    assert again["segments"] == created["segments"]


def test_old_database_gets_new_column(tmp_path):
    """Сервер с базой, созданной до появления разметки, должен запуститься и работать."""
    import sqlite3

    from talkmate import create_app
    from talkmate.config import Config

    path = tmp_path / "old.db"
    config = Config(DATABASE_URL=f"sqlite:///{path}", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40)
    create_app(config, recognizer=StubRecognizer("текст"), emotion_backend=StubEmotion())
    db = sqlite3.connect(path)
    db.execute("ALTER TABLE speech DROP COLUMN segments")
    db.commit()
    db.close()

    app = create_app(config, recognizer=StubRecognizer("раз два три четыре пять"), emotion_backend=StubEmotion())
    client = app.test_client()
    headers = auth(register(client)["token"])
    wav = tmp_path / "a.wav"
    import soundfile as sf

    sf.write(wav, voice(duration=4.0), SR)
    assert upload(client, headers, wav).status_code == 201
    assert client.get("/api/speeches", headers=headers).get_json()[0]["segments"]
