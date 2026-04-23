from __future__ import annotations
from datetime import datetime, timezone
from statistics import mean
import numpy as np
from sqlalchemy.orm import Session
from app.db import models


FLAG_EXCLUSION_SET = {"YELLOW", "RED", "SAFETY CAR", "SC", "VSC"}


def _get_stint_or_raise(
    db: Session,
    session_key: int,
    driver_number: int,
    stint_number: int,
) -> models.Stint:
    stint = (
        db.query(models.Stint)
        .filter(
            models.Stint.session_key == session_key,
            models.Stint.driver_number == driver_number,
            models.Stint.stint_number == stint_number,
        )
        .one_or_none()
    )

    if stint is None:
        raise ValueError(
            f"Stint not found for session_key={session_key}, "
            f"driver_number={driver_number}, stint_number={stint_number}"
        )

    return stint


def _get_flagged_lap_numbers(db: Session, session_key: int) -> set[int]:
    """
    Return lap numbers in this session that were affected by relevant flag events.

    V1 behavior is intentionally conservative:
    if a relevant flag event occurred on a lap, exclude that whole lap.
    """
    rows = (
        db.query(models.RaceControl.lap_number, models.RaceControl.flag)
        .filter(
            models.RaceControl.session_key == session_key,
            models.RaceControl.category == "Flag",
            models.RaceControl.lap_number.isnot(None),
            models.RaceControl.flag.isnot(None),
        )
        .all()
    )

    flagged_laps: set[int] = set()

    for lap_number, flag in rows:
        if flag and flag.upper() in FLAG_EXCLUSION_SET:
            flagged_laps.add(lap_number)

    return flagged_laps


def get_clean_laps(
    db: Session,
    session_key: int,
    driver_number: int,
    stint_number: int,
) -> list[models.Lap]:
    """
    Query laps for a driver's stint and filter to clean laps only.

    V1 clean-lap rules:
    - Exclude laps with null lap_duration
    - Exclude pit-out laps
    - Exclude the first 3 laps of a stint (warm-up laps)
    - Exclude any lap whose lap_number appears in race_control with
      a relevant flag state

    Notes:
    - This version uses lap-number-based flag filtering, not timestamp overlap.
    - Pit-in lap exclusion is intentionally omitted for now because we do not
      yet have a reliable pit-in signal in the current data model.
    """
    stint = _get_stint_or_raise(db, session_key, driver_number, stint_number)

    stint_start_lap = stint.lap_start
    stint_end_lap = stint.lap_end

    if stint_start_lap is None or stint_end_lap is None:
        raise ValueError(
            f"Stint boundaries missing for session_key={session_key}, "
            f"driver_number={driver_number}, stint_number={stint_number}"
        )

    flagged_lap_numbers = _get_flagged_lap_numbers(db, session_key)
    warmup_laps = {stint_start_lap, stint_start_lap + 1, stint_start_lap + 2}

    laps = (
        db.query(models.Lap)
        .filter(
            models.Lap.session_key == session_key,
            models.Lap.driver_number == driver_number,
            models.Lap.lap_number >= stint_start_lap,
            models.Lap.lap_number <= stint_end_lap,
        )
        .order_by(models.Lap.lap_number.asc())
        .all()
    )

    clean_laps: list[models.Lap] = []

    for lap in laps:
        if lap.lap_duration is None:
            continue

        if lap.is_pit_out_lap:
            continue

        if lap.lap_number in warmup_laps:
            continue

        if lap.lap_number in flagged_lap_numbers:
            continue

        clean_laps.append(lap)

    return clean_laps


def _compute_average_lap_time_seconds(clean_laps: list[models.Lap]) -> float:
    return float(mean(lap.lap_duration for lap in clean_laps))


def _compute_degradation_seconds_per_lap(clean_laps: list[models.Lap]) -> float:
    """
    Compute linear degradation as seconds per lap across clean laps.

    Requires at least 3 clean laps. Caller is expected to enforce that.
    """
    if len(clean_laps) < 3:
        raise ValueError("Need at least 3 clean laps to compute degradation")

    x = np.arange(len(clean_laps), dtype=float)
    y = np.array([lap.lap_duration for lap in clean_laps], dtype=float)

    slope, _intercept = np.polyfit(x, y, 1)
    return float(slope)


def compute_stint_pace_summary(
    db: Session,
    session_key: int,
    driver_number: int,
    stint_number: int,
) -> models.StintPaceSummary:
    """
    Compute/update the pace summary for a single stint.

    Important:
    - This function does NOT commit.
    - The caller owns the transaction boundary.

    Behavior:
    - Requires at least 3 clean laps
    - If insufficient clean laps exist, raises ValueError and does not persist
      a partial summary row
    """
    stint = _get_stint_or_raise(db, session_key, driver_number, stint_number)
    clean_laps = get_clean_laps(db, session_key, driver_number, stint_number)

    if len(clean_laps) < 3:
        raise ValueError(
            f"Not enough clean laps to compute pace summary for "
            f"session_key={session_key}, driver_number={driver_number}, "
            f"stint_number={stint_number}"
        )

    avg_clean_lap_time_seconds = _compute_average_lap_time_seconds(clean_laps)
    degradation_seconds_per_lap = _compute_degradation_seconds_per_lap(clean_laps)
    clean_lap_count = len(clean_laps)
    computed_at = datetime.now(timezone.utc)

    existing = (
        db.query(models.StintPaceSummary)
        .filter(
            models.StintPaceSummary.session_key == session_key,
            models.StintPaceSummary.driver_number == driver_number,
            models.StintPaceSummary.stint_number == stint_number,
        )
        .one_or_none()
    )

    if existing is None:
        summary = models.StintPaceSummary(
            session_key=session_key,
            year=stint.year,
            driver_number=driver_number,
            stint_number=stint_number,
            compound=stint.compound,
            lap_start=stint.lap_start,
            lap_end=stint.lap_end,
            clean_lap_count=clean_lap_count,
            avg_clean_lap_time_seconds=avg_clean_lap_time_seconds,
            degradation_seconds_per_lap=degradation_seconds_per_lap,
            computed_at=computed_at,
        )
        db.add(summary)
        return summary

    existing.year = stint.year
    existing.compound = stint.compound
    existing.lap_start = stint.lap_start
    existing.lap_end = stint.lap_end
    existing.clean_lap_count = clean_lap_count
    existing.avg_clean_lap_time_seconds = avg_clean_lap_time_seconds
    existing.degradation_seconds_per_lap = degradation_seconds_per_lap
    existing.computed_at = computed_at
    return existing


def compute_all_stint_summaries(db: Session, session_key: int) -> None:
    """
    Compute pace summaries for all stints in a session.

    Uses the stints table as the source of truth.

    Transaction boundary:
    - process all stints
    - commit once at the end
    - rollback on unexpected failure
    """
    stints = (
        db.query(models.Stint)
        .filter(models.Stint.session_key == session_key)
        .order_by(models.Stint.driver_number.asc(), models.Stint.stint_number.asc())
        .all()
    )

    try:
        for stint in stints:
            try:
                compute_stint_pace_summary(
                    db=db,
                    session_key=session_key,
                    driver_number=stint.driver_number,
                    stint_number=stint.stint_number,
                )
            except ValueError:
                # Expected insufficient-data / missing-data case.
                # Replace with structured logging later.
                continue

        db.commit()

    except Exception:
        db.rollback()
        raise
