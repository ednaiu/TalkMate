import pytest

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis import analyze
from speech_analysis.emotion import StubEmotion
from speech_analysis.recognition import StubRecognizer
from speech_analysis.summarizer import Rut5Summarizer, make_summarizer, prepare, summarize_safely, tidy
from talkmate.config import Config

STORY = ("Однажды собака поехала в город, там её ждал её дом. Собака гуляла целый день, после чего решила отдохнуть. "
         "Купила круассаны кофе, пила на лавочке, наслаждалась солнцем. Конечно, в какой-то момент она устала и решила искать своего хозяина. "
         "Хозяин нашёлся, все рады. А ещё потом она решила найти себе друга, так появился кот. Вот такая вот история вышла у собаки.")


def test_prepare_drops_greeting_and_throwaway_opening():
    text = "Проверка тренировки. Сейчас я расскажу короткую историю о том, как залогиниться. Первое, открыть экран входа."
    assert prepare(text).startswith("Сейчас я расскажу")
    greeting = "Добрый день, уважаемые коллеги. Сегодня я расскажу о приложении. Оно записывает речь и оценивает темп."
    assert prepare(greeting).startswith("Сегодня я расскажу")


def test_prepare_removes_fillers_but_keeps_short_texts_whole():
    assert prepare("Ну, вот, приложение, как бы, оценивает темп речи.") == "Приложение, оценивает темп речи."
    assert prepare("Привет. Это тест.") == "Привет. Это тест."      # двух фраз слишком мало, чтобы что-то отбрасывать


def test_tidy():
    assert tidy("  приложение для   тренировки ") == "Приложение для тренировки."
    assert tidy("Готово!") == "Готово!"
    assert tidy("") is None


def test_factory_and_safe_call():
    assert make_summarizer(Config(MAIN_IDEA_BACKEND="extractive")) is None
    assert isinstance(make_summarizer(Config(MAIN_IDEA_BACKEND="rut5")), Rut5Summarizer)
    assert summarize_safely(None, STORY) is None

    class Broken:
        def summarize(self, text):
            raise RuntimeError("модель не загрузилась")

    assert summarize_safely(Broken(), STORY) is None


def test_short_text_is_not_sent_to_model():
    summarizer = Rut5Summarizer()
    summarizer._load = lambda: pytest.fail("модель не должна загружаться для короткого текста")
    assert summarizer.summarize("Раз, два, три, четыре.") is None


def test_pipeline_uses_summary_and_falls_back_to_quote(make_wav):
    class Fixed:
        def summarize(self, text):
            return "Собака гуляла по городу и нашла хозяина."

    wav = make_wav(duration=20.0)
    with_model = analyze(wav, T, StubRecognizer(STORY), StubEmotion(), Fixed())
    assert with_model.content["main_idea"] == "Собака гуляла по городу и нашла хозяина."
    assert with_model.content["main_idea_source"] == "model"

    class Broken:
        def summarize(self, text):
            raise RuntimeError("сбой")

    fallback = analyze(wav, T, StubRecognizer(STORY), StubEmotion(), Broken())
    assert fallback.content["main_idea_source"] == "quote" and fallback.content["main_idea"] in STORY


@pytest.mark.real
def test_real_model_summarizes_story_instead_of_quoting_first_sentence():
    pytest.importorskip("torch")
    pytest.importorskip("sentencepiece")
    summary = Rut5Summarizer().summarize(STORY)
    assert summary and "собак" in summary.lower()
    assert 4 <= len(summary.split()) <= 30
    # Вводная фраза не должна становиться основной мыслью.
    login = "Проверка тренировки. Сейчас я расскажу короткую историю о том, что нужно сделать, чтобы залогиниться. Первое, открыть экран входа, второе, ввести свой логин, третье, пароль и нажать на кнопку войти."
    assert Rut5Summarizer().summarize(login) != "Проверка тренировки."
