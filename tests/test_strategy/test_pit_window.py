import pytest

from app.strategy.pit_window import (
    PACE_DELTA_PIT_NOW,
    PACE_DELTA_PIT_SOON,
    TIRE_AGE_RATIO_PIT_NOW,
    TIRE_AGE_RATIO_PIT_SOON,
    score_pit_window,
)


def test_score_pit_window_returns_extend():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=98.4,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "EXTEND"


def test_score_pit_window_returns_pit_soon_via_tire_age():
    expected_life = 20.0
    current_tyre_age = int(expected_life * TIRE_AGE_RATIO_PIT_SOON)

    result = score_pit_window(
        current_tyre_age=current_tyre_age,
        expected_tire_life=expected_life,
        current_avg_lap=98.4,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_SOON"


def test_score_pit_window_returns_pit_soon_via_pace_delta():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=99.0,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_SOON"


def test_score_pit_window_returns_pit_now_via_tire_age():
    expected_life = 20.0
    current_tyre_age = int(expected_life * TIRE_AGE_RATIO_PIT_NOW)

    result = score_pit_window(
        current_tyre_age=current_tyre_age,
        expected_tire_life=expected_life,
        current_avg_lap=98.4,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_NOW"


def test_score_pit_window_returns_pit_now_via_pace_delta():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=100.0,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_NOW"


def test_score_pit_window_exact_tire_age_pit_soon_threshold():
    expected_life = 20.0
    current_tyre_age = expected_life * TIRE_AGE_RATIO_PIT_SOON

    result = score_pit_window(
        current_tyre_age=current_tyre_age,
        expected_tire_life=expected_life,
        current_avg_lap=98.2,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_SOON"


def test_score_pit_window_exact_tire_age_pit_now_threshold():
    expected_life = 20.0
    current_tyre_age = expected_life * TIRE_AGE_RATIO_PIT_NOW

    result = score_pit_window(
        current_tyre_age=current_tyre_age,
        expected_tire_life=expected_life,
        current_avg_lap=98.2,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_NOW"


def test_score_pit_window_exact_pace_delta_pit_soon_threshold():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=98.0 + PACE_DELTA_PIT_SOON,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_SOON"


def test_score_pit_window_exact_pace_delta_pit_now_threshold():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=98.0 + PACE_DELTA_PIT_NOW,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_NOW"


def test_score_pit_window_pit_now_takes_priority_over_pit_soon():
    result = score_pit_window(
        current_tyre_age=18,  # 18 / 20 = 0.9 -> PIT_NOW
        expected_tire_life=20.0,
        current_avg_lap=99.0,  # would only be PIT_SOON on pace alone
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "PIT_NOW"


def test_score_pit_window_negative_pace_delta_still_extends():
    result = score_pit_window(
        current_tyre_age=5,
        expected_tire_life=20.0,
        current_avg_lap=97.7,
        baseline_avg_lap=98.0,
        degradation_rate=0.15,
    )
    assert result == "EXTEND"


def test_score_pit_window_raises_for_non_positive_expected_tire_life():
    with pytest.raises(ValueError, match="expected_tire_life must be > 0"):
        score_pit_window(
            current_tyre_age=5,
            expected_tire_life=0,
            current_avg_lap=98.5,
            baseline_avg_lap=98.0,
            degradation_rate=0.15,
        )