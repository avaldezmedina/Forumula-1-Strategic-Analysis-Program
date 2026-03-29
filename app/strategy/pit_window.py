from sqlalchemy.orm import Session
from app.db import models


# =============================================================================
# Thresholds — adjust these as you validate against real race data
# These are intentionally configurable constants, not magic numbers buried
# in logic. If you need to change them, change them here in one place.
# =============================================================================

# Pace delta thresholds relative to driver's own stint baseline (in seconds)
PACE_DELTA_PIT_SOON = 1.0   # more than 1s off baseline -> PIT_SOON
PACE_DELTA_PIT_NOW = 2.0    # more than 2s off baseline -> PIT_NOW

# Tire age ratio thresholds (current_age / expected_life)
TIRE_AGE_RATIO_PIT_SOON = 0.75   # 75% of expected life used -> PIT_SOON
TIRE_AGE_RATIO_PIT_NOW = 0.90    # 90% of expected life used -> PIT_NOW


def score_pit_window(
    current_tyre_age: int,
    expected_tire_life: float,
    current_avg_lap: float,
    baseline_avg_lap: float,
    degradation_rate: float,
) -> str:
    """
    Core scoring logic. Returns 'EXTEND', 'PIT_SOON', or 'PIT_NOW'.

    Decision matrix:
    - If tire age ratio >= TIRE_AGE_RATIO_PIT_NOW -> PIT_NOW
    - If pace delta >= PACE_DELTA_PIT_NOW -> PIT_NOW
    - If tire age ratio >= TIRE_AGE_RATIO_PIT_SOON -> PIT_SOON
    - If pace delta >= PACE_DELTA_PIT_SOON -> PIT_SOON
    - Otherwise -> EXTEND

    TODO: Implement this function.
    This is pure logic with no database access — it takes numbers and
    returns a string. This makes it very easy to unit test.
    Write this first, then write the tests before anything else.

    Think about: the pace delta should be relative to the circuit baseline,
    not an absolute number. How do you calculate pace delta correctly?
    Hint: delta = current_avg_lap - baseline_avg_lap
    A positive delta means the driver is slower than baseline.
    """
    raise NotImplementedError


def compute_pit_window_scores_for_session(db: Session, session_key: int) -> None:
    """
    Compute pit window scores for every driver at every lap in a session.
    Writes results to the pit_window_scores table.

    TODO: Implement this function. It should:
    1. Fetch all stints for this session
    2. For each stint, fetch the corresponding StintPaceSummary
    3. Fetch the TireLifeEstimate for this circuit and compound
    4. For each lap in the stint, call score_pit_window()
    5. Persist a PitWindowScore record for each lap

    Think about: what do you do if no TireLifeEstimate exists for
    this compound at this circuit? (it's a new circuit, or missing data)
    You need a fallback strategy. What is it?
    """
    raise NotImplementedError
