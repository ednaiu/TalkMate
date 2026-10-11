import pytest

from .conftest import auth, register, upload

ADMIN_PATHS = [
    ("get", "/api/admin/articles"),
    ("post", "/api/admin/articles"),
    ("put", "/api/admin/articles/1"),
    ("delete", "/api/admin/articles/1"),
    ("get", "/api/admin/thresholds"),
    ("put", "/api/admin/thresholds"),
    ("get", "/api/admin/users"),
    ("patch", "/api/admin/users/1"),
]


@pytest.mark.parametrize("method,path", ADMIN_PATHS)
def test_admin_api_closed_for_guests_and_users(client, user, method, path):
    assert getattr(client, method)(path, json={}).status_code == 401
    assert getattr(client, method)(path, json={}, headers=user["headers"]).status_code == 403


def test_admin_is_seeded_with_role(client, admin):
    assert client.get("/api/me", headers=admin).get_json()["role"] == "admin"


def test_user_cannot_register_as_admin(client):
    data = register(client, email="sneaky@test.ru", role="admin")
    assert data["user"]["role"] == "user"


# --- Статьи ---

def test_add_article_visible_to_users(client, admin, user):
    response = client.post("/api/admin/articles", headers=admin, json={"title": "Работа с вопросами", "content": "Текст"})
    assert response.status_code == 201
    titles = [a["title"] for a in client.get("/api/articles", headers=user["headers"]).get_json()]
    assert titles[-1] == "Работа с вопросами"


@pytest.mark.parametrize("payload", [{"title": "", "content": "x"}, {"title": "x", "content": "  "}, {"title": "x"}])
def test_add_article_requires_title_and_content(client, admin, payload):
    assert client.post("/api/admin/articles", headers=admin, json=payload).status_code == 400


def test_edit_article_title_and_text_separately(client, admin, user):
    article_id = client.get("/api/admin/articles", headers=admin).get_json()[0]["id"]
    client.patch(f"/api/admin/articles/{article_id}", headers=admin, json={"title": "Жесты"})
    after_title = client.get(f"/api/articles/{article_id}", headers=user["headers"]).get_json()
    assert after_title["title"] == "Жесты" and after_title["content"].startswith("Жестикуляция")
    client.patch(f"/api/admin/articles/{article_id}", headers=admin, json={"content": "Новый текст"})
    after_text = client.get(f"/api/articles/{article_id}", headers=user["headers"]).get_json()
    assert after_text["title"] == "Жесты" and after_text["content"] == "Новый текст"


def test_edit_article_rejects_empty_and_missing(client, admin):
    assert client.patch("/api/admin/articles/1", headers=admin, json={"title": " "}).status_code == 400
    assert client.put("/api/admin/articles/9999", headers=admin, json={"title": "x"}).status_code == 404


def test_delete_article(client, admin, user):
    before = client.get("/api/articles", headers=user["headers"]).get_json()
    assert client.delete(f"/api/admin/articles/{before[0]['id']}", headers=admin).status_code == 204
    after = client.get("/api/articles", headers=user["headers"]).get_json()
    assert len(after) == len(before) - 1


# --- Пороги ---

def test_thresholds_defaults(client, admin):
    body = client.get("/api/admin/thresholds", headers=admin).get_json()
    assert body["values"] == body["defaults"]
    assert set(body["labels"]) == set(body["values"])


def test_volume_threshold_changes_assessment(client, admin, user, make_wav):
    wav = make_wav(amplitude=0.15)
    assert upload(client, user["headers"], wav).get_json()["feedback"]["volume"] == "normal"
    response = client.put("/api/admin/thresholds", headers=admin, json={"volume_quiet_db": -10, "volume_loud_db": -3})
    assert response.status_code == 200 and response.get_json()["values"]["volume_quiet_db"] == -10
    assert upload(client, user["headers"], wav).get_json()["feedback"]["volume"] == "quiet"


def test_monotony_threshold_changes_assessment(client, admin, user, make_wav):
    wav = make_wav(duration=8.0, f0=150.0, wobble=5.0)
    assert upload(client, user["headers"], wav).get_json()["feedback"]["monotony"] == "expressive"
    client.put("/api/admin/thresholds", headers=admin, json={"monotony_min_semitones": 12})
    assert upload(client, user["headers"], wav).get_json()["feedback"]["monotony"] == "monotone"


@pytest.mark.parametrize(
    "payload",
    [
        {"unknown": 1},
        {"volume_quiet_db": "громко"},
        {"volume_quiet_db": True},
        {"volume_quiet_db": -5, "volume_loud_db": -20},
        {"rate_slow": 200},
        {"monotony_min_semitones": -1},
        {"fillers_max": -2},
    ],
)
def test_thresholds_validation(client, admin, payload):
    assert client.put("/api/admin/thresholds", headers=admin, json=payload).status_code == 400
    body = client.get("/api/admin/thresholds", headers=admin).get_json()
    assert body["values"] == body["defaults"]


# --- Пользователи ---

def test_list_users(client, admin, user):
    emails = [u["email"] for u in client.get("/api/admin/users", headers=admin).get_json()]
    assert emails == ["admin@test.ru", "user@test.ru"]


def test_edit_user_name_and_email(client, admin, user):
    response = client.patch(f"/api/admin/users/{user['id']}", headers=admin, json={"name": "Эдна Ю.", "email": "Edna@itmo.ru"})
    assert response.status_code == 200
    assert response.get_json()["name"] == "Эдна Ю." and response.get_json()["email"] == "edna@itmo.ru"
    assert client.post("/api/auth/login", json={"email": "edna@itmo.ru", "password": "secret1"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "user@test.ru", "password": "secret1"}).status_code == 401


def test_edit_user_validation(client, admin, user):
    url = f"/api/admin/users/{user['id']}"
    assert client.patch(url, headers=admin, json={"email": "bad"}).status_code == 400
    assert client.patch(url, headers=admin, json={"name": ""}).status_code == 400
    assert client.patch(url, headers=admin, json={"email": "admin@test.ru"}).status_code == 409
    assert client.patch("/api/admin/users/9999", headers=admin, json={"name": "x"}).status_code == 404


def test_edit_user_cannot_change_role_or_password(client, admin, user):
    client.patch(f"/api/admin/users/{user['id']}", headers=admin, json={"role": "admin", "password": "hacked1"})
    assert client.get("/api/me", headers=user["headers"]).get_json()["role"] == "user"
    assert client.post("/api/auth/login", json={"email": "user@test.ru", "password": "secret1"}).status_code == 200


def test_admin_page_served(client):
    response = client.get("/admin")
    assert response.status_code == 200 and b"TalkMate" in response.data
