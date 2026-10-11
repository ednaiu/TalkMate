import json

import pytest
import soundfile as sf

from training.metrics import f1_for_class, macro_f1
from training.train_emotion import read_manifest

from .conftest import SR, voice


def test_f1_formula_from_slide():
    # Для класса a: точность 2/3, полнота 2/2, F1 = 2 * (2/3) * 1 / (2/3 + 1) = 0.8
    y_true = ["a", "a", "b", "b"]
    y_pred = ["a", "a", "a", "b"]
    assert f1_for_class(y_true, y_pred, "a") == pytest.approx(0.8)
    assert f1_for_class(y_true, y_pred, "b") == pytest.approx(2 * 1.0 * 0.5 / 1.5)
    assert macro_f1(y_true, y_pred) == pytest.approx((0.8 + 2 / 3) / 2)


def test_f1_edge_cases():
    assert macro_f1([], []) == 0.0
    assert macro_f1(["a", "b"], ["a", "b"]) == 1.0
    assert f1_for_class(["a"], ["b"], "a") == 0.0


def test_read_dusha_tsv_manifest(tmp_path):
    manifest = tmp_path / "raw_crowd_train.tsv"
    manifest.write_text(
        "hash_id\taudio_path\tduration\tannotator_emo\tgolden_emo\tspeaker_emo\n"
        "1\twavs/1.wav\t3.1\tangry\t\tangry\n"
        "1\twavs/1.wav\t3.1\tneutral\t\tangry\n"      # вторая оценка той же записи
        "2\twavs/2.wav\t2.0\tpositive\tpositive\tneutral\n"
        "3\twavs/3.wav\t2.0\tother\t\tother\n"
        "4\twavs/4.wav\t2.0\tsad\t\t\n",
        encoding="utf-8",
    )
    items = read_manifest(manifest)
    assert items == [(tmp_path / "wavs/1.wav", "anger"), (tmp_path / "wavs/2.wav", "happiness")]
    assert read_manifest(manifest, audio_root="/data", limit=1)[0][0].as_posix() == "/data/wavs/1.wav"


def test_read_jsonl_manifest(tmp_path):
    manifest = tmp_path / "train.jsonl"
    manifest.write_text(
        json.dumps({"audio_path": "a.wav", "emotion": "sad"}) + "\n" + json.dumps({"audio_path": "b.wav", "emotion": "neutral"}) + "\n",
        encoding="utf-8",
    )
    assert [label for _, label in read_manifest(manifest)] == ["sadness", "neutral"]


def test_split_items_is_stratified_and_disjoint():
    from training.train_emotion import split_items

    items = [(f"a{i}", "anger") for i in range(20)] + [(f"n{i}", "neutral") for i in range(80)]
    train, val = split_items(items, 0.1, seed=0)
    assert len(train) == 90 and len(val) == 10
    assert sorted(label for _, label in val) == ["anger"] * 2 + ["neutral"] * 8
    assert not {source for source, _ in train} & {source for source, _ in val}


def test_balanced_weights():
    from training.train_emotion import balanced_weights

    dusha = [("x", "neutral")] * 90 + [("x", "anger")] * 10
    resd = [("x", "fear")] * 10
    weights = balanced_weights({"dusha": dusha, "resd": resd}, resd_share=0.25)
    assert weights.sum() == pytest.approx(1.0)
    assert weights[:90].sum() == pytest.approx(weights[90:100].sum()) == pytest.approx(0.375)
    assert weights[100:].sum() == pytest.approx(0.25)


def test_augment_and_crop_keep_audio_valid():
    import numpy as np

    from training.train_emotion import augment, crop

    rng = np.random.default_rng(0)
    samples = voice(duration=3.0, amplitude=0.9)
    for _ in range(20):
        changed = augment(samples, rng)
        assert changed.dtype == np.float32 and len(changed) == len(samples)
        assert np.max(np.abs(changed)) <= 1.0
    assert len(crop(samples, 1.0, rng)) == SR
    assert len(crop(samples, 10.0, rng)) == len(samples)
    assert np.array_equal(crop(samples, 1.0), samples[:SR])     # без генератора обрезка детерминирована


@pytest.mark.real
def test_training_loop_runs_on_tiny_model(tmp_path):
    """Прогон полного дообучения на крошечной модели WavLM: заморозка, шаг Adam, F1 по эпохам, сохранение весов."""
    torch = pytest.importorskip("torch")
    from transformers import Wav2Vec2FeatureExtractor, WavLMConfig, WavLMForSequenceClassification

    from speech_analysis.emotion import EMOTIONS
    from training.train_emotion import freeze, train

    items = []
    for index, (label, f0) in enumerate([("anger", 220.0), ("sadness", 110.0)] * 4):
        path = tmp_path / f"{index}.wav"
        sf.write(path, voice(duration=1.5, f0=f0, amplitude=0.3), SR)
        items.append((path, label))

    torch.manual_seed(0)
    config = WavLMConfig(
        hidden_size=32, num_hidden_layers=3, num_attention_heads=2, intermediate_size=64,
        conv_dim=(16, 16), conv_stride=(8, 8), conv_kernel=(10, 8), num_conv_pos_embeddings=16,
        num_conv_pos_embedding_groups=2, classifier_proj_size=32, num_labels=len(EMOTIONS),
        id2label=dict(enumerate(EMOTIONS)), label2id={label: i for i, label in enumerate(EMOTIONS)},
        mask_time_prob=0.0, num_buckets=32, max_bucket_distance=80,
    )
    model = WavLMForSequenceClassification(config)
    head_before = model.classifier.weight.detach().clone()
    top_before = model.wavlm.encoder.layers[2].feed_forward.output_dense.weight.detach().clone()
    bottom_before = model.wavlm.encoder.layers[0].feed_forward.output_dense.weight.detach().clone()
    cnn_before = model.wavlm.feature_extractor.conv_layers[0].conv.weight.detach().clone()

    log = []
    history = train({"dusha": items}, {"dusha": items}, model, Wav2Vec2FeatureExtractor(return_attention_mask=True),
                    tmp_path / "out", epochs=2, lr=1e-3, batch_size=4, accumulate=1, max_seconds=1.5,
                    unfreeze_layers=1, device="cpu", log=log.append)

    assert len(history) == 2 and all(0.0 <= h["dusha"] <= 1.0 for h in history)
    assert not torch.equal(head_before, model.classifier.weight)
    assert not torch.equal(top_before, model.wavlm.encoder.layers[2].feed_forward.output_dense.weight)
    # Замороженные части не меняются.
    assert torch.equal(bottom_before, model.wavlm.encoder.layers[0].feed_forward.output_dense.weight)
    assert torch.equal(cnn_before, model.wavlm.feature_extractor.conv_layers[0].conv.weight)
    assert (tmp_path / "out" / "config.json").exists()
    assert log[1].startswith("Epoch") and len(log) == 4

    everything = freeze(model, unfreeze_layers=3)
    only_head = freeze(model, unfreeze_layers=0)
    assert only_head < everything
