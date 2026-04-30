from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from sqlalchemy.orm import Session

from app.db import models


MIN_SAMPLE_STINT_COUNT = 3
SHORT_STINT_FACTOR = 0.7


def _get_pace_summaries_for_circuit_compound(
    db: Session,
    circuit_key: int,
    compound: str,
) -> list[models.StintPaceSummary]:
    """
    Load all stint pace summaries for a given circuit and compound across
    all available historical sessions.

    Join path:
    stint_pace_summary -> sessions -> meetings -> circuit_key
    """
    return (
        db.query(models.StintPaceSummary)
        .join(
            models.Session,
            models.StintPaceSummary.session_key == models.Session.session_key,
        )
        .join(
            models.Meeting,
            models.Session.meeting_key == models.Meeting.meeting_key,
        )
        .filter(
            models.Meeting.circuit_key == circuit_key,
            models.StintPaceSummary.compound == compound,
        )
        .order_by(
            models.StintPaceSummary.session_key.asc(),
            models.StintPaceSummary.driver_number.asc(),
            models.StintPaceSummary.stint_number.asc(),
        )
        .all()
    )


def _get_stint_length(summary: models.StintPaceSummary) -> int:
    return summary.lap_end - summary.lap_start + 1


def _exclude_short_stints(
    summaries: list[models.StintPaceSummary],
) -> list[models.StintPaceSummary]:
    """
    Exclude stints that are significantly shorter than the baseline average.

    V1 heuristic:
    - compute the average stint length across all candidate summaries
    - exclude any stint with length < SHORT_STINT_FACTOR * average length

    This is a simple, explicit filter for likely strategy-distorted or
    neutralization-distorted short runs.
    """
    if not summaries:
        return []

    lengths = [_get_stint_length(summary) for summary in summaries]
    avg_length = mean(lengths)
    min_allowed_length = avg_length * SHORT_STINT_FACTOR

    return [
        summary
        for summary in summaries
        if _get_stint_length(summary) >= min_allowed_length
    ]


def compute_tire_life_estimate(
    db: Session,
    circuit_key: int,
    compound: str,
) -> models.TireLifeEstimate:
    """
    Compute expected tire life for a compound at a circuit using
    historical race stint data.

    Algorithm:
    1. Query all StintPaceSummary records for this circuit_key and compound
       across all historical sessions
    2. Exclude stints that ended early using a simple short-stint heuristic
    3. Calculate average laps per stint
    4. Calculate average degradation rate across retained stints
    5. Upsert and return a TireLifeEstimate record

    Important:
    - This function does NOT commit.
    - The caller owns the transaction boundary.
    - The caller must resolve circuit_key before invoking this function.

    Raises:
    - ValueError if there is insufficient retained sample data
    """
    summaries = _get_pace_summaries_for_circuit_compound(db, circuit_key, compound)

    if len(summaries) < MIN_SAMPLE_STINT_COUNT:
        raise ValueError(
            f"Not enough historical pace summaries for circuit_key={circuit_key}, "
            f"compound={compound}. Found {len(summaries)}, "
            f"need at least {MIN_SAMPLE_STINT_COUNT}."
        )

    filtered_summaries = _exclude_short_stints(summaries)

    if len(filtered_summaries) < MIN_SAMPLE_STINT_COUNT:
        raise ValueError(
            f"Not enough retained pace summaries after short-stint filtering for "
            f"circuit_key={circuit_key}, compound={compound}. "
            f"Found {len(filtered_summaries)}, need at least {MIN_SAMPLE_STINT_COUNT}."
        )

    expected_laps_before_significant_deg = float(
        mean(_get_stint_length(summary) for summary in filtered_summaries)
    )
    avg_degradation_seconds_per_lap = float(
        mean(summary.degradation_seconds_per_lap for summary in filtered_summaries)
    )
    sample_stint_count = len(filtered_summaries)

    # V1: leave avg_deg_onset_lap unset.
    # We do not yet have explicit logic for estimating the lap where degradation
    # meaningfully begins. That requires a more detailed per-stint shape analysis
    # rather than a simple aggregate over summary rows.
    avg_deg_onset_lap = None

    computed_at = datetime.now(timezone.utc)

    existing = (
        db.query(models.TireLifeEstimate)
        .filter(
            models.TireLifeEstimate.circuit_key == circuit_key,
            models.TireLifeEstimate.compound == compound,
        )
        .one_or_none()
    )

    if existing is None:
        estimate = models.TireLifeEstimate(
            circuit_key=circuit_key,
            compound=compound,
            expected_laps_before_significant_deg=expected_laps_before_significant_deg,
            avg_degradation_seconds_per_lap=avg_degradation_seconds_per_lap,
            avg_deg_onset_lap=avg_deg_onset_lap,
            sample_stint_count=sample_stint_count,
            computed_at=computed_at,
        )
        db.add(estimate)
        return estimate

    existing.expected_laps_before_significant_deg = expected_laps_before_significant_deg
    existing.avg_degradation_seconds_per_lap = avg_degradation_seconds_per_lap
    existing.avg_deg_onset_lap = avg_deg_onset_lap
    existing.sample_stint_count = sample_stint_count
    existing.computed_at = computed_at
    return existing


def get_tire_life_estimate(
    db: Session,
    circuit_key: int,
    compound: str,
) -> models.TireLifeEstimate | None:
    """
    Retrieve a precomputed tire life estimate.
    Returns None if no estimate exists for this circuit/compound combination.
    """
    return (
        db.query(models.TireLifeEstimate)
        .filter(
            models.TireLifeEstimate.circuit_key == circuit_key,
            models.TireLifeEstimate.compound == compound,
        )
        .one_or_none()
    )