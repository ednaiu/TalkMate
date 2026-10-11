"""Сервер приложения TalkMate. Слои повторяют диаграмму компонентов:
controllers, services, repositories, models и data_connector."""
import logging

from flask import Flask, g, jsonify, request, send_from_directory
from speech_analysis import lang
from werkzeug.exceptions import HTTPException

from .analysis_client import make_analysis_client
from .config import Config
from .data_connector import DataConnector, make_engine
from .errors import ApiError, localized
from .seed import seed

__all__ = ["create_app", "make_engine"]


def create_app(config=None, recognizer=None, emotion_backend=None, analysis=None, mailer=None):
    """Собирает приложение. Распознаватель, модель эмоций или весь клиент анализа можно подменить в тестах."""
    config = config or Config()
    app = Flask(__name__, static_folder="static")
    app.config["TM"] = config
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_AUDIO_MB + config.MAX_SLIDES_MB) * 1024 * 1024
    app.json.ensure_ascii = False
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    connector = DataConnector(config.DATABASE_URL)
    connector.create_schema()
    app.extensions["connector"] = connector
    app.extensions["mailer"] = mailer
    app.extensions["analysis"] = analysis or make_analysis_client(config, recognizer, emotion_backend)

    with connector.session() as session:
        seed(session, config)

    @app.before_request
    def open_session():
        g.db = connector.session()
        # Язык интерфейса приложение сообщает заголовком: на нём пишутся рекомендации, ошибки и письма.
        g.lang_scope = lang.use(ui=lang.normalize(request.headers.get("Accept-Language")))
        g.lang_scope.__enter__()

    @app.teardown_request
    def close_session(exc):
        scope = g.pop("lang_scope", None)
        if scope is not None:
            scope.__exit__(None, None, None)
        db = g.pop("db", None)
        if db is not None:
            if exc is not None:
                db.rollback()
            db.close()

    @app.errorhandler(ApiError)
    def api_error(err):
        return jsonify({"error": err.code, "message": localized(err.code, err.message, lang.ui())}), err.status

    @app.errorhandler(HTTPException)
    def http_error(err):
        messages = {404: "Не найдено", 405: "Метод не поддерживается", 413: "Файл слишком большой"}
        code = err.name.lower().replace(" ", "_")
        return jsonify({"error": code, "message": localized(code, messages.get(err.code, err.description), lang.ui())}), err.code

    @app.errorhandler(Exception)
    def unexpected(err):
        logging.getLogger(__name__).exception("Необработанная ошибка")
        return jsonify({"error": "internal", "message": localized("internal", "Внутренняя ошибка сервера", lang.ui())}), 500

    from .controllers import admin_bp, article_bp, auth_bp, speech_bp

    for blueprint in (auth_bp, article_bp, speech_bp):
        app.register_blueprint(blueprint, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.get("/admin")
    @app.get("/admin/")
    def admin_page():
        return send_from_directory(app.static_folder, "admin.html")

    return app
