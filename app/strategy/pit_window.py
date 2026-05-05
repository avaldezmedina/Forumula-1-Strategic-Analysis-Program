from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import models
from app.strategy.tire_life import get_tire_life_estimate


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

    Notes:
    - pace delta = current_avg_lap - baseline_avg_lap
    - positive delta means the driver is slower than baseline
    - degradation_rate is accepted as an input because later scoring versions
      may use it, but V1 does not need it directly
    """
    if expected_tire_life <= 0:
        raise ValueError("expected_tire_life must be > 0")

    tire_age_ratio = current_tyre_age / expected_tire_life
    pace_delta = current_avg_lap - baseline_avg_lap

    if tire_age_ratio >= TIRE_AGE_RATIO_PIT_NOW:
        return "PIT_NOW"

    if pace_delta >= PACE_DELTA_PIT_NOW:
        return "PIT_NOW"

    if tire_age_ratio >= TIRE_AGE_RATIO_PIT_SOON:
        return "PIT_SOON"

    if pace_delta >= PACE_DELTA_PIT_SOON:
        return "PIT_SOON"

    return "EXTEND"


def _get_circuit_key_for_session(db: Session, session_key: int) -> int:
    session_row = (
        db.query(models.Session)
        .filter(models.Session.session_key == session_key)
        .one_or_none()
    )
    if session_row is None:
        raise ValueError(f"Session not found for session_key={session_key}")

    meeting = (
        db.query(models.Meeting)
        .filter(models.Meeting.meeting_key == session_row.meeting_key)
        .one_or_none()
    )
    if meeting is None:
        raise ValueError(
            f"Meeting not found for meeting_key={session_row.meeting_key} "
            f"(session_key={session_key})"
        )
    if meeting.circuit_key is None:
        raise ValueError(
            f"Circuit key missing for meeting_key={meeting.meeting_key} "
            f"(session_key={session_key})"
        )

    return meeting.circuit_key


def compute_pit_window_scores_for_session(db: Session, session_key: int) -> None:
    """
    Compute pit window scores for every driver at every lap in a session.
    Writes results to the pit_window_scores table.

    Behavior:
    1. Fetch all stints for this session
    2. For each stint, fetch the corresponding StintPaceSummary
    3. Resolve the circuit_key for the session
    4. Fetch the TireLifeEstimate for this circuit and compound
    5. For each lap in the stint, compute current tyre age and call score_pit_window()
    6. Upsert a PitWindowScore record for each lap

    Fallback strategy:
    - If no StintPaceSummary exists for a stint, skip that stint
    - If no TireLifeEstimate exists for this circuit/compound, skip that stint

    Important:
    - This function does NOT commit.
    - The caller owns the transaction boundary.

    TODO: Exclude pit-out laps from pit-window scoring. Their lap times include
    pit-lane traversal / out-lap effects and can create false PIT_NOW signals.

    TODO: Replace single-lap pace delta with a rolling clean-lap average and
    compare it against an age-adjusted expected pace to reduce lap-to-lap noise.
    """
    circuit_key = _get_circuit_key_for_session(db, session_key)

    stints = (
        db.query(models.Stint)
        .filter(models.Stint.session_key == session_key)
        .order_by(models.Stint.driver_number.asc(), models.Stint.stint_number.asc())
        .all()
    )

    computed_at = datetime.now(timezone.utc)

    for stint in stints:
        pace_summary = (
            db.query(models.StintPaceSummary)
            .filter(
                models.StintPaceSummary.session_key == session_key,
                models.StintPaceSummary.driver_number == stint.driver_number,
                models.StintPaceSummary.stint_number == stint.stint_number,
            )
            .one_or_none()
        )

        if pace_summary is None:
            continue

        tire_life_estimate = get_tire_life_estimate(db, circuit_key, stint.compound)
        if tire_life_estimate is None:
            continue

        laps = (
            db.query(models.Lap)
            .filter(
                models.Lap.session_key == session_key,
                models.Lap.driver_number == stint.driver_number,
                models.Lap.lap_number >= stint.lap_start,
                models.Lap.lap_number <= stint.lap_end,
            )
            .order_by(models.Lap.lap_number.asc())
            .all()
        )

        tyre_age_at_start = stint.tyre_age_at_start or 0

        for lap in laps:
            if lap.lap_duration is None:
                continue

            laps_into_stint = lap.lap_number - stint.lap_start
            current_tyre_age = tyre_age_at_start + laps_into_stint

            expected_life = float(
                tire_life_estimate.expected_laps_before_significant_deg
            )

            recommendation = score_pit_window(
                current_tyre_age=current_tyre_age,
                expected_tire_life=expected_life,
                current_avg_lap=float(lap.lap_duration),
                baseline_avg_lap=float(pace_summary.avg_clean_lap_time_seconds),
                degradation_rate=float(pace_summary.degradation_seconds_per_lap),
            )

            estimated_laps_remaining = expected_life - current_tyre_age

            values = {
                "session_key": session_key,
                "year": stint.year,
                "driver_number": stint.driver_number,
                "lap_number": lap.lap_number,
                "stint_number": stint.stint_number,
                "compound": stint.compound,
                "current_tyre_age_laps": current_tyre_age,
                "current_avg_clean_lap_time_seconds": float(lap.lap_duration),
                "current_degradation_seconds_per_lap": (
                    pace_summary.degradation_seconds_per_lap
                ),
                "expected_laps_before_significant_deg": (
                    tire_life_estimate.expected_laps_before_significant_deg
                ),
                "estimated_laps_remaining": estimated_laps_remaining,
                "recommendation": recommendation,
                "computed_at": computed_at,
            }

            stmt = (
                insert(models.PitWindowScore)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[
                        "session_key",
                        "driver_number",
                        "lap_number",
                    ],
                    set_={
                        "year": values["year"],
                        "stint_number": values["stint_number"],
                        "compound": values["compound"],
                        "current_tyre_age_laps": values["current_tyre_age_laps"],
                        "current_avg_clean_lap_time_seconds": values[
                            "current_avg_clean_lap_time_seconds"
                        ],
                        "current_degradation_seconds_per_lap": values[
                            "current_degradation_seconds_per_lap"
                        ],
                        "expected_laps_before_significant_deg": values[
                            "expected_laps_before_significant_deg"
                        ],
                        "estimated_laps_remaining": values[
                            "estimated_laps_remaining"
                        ],
                        "recommendation": values["recommendation"],
                        "computed_at": values["computed_at"],
                    },
                )
            )

            db.execute(stmt)