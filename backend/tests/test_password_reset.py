from datetime import timedelta

import pytest

from speech_analysis.emotion import StubEmotion
from speech_analysis.recognition import StubRecognizer
from talkmate import create_app
from talkmate.config import Config
from talkmate.models import PasswordReset, utcnow
from talkmate.services import password_reset_service as service
from talkmate.services.mailer import Mailer

from .conftest import register


class FakeMailer:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send_reset_code(self, email, name, code, minutes):
        if self.fail:
            raise OSError("smtp недоступен")
        self.sent.append((email, name, code, minutes))
        return True


@pytest.fixture
def mailer():
    return FakeMailer()


@pytest.fixture
def app(tmp_path, mailer):
    config = Config(DATABASE_URL="sqlite://", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40)
    return create_app(config, recognizer=StubRecognizer("текст"), emotion_backend=StubEmotion(), mailer=mailer)


@pytest.fixture
def client(app):
    client = app.test_client()
    register(client, email="edna@itmo.ru", password="oldpass1")
    return client


def forgot(client, email="edna@itmo.ru"):
    return client.post("/api/auth/forgot", json={"email": email})


def reset(client, code, password="newpass1", email="edna@itmo.ru"):
    return client.post("/api/auth/reset", json={"email": email, "code": code, "password": password})


def login(client, password):
    return client.post("/api/auth/login", json={"email": "edna@itmo.ru", "password": password}).status_code


def test_full_recovery_changes_password_and_logs_in(client, mailer):
    assert forgot(client, " Edna@ITMO.ru ").status_code == 200
    email, name, code, minutes = mailer.sent[0]
    assert email == "edna@itmo.ru" and name == "Эдна" and minutes == 15
    assert len(code) == 6 and code.isdigit()

    response = reset(client, code)
    assert response.status_code == 200
    token = response.get_json()["token"]
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).get_json()["email"] == "edna@itmo.ru"
    assert login(client, "newpass1") == 200
    assert login(client, "oldpass1") == 401


def test_unknown_email_gets_same_answer_and_no_letter(client, mailer):
    known, unknown = forgot(client), forgot(client, "ghost@itmo.ru")
    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()
    assert [sent[0] for sent in mailer.sent] == ["edna@itmo.ru"]


def test_code_is_stored_hashed(app, client, mailer):
    forgot(client)
    with app.extensions["connector"].session() as session:
        stored = session.query(PasswordReset).one().code_hash
    assert mailer.sent[0][2] not in stored and stored.startswith("pbkdf2:")


def test_wrong_code_is_rejected_and_password_stays(client, mailer):
    forgot(client)
    wrong = "000000" if mailer.sent[0][2] != "000000" else "111111"
    response = reset(client, wrong)
    assert response.status_code == 400 and response.get_json()["error"] == "invalid_code"
    assert login(client, "oldpass1") == 200


def test_code_works_only_once(client, mailer):
    forgot(client)
    code = mailer.sent[0][2]
    assert reset(client, code).status_code == 200
    assert reset(client, code, password="another1").status_code == 400
    assert login(client, "newpass1") == 200


def test_code_is_blocked_after_five_wrong_attempts(client, mailer):
    forgot(client)
    code = mailer.sent[0][2]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(service.MAX_ATTEMPTS):
        assert reset(client, wrong).status_code == 400
    # Верный код после исчерпания попыток уже не принимается: шесть цифр нельзя перебирать.
    assert reset(client, code).status_code == 400
    assert login(client, "oldpass1") == 200


def test_expired_code_is_rejected(app, client, mailer):
    forgot(client)
    with app.extensions["connector"].session() as session:
        session.query(PasswordReset).one().expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
    assert reset(client, mailer.sent[0][2]).status_code == 400


def test_repeat_request_within_a_minute_sends_nothing(client, mailer):
    forgot(client)
    forgot(client)
    assert len(mailer.sent) == 1
    assert reset(client, mailer.sent[0][2]).status_code == 200


def test_new_request_after_pause_invalidates_previous_code(app, client, mailer):
    forgot(client)
    with app.extensions["connector"].session() as session:
        session.query(PasswordReset).one().created_at = utcnow() - timedelta(minutes=2)
        session.commit()
    forgot(client)
    first, second = mailer.sent[0][2], mailer.sent[1][2]
    if first != second:
        assert reset(client, first).status_code == 400
    assert reset(client, second).status_code == 200


def test_weak_new_password_is_rejected_before_code_check(client, mailer):
    forgot(client)
    response = reset(client, mailer.sent[0][2], password="123")
    assert response.status_code == 400 and response.get_json()["error"] == "weak_password"
    assert reset(client, mailer.sent[0][2]).status_code == 200      # попытка не сгорела


def test_reset_for_unknown_email_looks_like_wrong_code(client):
    response = reset(client, "123456", email="ghost@itmo.ru")
    assert response.status_code == 400 and response.get_json()["error"] == "invalid_code"


def test_mail_failure_is_reported(tmp_path):
    config = Config(DATABASE_URL="sqlite://", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40)
    client = create_app(config, recognizer=StubRecognizer("текст"), emotion_backend=StubEmotion(), mailer=FakeMailer(fail=True)).test_client()
    register(client, email="edna@itmo.ru")
    response = forgot(client)
    assert response.status_code == 503 and response.get_json()["error"] == "mail_unavailable"


def test_mailer_without_smtp_logs_code_instead_of_sending(caplog):
    mailer = Mailer(Config(SMTP_HOST=""))
    assert not mailer.configured
    with caplog.at_level("WARNING"):
        assert mailer.send_reset_code("edna@itmo.ru", "Эдна", "123456", 15) is False
    assert "123456" in caplog.text and "SMTP не настроен" in caplog.text


def test_mailer_with_smtp_sends_letter(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    config = Config(SMTP_HOST="smtp.example.com", SMTP_PORT=587, SMTP_USER="bot@example.com", SMTP_PASSWORD="pw", SMTP_FROM="TalkMate <bot@example.com>")
    assert Mailer(config).send_reset_code("edna@itmo.ru", "Эдна", "654321", 15) is True
    assert sent["server"] == ("smtp.example.com", 587) and sent["tls"] and sent["login"] == ("bot@example.com", "pw")
    assert sent["message"]["To"] == "edna@itmo.ru"
    assert "654321" in sent["message"].get_content()
