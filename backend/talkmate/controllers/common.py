from functools import wraps

from flask import current_app, g, request

from ..errors import ApiError
from ..services.auth_service import AuthService


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "bad_request", "Ожидается JSON-объект")
    return data


def auth_service():
    return AuthService(g.db, current_app.config["TM"])


def _current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError(401, "unauthorized", "Требуется вход в систему")
    return auth_service().user_from_token(header[7:])


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = _current_user()
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = _current_user()
        if g.user.role != "admin":
            raise ApiError(403, "forbidden", "Нужны права администратора")
        return view(*args, **kwargs)

    return wrapper
