"""Сервер анализа речи как отдельный узел и клиент к нему на стороне сервера приложения."""
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from speech_analysis import AnalysisResult
from speech_analysis.audio import AudioError
from speech_analysis.emotion import StubEmotion
from speech_analysis.preprocess import normalize_amplitude, prepare_for_emotion, remove_noise
from speech_analysis.recognition import RecognitionError, StubRecognizer
from speech_analysis.server import create_analysis_app, read_thresholds, threshold_table
from talkmate import create_app
from talkmate.analysis_client import AnalysisUnavailable, LocalAnalysisClient, RemoteAnalysisClient, make_analysis_client
from talkmate.config import Config

from .conftest import SR, register, auth, upload, voice

TEXT = " ".join(["ну"] * 3 + ["слово"] * 22)


@pytest.fixture
def shared_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    threshold_table.metadata.create_all(engine)
    return engine


@pytest.fixture
def analysis_app(tmp_path, shared_engine):
    config = Config(DATABASE_URL="", AUDIO_DIR=tmp_path, ANALYSIS_TOKEN="")
    return create_analysis_app(config, StubRecognizer(TEXT), StubEmotion("neutral"), engine=shared_engine)


def post_audio(client, path, **kwargs):
    with open(path, "rb") as fh:
        return client.post("/analyze", data={"audio": (fh, "speech.wav")}, content_type="multipart/form-data", **kwargs)


# --- Сервер анализа ---

def test_analysis_server_health(analysis_app):
    assert analysis_app.test_client().get("/health").get_json() == {"status": "ok"}


def test_analysis_server_returns_all_metrics(analysis_app, make_wav):
    response = post_audio(analysis_app.test_client(), make_wav(duration=10.0, amplitude=0.01, f0=140.0))
    assert response.status_code == 200
    body = response.get_json()
    assert round(body["speech_rate"]) == 150
    assert body["volume"] == "quiet" and body["monotony"] == "monotone"
    assert body["num_fillers"] == 3 and body["emotion"] == "neutral"
    AnalysisResult(**body)  # ответ раскладывается обратно в результат без лишних и недостающих полей


def test_analysis_server_reads_thresholds_from_shared_database(analysis_app, shared_engine, make_wav):
    wav = make_wav(amplitude=0.15)
    client = analysis_app.test_client()
    assert post_audio(client, wav).get_json()["volume"] == "normal"
    with shared_engine.begin() as connection:
        connection.execute(threshold_table.insert(), [{"key": "volume_quiet_db", "value": -10.0}, {"key": "volume_loud_db", "value": -3.0}])
    assert post_audio(client, wav).get_json()["volume"] == "quiet"


def test_thresholds_fall_back_to_defaults_without_table():
    engine = create_engine("sqlite://")
    assert read_thresholds(engine)["rate_slow"] == 90.0
    assert read_thresholds(None)["rate_fast"] == 140.0


def test_analysis_server_errors(analysis_app, tmp_path):
    client = analysis_app.test_client()
    assert client.post("/analyze", data={}, content_type="multipart/form-data").status_code == 400
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    response = post_audio(client, bad)
    assert response.status_code == 422 and response.get_json()["error"] == "bad_audio"


def test_analysis_server_reports_recognition_failure(tmp_path, make_wav):
    class Down:
        def recognize(self, samples):
            raise RecognitionError("модель не загрузилась")

    app = create_analysis_app(Config(DATABASE_URL="", AUDIO_DIR=tmp_path), Down(), StubEmotion())
    response = post_audio(app.test_client(), make_wav())
    assert response.status_code == 503 and response.get_json()["error"] == "recognition_unavailable"


def test_analysis_server_token(tmp_path, make_wav):
    config = Config(DATABASE_URL="", AUDIO_DIR=tmp_path, ANALYSIS_TOKEN="s3cret")
    client = create_analysis_app(config, StubRecognizer(TEXT), StubEmotion()).test_client()
    assert post_audio(client, make_wav()).status_code == 403
    assert post_audio(client, make_wav(), headers={"X-Analysis-Token": "wrong"}).status_code == 403
    assert post_audio(client, make_wav(), headers={"X-Analysis-Token": "s3cret"}).status_code == 200


# --- Клиент на стороне сервера приложения ---

class Bridge:
    """Вместо сети передаёт запросы клиента прямо в тестовый клиент сервера анализа."""

    def __init__(self, app):
        self.client = app.test_client()
        self.calls = []

    def post(self, url, files, headers, timeout, data=None):
        self.calls.append((url, headers))
        body = {field: (stream, name) for field, (name, stream) in files.items()}
        body.update(data or {})
        response = self.client.post("/analyze", data=body, headers=headers, content_type="multipart/form-data")

        class Reply:
            status_code = response.status_code

            @staticmethod
            def json():
                data = response.get_json()
                if data is None:
                    raise ValueError("не JSON")
                return data

        return Reply


def test_client_factory_picks_remote_when_url_set():
    assert isinstance(make_analysis_client(Config(ANALYSIS_URL="")), LocalAnalysisClient)
    assert isinstance(make_analysis_client(Config(ANALYSIS_URL="http://127.0.0.1:5051")), RemoteAnalysisClient)


