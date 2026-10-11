import json
import uuid
from datetime import timedelta

from speech_analysis import lang
from speech_analysis.audio import AudioError
from speech_analysis.recognition import RecognitionError
from speech_analysis.server import parse_slide_times
from speech_analysis.thresholds import for_language

from ..analysis_client import AnalysisUnavailable
from ..errors import ApiError
from ..models import Feedback, Recommendation, Speech, utcnow
from ..repositories import RecommendationRepository, SpeechRepository
from .recommendation_service import build_recommendation
from .threshold_service import ThresholdService

TEMPO_POINTS = 5          # столько последних тренировок на графике темпа в личном кабинете
RECENT_TRAININGS = 2      # столько последних тренировок в списке под графиком
TITLE_LENGTH = 48


def title_of(speech):
    """Название тренировки: её основная мысль, а если мысли нет, начало сказанного."""
    idea = ""
    if speech.content:
        idea = (json.loads(speech.content).get("main_idea") or "").strip()
    text = idea or " ".join((speech.text or "").split()[:7])
    text = text.rstrip(".!?…,;: ")
    if not text:
        return lang.text("Тренировка", "Practice")
    if len(text) > TITLE_LENGTH:
        text = text[:TITLE_LENGTH].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def brief(speech):
    return {"id": speech.id, "title": title_of(speech), "date": speech.created_at.isoformat(), "duration": round(speech.duration)}


def streak(days, today):
    """Сколько дней подряд были тренировки. Сегодняшний день без тренировки серию ещё не обрывает."""
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


ALLOWED_AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".3gp", ".webm"}


