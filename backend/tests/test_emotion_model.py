"""Обучение и оценка головы модели эмоций. Признаки синтетические, поэтому тесты идут без кодировщика."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from speech_analysis.emotion_head import EMOTIONS, build_head, load_head, save_head, softmax
from speech_analysis.emotion_head import decide
from training.evaluate import clip_predictions, clip_probabilities, confusion_markdown, pick_threshold, report, threshold_curve
from training.train_head import predict, sample_weights, split_by_clip, train_head

LAYERS, DIM = 4, 16   # DIM: первая половина чисел играет роль средних, вторая отклонений
ANGER, DISGUST, FEAR, HAPPY, NEUTRAL, SAD = (EMOTIONS.index(n) for n in ("anger", "disgust", "fear", "happiness", "neutral", "sadness"))


def make_set(classes, per_class, seed, shift=0.0, windows=1):
    """Каждый класс лежит вокруг своего центра в последнем слое; нижние слои заполнены шумом."""
    rng = np.random.default_rng(seed)
    centers = np.random.default_rng(123).normal(0, 3, (len(EMOTIONS), DIM))
    x, y, clips = [], [], []
    clip = 0
    for label in classes:
        for _ in range(per_class):
            for _ in range(windows):
                features = rng.normal(0, 1, (LAYERS, DIM))
                features[-1] += centers[label] + shift
                x.append(features)
                y.append(label)
                clips.append(clip)
            clip += 1
    return {"x": np.array(x, dtype=np.float16), "y": np.array(y), "clips": np.array(clips),
            "base_logits": np.zeros((len(y), len(EMOTIONS)), dtype=np.float32)}


# --- Метрики ---

def test_report_metrics_by_hand():
    y_true = [ANGER, ANGER, NEUTRAL, NEUTRAL, NEUTRAL, SAD]
    y_pred = [ANGER, NEUTRAL, NEUTRAL, NEUTRAL, NEUTRAL, FEAR]
    result = report(y_true, y_pred, EMOTIONS)
    assert result["accuracy"] == pytest.approx(4 / 6, abs=1e-4)
    assert result["uar"] == pytest.approx((0.5 + 1.0 + 0.0) / 3, abs=1e-4)
    assert result["per_class"]["neutral"] == {"precision": 0.75, "recall": 1.0, "f1": pytest.approx(0.8571, abs=1e-4), "support": 3}
    assert result["per_class"]["sadness"]["f1"] == 0.0
    # Ответ «страх», которого нет в разметке, виден в матрице как отдельный столбец.
    assert result["confusion"]["sadness"]["fear"] == 1
    assert result["neutral_false_alarm"] == 0.0
    # Из трёх нейтральных записей две названы отрицательными эмоциями.
    assert report([NEUTRAL] * 3 + [ANGER], [FEAR, SAD, HAPPY, ANGER], EMOTIONS)["neutral_false_alarm"] == pytest.approx(0.6667, abs=1e-4)
    assert "| sadness |" in confusion_markdown(result)


def test_clip_predictions_pool_window_probabilities():
    probabilities = np.zeros((4, len(EMOTIONS)))
    probabilities[0, ANGER] = 0.6; probabilities[0, SAD] = 0.4     # запись 7, окно 1
    probabilities[2, SAD] = 0.9; probabilities[2, ANGER] = 0.1     # запись 7, окно 2
    probabilities[1, NEUTRAL] = 1.0                                # запись 3
    probabilities[3, NEUTRAL] = 1.0
    y_true, y_pred = clip_predictions(probabilities, np.array([7, 3, 7, 3]), np.array([SAD, NEUTRAL, SAD, NEUTRAL]))
    assert y_true == [NEUTRAL, SAD] and y_pred == [NEUTRAL, SAD]


def test_softmax_rows_sum_to_one():
    result = softmax(np.array([[1000.0, 1000.0], [0.0, np.log(3.0)]]))
    assert result[0] == pytest.approx([0.5, 0.5])
    assert result[1] == pytest.approx([0.25, 0.75])


# --- Подготовка данных ---

def test_split_keeps_windows_of_a_clip_together_and_class_shares():
    data = make_set([ANGER, NEUTRAL], per_class=40, seed=0, windows=3)
    train, val = split_by_clip(data, 0.25, seed=0)
    assert not set(train["clips"]) & set(val["clips"])
    assert len(train["y"]) + len(val["y"]) == len(data["y"])
    assert np.bincount(val["y"], minlength=7)[[ANGER, NEUTRAL]].tolist() == [30, 30]
    other_train, _ = split_by_clip(data, 0.25, seed=1)
    assert set(other_train["clips"]) != set(train["clips"])


def test_sample_weights_balance_classes_and_datasets():
    dusha = {"y": np.array([NEUTRAL] * 90 + [ANGER] * 10)}
    resd = {"y": np.array([FEAR] * 5 + [DISGUST] * 5)}
    weights = sample_weights({"dusha": dusha, "resd": resd}, resd_share=0.3)
    assert weights.sum() == pytest.approx(1.0)
    assert weights[100:].sum() == pytest.approx(0.3)
    assert weights[:90].sum() == pytest.approx(weights[90:100].sum())   # нейтральная не давит редкую злость
    assert sample_weights({"dusha": dusha}, 0.3).sum() == pytest.approx(1.0)


# --- Обучение ---

def test_head_learns_separable_classes():
    train = make_set([ANGER, HAPPY, NEUTRAL, SAD], per_class=60, seed=1)
    val = make_set([ANGER, HAPPY, NEUTRAL, SAD], per_class=20, seed=2)
    head, config, history = train_head({"dusha": train}, {"dusha": val}, epochs=40, lr=1e-2, batch_size=32, hidden=16,
                                       device="cpu", log=lambda _: None)
    assert history[-1]["dusha"] > 0.95
    assert config["n_layers"] == LAYERS and config["layer_start"] == 0
    # Сигнал лежит в последнем слое, и обученные веса слоёв это отражают.
    assert int(head.layer_weights().argmax()) == LAYERS - 1


def test_last_layer_variant_uses_single_layer():
    train = make_set([ANGER, NEUTRAL], per_class=40, seed=1)
    head, config, _ = train_head({"dusha": train}, {"dusha": train}, layers="last", hidden=0, epochs=3, batch_size=16,
                                 device="cpu", log=lambda _: None)
    assert config["n_layers"] == 1 and config["layer_start"] == LAYERS - 1
    assert predict(head, train["x"], "cpu").shape == (80, len(EMOTIONS))


def test_joint_training_keeps_emotions_missing_from_dusha():
    """Причина обучать на двух датасетах сразу: без RESD модель перестаёт узнавать страх и отвращение."""
    dusha = make_set([ANGER, HAPPY, NEUTRAL, SAD], per_class=80, seed=1)
    resd = make_set(list(range(len(EMOTIONS))), per_class=15, seed=2)
    resd_val = make_set(list(range(len(EMOTIONS))), per_class=15, seed=3)
    quiet = dict(epochs=40, lr=1e-2, batch_size=32, hidden=16, device="cpu", log=lambda _: None)

    dusha_val = make_set([ANGER, HAPPY, NEUTRAL, SAD], per_class=20, seed=4)
    val = {"dusha": dusha_val, "resd": resd_val}
    alone, _, _ = train_head({"dusha": dusha}, val, **quiet)
    joint, _, _ = train_head({"dusha": dusha, "resd": resd}, val, **quiet)

    def recall(head, label):
        mask = resd_val["y"] == label
        return float((predict(head, resd_val["x"][mask], "cpu").argmax(1) == label).mean())

    assert recall(alone, FEAR) < 0.1 and recall(alone, DISGUST) < 0.1
    assert recall(joint, FEAR) > 0.6 and recall(joint, DISGUST) > 0.6


def test_best_epoch_weights_are_restored():
    train = make_set([ANGER, NEUTRAL], per_class=30, seed=1)
    head, _, history = train_head({"dusha": train}, {"dusha": train}, epochs=4, batch_size=16, hidden=8,
                                  device="cpu", log=lambda _: None)
    best = max(h["mean"] for h in history)
    y_true, y_pred = clip_predictions(predict(head, train["x"], "cpu"), train["clips"], train["y"])
    assert report(y_true, y_pred, EMOTIONS)["macro_f1"] == pytest.approx(best, abs=1e-4)


def test_training_is_reproducible_for_a_seed():
    train = make_set([ANGER, NEUTRAL, SAD], per_class=30, seed=1)
    kwargs = dict(epochs=3, batch_size=16, hidden=8, device="cpu", log=lambda _: None)
    first, _, _ = train_head({"dusha": train}, {"dusha": train}, seed=5, **kwargs)
    second, _, _ = train_head({"dusha": train}, {"dusha": train}, seed=5, **kwargs)
    assert np.allclose(predict(first, train["x"], "cpu"), predict(second, train["x"], "cpu"))


def test_head_save_and_load_round_trip(tmp_path):
    train = make_set([ANGER, NEUTRAL], per_class=20, seed=1)
    head, config, _ = train_head({"dusha": train}, {"dusha": train}, epochs=2, batch_size=16, hidden=8,
                                 device="cpu", log=lambda _: None)
    path = tmp_path / "head.pt"
    save_head(head, path, config, {"labels": EMOTIONS, "preprocess": "raw"})
    loaded, meta = load_head(path)
    assert meta == {"labels": EMOTIONS, "preprocess": "raw"}
    assert np.allclose(predict(head, train["x"], "cpu"), predict(loaded, train["x"], "cpu"), atol=1e-6)


def test_head_ignores_scale_of_layers():
    """Признаки разных слоёв отличаются масштабом на порядки; нормировка внутри головы это снимает."""
    head = build_head(n_layers=2, dim=4, hidden=0, n_classes=3, dropout=0.0)
    head.eval()
    features = torch.randn(5, 2, 4)
    scale = torch.tensor([1.0, 500.0])[None, :, None]
    head.std.copy_(torch.ones(2, 4))
    plain = head(features)
    head.std.copy_(torch.ones(2, 4) * scale[0])
    assert torch.allclose(head(features * scale), plain, atol=1e-4)


def test_best_epoch_is_chosen_on_dusha_validation():
    """Проверочная часть RESD не участвует в выборе эпохи: кодировщик видел эти записи при своём обучении."""
    train = make_set([ANGER, NEUTRAL], per_class=40, seed=1)
    val = {"dusha": make_set([ANGER, NEUTRAL], per_class=20, seed=2), "resd": make_set([FEAR, DISGUST], per_class=20, seed=3)}
    _, _, history = train_head({"dusha": train}, val, epochs=5, batch_size=16, hidden=8, device="cpu", log=lambda _: None)
    assert all(h["mean"] == pytest.approx(h["dusha"], abs=1e-4) for h in history)
    _, _, history = train_head({"dusha": train}, val, epochs=2, batch_size=16, hidden=8, device="cpu", select_on="all",
                               log=lambda _: None)
    assert all(h["mean"] == pytest.approx((h["dusha"] + h["resd"]) / 2, abs=1e-4) for h in history)


# --- Порог для отрицательных эмоций ---

def probs(**values):
    row = np.zeros(len(EMOTIONS))
    for name, value in values.items():
        row[EMOTIONS.index(name)] = value
    return row


def test_decide_without_threshold_is_argmax():
    assert decide(probs(sadness=0.45, neutral=0.40, happiness=0.15)) == SAD


def test_decide_demotes_unsure_negative_emotion():
    row = probs(sadness=0.45, neutral=0.40, happiness=0.15)
    assert decide(row, negative_threshold=0.5) == NEUTRAL
    assert decide(row, negative_threshold=0.4) == SAD
    # Уверенный отрицательный ответ и любой неотрицательный порог не трогает.
    assert decide(probs(anger=0.8, neutral=0.2), negative_threshold=0.6) == ANGER
    assert decide(probs(happiness=0.35, neutral=0.33, fear=0.32), negative_threshold=0.9) == HAPPY


def test_threshold_curve_trades_false_alarms_for_recall():
    # Три нейтральные записи, две из которых модель неуверенно называет грустью, и одна настоящая грусть.
    pooled = np.stack([
        probs(sadness=0.45, neutral=0.40, happiness=0.15),
        probs(sadness=0.50, neutral=0.45, happiness=0.05),
        probs(neutral=0.9, sadness=0.1),
        probs(sadness=0.7, neutral=0.3),
    ])
    y_true = [NEUTRAL, NEUTRAL, NEUTRAL, SAD]
    curve = threshold_curve(y_true, pooled, EMOTIONS, thresholds=[0.0, 0.48, 0.6, 0.8])
    assert [row["neutral_false_alarm"] for row in curve] == [pytest.approx(0.6667, abs=1e-4), pytest.approx(0.3333, abs=1e-4), 0.0, 0.0]
    assert [row["accuracy"] for row in curve] == [0.5, 0.75, 1.0, 0.75]      # слишком высокий порог теряет и настоящую грусть
    assert pick_threshold(curve, max_false_alarm=0.1) == 0.6
    assert pick_threshold(curve, max_false_alarm=0.5) == 0.48


def test_clip_probabilities_average_windows():
    y_true, pooled = clip_probabilities(np.array([[1.0, 0.0], [0.0, 1.0], [0.2, 0.8]]), np.array([5, 5, 9]), np.array([0, 0, 1]))
    assert y_true == [0, 1]
    assert pooled.tolist() == [[0.5, 0.5], [0.2, 0.8]]
