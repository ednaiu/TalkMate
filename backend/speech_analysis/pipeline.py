from dataclasses import dataclass, field

from . import fillers as fillers_mod
from . import lang
from .audio import SAMPLE_RATE, dead_air_seconds, duration_seconds, load_audio
from .clarity import clarity_score, classify_clarity
from .content import analyze_content
from .emotion import detect_emotion
from .recognition import spread_evenly
from .segments import build_segments
from .slide_match import match_slides
from .slides import SlidesError
from .summarizer import summarize_safely
from .monotony import classify_monotony, pitch_variability
from .speed import speech_rate
from .thresholds import for_language
from .volume import classify_volume, mean_volume_db


@dataclass
class AnalysisResult:
    text: str
    duration: float
    speech_rate: float
    volume: str
    volume_db: float
    monotony: str
    pitch_variability: float
    num_fillers: int
    fillers: list = field(default_factory=list)
    top_fillers: list = field(default_factory=list)
    emotion: str | None = None
    dead_air: float = 0.0
    segments: list = field(default_factory=list)
    clarity: float | None = None
    clarity_level: str | None = None
    content: dict = field(default_factory=dict)
    # Сопоставление с презентацией; пусто, если её не прикладывали.
    slides: dict | None = None
    # Язык речи, по правилам которого сделан разбор: ru или en.
    language: str = "ru"


def analyze(path, thresholds, recognizer, emotion_backend=None, summarizer=None, slides_path=None, slide_reader=None,
            slide_times=None, embedder=None, speech_lang=None, ui_lang=None):
    """Полный разбор записи: распознавание, темп, громкость, монотонность, заполнители, эмоция.

    speech_lang: язык речи, если приложение знает его заранее; иначе он определяется по записи.
    ui_lang: язык, на котором пишутся пояснения для пользователя.
    """
    samples = load_audio(path)
    duration = duration_seconds(samples)
    hint = speech_lang if speech_lang in lang.LANGUAGES else None
    fallback = lang.normalize(ui_lang, lang.ui())

    # Распознаватель с временем слов даёт разметку по фразам; без него слова раскладываются по записи равномерно.
    language = None
    if hasattr(recognizer, "recognize_bilingual"):
        tokens, language = recognizer.recognize_bilingual(samples, hint, fallback)
        text = "".join(token[0] for token in tokens).strip()
    elif hasattr(recognizer, "recognize_detailed"):
        tokens = recognizer.recognize_detailed(samples)
        text = "".join(token[0] for token in tokens).strip()
    elif hasattr(recognizer, "recognize_timed"):
        tokens = recognizer.recognize_timed(samples)
        text = "".join(piece for piece, _ in tokens).strip()
    else:
        text = recognizer.recognize(samples)
        tokens = spread_evenly(text, duration)
    language = language or hint or lang.detect(text) or fallback

    with lang.use(speech=language, ui=fallback):
        return evaluate(samples, duration, text, tokens, for_language(thresholds, language), language, emotion_backend,
                        summarizer, slides_path, slide_reader, slide_times, embedder)


def evaluate(samples, duration, text, tokens, thresholds, language, emotion_backend, summarizer, slides_path, slide_reader,
             slide_times, embedder):
    """Оценки по распознанному тексту и звуку. Язык речи и язык пояснений уже выбраны вызывающим."""
    rate = speech_rate(text, duration)
    volume_db = mean_volume_db(samples)
    variability = pitch_variability(samples)
    found = fillers_mod.find_fillers(text)
    clarity = clarity_score([token[2] for token in tokens if len(token) > 2 and token[0].strip()])
    segments = build_segments(tokens, duration, thresholds, samples, SAMPLE_RATE,
                              emotion=(lambda chunk: detect_emotion(emotion_backend, chunk)) if emotion_backend else None)

    return AnalysisResult(
        text=text,
        duration=duration,
        speech_rate=rate,
        volume=classify_volume(volume_db, thresholds),
        volume_db=volume_db,
        monotony=classify_monotony(variability, thresholds),
        pitch_variability=variability,
        num_fillers=len(found),
        fillers=found,
        top_fillers=fillers_mod.top_fillers(found),
        emotion=detect_emotion(emotion_backend, samples),
        dead_air=dead_air_seconds(samples),
        clarity=clarity,
        clarity_level=classify_clarity(clarity, thresholds),
        content=analyze_content(text, summarize_safely(summarizer, text)),
        segments=segments,
        slides=compare_with_slides(slides_path, slide_reader, segments, duration, slide_times, embedder),
        language=language,
    )


def compare_with_slides(slides_path, slide_reader, segments, duration, slide_times=None, embedder=None):
    """Разбор презентации не должен ронять разбор речи: при ошибке возвращается её описание."""
    if slides_path is None or slide_reader is None:
        return None
    try:
        return match_slides(slide_reader.read(slides_path), segments, duration, slide_times, embedder)
    except SlidesError as exc:
        return {"error": str(exc)}
