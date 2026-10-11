from flask import Blueprint, current_app, g, jsonify

from ..services.mailer import Mailer
from ..services.password_reset_service import PasswordResetService

from .common import auth_service, json_body, login_required

bp = Blueprint("auth", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.post("/auth/register")
def register():
    service = auth_service()
    user = service.register(json_body())
    return jsonify({"token": service.issue_token(user), "user": user.to_dict()}), 201


@bp.post("/auth/login")
def login():
    data = json_body()
    service = auth_service()
    user = service.login(data.get("email"), data.get("password"))
    return jsonify({"token": service.issue_token(user), "user": user.to_dict()})


def _reset_service():
    return PasswordResetService(g.db, current_app.extensions.get("mailer") or Mailer(current_app.config["TM"]))


@bp.post("/auth/forgot")
def forgot_password():
    _reset_service().request(json_body().get("email"))
    # Ответ не раскрывает, зарегистрирован ли адрес.
    return jsonify({"message": "Если такой адрес зарегистрирован, на него отправлен код"})


@bp.post("/auth/reset")
def reset_password():
    data = json_body()
    user = _reset_service().reset(data.get("email"), data.get("code"), data.get("password"))
    return jsonify({"token": auth_service().issue_token(user), "user": user.to_dict()})


@bp.get("/me")
@login_required
def me():
    return jsonify(g.user.to_dict())
