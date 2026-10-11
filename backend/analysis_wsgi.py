import os

from speech_analysis.server import create_analysis_app

app = create_analysis_app()

if __name__ == "__main__":
    # Сервер внутренний: по умолчанию слушает только локальный адрес.
    app.run(host=os.environ.get("ANALYSIS_HOST", "127.0.0.1"), port=int(os.environ.get("ANALYSIS_PORT", "5051")), threaded=True)
