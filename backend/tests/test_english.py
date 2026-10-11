"""Два языка: английская речь разбирается по своим правилам, пояснения приходят на языке интерфейса."""
import pytest

from speech_analysis import lang
from speech_analysis.content import analyze_content, content_words
from speech_analysis.fillers import find_fillers
from speech_analysis.pipeline import analyze
from speech_analysis.recognition import BilingualRecognizer, StubRecognizer
from speech_analysis.slide_match import match_slides
from speech_analysis.slides import StubSlideReader
from speech_analysis.speed import count_words
from speech_analysis.thresholds import DEFAULT_THRESHOLDS, for_language
from talkmate import create_app
from talkmate.config import Config
from speech_analysis.emotion import StubEmotion

TALK = ("Good afternoon, colleagues. Today I will talk about our project, an application for practicing public speaking. "
        "Um, the main idea is, you know, quite simple. The user records a speech, and the server, like, evaluates the pace. "
        "First, the application recognizes the speech. Second, it basically counts filler words. For example, it finds words "
        "such as well and you know. In conclusion, regular practice makes a speaker more confident. Thank you for your attention.")
EN = {"Accept-Language": "en-US,en;q=0.9"}


def test_language_is_detected_by_letters():
    assert lang.detect("Good afternoon, colleagues") == "en"
    assert lang.detect("Добрый день, коллеги") == "ru"
    assert lang.detect("Смотрите на слайд about TalkMate, там всё показано") == "ru"
    assert lang.detect("... 123") is None
    assert lang.normalize("en-GB") == "en" and lang.normalize("fr") == "ru" and lang.normalize(None) == "ru"


def test_english_fillers_are_found_only_where_they_are_fillers():
    with lang.use(speech="en"):
        assert find_fillers(TALK) == ["um", "you know", "like", "basically", "you know"]
        assert find_fillers("I like this plan. It looks like rain, so we stay.") == []
        assert find_fillers("So, uh, well, I mean, it is kind of late. Uhm, okay, let us go.") == ["so", "uh", "well", "i mean", "kind of", "um", "okay"]
    # Русские правила английские слова не трогают, и наоборот.
    assert find_fillers("Um, basically it works") == []
    with lang.use(speech="en"):
        assert find_fillers("Ну вот, значит, начнём") == []


def test_english_numbers_and_stopwords():
    with lang.use(speech="en"):
        assert count_words("It costs 21 dollars") == 5           # twenty one
        assert content_words("The user records a speech and the server evaluates it") == ["user", "records", "speech", "server", "evaluates"]


def test_english_structure_and_main_idea_with_russian_and_english_notes():
    with lang.use(speech="en", ui="en"):
        content = analyze_content(TALK)
    assert content["structure"]["intro"] and content["structure"]["conclusion"] and content["structure"]["links"] >= 2
    assert content["structure"]["level"] == "good"
    assert content["structure"]["summary"].startswith("There is an introduction")
    assert "speech" in content["keywords"] and content["main_idea_source"] == "quote"
    with lang.use(speech="en", ui="ru"):
        assert analyze_content(TALK)["structure"]["summary"].startswith("Вступление есть")


def test_english_tempo_norm_is_separate():
    english = for_language(DEFAULT_THRESHOLDS, "en")
    assert (english["rate_slow"], english["rate_fast"]) == (110.0, 170.0)
    assert for_language(DEFAULT_THRESHOLDS, "ru")["rate_fast"] == 140.0
    assert DEFAULT_THRESHOLDS["rate_fast"] == 140.0                # исходный словарь не меняется


def test_pipeline_detects_english_speech_and_uses_its_rules(make_wav):
    result = analyze(make_wav(duration=40.0), DEFAULT_THRESHOLDS, StubRecognizer(TALK), ui_lang="en")
    assert result.language == "en"
    assert result.num_fillers == 5 and result.top_fillers[0] == "you know"
    assert result.content["structure"]["summary"].startswith("There is")
    russian = analyze(make_wav(duration=10.0), DEFAULT_THRESHOLDS, StubRecognizer("Ну вот, значит, коллеги, начнём наш доклад"), ui_lang="en")
    assert russian.language == "ru" and russian.num_fillers == 3


class FakeModel:
    def __init__(self, text):
        self.text, self.calls = text, []

    def recognize_detailed(self, samples):
        self.calls.append(len(samples))
        return [(self.text, 0.0, 0.9)]


