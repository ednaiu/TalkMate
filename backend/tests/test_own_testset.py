"""Свой тестовый набор: замер на записях с дословной расшифровкой и выгрузка черновика из базы."""
import json

import numpy as np
import soundfile as sf

from speech_analysis.recognition import StubRecognizer
from training.export_dataset import export
from training.own_testset import evaluate, load_items

from .conftest import SR, upload, voice


def _phrases():
    """Четыре «фразы» с паузами и тихим фоном, как в комнате."""
    pause = np.zeros(SR // 2, dtype=np.float32)
    speech = np.concatenate([np.concatenate([voice(duration=1.5, amplitude=0.3), pause]) for _ in range(4)])
    return speech + np.random.default_rng(0).normal(0, 0.001, len(speech)).astype(np.float32)


def test_evaluation_counts_errors_fillers_and_pace(tmp_path):
    sf.write(tmp_path / "rec1.wav", _phrases(), SR)
    (tmp_path / "rec1.txt").write_text("ну вот э-э сегодня я расскажу о проекте", encoding="utf-8")
    (tmp_path / "rec1.json").write_text(json.dumps({"pace": "slow", "noisy": False}), encoding="utf-8")
    sf.write(tmp_path / "lonely.wav", _phrases(), SR)  # без расшифровки в набор не попадает
    items = load_items(tmp_path)
    assert [name for name, *_ in items] == ["rec1"]

    summary, rows = evaluate(items, StubRecognizer("ну сегодня я расскажу о проекте").recognize)
    assert summary["recordings"] == 1
    assert summary["filler_recall"] == 0.3333       # из «ну», «вот», «э-э» услышано только «ну»
    assert summary["sound_recall"] == 0.0           # звук-пауза «э-э» потерян
    assert 0 < summary["wer"] < 1
    assert summary["pace_agreement_with_people"] == 1.0
    assert summary["noise_agreement_with_people"] == 1.0
    assert rows[0]["rate_model"] < rows[0]["rate_reference"]


def test_export_takes_only_consented_recordings(app, client, user, make_wav, tmp_path):
    first = upload(client, user["headers"], make_wav()).get_json()["id"]
    client.put(f"/api/speeches/{first}/ratings/pace", headers=user["headers"], json={"verdict": "wrong"})
    out = tmp_path / "draft"
    with app.extensions["connector"].session() as session:
        assert export(session, app.config["TM"].AUDIO_DIR, out) == 0
    client.put("/api/consent", headers=user["headers"], json={"share_recordings": True})
    with app.extensions["connector"].session() as session:
        assert export(session, app.config["TM"].AUDIO_DIR, out) == 1
    name = f"rec{first:05d}"
    assert (out / f"{name}.txt").read_text(encoding="utf-8")
    assert json.loads((out / f"{name}.model.json").read_text(encoding="utf-8"))["ratings"] == {"pace": "wrong"}
