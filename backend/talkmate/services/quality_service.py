"""Замер качества на живых записях: оценки пользователей «верно / неверно» и согласие отдавать записи.

Оценки показывают, насколько разбор совпадает с ощущениями человека, по каждому показателю отдельно.
Записи людей, которые дали согласие, можно выгрузить для своего тестового набора (training/export_dataset.py).
"""
from ..errors import ApiError
from ..models import Rating, utcnow
from .speech_service import SpeechService

METRICS = ("pace", "volume", "monotony", "fillers", "clarity", "noise", "emotion", "main_idea", "structure", "slides",
           "transcript", "overall")
VERDICTS = ("correct", "wrong")
MAX_COMMENT = 500


class QualityService:
    def __init__(self, db, speeches: SpeechService):
        self.db = db
        self.speeches = speeches

    def rate(self, user, speech_id, metric, data):
        if metric not in METRICS:
            raise ApiError(400, "invalid_metric", f"Неизвестный показатель: {metric}")
        verdict = data.get("verdict")
        if verdict not in VERDICTS:
            raise ApiError(400, "invalid_verdict", "Оценка должна быть correct или wrong")
        comment = data.get("comment")
        if comment is not None and (not isinstance(comment, str) or len(comment) > MAX_COMMENT):
            raise ApiError(400, "invalid_comment", f"Комментарий: строка до {MAX_COMMENT} символов")
        speech = self.speeches.get(user, speech_id)
        rating = next((r for r in speech.ratings if r.metric == metric), None)
        if rating is None:
            rating = Rating(metric=metric, verdict=verdict)
            speech.ratings.append(rating)
        rating.verdict = verdict
        rating.comment = (comment or "").strip() or None
        rating.created_at = utcnow()
        self.db.commit()
        return rating

    def ratings(self, user, speech_id):
        return sorted(self.speeches.get(user, speech_id).ratings, key=lambda r: METRICS.index(r.metric))

    def summary(self):
        """Для администратора: сколько оценок по каждому показателю и доля «верно»."""
        rows = {metric: {"correct": 0, "wrong": 0} for metric in METRICS}
        for rating in self.db.query(Rating).all():
            rows[rating.metric][rating.verdict] += 1
        result = []
        for metric, counts in rows.items():
            total = counts["correct"] + counts["wrong"]
            result.append({"metric": metric, "total": total, "correct": counts["correct"],
                           "share_correct": round(counts["correct"] / total, 3) if total else None})
        return result

    def set_consent(self, user, data):
        value = data.get("share_recordings")
        if not isinstance(value, bool):
            raise ApiError(400, "invalid_consent", "share_recordings должно быть true или false")
        user.share_recordings = value
        user.share_recordings_at = utcnow()
        self.db.commit()
        return {"share_recordings": user.share_recordings, "share_recordings_at": user.share_recordings_at.isoformat()}
