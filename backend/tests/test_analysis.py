import numpy as np
import pytest

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis import analyze
from speech_analysis.audio import AudioError, load_audio
from speech_analysis.emotion import StubEmotion, detect_emotion, windows
from speech_analysis.fillers import count_fillers, find_fillers, top_fillers
from speech_analysis.monotony import classify_monotony, pitch_variability, segment_pitches
from speech_analysis.recognition import (
    OnnxRecognizer,
    RecognitionError,
    StubRecognizer,
    make_recognizer,
    split_for_recognition,
)
from talkmate.services.recommendation_service import build_recommendation, find_issues
from speech_analysis.speed import classify_rate, count_words, speech_rate
from speech_analysis.volume import classify_volume, mean_volume_db
from talkmate.config import Config

from .conftest import SR, voice


# --- Скорость ---

def test_count_words_ignores_punctuation():
    assert count_words("Добрый день, коллеги! Сегодня — о проекте.") == 6


def test_count_words_hyphenated_is_one_word():
    assert count_words("что-то из-за") == 2


def test_speech_rate_is_words_per_minute():
    text = " ".join(["слово"] * 50)
    assert speech_rate(text, 20.0) == pytest.approx(150.0)


def test_speech_rate_zero_duration():
    assert speech_rate("раз два", 0) == 0.0


@pytest.mark.parametrize("rate,label", [(89, "slow"), (90, "normal"), (120, "normal"), (140, "normal"), (141, "fast")])
def test_classify_rate(rate, label):
    assert classify_rate(rate, T) == label


# --- Громкость ---

