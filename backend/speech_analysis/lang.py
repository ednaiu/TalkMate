"""Два языка сервера: русский и английский.

У запроса два независимых языка. Язык речи определяется по записи и выбирает правила разбора: слова-заполнители,
служебные слова, признаки структуры, норму темпа. Язык интерфейса приходит от приложения и выбирает, на каком
языке написаны рекомендации и сообщения. Русскоязычный пользователь может записать английскую речь и получить
разбор по английским правилам с пояснениями на русском.
"""
import re
from contextlib import contextmanager
from contextvars import ContextVar

LANGUAGES = ("ru", "en")
_speech = ContextVar("speech_language", default="ru")
_ui = ContextVar("ui_language", default="ru")

CYRILLIC = re.compile("[а-яё]", re.IGNORECASE)
LATIN = re.compile("[a-z]", re.IGNORECASE)


def normalize(code, default="ru"):
    """ru или en по коду языка или заголовку Accept-Language вроде «en-US,en;q=0.9»."""
    code = (code or "").strip().lower()[:2]
    return code if code in LANGUAGES else default


@contextmanager
def use(speech=None, ui=None):
    """На время блока задаёт язык речи и язык интерфейса для всех функций разбора."""
    tokens = []
    if speech is not None:
        tokens.append((_speech, _speech.set(normalize(speech))))
    if ui is not None:
        tokens.append((_ui, _ui.set(normalize(ui))))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def speech():
    return _speech.get()


def ui():
    return _ui.get()


def text(russian, english):
    """Текст для пользователя на языке интерфейса."""
    return english if _ui.get() == "en" else russian


def rule(russian, english):
    """Правило разбора для языка речи."""
    return english if _speech.get() == "en" else russian


def detect(sample):
    """Язык текста по буквам: en, ru или None, если букв нет."""
    cyrillic, latin = len(CYRILLIC.findall(sample or "")), len(LATIN.findall(sample or ""))
    if not cyrillic and not latin:
        return None
    return "en" if latin > cyrillic else "ru"


def own_script():
    """Буквы языка речи: по ним отбираются слова слайда, которые распознаватель мог записать."""
    return LATIN if _speech.get() == "en" else CYRILLIC