def test_remote_client_round_trip(analysis_app, make_wav):
    bridge = Bridge(analysis_app)
    result = RemoteAnalysisClient("http://analysis:5051/", token="t", session=bridge).analyze(make_wav(duration=10.0), {})
    assert isinstance(result, AnalysisResult)
    assert round(result.speech_rate) == 150 and result.top_fillers == ["ну"]
    assert bridge.calls == [("http://analysis:5051/analyze", {"X-Analysis-Token": "t"})]


def test_remote_client_maps_errors(analysis_app, tmp_path, make_wav):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    with pytest.raises(AudioError):
        RemoteAnalysisClient("http://analysis", session=Bridge(analysis_app)).analyze(bad, {})

    class Offline:
        def post(self, *args, **kwargs):
            raise ConnectionError("connection refused")

    with pytest.raises(AnalysisUnavailable):
        RemoteAnalysisClient("http://analysis", session=Offline()).analyze(make_wav(), {})


def test_app_server_works_through_separate_analysis_server(tmp_path, make_wav):
    """Сервер приложения и сервер анализа на общей базе: порог, изменённый администратором, доходит до анализа."""
    db_url = f"sqlite:///{tmp_path / 'shared.db'}"
    config = Config(DATABASE_URL=db_url, AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40,
                    ADMIN_EMAIL="admin@test.ru", ADMIN_PASSWORD="adminpass", ANALYSIS_TOKEN="")
    analysis_app = create_analysis_app(config, StubRecognizer(TEXT), StubEmotion("happiness"))
    app = create_app(config, analysis=RemoteAnalysisClient("http://analysis", session=Bridge(analysis_app)))
    client = app.test_client()
    headers = auth(register(client)["token"])
    wav = make_wav(duration=10.0, amplitude=0.15)

    first = upload(client, headers, wav)
    assert first.status_code == 201, first.get_json()
    assert first.get_json()["feedback"]["volume"] == "normal"
    assert first.get_json()["feedback"]["emotion"] == "happiness"

    admin = auth(client.post("/api/auth/login", json={"email": "admin@test.ru", "password": "adminpass"}).get_json()["token"])
    client.put("/api/admin/thresholds", headers=admin, json={"volume_quiet_db": -10, "volume_loud_db": -3})
    second = upload(client, headers, wav).get_json()
    assert second["feedback"]["volume"] == "quiet"
    assert "увеличить громкость" in second["recommendation"]["description"]


def test_app_server_reports_analysis_server_outage(tmp_path, make_wav):
    class Offline:
        def post(self, *args, **kwargs):
            raise ConnectionError("connection refused")

    config = Config(DATABASE_URL="sqlite://", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40)
    app = create_app(config, analysis=RemoteAnalysisClient("http://analysis", session=Offline()))
    client = app.test_client()
    response = upload(client, auth(register(client)["token"]), make_wav())
    assert response.status_code == 503 and response.get_json()["error"] == "analysis_unavailable"
    assert list(config.AUDIO_DIR.iterdir()) == []


# --- Подготовка звука для модели эмоций ---

def test_normalize_amplitude_sets_peak():
    quiet = voice(amplitude=0.02)
    assert np.max(np.abs(normalize_amplitude(quiet))) == pytest.approx(0.95, abs=1e-3)
    silence = np.zeros(SR, dtype=np.float32)
    assert not np.any(normalize_amplitude(silence))


def test_remove_noise_lowers_noise_and_keeps_voice():
    rng = np.random.default_rng(1)
    speech = np.concatenate([voice(duration=1.5, amplitude=0.3), np.zeros(SR, dtype=np.float32), voice(duration=1.5, amplitude=0.3)])
    noisy = speech + rng.normal(0, 0.01, len(speech)).astype(np.float32)
    cleaned = remove_noise(noisy)
    pause = slice(int(1.7 * SR), int(2.3 * SR))
    spoken = slice(int(0.3 * SR), int(1.2 * SR))
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)))
    assert len(cleaned) == len(noisy)
    assert rms(cleaned[pause]) < 0.5 * rms(noisy[pause])
    assert rms(cleaned[spoken]) > 0.8 * rms(noisy[spoken])


def test_prepare_for_emotion_keeps_length_and_range():
    samples = voice(duration=3.0, amplitude=0.05)
    prepared = prepare_for_emotion(samples)
    assert len(prepared) == len(samples) and prepared.dtype == np.float32
    assert np.max(np.abs(prepared)) == pytest.approx(0.95, abs=1e-3)


def test_emotion_backend_receives_prepared_audio():
    from speech_analysis.emotion import detect_emotion

    seen = {}

    class Spy:
        def predict(self, samples):
            seen["peak"] = float(np.max(np.abs(samples)))
            return "neutral"

    assert detect_emotion(Spy(), voice(amplitude=0.02)) == "neutral"
    assert seen["peak"] == pytest.approx(0.95, abs=1e-3)
