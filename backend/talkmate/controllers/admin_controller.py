"""Функции администратора из диаграммы вариантов использования: статьи, пороговые значения, данные пользователей."""
from flask import Blueprint, g, jsonify

from ..services.article_service import ArticleService
from ..services.threshold_service import ThresholdService
from ..services.user_service import UserService
from .common import admin_required, json_body

bp = Blueprint("admin", __name__)


@bp.get("/articles")
@admin_required
def list_articles():
    return jsonify([a.to_dict() for a in ArticleService(g.db).list()])


@bp.post("/articles")
@admin_required
def add_article():
    return jsonify(ArticleService(g.db).add(json_body()).to_dict()), 201


@bp.put("/articles/<int:article_id>")
@bp.patch("/articles/<int:article_id>")
@admin_required
def edit_article(article_id):
    return jsonify(ArticleService(g.db).edit(article_id, json_body()).to_dict())


@bp.delete("/articles/<int:article_id>")
@admin_required
def delete_article(article_id):
    ArticleService(g.db).delete(article_id)
    return "", 204


@bp.get("/thresholds")
@admin_required
def get_thresholds():
    return jsonify(ThresholdService(g.db).describe())


@bp.put("/thresholds")
@admin_required
def put_thresholds():
    return jsonify({"values": ThresholdService(g.db).update(json_body())})


@bp.get("/users")
@admin_required
def list_users():
    return jsonify([u.to_dict() for u in UserService(g.db).list()])


@bp.patch("/users/<int:user_id>")
@bp.put("/users/<int:user_id>")
@admin_required
def edit_user(user_id):
    return jsonify(UserService(g.db).edit(user_id, json_body()).to_dict())
