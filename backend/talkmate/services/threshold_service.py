from speech_analysis.thresholds import DEFAULT_THRESHOLDS, THRESHOLD_LABELS

from ..errors import ApiError
from ..repositories import ThresholdRepository


class ThresholdService:
    def __init__(self, db):
        self.db = db
        self.thresholds = ThresholdRepository(db)

    def values(self):
        return {**DEFAULT_THRESHOLDS, **self.thresholds.stored()}

    def describe(self):
        return {"values": self.values(), "labels": THRESHOLD_LABELS, "defaults": DEFAULT_THRESHOLDS}

    def update(self, data):
        values = self.values()
        for key, raw in data.items():
            if key not in DEFAULT_THRESHOLDS:
                raise ApiError(400, "unknown_threshold", f"Неизвестный порог: {key}")
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ApiError(400, "invalid_threshold", f"Значение порога {key} должно быть числом")
            values[key] = float(raw)
        if values["volume_quiet_db"] >= values["volume_loud_db"]:
            raise ApiError(400, "invalid_threshold", "Порог «тихо» должен быть ниже порога «громко»")
        if values["rate_slow"] >= values["rate_fast"]:
            raise ApiError(400, "invalid_threshold", "Нижняя граница темпа должна быть меньше верхней")
        if not 0 <= values["clarity_unclear"] < values["clarity_clear"] <= 100:
            raise ApiError(400, "invalid_threshold", "Пороги чёткости: от 0 до 100, нижний меньше верхнего")
        if values["monotony_min_semitones"] < 0 or values["fillers_max"] < 0 or values["rate_slow"] <= 0:
            raise ApiError(400, "invalid_threshold", "Порог не может быть отрицательным")
        for key in data:
            self.thresholds.set(key, values[key])
        self.db.commit()
        return self.values()
