import numpy as np

from speech_analysis import DEFAULT_THRESHOLDS as T
from speech_analysis.noise import classify_noise, estimate_snr_db
from talkmate.services.recommendation_service import build_recommendation, find_issues

from .conftest import SR, voice


def phrases_with_pauses(noise_amplitude, seed=0):
    """Четыре «фразы» по секунде с паузами по полсекунды и ровным фоновым шумом."""
    rng = np.random.default_rng(seed)
    pause = np.zeros(SR // 2, dtype=np.float32)
    speech = np.concatenate([np.concatenate([voice(duration=1.0, amplitude=0.3), pause]) for _ in range(4)])
    return (speech + rng.normal(0, noise_amplitude, len(speech))).astype(np.float32)


def test_quiet_room_is_clean():
    snr = estimate_snr_db(phrases_with_pauses(0.001))
    assert snr is not None and snr > 30
    assert classify_noise(snr, T) == "clean"


def test_loud_background_is_noisy():
    snr = estimate_snr_db(phrases_with_pauses(0.06))
    assert snr is not None and snr < T["noise_snr_min_db"]
    assert classify_noise(snr, T) == "noisy"


def test_steady_sound_without_pauses_is_undetermined():
    assert estimate_snr_db(voice(duration=4.0)) is None
    assert classify_noise(None, T) is None


def test_digital_silence_is_ignored():
    samples = np.concatenate([np.zeros(SR, dtype=np.float32), phrases_with_pauses(0.001)])
    assert estimate_snr_db(samples) > 30


def _result(**overrides):
    from speech_analysis import AnalysisResult

    base = dict(text="", duration=60, speech_rate=120, volume="normal", volume_db=-20, monotony="expressive",
                pitch_variability=3.0, num_fillers=0, fillers=[], top_fillers=[], emotion="neutral")
    base.update(overrides)
    return AnalysisResult(**base)


def test_noisy_recording_asks_for_quiet_instead_of_blaming_diction():
    result = _result(clarity=60.0, clarity_level="unclear", snr_db=9.0, noise_level="noisy")
    assert find_issues(result, T) == ["noisy"]
    _, text = build_recommendation(result, T)
    assert "тихом месте" in text and "9 дБ" in text and "чётче" not in text


def test_clean_recording_keeps_clarity_advice():
    result = _result(clarity=60.0, clarity_level="unclear", snr_db=35.0, noise_level="clean")
    assert find_issues(result, T) == ["unclear"]


def test_noise_threshold_is_validated(client, admin):
    assert client.put("/api/admin/thresholds", headers=admin, json={"noise_snr_min_db": 80}).status_code == 400
    assert client.put("/api/admin/thresholds", headers=admin, json={"noise_snr_min_db": 12}).status_code == 200
