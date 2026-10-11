"""Проверка на настоящей речи: синтез macOS (голос Milena), распознавание GigaAM и Vosk, модель эмоций.

Запуск: pytest -m real. Тесты пропускаются, если нет нужных инструментов или моделей.
"""
import shutil
import subprocess

import pytest

from speech_analysis import DEFAULT_THRESHOLDS, analyze
from speech_analysis.audio import load_audio
from speech_analysis.emotion import DEFAULT_HEAD, EMOTIONS, AniemoreEmotion, HeadEmotion, detect_emotion, make_emotion
from speech_analysis.recognition import OnnxRecognizer, RecognitionError, VoskRecognizer, make_recognizer
from speech_analysis.speed import tokenize
from talkmate.config import Config

pytestmark = pytest.mark.real

TEXT = (
    "Добрый день, уважаемые коллеги. Сегодня я расскажу о приложении для тренировки публичных выступлений. "
    "Ну, вот, оно записывает речь и, как бы, оценивает темп, громкость и интонацию. "
    "Короче, после каждой записи пользователь получает рекомендации."
)


def has_voice():
    if not shutil.which("say") or not shutil.which("ffmpeg"):
        return False
    return "Milena" in subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def spoken_wav(tmp_path_factory):
    if not has_voice():
        pytest.skip("нет синтезатора речи macOS с голосом Milena")
    folder = tmp_path_factory.mktemp("say")
    aiff, wav = folder / "speech.aiff", folder / "speech.wav"
    subprocess.run(["say", "-v", "Milena", "-o", str(aiff), TEXT], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(aiff), "-ar", "16000", "-ac", "1", str(wav)], check=True)
    return wav


@pytest.fixture(scope="module")
def vosk():
    try:
        return VoskRecognizer(Config().VOSK_MODEL_PATH)
    except RecognitionError as exc:
        pytest.skip(str(exc))


def test_vosk_recognizes_russian_speech(spoken_wav, vosk):
    words = set(tokenize(vosk.recognize(load_audio(spoken_wav))))
    expected = {"добрый", "день", "коллеги", "приложении", "публичных", "выступлений", "громкость", "рекомендации"}
    assert len(expected & words) >= 6, words


def test_full_analysis_of_real_speech(spoken_wav, vosk):
    result = analyze(spoken_wav, DEFAULT_THRESHOLDS, vosk, None)
    assert 15 < result.duration < 40
    assert 60 < result.speech_rate < 220
    assert result.num_fillers >= 3, result.text
    assert {"ну", "вот"} & set(result.fillers)
    assert -45 < result.volume_db < -5
    assert 0.5 < result.pitch_variability < 12


@pytest.fixture(scope="module")
def gigaam():
    pytest.importorskip("onnx_asr")
    try:
        return OnnxRecognizer(Config().ASR_MODEL)
    except RecognitionError as exc:
        pytest.skip(str(exc))


def test_default_recognizer_is_local_gigaam(gigaam):
    recognizer = make_recognizer(Config())
    assert recognizer.name == "onnx" and recognizer.model_name == "gigaam-v3-e2e-ctc"


def test_gigaam_recognizes_russian_speech_better_than_vosk(spoken_wav, gigaam, vosk):
    samples = load_audio(spoken_wav)
    expected = tokenize(TEXT)

    def word_errors(text):
        import jiwer

        return jiwer.wer(" ".join(expected), " ".join(tokenize(text)))

    assert word_errors(gigaam.recognize(samples)) < 0.1
    assert word_errors(gigaam.recognize(samples)) <= word_errors(vosk.recognize(samples))


def test_full_analysis_with_gigaam_counts_every_filler(spoken_wav, gigaam):
    result = analyze(spoken_wav, DEFAULT_THRESHOLDS, gigaam, None)
    # В тексте четыре заполнителя: «ну», «вот», «как бы», «короче».
    assert sorted(result.fillers) == ["вот", "как бы", "короче", "ну"], result.text
    assert 90 < result.speech_rate < 200


def test_aniemore_model_returns_known_emotion(spoken_wav):
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    label = AniemoreEmotion(Config().EMOTION_MODEL).predict(load_audio(spoken_wav))
    assert label in EMOTIONS


def test_trained_head_is_default_and_gives_probabilities(spoken_wav):
    pytest.importorskip("torch")
    assert DEFAULT_HEAD.exists(), "веса головы должны лежать в репозитории"
    backend = make_emotion(Config())
    assert isinstance(backend, HeadEmotion)
    assert backend.preprocess == "norm" and 0.0 < backend.negative_threshold < 1.0
    samples = load_audio(spoken_wav)
    probabilities = backend.probabilities(samples)
    assert probabilities.shape == (len(EMOTIONS),) and probabilities.sum() == pytest.approx(1.0, abs=1e-4)
    # Синтезатор читает ровным голосом: отрицательной эмоции в такой записи быть не должно.
    assert detect_emotion(backend, samples) in ("neutral", "happiness", "enthusiasm")