def test_volume_matches_known_amplitude():
    # У синусоиды с амплитудой A среднеквадратичное значение A/√2.
    t = np.arange(SR * 2) / SR
    tone = (0.1 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    assert mean_volume_db(tone) == pytest.approx(20 * np.log10(0.1 / np.sqrt(2)), abs=0.5)


def test_volume_ignores_silence_between_phrases():
    speech = voice(duration=1.0, amplitude=0.2)
    with_pauses = np.concatenate([speech, np.zeros(SR * 3, dtype=np.float32), speech])
    assert mean_volume_db(with_pauses) == pytest.approx(mean_volume_db(speech), abs=1.0)


def test_volume_of_silence():
    assert mean_volume_db(np.zeros(SR, dtype=np.float32)) == -80.0


def test_classify_volume_levels():
    assert classify_volume(mean_volume_db(voice(amplitude=0.01)), T) == "quiet"
    assert classify_volume(mean_volume_db(voice(amplitude=0.15)), T) == "normal"
    assert classify_volume(mean_volume_db(voice(amplitude=0.9)), T) == "loud"


def test_classify_volume_uses_thresholds():
    custom = dict(T, volume_quiet_db=-10.0, volume_loud_db=-5.0)
    assert classify_volume(-20.0, T) == "normal"
    assert classify_volume(-20.0, custom) == "quiet"


# --- Монотонность ---

def test_segment_pitches_find_fundamental():
    pitches = segment_pitches(voice(duration=3.0, f0=150.0))
    assert len(pitches) >= 5
    assert np.median(pitches) == pytest.approx(150.0, rel=0.03)


def test_flat_voice_is_monotone():
    variability = pitch_variability(voice(duration=4.0, f0=140.0))
    assert variability < 0.3
    assert classify_monotony(variability, T) == "monotone"


def test_varying_voice_is_expressive():
    variability = pitch_variability(voice(duration=6.0, f0=110.0, f0_end=220.0))
    assert variability > 2.5
    assert classify_monotony(variability, T) == "expressive"


def test_variability_grows_with_pitch_range():
    small = pitch_variability(voice(duration=8.0, f0=150.0, wobble=1.0))
    large = pitch_variability(voice(duration=8.0, f0=150.0, wobble=5.0))
    assert small < large


def test_variability_of_silence_is_zero():
    assert pitch_variability(np.zeros(SR * 2, dtype=np.float32)) == 0.0


# --- Заполнители ---

def test_fillers_single_words():
    assert find_fillers("Ну вот, значит, мы начали") == ["ну", "вот", "значит"]


def test_fillers_phrases_counted_once():
    assert find_fillers("это как бы работает, так сказать") == ["как бы", "так сказать"]


def test_fillers_do_not_match_inside_words():
    # «вот» внутри «живот» и «ну» внутри «нужно» заполнителями не считаются.
    assert count_fillers("живот нужно типаж эмоция") == 0


def test_fillers_case_and_yo():
    assert count_fillers("НУ Короче ээ") == 3


def test_fillers_empty_text():
    assert count_fillers("") == 0


@pytest.mark.parametrize("text", ["э-э", "ээ", "э", "э-э-э", "эээ", "эм", "э-эм", "эмм"])
def test_hesitation_spellings_are_one_filler(text):
    assert find_fillers(f"мы {text} начали") == ["э-э"]


def test_hesitation_sounds_m_and_a():
    assert find_fillers("м-м ну да") == ["м-м", "ну"]
    assert find_fillers("хм а-а понятно ммм") == ["м-м", "а-а", "м-м"]


def test_repeated_hesitation_tokens_merge():
    # Так выглядит «э-э» после удаления дефисов: два токена, но пауза одна.
    assert find_fillers("выгоднее будет э э сделать") == ["э-э"]
    assert find_fillers("э э ну э э") == ["э-э", "ну", "э-э"]


def test_ordinary_words_are_not_hesitations():
    # Союз «а», предлог и слова на «э» и «м» заполнителями не считаются.
    assert count_fillers("а мы это этаж эхо мама м") == 0


@pytest.mark.parametrize("text,expected", [
    ("Эээ, такой тест презентации, да, И-и-и Каждый хотел бы узнать.", ["э-э", "да", "и-и"]),   # запись с телефона
    ("Хмм, что бы сказать? Первая презентация.", ["м-м"]),
    ("Так. При первом запуске телефон спросит разрешение.", ["так"]),
    ("Ну-у, я думаю, о-о-о, это ууу сложно", ["ну", "о-о", "у-у"]),
    ("Итак, начнём. Смотрите, это просто, ладно?", ["итак", "смотрите", "ладно"]),
])
def test_fillers_from_real_recordings(text, expected):
    assert find_fillers(text) == expected


def test_ambiguous_words_count_only_when_set_off_by_punctuation():
    assert count_fillers("так вышло, что да будет так") == 0
    assert count_fillers("это просто отлично и хорошо сделано") == 0
    assert find_fillers("Мы, так, начали. Да, хорошо, продолжим.") == ["так", "да", "хорошо"]
    # В тексте без пунктуации такие слова не считаются: отличить вставку от обычного слова нечем.
    assert count_fillers("мы так начали да хорошо продолжим") == 0


def test_ordinary_repeated_letters_are_not_drawl():
    assert count_fillers("ее ии шоссе и о у") == 0


def test_split_by_fillers_keeps_text_and_marks_spans():
    from speech_analysis.fillers import split_by_fillers

    text = "Ну, вот сегодня я, как бы, расскажу. Э-э, да."
    parts = split_by_fillers(text)
    assert "".join(p["text"] for p in parts) == text
    assert [p["text"] for p in parts if p["filler"]] == ["Ну", "вот", "как бы", "Э-э", "да"]
    assert split_by_fillers("обычная фраза") == [{"text": "обычная фраза", "filler": False, "unclear": False}]
    assert split_by_fillers("") == []


def test_millimetres_are_not_a_hesitation():
    assert count_fillers("зазор 5 мм между деталями") == 0
    assert find_fillers("зазор мм небольшой") == ["м-м"]


def test_count_words_spells_out_numbers():
    assert count_words("в 22 раза") == 4          # в двадцать два раза
    assert count_words("125 человек") == 4        # сто двадцать пять человек
    assert count_words("слайд 3") == 2


def test_top_fillers_ordered_by_frequency():
    found = find_fillers("ну вот ну типа ну вот")
    assert top_fillers(found, limit=2) == ["ну", "вот"]


# --- Распознавание ---

def test_split_keeps_short_audio_whole():
    samples = voice(duration=5.0)
    assert len(split_for_recognition(samples)) == 1


def test_split_long_audio_into_chunks_under_limit():
    phrase = voice(duration=4.0)
    pause = np.zeros(SR, dtype=np.float32)
    samples = np.concatenate([np.concatenate([phrase, pause]) for _ in range(14)])  # 70 секунд
    chunks = split_for_recognition(samples, max_sec=25.0)
    assert len(chunks) >= 3
    assert all(len(c) <= 25 * SR for c in chunks)
    assert sum(len(c) for c in chunks) == len(samples)


def test_split_hard_cuts_continuous_sound():
    chunks = split_for_recognition(voice(duration=60.0), max_sec=25.0)
    assert all(len(c) <= 25 * SR for c in chunks)
    assert sum(len(c) for c in chunks) == 60 * SR


class FakeOnnxModel:
    def __init__(self, replies=None, fail=False):
        self.replies = list(replies or [])
        self.fail = fail
        self.calls = []

    def with_timestamps(self):
        return self

    def recognize(self, waveform, sample_rate):
        from types import SimpleNamespace

        self.calls.append((waveform, sample_rate))
        if self.fail:
            raise RuntimeError("сбой onnxruntime")
        reply = self.replies.pop(0) if self.replies else ""
        if isinstance(reply, tuple):   # (кусочки текста, их время), как отдаёт настоящая модель
            return SimpleNamespace(text="".join(reply[0]), tokens=list(reply[0]), timestamps=list(reply[1]))
        return SimpleNamespace(text=reply, tokens=None, timestamps=None)


@pytest.fixture
def onnx_model(monkeypatch):
    """Подставляет модель в кеш распознавателя, чтобы тест не скачивал настоящую."""
    def install(name="fake-model", **kwargs):
        model = FakeOnnxModel(**kwargs)
        monkeypatch.setitem(OnnxRecognizer._models, name, model)
        return model

    return install


def test_onnx_recognizer_passes_float_audio_at_16k(onnx_model):
    model = onnx_model(replies=["Привет, мир"])
    samples = voice(duration=2.0).astype(np.float64)
    assert OnnxRecognizer("fake-model").recognize(samples) == "Привет, мир"
    waveform, rate = model.calls[0]
    assert rate == SR and waveform.dtype == np.float32 and len(waveform) == len(samples)


def test_onnx_recognizer_splits_long_audio_and_joins_text(onnx_model):
    model = onnx_model(replies=[" часть один ", "", "часть три"])
    assert OnnxRecognizer("fake-model").recognize(voice(duration=60.0)) == "часть один часть три"
    assert len(model.calls) == 3
    assert all(len(waveform) <= 25 * SR for waveform, _ in model.calls)


def test_onnx_recognizer_reports_model_failure(onnx_model):
    onnx_model(fail=True)
    with pytest.raises(RecognitionError):
        OnnxRecognizer("fake-model").recognize(voice(duration=1.0))


def test_onnx_recognizer_unknown_model_is_recognition_error():
    pytest.importorskip("onnx_asr")
    with pytest.raises(RecognitionError):
        OnnxRecognizer("no-such-model-name")


def test_recognizer_factory(onnx_model, tmp_path):
    onnx_model("picked")
    assert make_recognizer(Config(RECOGNIZER="onnx", ASR_MODEL="picked")).model_name == "picked"
    assert make_recognizer(Config(RECOGNIZER="auto", ASR_MODEL="picked")).name == "onnx"
    assert make_recognizer(Config(RECOGNIZER="stub")).name == "stub"
    with pytest.raises(RecognitionError):
        make_recognizer(Config(RECOGNIZER="yandex"))


def test_auto_recognizer_without_any_model_fails(tmp_path):
    pytest.importorskip("onnx_asr")
    config = Config(RECOGNIZER="auto", ASR_MODEL="no-such-model-name", VOSK_MODEL_PATH=str(tmp_path / "missing"))
    with pytest.raises(RecognitionError):
        make_recognizer(config)


def test_no_external_recognition_service_in_code():
    """Распознавание идёт только локальными моделями: в коде не должно остаться обращений к облачным сервисам."""
    import pathlib

    import speech_analysis

    for path in pathlib.Path(speech_analysis.__file__).parent.glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "yandex" not in source and "speechkit" not in source and "api-key" not in source, path.name


# --- Эмоции ---

def test_emotion_windows_cover_short_audio():
    assert len(windows(voice(duration=3.0))) == 1


def test_emotion_windows_are_capped():
    parts = windows(np.zeros(SR * 600, dtype=np.float32))
    assert len(parts) == 12
    assert all(len(p) <= 8 * SR for p in parts)


def test_detect_emotion_off():
    assert detect_emotion(None, voice()) is None


def test_detect_emotion_survives_model_failure():
    class Broken:
        def predict(self, samples):
            raise RuntimeError("нет модели")

    assert detect_emotion(Broken(), voice()) is None


def test_detect_emotion_rejects_unknown_label():
    assert detect_emotion(StubEmotion("surprise"), voice()) is None
    assert detect_emotion(StubEmotion("happiness"), voice()) == "happiness"


# --- Загрузка аудио ---

def test_load_audio_resamples_to_16k(tmp_path):
    import soundfile as sf

    path = tmp_path / "hi.wav"
    sf.write(path, np.stack([voice(duration=2.0, sr=44100)] * 2, axis=1), 44100)
    samples = load_audio(path)
    assert samples.ndim == 1
    assert len(samples) == pytest.approx(2 * SR, abs=10)


def test_load_audio_rejects_garbage(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"this is not audio")
    with pytest.raises(AudioError):
        load_audio(path)


def test_load_audio_rejects_too_short(make_wav):
    with pytest.raises(AudioError):
        load_audio(make_wav(duration=0.3))


# --- Конвейер и рекомендации ---

def test_pipeline_end_to_end(make_wav):
    text = " ".join(["ну"] * 3 + ["слово"] * 22)  # 25 слов за 10 секунд: 150 слов/мин
    result = analyze(make_wav(duration=10.0, f0=140.0, amplitude=0.01), T, StubRecognizer(text), StubEmotion("neutral"))
    assert round(result.speech_rate) == 150 and classify_rate(result.speech_rate, T) == "fast"
    assert result.duration == pytest.approx(10.0, abs=0.01)
    assert result.volume == "quiet"
    assert result.monotony == "monotone"
    assert result.num_fillers == 3
    assert result.top_fillers == ["ну"]
    assert result.emotion == "neutral"


def _result(**overrides):
    from speech_analysis import AnalysisResult

    base = dict(text="", duration=60, speech_rate=120, volume="normal", volume_db=-20, monotony="expressive",
                pitch_variability=3.0, num_fillers=0, fillers=[], top_fillers=[], emotion="neutral")
    base.update(overrides)
    return AnalysisResult(**base)


def test_recommendation_for_quiet_speech_matches_mockup():
    title, text = build_recommendation(_result(volume="quiet"), T)
    assert title == "У вас здорово получается!"
    assert text.startswith("В следующий раз попробуйте **увеличить громкость** вашего голоса")


def test_recommendation_when_everything_is_fine():
    result = _result()
    assert find_issues(result, T) == []
    assert build_recommendation(result, T)[0] == "Отличное выступление!"


def test_recommendation_lists_every_issue():
    result = _result(speech_rate=250, volume="loud", monotony="monotone", num_fillers=9,
                     top_fillers=["ну", "вот"], emotion="fear")
    assert find_issues(result, T) == ["volume_loud", "rate_fast", "monotone", "fillers", "emotion"]
    title, text = build_recommendation(result, T)
    assert title == "Есть над чем поработать"
    for fragment in ("говорить немного тише", "замедлить темп", "250", "добавить интонации", "«ну», «вот»", "страх"):
        assert fragment in text


def test_recommendation_slow_rate_and_filler_threshold():
    assert find_issues(_result(speech_rate=80), T) == ["rate_slow"]
    assert find_issues(_result(num_fillers=4), T) == []
    assert find_issues(_result(num_fillers=5), T) == ["fillers"]
