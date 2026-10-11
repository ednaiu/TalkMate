import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Настройки сервера. Все значения переопределяются переменными окружения."""

    def __init__(self, **overrides):
        env = os.environ
        self.DATABASE_URL = env.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'talkmate.db'}")
        self.SECRET_KEY = env.get("SECRET_KEY", "dev-secret-change-me-in-production-please")
        self.TOKEN_TTL_HOURS = int(env.get("TOKEN_TTL_HOURS", "720"))
        self.AUDIO_DIR = Path(env.get("AUDIO_DIR", BASE_DIR / "uploads"))
        # Модель английской речи (многоязычная, она же определяет язык записи); off оставляет только русскую.
        self.ASR_MODEL_EN = env.get("ASR_MODEL_EN", "nemo-parakeet-tdt-0.6b-v3")
        self.ASR_EN_QUANTIZATION = env.get("ASR_EN_QUANTIZATION", "int8")
        self.MAX_AUDIO_MB = int(env.get("MAX_AUDIO_MB", "64"))
        self.MAX_SLIDES_MB = int(env.get("MAX_SLIDES_MB", "40"))
        # Распознавание текста на картинках слайдов: on или off (тогда читается только текстовый слой PDF).
        self.SLIDES_OCR = env.get("SLIDES_OCR", "on")
        # Кодировщик смысловых векторов для сопоставления слайдов с речью; off оставляет сравнение по словам.
        self.SLIDES_EMBEDDER = env.get("SLIDES_EMBEDDER", "intfloat/multilingual-e5-small")

        # Сервер анализа речи. Пустой адрес означает анализ внутри процесса сервера приложения.
        self.ANALYSIS_URL = env.get("ANALYSIS_URL", "")
        self.ANALYSIS_TOKEN = env.get("ANALYSIS_TOKEN", "")

        # Распознавание речи: onnx (модель ASR_MODEL) | vosk | stub | auto (onnx, при неудаче vosk)
        self.RECOGNIZER = env.get("RECOGNIZER", "auto")
        self.ASR_MODEL = env.get("ASR_MODEL", "gigaam-v3-e2e-ctc")
        self.VOSK_MODEL_PATH = env.get("VOSK_MODEL_PATH", str(BASE_DIR / "models" / "vosk-model-small-ru-0.22"))

        # Эмоциональная окраска: talkmate (кодировщик Aniemore и дообученная голова) | aniemore | stub | off
        self.EMOTION_BACKEND = env.get("EMOTION_BACKEND", "talkmate")
        self.EMOTION_MODEL = env.get("EMOTION_MODEL", "Aniemore/wavlm-emotion-russian-resd")
        self.EMOTION_HEAD = env.get("EMOTION_HEAD", "")
        self.EMOTION_PREPROCESS = env.get("EMOTION_PREPROCESS", "")

        # Основная мысль выступления: rut5 (локальная модель пересказа) | extractive (цитата из речи, без модели)
        self.MAIN_IDEA_BACKEND = env.get("MAIN_IDEA_BACKEND", "rut5")
        self.MAIN_IDEA_MODEL = env.get("MAIN_IDEA_MODEL", "cointegrated/rut5-base-absum")

        # Почта для писем с кодом восстановления пароля. Без SMTP_HOST код пишется в журнал сервера.
        self.SMTP_HOST = env.get("SMTP_HOST", "")
        self.SMTP_PORT = int(env.get("SMTP_PORT", "587"))
        self.SMTP_USER = env.get("SMTP_USER", "")
        self.SMTP_PASSWORD = env.get("SMTP_PASSWORD", "")
        self.SMTP_FROM = env.get("SMTP_FROM", "")
        self.SMTP_TLS = env.get("SMTP_TLS", "1") != "0"

        self.ADMIN_EMAIL = env.get("ADMIN_EMAIL", "admin@talkmate.local")
        self.ADMIN_PASSWORD = env.get("ADMIN_PASSWORD", "admin12345")
        self.ADMIN_NAME = env.get("ADMIN_NAME", "Администратор")

        for key, value in overrides.items():
            setattr(self, key, value)
