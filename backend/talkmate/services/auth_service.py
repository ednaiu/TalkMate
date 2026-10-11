import re
from datetime import date, datetime, timedelta, timezone

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import ApiError
from ..models import User
from ..repositories import UserRepository

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 6


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def validate_email(email):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 190:
        raise ApiError(400, "invalid_email", "Введите корректный email")
    return email


def validate_name(name):
    name = (name or "").strip()
    if not name:
        raise ApiError(400, "invalid_name", "Введите имя")
    if len(name) > 120:
        raise ApiError(400, "invalid_name", "Имя слишком длинное")
    return name


def validate_password(password):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise ApiError(400, "weak_password", f"Пароль должен быть не короче {MIN_PASSWORD} символов")
    return password


def _birth_date(value):
    if value in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, "invalid_birth_date", "Дата рождения должна быть в формате ГГГГ-ММ-ДД")
    if parsed > date.today() or parsed.year < 1900:
        raise ApiError(400, "invalid_birth_date", "Проверьте дату рождения")
    return parsed


def _gender(value):
    if value in (None, ""):
        return None
    if value not in ("male", "female"):
        raise ApiError(400, "invalid_gender", "Пол указывается как male или female")
    return value


class AuthService:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.users = UserRepository(db)

    def register(self, data):
        name = validate_name(data.get("name"))
        email = validate_email(data.get("email"))
        password = validate_password(data.get("password"))
        if self.users.by_email(email) is not None:
            raise ApiError(409, "email_taken", "Пользователь с таким email уже зарегистрирован")
        user = self.users.add(
            User(
                name=name,
                email=email,
                password=hash_password(password),
                phone=(str(data.get("phone") or "").strip()[:32] or None),
                birth_date=_birth_date(data.get("birth_date")),
                gender=_gender(data.get("gender")),
            )
        )
        self.db.commit()
        return user

    def login(self, email, password):
        user = self.users.by_email(str(email or "").strip().lower())
        if user is None or not check_password_hash(user.password, str(password or "")):
            raise ApiError(401, "invalid_credentials", "Неверный email или пароль")
        return user

    def issue_token(self, user):
        payload = {
            "sub": str(user.id),
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=self.config.TOKEN_TTL_HOURS),
        }
        return jwt.encode(payload, self.config.SECRET_KEY, algorithm="HS256")

    def user_from_token(self, token):
        try:
            payload = jwt.decode(token, self.config.SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise ApiError(401, "unauthorized", "Сессия истекла, войдите снова")
        user = self.users.get(int(payload["sub"]))
        if user is None:
            raise ApiError(401, "unauthorized", "Пользователь не найден")
        return user
