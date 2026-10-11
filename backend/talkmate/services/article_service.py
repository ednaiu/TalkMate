from speech_analysis.lang import normalize

from ..errors import ApiError
from ..models import Article
from ..repositories import ArticleRepository


def _fields(data, partial=False):
    fields = {}
    for key, limit, label in (("title", 255, "заголовок"), ("content", 100_000, "текст")):
        if key in data or not partial:
            value = str(data.get(key) or "").strip()
            if not value:
                raise ApiError(400, f"invalid_{key}", f"Заполните {label} статьи")
            if len(value) > limit:
                raise ApiError(400, f"invalid_{key}", f"Слишком длинный {label}")
            fields[key] = value
    return fields


class ArticleService:
    def __init__(self, db):
        self.db = db
        self.articles = ArticleRepository(db)

    def list(self, lang=None):
        return self.articles.all(lang)

    def get(self, article_id):
        article = self.articles.get(article_id)
        if article is None:
            raise ApiError(404, "not_found", "Статья не найдена")
        return article

    def add(self, data):
        article = self.articles.add(Article(**_fields(data), lang=normalize(data.get("lang"))))
        self.db.commit()
        return article

    def edit(self, article_id, data):
        article = self.get(article_id)
        for key, value in _fields(data, partial=True).items():
            setattr(article, key, value)
        if "lang" in data:
            article.lang = normalize(data.get("lang"))
        self.db.commit()
        return article

    def delete(self, article_id):
        self.articles.delete(self.get(article_id))
        self.db.commit()
