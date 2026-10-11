from speech_analysis.emotion import StubEmotion
from speech_analysis.recognition import StubRecognizer
from talkmate import create_app
from talkmate.config import Config
from talkmate.models import Threshold


def make(tmp_path):
    config = Config(DATABASE_URL=f"sqlite:///{tmp_path / 'db.sqlite'}", AUDIO_DIR=tmp_path / "uploads", SECRET_KEY="k" * 40)
    return create_app(config, recognizer=StubRecognizer("текст"), emotion_backend=StubEmotion())


def stored(app):
    with app.extensions["connector"].session() as session:
        return {row.key: row.value for row in session.query(Threshold)}


def set_values(app, **values):
    with app.extensions["connector"].session() as session:
        for key, value in values.items():
            session.get(Threshold, key).value = value
        session.commit()


def test_new_database_gets_researched_norm(tmp_path):
    values = stored(make(tmp_path))
    assert values["rate_slow"] == 90 and values["rate_fast"] == 140


def test_old_default_norm_is_replaced_on_start(tmp_path):
    set_values(make(tmp_path), rate_slow=120, rate_fast=180)       # база, созданная прежней версией
    values = stored(make(tmp_path))
    assert values["rate_slow"] == 90 and values["rate_fast"] == 140


def test_intermediate_default_norm_is_replaced_too(tmp_path):
    set_values(make(tmp_path), rate_slow=100, rate_fast=140)
    assert stored(make(tmp_path))["rate_slow"] == 90


def test_norm_changed_by_administrator_is_kept(tmp_path):
    set_values(make(tmp_path), rate_slow=110, rate_fast=180)
    values = stored(make(tmp_path))
    assert values["rate_slow"] == 110 and values["rate_fast"] == 180
