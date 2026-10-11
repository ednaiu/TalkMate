import pytest

pytest.importorskip("jiwer")
pytest.importorskip("num2words")

import numpy as np

from training.asr_benchmark import evaluate, filler_counts, normalize_text

from .conftest import SR


def test_normalize_text_strips_case_and_punctuation():
    assert normalize_text("Ну, вот: «Ёжик» — это всё-таки ёж!") == "ну вот ежик это все таки еж"


def test_normalize_text_spells_numbers():
    # Часть моделей пишет числа цифрами, эталон словами: без этого им засчитывалась бы ошибка.
    assert normalize_text("в 22 раза") == normalize_text("в двадцать два раза") == "в двадцать два раза"
    assert normalize_text("2024год") == "две тысячи двадцать четыре год"


def test_filler_counts_match_by_word_and_multiplicity():
    reference = "ну вот это как бы работает ну"
    assert filler_counts(reference, "ну вот это как бы работает ну") == (4, 4, 4)
    assert filler_counts(reference, "вот это работает ну") == (4, 2, 2)          # модель «причесала» речь
    assert filler_counts(reference, "ну ну ну ну типа это работает") == (4, 2, 5)  # лишние заполнители не засчитываются
    assert filler_counts("это работает", "это работает") == (0, 0, 0)


def test_evaluate_computes_app_metrics():
    items = [
        (np.zeros(SR * 6, dtype=np.float32), "ну вот мы начали работу"),
        (np.zeros(SR * 4, dtype=np.float32), "это короче просто"),
    ]
    replies = iter(["Вот мы начали работу.", "это короче просто"])
    metrics, pairs = evaluate(lambda samples: next(replies), items)
    assert metrics["n"] == 2 and metrics["audio_minutes"] == 0.2
    assert metrics["wer"] == pytest.approx(1 / 8)                 # одно пропущенное слово из восьми
    assert metrics["word_count_error"] == pytest.approx((1 / 5 + 0) / 2)
    assert metrics["fillers_in_reference"] == 3
    assert metrics["filler_recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["filler_precision"] == 1.0
    assert pairs[0] == ("ну вот мы начали работу", "вот мы начали работу")
    assert metrics["sound_recall"] is None


def test_evaluate_tracks_hesitation_sounds_separately():
    items = [(np.zeros(SR * 3, dtype=np.float32), "выгоднее будет э-э сделать ну так"), (np.zeros(SR * 3, dtype=np.float32), "мм да")]
    replies = iter(["Выгоднее будет э-э сделать, ну так.", "да"])
    metrics, _ = evaluate(lambda samples: next(replies), items)
    assert metrics["sounds_in_reference"] == 2 and metrics["sound_recall"] == 0.5
    assert metrics["fillers_in_reference"] == 3 and metrics["filler_recall"] == pytest.approx(2 / 3, abs=1e-4)


def test_hyphens_do_not_count_as_word_errors():
    metrics, _ = evaluate(lambda samples: "все таки пришел", [(np.zeros(SR, dtype=np.float32), "все-таки пришел")])
    assert metrics["wer"] == 0.0


def test_evaluate_without_fillers_reports_none():
    metrics, _ = evaluate(lambda samples: "добрый день", [(np.zeros(SR, dtype=np.float32), "добрый день")])
    assert metrics["wer"] == 0.0 and metrics["filler_recall"] is None and metrics["filler_precision"] is None
