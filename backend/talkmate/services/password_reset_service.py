"""Восстановление пароля по одноразовому коду из письма."""
import logging
import secrets
from datetime import timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import ApiError
from ..models import PasswordReset, utcnow
from ..repositories import PasswordResetRepository, UserRepository
from .auth_service import hash_password, validate_password

log = logging.getLogger(__name__)

CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5
RESEND_AFTER_SECONDS = 60

BAD_CODE = ApiError(400, "invalid_code", "Неверный или просроченный код. Запросите новый")


class PasswordResetService:
    def __init__(self, db, mailer):
        self.db = db
        self.mailer = mailer
        self.users = UserRepository(db)
        self.resets = PasswordResetRepository(db)

    def request(self, email):
        """Создаёт код и отправляет его. Ответ одинаков для существующего и несуществующего адреса."""
        user = self.users.by_email(str(email or "").strip().lower())
        if user is None:
            return
        latest = self.resets.latest(user.id)
        if latest is not None and (utcnow() - latest.created_at).total_seconds() < RESEND_AFTER_SECONDS:
            return  # защита от засыпания ящика письмами: прежний код ещё действует
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.resets.replace(user.id, PasswordReset(
            user_id=user.id,
            code_hash=generate_password_hash(code, method="pbkdf2:sha256"),
            expires_at=utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
        ))
        self.db.commit()
        try:
            self.mailer.send_reset_code(user.email, user.name, code, CODE_TTL_MINUTES)
        except Exception:
            log.exception("Не удалось отправить письмо с кодом")
            raise ApiError(503, "mail_unavailable", "Не удалось отправить письмо. Попробуйте позже")

    def reset(self, email, code, new_password):
        """Проверяет код и меняет пароль. Возвращает пользователя."""
        validate_password(new_password)
        user = self.users.by_email(str(email or "").strip().lower())
        reset = self.resets.latest(user.id) if user is not None else None
        if reset is None or reset.expires_at < utcnow() or reset.attempts >= MAX_ATTEMPTS:
            raise BAD_CODE
        if not check_password_hash(reset.code_hash, str(code or "").strip()):
            reset.attempts += 1
            self.db.commit()
            raise BAD_CODE
        user.password = hash_password(new_password)
        self.resets.clear(user.id)
        self.db.commit()
        return user
