"""Controllers: разбор HTTP-запроса, проверка доступа, вызов сервиса, ответ в JSON."""
from .admin_controller import bp as admin_bp
from .article_controller import bp as article_bp
from .auth_controller import bp as auth_bp
from .speech_controller import bp as speech_bp

__all__ = ["admin_bp", "article_bp", "auth_bp", "speech_bp"]
