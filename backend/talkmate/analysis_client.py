"""Связь сервера приложения с сервером анализа речи.

По диаграмме компонентов анализ живёт в отдельном сервере. Если ANALYSIS_URL не задан,
те же алгоритмы вызываются внутри процесса: так удобнее для разработки и тестов.
"""
from contextlib import ExitStack

from speech_analysis import AnalysisResult, analyze
import json

from speech_analysis.audio import AudioError
from speech_analysis.embeddings import make_embedder
from speech_analysis.emotion import make_emotion
from speech_analysis.recognition import RecognitionError, make_recognizer
from speech_analysis.slides import make_slide_reader
from speech_analysis.summarizer import make_summarizer


class AnalysisUnavailable(RuntimeError):
    """Сервер анализа не отвечает."""


class LocalAnalysisClient:
    def __init__(self, config, recognizer=None, emotion_backend=None, slide_reader=None):
        self.config = config
        self.recognizer = recognizer
        self.emotion_backend = emotion_backend
        self._emotion_ready = emotion_backend is not None
        self.summarizer = make_summarizer(config)
        self.slide_reader = slide_reader or make_slide_reader(config)
        self.embedder = make_embedder(config)

    def analyze(self, path, thresholds, slides_path=None, slide_times=None, speech_lang=None, ui_lang=None):
        if self.recognizer is None:
            self.recognizer = make_recognizer(self.config)
        if not self._emotion_ready:
            self.emotion_backend = make_emotion(self.config)
            self._emotion_ready = True
        return analyze(path, thresholds, self.recognizer, self.emotion_backend, self.summarizer, slides_path, self.slide_reader,
                       slide_times, self.embedder, speech_lang, ui_lang)


class RemoteAnalysisClient:
    """Отправляет запись на сервер анализа. Пороги тот читает из общей базы сам."""

    def __init__(self, url, token="", session=None, timeout=300):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def analyze(self, path, thresholds, slides_path=None, slide_times=None, speech_lang=None, ui_lang=None):
        headers = {"X-Analysis-Token": self.token} if self.token else {}
        # Сетевые ошибки requests наследуют OSError, поэтому файлы открываем вне блока try.
        with ExitStack() as stack:
            files = {"audio": (path.name, stack.enter_context(open(path, "rb")))}
            if slides_path is not None:
                files["slides"] = (slides_path.name, stack.enter_context(open(slides_path, "rb")))
            try:
                data = {key: value for key, value in (("slide_times", json.dumps(slide_times) if slide_times else None),
                                                      ("speech_lang", speech_lang), ("ui_lang", ui_lang)) if value}
                response = self.session.post(f"{self.url}/analyze", files=files, data=data, headers=headers, timeout=self.timeout)
            except Exception as exc:
                raise AnalysisUnavailable(str(exc)) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise AnalysisUnavailable(f"непонятный ответ, статус {response.status_code}") from exc
        if response.status_code == 200:
            return AnalysisResult(**body)
        message = body.get("message", "")
        if body.get("error") == "bad_audio":
            raise AudioError(message)
        if body.get("error") == "recognition_unavailable":
            raise RecognitionError(message)
        raise AnalysisUnavailable(f"статус {response.status_code}: {message}")


def make_analysis_client(config, recognizer=None, emotion_backend=None):
    if config.ANALYSIS_URL:
        return RemoteAnalysisClient(config.ANALYSIS_URL, config.ANALYSIS_TOKEN)
    return LocalAnalysisClient(config, recognizer, emotion_backend)
