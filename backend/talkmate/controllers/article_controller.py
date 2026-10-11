from flask import Blueprint, g, jsonify

from speech_analysis import lang

from ..services.article_service import ArticleService
from .common import login_required

bp = Blueprint("articles", __name__)


@bp.get("/articles")
@login_required
def articles():
    return jsonify([a.to_dict(with_content=False) for a in ArticleService(g.db).list(lang.ui())])


@bp.get("/articles/<int:article_id>")
@login_required
def article(article_id):
    return jsonify(ArticleService(g.db).get(article_id).to_dict())
