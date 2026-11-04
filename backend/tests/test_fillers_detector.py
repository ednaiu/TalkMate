"""Части детектора звуков-пауз и английского замера, которые не требуют моделей."""
import numpy as np

from speech_analysis.audio import SAMPLE_RATE
from training.en_asr_benchmark import fillers_en, matched, normalize_en, repetitions
from training.fillers_detector import (balance, context_window, frame_range, match_episodes, merge_detections, metrics,
                                       pick_threshold, pool_frames, read_annotations, window_starts)

CSV = """clip_name,pfID,fullvoc_label,consolidated_label,episode_split_subset,clip_split_subset,podcast_filename,event_start_inepisode,event_end_inepisode,event_start_inclip,event_end_inclip,clip_start_inepisode,clip_end_inepisode,duration,confidence,agreement
1.wav,1,Uh,Uh,train,train,show_ep1,10.4,10.6,0.4,0.6,10.0,11.0,0.2,1,3
2.wav,2,Words,Words,train,train,show_ep1,20.4,20.6,0.4,0.6,20.0,21.0,0.2,1,3
3.wav,3,Breath,Breath,train,train,show_ep1,30.4,30.6,0.4,0.6,30.0,31.0,0.2,1,3
4.wav,4,Um,Um,test,test,show_ep2,5.4,5.6,0.4,0.6,5.0,6.0,0.2,1,3
5.wav,5,Cough,None,train,extra,show_ep1,40.4,40.6,0.4,0.6,40.0,41.0,0.2,1,3
"""


def test_annotations_are_read_by_split_without_unknown_labels(tmp_path):
    path = tmp_path / "pf.csv"
    path.write_text(CSV, encoding="utf-8")
    assert read_annotations(path, "train") == {"show_ep1": [(10.0, "Uh"), (20.0, "Words"), (30.0, "Breath")]}
    assert read_annotations(path, "test") == {"show_ep2": [(5.0, "Um")]}
    path.write_text(CSV.replace(",Uh,train,", ",uh,TRAIN,"), encoding="utf-8")
    assert read_annotations(path, "train")["show_ep1"][0] == (10.0, "Uh")


def test_balance_keeps_all_fillers_and_limits_others():
    events = {"a": [(1.0, "Uh"), (2.0, "Words"), (3.0, "Words"), (4.0, "Breath")], "b": [(1.0, "Um")]}
    kept = balance(events, negatives_per_filler=1.0)
    labels = [label for items in kept.values() for _, label in items]
    assert labels.count("Uh") + labels.count("Um") == 2 and len(labels) == 4


def test_episodes_match_audio_files_by_name():
    files = ["data/train/show_ep1.mp3", "data/test/Free Podcast Day_Home Grown Girls – Apr 7 2018.mp3", "README.md"]
    names = ["show_ep1", "free podcast day_home grown girls - apr 7 2018.mp3", "show_ep3"]
    assert match_episodes(names, files) == {
        "show_ep1": "data/train/show_ep1.mp3",
        "free podcast day_home grown girls - apr 7 2018.mp3": "data/test/Free Podcast Day_Home Grown Girls – Apr 7 2018.mp3"}


def test_empty_split_explains_what_is_in_the_file(tmp_path):
    import pytest

    path = tmp_path / "pf.csv"
    path.write_text(CSV, encoding="utf-8")
    with pytest.raises(ValueError, match="разбиения"):
        read_annotations(path, "validation")


def test_context_window_keeps_the_clip_position_near_edges():
    samples = np.zeros(10 * SAMPLE_RATE, dtype=np.float32)
    piece, start, end = context_window(samples, 0.5)
    assert len(piece) == int(3.0 * SAMPLE_RATE) and (start, end) == (0.5, 1.5)
    piece, start, end = context_window(samples, 4.0)
    assert len(piece) == int(4.0 * SAMPLE_RATE) and (start, end) == (1.5, 2.5)


def test_frames_of_the_central_second_are_pooled():
    assert frame_range(1.5, 2.5, 200) == (75, 125)
    assert frame_range(9.8, 10.8, 500) == (490, 500)
    states = np.zeros((3, 200, 4), dtype=np.float32)
    states[:, 75:125, :] = 2.0
    feature = pool_frames(states, 75, 125)
    assert feature.shape == (3, 8) and np.allclose(feature[:, :4], 2.0) and np.allclose(feature[:, 4:], 1e-4)


def test_windows_cover_the_whole_recording_and_merge_into_events():
    assert window_starts(0.6) == [0.0]
    starts = window_starts(2.1, hop=0.5)
    assert starts == [0.0, 0.5, 1.0, 1.1]
    events = merge_detections([0.0, 0.25, 0.5, 2.0], [0.9, 0.8, 0.2, 0.95], threshold=0.5)
    assert events == [(0.0, 1.25, 0.9), (2.0, 3.0, 0.95)]


def test_threshold_prefers_precision_and_metrics_are_correct():
    y = [1, 1, 1, 0, 0, 0]
    scores = [0.9, 0.8, 0.3, 0.7, 0.2, 0.1]
    assert metrics(y, scores, 0.5) == {"threshold": 0.5, "precision": 0.6667, "recall": 0.6667, "f1": 0.6667}
    chosen = pick_threshold(y, scores, min_precision=0.9)
    assert chosen["precision"] == 1.0 and chosen["recall"] == 0.6667


def test_english_benchmark_counts_sounds_phrases_and_repetitions():
    reference = normalize_en("OH UM I DON'T KNOW, YOU KNOW, ON ON")
    assert reference == "oh um i don't know you know on on"
    assert fillers_en(reference) == ["um", "you know"]
    assert matched(reference, "oh i don't know you know", ("um", "uh")) == (1, 0, 0)
    assert matched(reference, "oh i don't know you know", ("you know",)) == (1, 1, 1)
    assert repetitions(reference) == 1