def test_bilingual_recognizer_probes_the_start_and_picks_the_model():
    russian, english = FakeModel("Добрый день"), FakeModel("Good afternoon")
    recognizer = BilingualRecognizer(russian, lambda: english)
    long = [0.0] * (16000 * 40)
    tokens, language = recognizer.recognize_bilingual(long)
    assert language == "en" and english.calls == [16000 * 30, 16000 * 40] and russian.calls == []
    # Короткая запись распознаётся один раз: проба и есть результат.
    english.calls.clear()
    assert recognizer.recognize_bilingual([0.0] * 16000)[1] == "en" and english.calls == [16000]
    # Русская речь: многоязычная модель слышит кириллицу, запись уходит русской модели.
    english.text = "Добрый день"
    assert recognizer.recognize_bilingual(long)[1] == "ru" and russian.calls == [16000 * 40]
    # Язык задан заранее: проба не нужна.
    english.calls.clear()
    assert recognizer.recognize_bilingual(long, "en")[1] == "en" and english.calls == [16000 * 40]


def test_slide_notes_and_key_terms_follow_the_languages():
    slides = StubSlideReader(["Speech recognition\nThe server recognizes speech with an open model",
                              "Filler words\nThe application counts filler words and pauses",
                              "Results\nRegular practice makes speakers confident"]).read(None)
    segments = [{"start": 0, "end": 10, "text": "The server recognizes speech with an open model."}]
    with lang.use(speech="en", ui="en"):
        report = match_slides(slides, segments, 10, [{"page": 1, "start": 0}])
    assert report["items"][0]["status"] == "partly" and report["items"][0]["reading"] == 100
    assert report["notes"][0].startswith("Slides 2 and 3: what is written on the slide was never said.")
    assert "Slide 1: you read the text off the slide" in report["notes"][1]


@pytest.fixture
def english_app(tmp_path):
    config = Config(DATABASE_URL="sqlite://", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="test")
    return create_app(config, recognizer=StubRecognizer(TALK), emotion_backend=StubEmotion("neutral"))


def test_api_answers_in_english_when_the_app_asks(english_app, make_wav):
    client = english_app.test_client()
    wrong = client.post("/api/auth/login", json={"email": "nobody@test.ru", "password": "secret1"}, headers=EN)
    assert wrong.get_json()["message"] == "Wrong email or password"
    assert client.post("/api/auth/login", json={"email": "nobody@test.ru", "password": "secret1"}).get_json()["message"] == "Неверный email или пароль"

    token = client.post("/api/auth/register", json={"name": "Edna", "email": "edna@test.ru", "password": "secret1"}, headers=EN).get_json()["token"]
    auth = {"Authorization": f"Bearer {token}", **EN}
    titles = [a["title"] for a in client.get("/api/articles", headers=auth).get_json()]
    assert titles[0] == "Gestures and movement" and len(titles) == 5
    russian = client.get("/api/articles", headers={"Authorization": f"Bearer {token}"}).get_json()
    assert russian[0]["title"] == "Жестикуляция и движение" and len(russian) == 5

    with open(make_wav(duration=40.0), "rb") as audio:
        created = client.post("/api/speeches", headers=auth, content_type="multipart/form-data", data={"audio": (audio, "speech.wav")}).get_json()
    assert created["language"] == "en"
    assert created["feedback"]["num_fillers"] == 5 and "you know" in created["feedback"]["fillers"]
    assert created["recommendation"]["title"] in ("You are doing well!", "There is room to improve")
    assert "**drop the filler words** (“you know”" in created["recommendation"]["description"]
    assert created["content"]["structure"]["summary"].startswith("There is an introduction")
    assert client.get("/api/stats", headers=auth).get_json()["thresholds"]["rate_fast"] == 170.0
    assert client.get("/api/stats", headers={"Authorization": f"Bearer {token}"}).get_json()["thresholds"]["rate_fast"] == 140.0

    silent = client.post("/api/speeches", headers=auth, content_type="multipart/form-data", data={})
    assert silent.get_json()["message"] == "No audio file was sent"


def test_english_speech_gets_russian_advice_for_a_russian_interface(english_app, make_wav):
    client = english_app.test_client()
    token = client.post("/api/auth/register", json={"name": "Эдна", "email": "edna@test.ru", "password": "secret1"}).get_json()["token"]
    with open(make_wav(duration=40.0), "rb") as audio:
        created = client.post("/api/speeches", headers={"Authorization": f"Bearer {token}"}, content_type="multipart/form-data",
                              data={"audio": (audio, "speech.wav")}).get_json()
    assert created["language"] == "en" and created["feedback"]["num_fillers"] == 5
    assert "**убрать слова-заполнители** («you know»" in created["recommendation"]["description"]


def test_main_idea_is_not_a_run_on_sentence():
    # Распознаватель поставил запятые вместо точек: «фраза» из сорока слов делится на части.
    run_on = ("First, the application recognizes the speech, second, it counts filler words in the speech, for example, it finds "
              "words such as well, and, in conclusion, regular practice of speech makes a speaker more confident and calm on stage, "
              "which is the point of this whole speech practice application.")
    with lang.use(speech="en", ui="en"):
        idea = analyze_content(run_on)["main_idea"]
    assert idea and len(idea.split()) <= 28 and idea[0].isupper() and idea.endswith(".")
