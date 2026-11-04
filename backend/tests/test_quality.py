"""Оценки разбора «верно / неверно» и согласие отдавать записи."""
from .conftest import auth, register, upload


def _speech(client, user, make_wav):
    response = upload(client, user["headers"], make_wav())
    assert response.status_code == 201
    return response.get_json()["id"]


def test_user_rates_a_metric_and_can_change_mind(client, user, make_wav):
    speech_id = _speech(client, user, make_wav)
    url = f"/api/speeches/{speech_id}/ratings/pace"
    assert client.put(url, headers=user["headers"], json={"verdict": "wrong", "comment": "было медленно"}).status_code == 200
    assert client.put(url, headers=user["headers"], json={"verdict": "correct"}).status_code == 200
    ratings = client.get(f"/api/speeches/{speech_id}/ratings", headers=user["headers"]).get_json()
    assert [(r["metric"], r["verdict"], r["comment"]) for r in ratings] == [("pace", "correct", None)]


def test_bad_metric_and_verdict_are_rejected(client, user, make_wav):
    speech_id = _speech(client, user, make_wav)
    assert client.put(f"/api/speeches/{speech_id}/ratings/mood", headers=user["headers"], json={"verdict": "correct"}).status_code == 400
    assert client.put(f"/api/speeches/{speech_id}/ratings/pace", headers=user["headers"], json={"verdict": "maybe"}).status_code == 400
    assert client.put(f"/api/speeches/{speech_id}/ratings/pace", headers=user["headers"],
                      json={"verdict": "wrong", "comment": "x" * 501}).status_code == 400


def test_nobody_rates_someone_elses_speech(client, user, make_wav):
    speech_id = _speech(client, user, make_wav)
    other = auth(register(client, email="other@test.ru")["token"])
    assert client.put(f"/api/speeches/{speech_id}/ratings/pace", headers=other, json={"verdict": "wrong"}).status_code == 404
    assert client.get(f"/api/speeches/{speech_id}/ratings", headers=other).status_code == 404


def test_ratings_go_away_with_the_speech(client, user, make_wav):
    speech_id = _speech(client, user, make_wav)
    client.put(f"/api/speeches/{speech_id}/ratings/emotion", headers=user["headers"], json={"verdict": "wrong"})
    assert client.delete(f"/api/speeches/{speech_id}", headers=user["headers"]).status_code == 204


def test_admin_sees_share_of_correct_by_metric(client, user, admin, make_wav):
    first, second = _speech(client, user, make_wav), _speech(client, user, make_wav)
    client.put(f"/api/speeches/{first}/ratings/pace", headers=user["headers"], json={"verdict": "correct"})
    client.put(f"/api/speeches/{second}/ratings/pace", headers=user["headers"], json={"verdict": "wrong"})
    summary = {row["metric"]: row for row in client.get("/api/admin/ratings/summary", headers=admin).get_json()}
    assert summary["pace"] == {"metric": "pace", "total": 2, "correct": 1, "share_correct": 0.5}
    assert summary["emotion"]["share_correct"] is None
    assert client.get("/api/admin/ratings/summary", headers=user["headers"]).status_code == 403


def test_consent_is_stored_and_shown_in_profile(client, user):
    assert client.put("/api/consent", headers=user["headers"], json={"share_recordings": "yes"}).status_code == 400
    body = client.put("/api/consent", headers=user["headers"], json={"share_recordings": True}).get_json()
    assert body["share_recordings"] is True and body["share_recordings_at"]
    assert client.get("/api/profile", headers=user["headers"]).get_json()["user"]["share_recordings"] is True
