import jwt
import pytest

from speech_analysis.recognition import RecognitionError

from .conftest import auth, register, upload


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


# --- Регистрация и вход ---

def test_register_returns_token_and_user(client):
    data = register(client, email="New@Test.RU", phone="+79990001122", birth_date="2001-05-17", gender="female")
    assert data["token"]
    assert data["user"]["email"] == "new@test.ru"
    assert data["user"]["role"] == "user"
    assert data["user"]["birth_date"] == "2001-05-17"
    assert data["user"]["gender"] == "female"
    assert "password" not in data["user"]


def test_password_is_stored_hashed(app, client):
    register(client, password="secret1")
    from talkmate.models import User

    with app.extensions["connector"].session() as session:
        stored = session.query(User).filter_by(email="user@test.ru").one().password
    assert stored != "secret1" and stored.startswith("pbkdf2:")


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"name": "", "email": "a@b.ru", "password": "secret1"}, "invalid_name"),
        ({"name": "Аня", "email": "not-an-email", "password": "secret1"}, "invalid_email"),
        ({"name": "Аня", "email": "a@b.ru", "password": "123"}, "weak_password"),
        ({"name": "Аня", "email": "a@b.ru", "password": "secret1", "birth_date": "17.05.2001"}, "invalid_birth_date"),
        ({"name": "Аня", "email": "a@b.ru", "password": "secret1", "birth_date": "2999-01-01"}, "invalid_birth_date"),
        ({"name": "Аня", "email": "a@b.ru", "password": "secret1", "gender": "x"}, "invalid_gender"),
    ],
)
def test_register_validation(client, payload, code):
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == code


def test_register_duplicate_email(client):
    register(client)
    response = client.post("/api/auth/register", json={"name": "Другой", "email": "USER@test.ru", "password": "secret1"})
    assert response.status_code == 409
    assert response.get_json()["error"] == "email_taken"


def test_register_rejects_non_json(client):
    assert client.post("/api/auth/register", data="hello").status_code == 400


def test_login_success_and_me(client):
    register(client)
    response = client.post("/api/auth/login", json={"email": " User@Test.ru ", "password": "secret1"})
    assert response.status_code == 200
    me = client.get("/api/me", headers=auth(response.get_json()["token"]))
    assert me.get_json()["name"] == "Эдна"