class SpeechService:
    def __init__(self, db, config, analysis, logger):
        self.db = db
        self.config = config
        self.analysis = analysis
        self.logger = logger
        self.speeches = SpeechRepository(db)
        self.recommendations = RecommendationRepository(db)
        self.thresholds = ThresholdService(db)

    def create(self, user, upload, slides=None, slide_times=None, speech_lang=None):
        """Шаги 1–12 диаграммы последовательности: сохранить запись, распознать, оценить, выдать рекомендации."""
        if upload is None or not upload.filename:
            raise ApiError(400, "no_audio", "Не передан аудиофайл")
        ext = "." + upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if ext not in ALLOWED_AUDIO:
            raise ApiError(400, "bad_audio_format", "Формат файла не поддерживается")

        filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
        path = self.config.AUDIO_DIR / filename
        upload.save(path)
        # Презентация нужна только на время разбора: в базе остаётся результат сопоставления, сам файл не хранится.
        slides_path = None
        if slides is not None and slides.filename:
            if not slides.filename.lower().endswith(".pdf"):
                path.unlink(missing_ok=True)
                raise ApiError(400, "bad_slides_format", "Презентацию нужно приложить в формате PDF")
            slides_path = self.config.AUDIO_DIR / f"{user.id}_{uuid.uuid4().hex}.pdf"
            slides.save(slides_path)

        thresholds = self.thresholds.values()
        try:
            result = self._analyze(path, thresholds, slides_path, parse_slide_times(slide_times), speech_lang)
        except AudioError as exc:
            path.unlink(missing_ok=True)
            raise ApiError(422, "bad_audio", str(exc))
        except RecognitionError as exc:
            path.unlink(missing_ok=True)
            self.logger.error("Распознавание не удалось: %s", exc)
            raise ApiError(503, "recognition_unavailable", "Сервис распознавания речи недоступен")
        except AnalysisUnavailable as exc:
            path.unlink(missing_ok=True)
            self.logger.error("Сервер анализа недоступен: %s", exc)
            raise ApiError(503, "analysis_unavailable", "Сервер анализа речи недоступен")
        if not result.text.strip():
            path.unlink(missing_ok=True)
            if result.dead_air > result.duration / 2:
                raise ApiError(422, "no_signal", "Микрофон не передал звук: в записи тишина. Проверьте доступ к микрофону")
            raise ApiError(422, "no_speech", "Не удалось распознать речь. Говорите ближе к микрофону")

        language = getattr(result, "language", "ru")
        thresholds = for_language(thresholds, language)
        speech = Speech(user_id=user.id, text=result.text, audio_file=filename, duration=result.duration, language=language,
                        segments=json.dumps(result.segments, ensure_ascii=False),
                        content=json.dumps(result.content, ensure_ascii=False),
                        slides=json.dumps(result.slides, ensure_ascii=False) if result.slides else None)
        speech.feedback = Feedback(
            speech_rate=result.speech_rate,
            volume=result.volume,
            volume_db=result.volume_db,
            monotony=result.monotony,
            pitch_variability=result.pitch_variability,
            num_fillers=result.num_fillers,
            fillers="|".join(result.top_fillers),
            emotion=result.emotion,
            clarity=result.clarity,
            clarity_level=result.clarity_level,
        )
        self.speeches.add(speech)
        title, description = build_recommendation(result, thresholds)
        self.recommendations.add(Recommendation(user_id=user.id, speech_id=speech.id, title=title, description=description))
        self.db.commit()
        self.db.refresh(speech)
        return speech

    def _analyze(self, path, thresholds, slides_path, slide_times, speech_lang):
        try:
            return self.analysis.analyze(path, thresholds, slides_path, slide_times, speech_lang, lang.ui())
        finally:
            if slides_path is not None:
                slides_path.unlink(missing_ok=True)

    def get(self, user, speech_id):
        speech = self.speeches.get(speech_id)
        if speech is None or speech.user_id != user.id:
            raise ApiError(404, "not_found", "Запись не найдена")
        return speech

    def history(self, user):
        return self.speeches.of_user(user.id)

    def delete(self, user, speech_id):
        speech = self.get(user, speech_id)
        (self.config.AUDIO_DIR / speech.audio_file).unlink(missing_ok=True)
        if speech.recommendation is not None:
            self.recommendations.delete(speech.recommendation)
        self.speeches.delete(speech)
        self.db.commit()

    def user_recommendations(self, user):
        return self.recommendations.of_user(user.id)

    def trainings(self, user):
        """Все тренировки пользователя коротко, новые сверху: для списка в личном кабинете."""
        return [brief(speech) for speech in self.speeches.of_user(user.id)]

    def profile(self, user):
        """Личный кабинет: сколько тренировок и минут практики, сколько дней подряд, темп последних записей."""
        speeches = self.speeches.of_user(user.id)
        rated = [s for s in speeches if s.feedback is not None]
        thresholds = for_language(self.thresholds.values(), lang.ui())
        return {
            "user": user.to_dict(),
            "count": len(speeches),
            "minutes": round(sum(s.duration for s in speeches) / 60),
            "streak": streak({s.created_at.date() for s in speeches}, utcnow().date()),
            "tempo": [{"date": s.created_at.isoformat(), "rate": round(s.feedback.speech_rate)} for s in reversed(rated[:TEMPO_POINTS])],
            "rate_slow": thresholds["rate_slow"],
            "rate_fast": thresholds["rate_fast"],
            "recent": [brief(speech) for speech in speeches[:RECENT_TRAININGS]],
        }

    def stats(self, user):
        """Шаги 16–20: ряды показателей по всем записям пользователя в порядке времени."""
        points = [
            {
                "speech_id": s.id,
                "date": s.created_at.isoformat(),
                "speech_rate": round(s.feedback.speech_rate),
                "num_fillers": s.feedback.num_fillers,
                "volume_db": round(s.feedback.volume_db, 1),
                "pitch_variability": round(s.feedback.pitch_variability, 2),
                "emotion": s.feedback.emotion,
                "clarity": None if s.feedback.clarity is None else round(s.feedback.clarity),
            }
            for s in self.speeches.of_user(user.id, newest_first=False)
            if s.feedback is not None
        ]
        # Границы нормы на графиках берутся для языка интерфейса: считаем, что на нём человек и выступает.
        return {"count": len(points), "points": points, "thresholds": for_language(self.thresholds.values(), lang.ui())}
