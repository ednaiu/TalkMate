"""Отправка писем. Без настроенного SMTP письмо не уходит, а код пишется в журнал сервера."""
import logging
import smtplib

from speech_analysis import lang
from email.message import EmailMessage

log = logging.getLogger(__name__)


class Mailer:
    def __init__(self, config):
        self.config = config

    @property
    def configured(self):
        return bool(self.config.SMTP_HOST)

    def send_reset_code(self, email, name, code, minutes):
        if not self.configured:
            # Режим разработки: почтовый сервер не задан. В боевой установке этой строки в журнале быть не должно.
            log.warning("SMTP не настроен. Код восстановления для %s: %s", email, code)
            return False
        message = EmailMessage()
        message["Subject"] = lang.text("TalkMate: код для смены пароля", "TalkMate: your password reset code")
        message["From"] = self.config.SMTP_FROM or self.config.SMTP_USER
        message["To"] = email
        message.set_content(lang.text(
            f"Здравствуйте, {name}!\n\n"
            f"Код для смены пароля в TalkMate: {code}\n"
            f"Он действует {minutes} минут. Если вы не запрашивали смену пароля, просто не отвечайте на это письмо.\n",
            f"Hello, {name}!\n\n"
            f"Your TalkMate password reset code: {code}\n"
            f"It is valid for {minutes} minutes. If you did not ask to change your password, just ignore this email.\n",
        ))
        with smtplib.SMTP(self.config.SMTP_HOST, self.config.SMTP_PORT, timeout=20) as smtp:
            if self.config.SMTP_TLS:
                smtp.starttls()
            if self.config.SMTP_USER:
                smtp.login(self.config.SMTP_USER, self.config.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