def test_login_wrong_password_and_unknown_user_look_the_same(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"email": "user@test.ru", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@test.ru", "password": "secret1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()


@pytest.mark.parametrize("path", ["/api/me", "/api/articles", "/api/articles/1", "/api/speeches", "/api/stats", "/api/recommendations"])
def test_endpoints_require_token(client, path):
    assert client.get(path).status_code == 401


def test_bad_and_expired_tokens_rejected(client, user):
    assert client.get("/api/me", headers=auth("garbage")).status_code == 401
    forged = jwt.encode({"sub": str(user["id"]), "role": "admin"}, "another-secret-key-of-sufficient-length", algorithm="HS256")
    assert client.get("/api/me", headers=auth(forged)).status_code == 401
    expired = jwt.encode({"sub": str(user["id"]), "exp": 1}, "test-secret-key-that-is-long-enough-for-hs256", algorithm="HS256")
    assert client.get("/api/me", headers=auth(expired)).status_code == 401


# --- Статьи ---

def test_articles_seeded_from_mockup(client, user):
    titles = [a["title"] for a in client.get("/api/articles", headers=user["headers"]).get_json()]
    assert titles[:4] == ["Жестикуляция и движение", "Подготовка на площадке", "Использование презентаций", "Разогрев"]


def test_article_list_has_no_content_but_detail_has(client, user):
    listing = client.get("/api/articles", headers=user["headers"]).get_json()
    assert "content" not in listing[0]
    detail = client.get(f"/api/articles/{listing[0]['id']}", headers=user["headers"]).get_json()
    assert detail["content"].startswith("Жестикуляция, которой пользуются американские актёры")
    assert "**толкание, вытягивание, подъём, бросание и разрывание.**" in detail["content"]


def test_article_not_found(client, user):
    assert client.get("/api/articles/9999", headers=user["headers"]).status_code == 404


# --- Запись и анализ ---

def test_upload_speech_returns_feedback_and_recommendation(client, user, make_wav, recognizer):
    recognizer.text = " ".join(["ну", "вот", "как", "бы"] + ["слово"] * 21)  # 25 слов
    response = upload(client, user["headers"], make_wav(duration=10.0, amplitude=0.01, f0=140.0))
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["duration"] == pytest.approx(10.0, abs=0.01)
    fb = body["feedback"]
    assert fb["speech_rate"] == 150
    assert fb["volume"] == "quiet"
    assert fb["monotony"] == "monotone"
    assert fb["num_fillers"] == 3
    assert set(fb["fillers"]) == {"ну", "вот", "как бы"}
    assert fb["emotion"] == "neutral"
    assert "увеличить громкость" in body["recommendation"]["description"]
    assert body["recommendation"]["speech_id"] == body["id"]


def test_upload_saves_audio_file(app, client, user, make_wav):
    upload(client, user["headers"], make_wav())
    files = list(app.config["TM"].AUDIO_DIR.iterdir())
    assert len(files) == 1 and files[0].suffix == ".wav"


def test_upload_without_file(client, user):
    response = client.post("/api/speeches", headers=user["headers"], data={}, content_type="multipart/form-data")
    assert response.status_code == 400 and response.get_json()["error"] == "no_audio"


def test_upload_rejects_unknown_extension(client, user, make_wav):
    response = upload(client, user["headers"], make_wav(), filename="speech.exe")
    assert response.status_code == 400 and response.get_json()["error"] == "bad_audio_format"


def test_upload_garbage_is_422_and_leaves_no_file(app, client, user, tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"definitely not a wav file")
    response = upload(client, user["headers"], bad)
    assert response.status_code == 422 and response.get_json()["error"] == "bad_audio"
    assert list(app.config["TM"].AUDIO_DIR.iterdir()) == []
    assert client.get("/api/speeches", headers=user["headers"]).get_json() == []


def test_upload_too_short(client, user, make_wav):
    assert upload(client, user["headers"], make_wav(duration=0.4)).status_code == 422


def test_upload_with_no_recognized_speech(client, user, make_wav, recognizer):
    recognizer.text = "   "
    response = upload(client, user["headers"], make_wav())
    assert response.status_code == 422 and response.get_json()["error"] == "no_speech"


def test_upload_of_dead_microphone_recording_says_so(client, user, make_wav, recognizer):
    """Эмулятор с потерянным микрофоном отдаёт ровные нули: пользователю нужно сказать про микрофон, а не про дикцию."""
    import numpy as np

    from .conftest import SR, voice

    recognizer.text = ""
    samples = np.concatenate([voice(duration=1.0), np.zeros(SR * 6, dtype=np.float32)])
    response = upload(client, user["headers"], make_wav(samples))
    assert response.status_code == 422 and response.get_json()["error"] == "no_signal"
    assert "Микрофон" in response.get_json()["message"]


def test_dead_air_ignores_short_gaps_and_real_silence():
    import numpy as np

    from speech_analysis.audio import dead_air_seconds

    from .conftest import SR, voice

    speech = voice(duration=1.0)
    assert dead_air_seconds(speech) == 0.0
    assert dead_air_seconds(np.concatenate([speech, np.zeros(SR // 4, dtype=np.float32), speech])) == 0.0   # короткий провал
    noise = np.random.default_rng(0).normal(0, 1e-4, SR * 3).astype(np.float32)                           # тихая комната
    assert dead_air_seconds(noise) == 0.0
    cut = np.concatenate([speech, np.zeros(SR * 2, dtype=np.float32), speech, np.zeros(SR * 3, dtype=np.float32)])
    assert dead_air_seconds(cut) == 5.0


def test_upload_when_recognition_service_is_down(client, user, make_wav, recognizer, monkeypatch):
    def boom(samples):
        raise RecognitionError("timeout")

    monkeypatch.setattr(recognizer, "recognize", boom)
    response = upload(client, user["headers"], make_wav())
    assert response.status_code == 503 and response.get_json()["error"] == "recognition_unavailable"


def test_speech_history_newest_first_and_detail(client, user, make_wav):
    first = upload(client, user["headers"], make_wav()).get_json()
    second = upload(client, user["headers"], make_wav()).get_json()
    history = client.get("/api/speeches", headers=user["headers"]).get_json()
    assert [s["id"] for s in history] == [second["id"], first["id"]]
    assert client.get(f"/api/speeches/{first['id']}", headers=user["headers"]).get_json() == first


def test_users_cannot_see_each_others_speeches(client, user, make_wav):
    speech = upload(client, user["headers"], make_wav()).get_json()
    other = auth(register(client, email="other@test.ru")["token"])
    assert client.get(f"/api/speeches/{speech['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/speeches/{speech['id']}", headers=other).status_code == 404
    assert client.get("/api/speeches", headers=other).get_json() == []
    assert client.get("/api/stats", headers=other).get_json()["count"] == 0
    assert client.get("/api/recommendations", headers=other).get_json() == []


def test_delete_speech_removes_file_feedback_and_recommendation(app, client, user, make_wav):
    speech = upload(client, user["headers"], make_wav()).get_json()
    assert client.delete(f"/api/speeches/{speech['id']}", headers=user["headers"]).status_code == 204
    assert client.get(f"/api/speeches/{speech['id']}", headers=user["headers"]).status_code == 404
    assert client.get("/api/recommendations", headers=user["headers"]).get_json() == []
    assert list(app.config["TM"].AUDIO_DIR.iterdir()) == []


# --- Статистика и рекомендации ---

def test_stats_empty(client, user):
    body = client.get("/api/stats", headers=user["headers"]).get_json()
    assert body["count"] == 0 and body["points"] == []
    assert body["thresholds"]["rate_slow"] == 90 and body["thresholds"]["rate_fast"] == 140


def test_stats_points_in_chronological_order(client, user, make_wav, recognizer):
    recognizer.text = " ".join(["слово"] * 10)
    a = upload(client, user["headers"], make_wav(duration=4.0)).get_json()   # 150 слов/мин
    recognizer.text = " ".join(["ну"] * 2 + ["слово"] * 18)
    b = upload(client, user["headers"], make_wav(duration=6.0)).get_json()   # 200 слов/мин
    body = client.get("/api/stats", headers=user["headers"]).get_json()
    assert [p["speech_id"] for p in body["points"]] == [a["id"], b["id"]]
    assert [p["speech_rate"] for p in body["points"]] == [150, 200]
    assert [p["num_fillers"] for p in body["points"]] == [0, 2]
    assert all("volume_db" in p and "pitch_variability" in p for p in body["points"])


def test_recommendations_saved_per_speech(client, user, make_wav):
    upload(client, user["headers"], make_wav())
    upload(client, user["headers"], make_wav())
    recs = client.get("/api/recommendations", headers=user["headers"]).get_json()
    assert len(recs) == 2 and all(r["title"] and r["description"] for r in recs)


def test_unknown_route_is_json_404(client):
    response = client.get("/api/nope")
    assert response.status_code == 404 and "error" in response.get_json()
