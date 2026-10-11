"""Личный кабинет: сводка по тренировкам пользователя."""
from datetime import date, timedelta

from talkmate.models import Speech
from talkmate.services.speech_service import streak, title_of


def record(client, user, make_wav):
    with open(make_wav(), "rb") as audio:
        return client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data", data={"audio": (audio, "speech.wav")}).get_json()


def test_streak_counts_consecutive_days_and_forgives_today():
    today = date(2026, 10, 11)
    days = lambda *offsets: {today - timedelta(days=offset) for offset in offsets}
    assert streak(days(0, 1, 2, 3), today) == 4
    assert streak(days(1, 2), today) == 2                   # сегодня ещё не тренировались, серия не оборвана
    assert streak(days(2, 3), today) == 0                   # вчера пропуск
    assert streak(days(0, 2, 3), today) == 1
    assert streak(set(), today) == 0


def test_title_comes_from_main_idea_then_from_text():
    assert title_of(Speech(text="", content='{"main_idea": "Приложение помогает тренировать выступления каждый день."}')) \
        == "Приложение помогает тренировать выступления…"
    assert title_of(Speech(text="добрый день коллеги сегодня я расскажу о нашем проекте подробно", content=None)) == "добрый день коллеги сегодня я расскажу о"
    assert title_of(Speech(text="", content=None)) == "Тренировка"


def test_profile_of_a_new_user_is_empty(client, user):
    profile = client.get("/api/profile", headers=user["headers"]).get_json()
    assert profile["user"]["name"] == "Эдна"
    assert (profile["count"], profile["minutes"], profile["streak"]) == (0, 0, 0)
    assert profile["tempo"] == [] and profile["recent"] == []
    assert (profile["rate_slow"], profile["rate_fast"]) == (90.0, 140.0)
    assert client.get("/api/trainings", headers=user["headers"]).get_json() == []


def test_profile_sums_trainings(client, user, make_wav):
    created = [record(client, user, make_wav) for _ in range(3)]
    profile = client.get("/api/profile", headers=user["headers"]).get_json()
    assert profile["count"] == 3 and profile["streak"] == 1
    assert len(profile["tempo"]) == 3 and profile["tempo"][-1]["rate"] == created[-1]["feedback"]["speech_rate"]
    assert [item["id"] for item in profile["recent"]] == [created[2]["id"], created[1]["id"]]
    assert profile["recent"][0]["title"] and profile["recent"][0]["duration"] == 4
    trainings = client.get("/api/trainings", headers=user["headers"]).get_json()
    assert [item["id"] for item in trainings] == [c["id"] for c in reversed(created)]
    # Тренировка из списка открывается целиком.
    assert client.get(f"/api/speeches/{trainings[0]['id']}", headers=user["headers"]).get_json()["recommendation"]["title"]


def test_profile_needs_login_and_follows_the_language(client, user):
    assert client.get("/api/profile").status_code == 401
    english = client.get("/api/profile", headers={**user["headers"], "Accept-Language": "en"}).get_json()
    assert (english["rate_slow"], english["rate_fast"]) == (110.0, 170.0)
