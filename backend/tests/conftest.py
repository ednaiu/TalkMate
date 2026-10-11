import os

# Автотесты не загружают модель пересказа: основная мысль в них выбирается как цитата.
os.environ.setdefault("MAIN_IDEA_BACKEND", "extractive")
# И модель распознавания текста на слайдах: в тестах читается только текстовый слой PDF.
os.environ.setdefault("SLIDES_OCR", "off")
os.environ.setdefault("SLIDES_EMBEDDER", "off")
# И модель английской речи: язык в тестах определяется по тексту заглушки.
os.environ.setdefault("ASR_MODEL_EN", "off")

import numpy as np
import pytest
import soundfile as sf

from talkmate import create_app
from speech_analysis.emotion import StubEmotion
from speech_analysis.recognition import StubRecognizer
from talkmate.config import Config

SR = 16000


def voice(duration=4.0, f0=150.0, f0_end=None, amplitude=0.2, wobble=0.0, sr=SR):
    """Синтетический «голос»: основной тон с гармониками. f0 может плавно меняться или качаться."""
    t = np.arange(int(duration * sr)) / sr
    freq = np.full_like(t, f0) if f0_end is None else np.linspace(f0, f0_end, len(t))
    if wobble:
        freq = freq * (2.0 ** (wobble * np.sin(2 * np.pi * 0.4 * t) / 12.0))
    phase = 2 * np.pi * np.cumsum(freq) / sr
    wave = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)
    wave = wave / np.max(np.abs(wave)) * amplitude
    return wave.astype(np.float32)


@pytest.fixture
def make_wav(tmp_path):
    counter = {"n": 0}

    def _make(samples=None, **kwargs):
        if samples is None:
            samples = voice(**kwargs)
        counter["n"] += 1
        path = tmp_path / f"audio_{counter['n']}.wav"
        sf.write(path, samples, SR, subtype="PCM_16")
        return path

    return _make


@pytest.fixture
def recognizer():
    return StubRecognizer("добрый день коллеги сегодня я расскажу о нашем проекте")


@pytest.fixture
def app(tmp_path, recognizer):
    # TEST_DATABASE_URL позволяет прогнать те же тесты на MySQL.
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    if not url.startswith("sqlite"):
        from talkmate import make_engine
        from talkmate.models import Base

        engine = make_engine(url)
        Base.metadata.drop_all(engine)
        engine.dispose()
    config = Config(
        DATABASE_URL=url,
        AUDIO_DIR=tmp_path / "uploads",
        SECRET_KEY="test-secret-key-that-is-long-enough-for-hs256",
        ADMIN_EMAIL="admin@test.ru",
        ADMIN_PASSWORD="adminpass",
    )
    return create_app(config, recognizer=recognizer, emotion_backend=StubEmotion("neutral"))


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="user@test.ru", name="Эдна", password="secret1", **extra):
    response = client.post("/api/auth/register", json={"name": name, "email": email, "password": password, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(client):
    data = register(client)
    return {"headers": auth(data["token"]), **data["user"]}


@pytest.fixture
def admin(client):
    response = client.post("/api/auth/login", json={"email": "admin@test.ru", "password": "adminpass"})
    assert response.status_code == 200
    return auth(response.get_json()["token"])


def upload(client, headers, path, filename="speech.wav"):
    with open(path, "rb") as fh:
        return client.post("/api/speeches", headers=headers, data={"audio": (fh, filename)}, content_type="multipart/form-data")
