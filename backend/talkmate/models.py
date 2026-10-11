"""Схема БД по слайду «Проектирование базы данных».

К таблицам из схемы добавлены: роль и анкетные поля пользователя (экран Sing UP),
длительность записи и таблица порогов, которые редактирует администратор.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    birth_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    speeches = relationship("Speech", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "gender": self.gender,
            "created_at": self.created_at.isoformat(),
        }


class Speech(Base):
    __tablename__ = "speech"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    audio_file: Mapped[str] = mapped_column(String(255))
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    # Разметка расшифровки по фразам в JSON: темп, окраска и заполнители каждой фразы.
    segments: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Содержание в JSON: основная мысль, ключевые слова, оценка структуры.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Сопоставление речи с презентацией в JSON; пусто, если её не прикладывали.
    slides: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Язык речи, по правилам которого сделан разбор: ru или en. У старых записей пусто, это русский.
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User", back_populates="speeches")
    feedback = relationship("Feedback", back_populates="speech", uselist=False, cascade="all, delete-orphan")
    recommendation = relationship("Recommendation", back_populates="speech", uselist=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    speech_id: Mapped[int] = mapped_column(ForeignKey("speech.id", ondelete="CASCADE"), unique=True)
    # В схеме поле названо speach_rate; сохраняем имя столбца как в проекте БД.
    speech_rate: Mapped[float] = mapped_column("speach_rate", Float)
    volume: Mapped[str] = mapped_column(String(16))
    volume_db: Mapped[float] = mapped_column(Float, default=0.0)
    monotony: Mapped[str] = mapped_column(String(16))
    pitch_variability: Mapped[float] = mapped_column(Float, default=0.0)
    num_fillers: Mapped[int] = mapped_column(Integer, default=0)
    fillers: Mapped[str] = mapped_column(Text, default="")
    emotion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Чёткость речи в процентах и её уровень; пусто, если распознаватель не сообщает уверенность.
    clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    speech = relationship("Speech", back_populates="feedback")


class Article(Base):
    __tablename__ = "article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    # Язык статьи: ru или en. У статей, созданных до появления английской версии, пусто, это русский.
    lang: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def to_dict(self, with_content=True):
        data = {"id": self.id, "title": self.title, "lang": self.lang or "ru", "created_at": self.created_at.isoformat()}
        if with_content:
            data["content"] = self.content
        return data


class Recommendation(Base):
    __tablename__ = "recommendation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    speech_id: Mapped[int | None] = mapped_column(ForeignKey("speech.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User", back_populates="recommendations")
    speech = relationship("Speech", back_populates="recommendation")

    def to_dict(self):
        return {
            "id": self.id,
            "speech_id": self.speech_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


class PasswordReset(Base):
    """Одноразовый код для восстановления пароля. Хранится только хеш кода."""

    __tablename__ = "password_reset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Threshold(Base):
    """Пороговые значения оценок. Ключ — имя порога, значение — число."""

    __tablename__ = "threshold"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float)


def speech_to_dict(speech: Speech):
    fb = speech.feedback
    rec = speech.recommendation
    return {
        "id": speech.id,
        "text": speech.text,
        "duration": round(speech.duration, 2),
        "segments": json.loads(speech.segments) if speech.segments else [],
        "content": json.loads(speech.content) if speech.content else None,
        "slides": json.loads(speech.slides) if speech.slides else None,
        "language": speech.language or "ru",
        "created_at": speech.created_at.isoformat(),
        "feedback": None
        if fb is None
        else {
            "speech_rate": round(fb.speech_rate),
            "volume": fb.volume,
            "volume_db": round(fb.volume_db, 1),
            "monotony": fb.monotony,
            "pitch_variability": round(fb.pitch_variability, 2),
            "num_fillers": fb.num_fillers,
            "fillers": [w for w in fb.fillers.split("|") if w],
            "emotion": fb.emotion,
            "clarity": None if fb.clarity is None else round(fb.clarity),
            "clarity_level": fb.clarity_level,
        },
        "recommendation": rec.to_dict() if rec else None,
    }
