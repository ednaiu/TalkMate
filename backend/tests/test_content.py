import pytest

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis.content import analyze_content, content_words, main_idea, split_sentences, strip_fillers, structure
from talkmate.services.recommendation_service import build_recommendation, find_issues

from .conftest import upload

SPEECH = (
    "Добрый день, уважаемые коллеги. Сегодня я расскажу о приложении для тренировки публичных выступлений. "
    "Многие боятся выступать, потому что им не хватает практики. Во-первых, приложение записывает выступление и оценивает темп речи. "
    "Во-вторых, приложение считает слова-заполнители и показывает их в расшифровке выступления. Например, оно выделяет слова ну и вот. "
    "Поэтому человек видит, что именно исправить в своём выступлении. "
    "Итак, приложение помогает тренировать выступления каждый день. Спасибо за внимание."
)


def test_split_sentences():
    assert split_sentences("Раз. Два! Три? Четыре… Пять") == ["Раз.", "Два!", "Три?", "Четыре…", "Пять"]
    assert split_sentences("") == []


def test_content_words_drop_function_words_and_fillers():
    assert content_words("Ну, вот, я как бы расскажу вам про наше приложение") == ["расскажу", "приложение"]


def test_main_idea_is_the_most_loaded_sentence_and_keywords_are_frequent():
    idea, keywords = main_idea(SPEECH)
    assert "приложени" in idea.lower() and "выступлени" in idea.lower()
    # Это цитата, а не пересказ: фраза взята из речи, убрано только вводное «Итак».
    assert idea == "Приложение помогает тренировать выступления каждый день."
    assert "выступление" in keywords or "выступления" in keywords or "выступлений" in keywords
    assert any(k.startswith("приложени") for k in keywords)
    assert len(keywords) <= 5


def test_main_idea_is_shown_without_fillers():
    text = "Ну, вот, короче, приложение оценивает темп речи и громкость речи. Темп речи важен. Громкость речи тоже важна для речи."
    idea, _ = main_idea(text)
    assert idea == "Приложение оценивает темп речи и громкость речи."
    assert strip_fillers("Это, как бы, работает, ну, отлично.") == "Это, работает, отлично."
    assert strip_fillers("Это работает, ну, вот.") == "Это работает."
    assert strip_fillers("Обычная фраза.") == "Обычная фраза."


def test_main_idea_of_too_short_text_is_absent():
    assert main_idea("Раз, два, три.") == (None, [])
    assert main_idea("") == (None, [])


def test_good_structure():
    result = structure(SPEECH)
    assert result["level"] == "good"
    assert result["intro"] is True and result["conclusion"] is True and result["links"] >= 4
    assert "вступление есть" in result["summary"].lower() and "заключение есть" in result["summary"]


def test_structure_without_intro_and_conclusion():
    body = " ".join(["Приложение записывает речь и оценивает темп, громкость, интонацию и слова-заполнители человека."] * 6)
    result = structure(body)
    assert result["level"] == "weak"
    assert result["intro"] is False and result["conclusion"] is False and result["links"] == 0
    assert "вступления нет" in result["summary"].lower() and "заключения нет" in result["summary"]


def test_markers_count_only_in_their_part_of_the_speech():
    middle = " ".join(["Приложение записывает речь и оценивает темп, громкость и интонацию человека."] * 6)
    # «Спасибо» и «добрый день» в середине выступления не делают его началом или концом.
    text = middle + " Добрый день и спасибо. " + middle
    result = structure(text)
    assert result["intro"] is False and result["conclusion"] is False
    assert structure("Добрый день, коллеги. " + middle + " Потому что так удобнее, поэтому приложение полезно.")["level"] == "partial"


def test_short_recording_is_not_judged():
    result = structure("Добрый день. Спасибо за внимание.")
    assert result["level"] == "short" and result["intro"] is None
    assert "слишком короткая" in result["summary"]


def test_analyze_content_shape():
    result = analyze_content(SPEECH)
    assert set(result) == {"main_idea", "main_idea_source", "keywords", "structure"}
    assert result["main_idea_source"] == "quote"
    with_model = analyze_content(SPEECH, summary="Приложение помогает тренировать выступления.")
    assert with_model["main_idea"] == "Приложение помогает тренировать выступления." and with_model["main_idea_source"] == "model"
    assert analyze_content("Раз, два.")["main_idea_source"] is None
    assert set(result["structure"]) == {"level", "intro", "links", "conclusion", "summary"}


def test_api_returns_and_keeps_content(client, user, make_wav, recognizer):
    recognizer.text = SPEECH
    created = upload(client, user["headers"], make_wav(duration=30.0)).get_json()
    assert created["content"]["structure"]["level"] == "good"
    assert "приложени" in created["content"]["main_idea"].lower()
    again = client.get(f"/api/speeches/{created['id']}", headers=user["headers"]).get_json()
    assert again["content"] == created["content"]


def test_recommendation_covers_missing_intro_and_conclusion(client, user, make_wav, recognizer):
    recognizer.text = " ".join(["Приложение записывает речь и оценивает темп, громкость, интонацию и слова-заполнители человека."] * 6)
    body = upload(client, user["headers"], make_wav(duration=40.0, amplitude=0.15, f0=110.0, f0_end=220.0)).get_json()
    text = body["recommendation"]["description"]
    assert "начинать со вступления" in text and "заканчивать выводом" in text


def test_short_recording_gets_no_structure_advice():
    from speech_analysis import AnalysisResult

    result = AnalysisResult(text="", duration=5, speech_rate=120, volume="normal", volume_db=-20, monotony="expressive",
                            pitch_variability=3, num_fillers=0, content=analyze_content("Раз, два, три, четыре, пять."))
    assert find_issues(result, T) == []
    assert build_recommendation(result, T)[0] == "Отличное выступление!"
