"""Repositories: весь доступ к таблицам. Сервисы не пишут запросы сами."""
from sqlalchemy import select

from .models import Article, PasswordReset, Recommendation, Speech, Threshold, User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def get(self, user_id):
        return self.db.get(User, user_id)

    def by_email(self, email, exclude_id=None):
        query = select(User).where(User.email == email)
        if exclude_id is not None:
            query = query.where(User.id != exclude_id)
        return self.db.scalar(query)

    def all(self):
        return list(self.db.scalars(select(User).order_by(User.id)))

    def add(self, user):
        self.db.add(user)
        return user


class ArticleRepository:
    def __init__(self, db):
        self.db = db

    def get(self, article_id):
        return self.db.get(Article, article_id)

    def all(self, lang=None):
        """Все статьи или статьи одного языка. Статьи без языка считаются русскими."""
        query = select(Article).order_by(Article.id)
        if lang == "en":
            query = query.where(Article.lang == "en")
        elif lang is not None:
            query = query.where((Article.lang.is_(None)) | (Article.lang != "en"))
        return list(self.db.scalars(query))

    def has_language(self, lang):
        return self.db.scalar(select(Article.id).where(Article.lang == lang).limit(1)) is not None

    def is_empty(self):
        return self.db.scalar(select(Article.id).limit(1)) is None

    def add(self, article):
        self.db.add(article)
        return article

    def delete(self, article):
        self.db.delete(article)


class SpeechRepository:
    """Таблицы speech и feedback: оценка всегда хранится вместе со своей записью."""

    def __init__(self, db):
        self.db = db

    def get(self, speech_id):
        return self.db.get(Speech, speech_id)

    def of_user(self, user_id, newest_first=True):
        order = (Speech.created_at.desc(), Speech.id.desc()) if newest_first else (Speech.created_at, Speech.id)
        return list(self.db.scalars(select(Speech).where(Speech.user_id == user_id).order_by(*order)))

    def add(self, speech):
        self.db.add(speech)
        self.db.flush()
        return speech

    def delete(self, speech):
        self.db.delete(speech)


class RecommendationRepository:
    def __init__(self, db):
        self.db = db

    def of_user(self, user_id):
        query = (
            select(Recommendation)
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        )
        return list(self.db.scalars(query))

    def add(self, recommendation):
        self.db.add(recommendation)
        return recommendation

    def delete(self, recommendation):
        self.db.delete(recommendation)


class ThresholdRepository:
    def __init__(self, db):
        self.db = db

    def stored(self):
        return {row.key: row.value for row in self.db.scalars(select(Threshold))}

    def set(self, key, value):
        row = self.db.get(Threshold, key)
        if row is None:
            self.db.add(Threshold(key=key, value=value))
        else:
            row.value = value


class PasswordResetRepository:
    def __init__(self, db):
        self.db = db

    def latest(self, user_id):
        query = select(PasswordReset).where(PasswordReset.user_id == user_id).order_by(PasswordReset.id.desc()).limit(1)
        return self.db.scalar(query)

    def replace(self, user_id, reset):
        """У пользователя действует только последний код: прежние удаляются."""
        self.clear(user_id)
        self.db.add(reset)
        return reset

    def clear(self, user_id):
        for row in self.db.scalars(select(PasswordReset).where(PasswordReset.user_id == user_id)):
            self.db.delete(row)
