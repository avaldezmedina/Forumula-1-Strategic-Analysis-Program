from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.base import get_db
from app.db import models

router = APIRouter(prefix="/strategy", tags=["strategy"])


# =============================================================================
# Response schemas
# These schemas expose values that exist in the current precomputed tables.
# The API layer does not run strategy calculations on demand.
# =============================================================================

class StintAnalysis(BaseModel):
    stint_number: int
    compound: str
    lap_start: int
    lap_end: int
    clean_lap_count: int
    avg_clean_lap_time_seconds: float
    degradation_seconds_per_lap: float


class PaceAnalysis(BaseModel):
    current_avg_clean_lap_time_seconds: Optional[float]
    current_degradation_seconds_per_lap: float
    current_tyre_age_laps: int
    expected_laps_before_significant_deg: float
    estimated_laps_remaining: float
    tire_life_ratio: float

    # V1 does not have a defensible model for projected new-tire pace yet.
    projected_new_tire_pace: Optional[float] = None


class StrategyRecommendation(BaseModel):
    session_key: int
    year: int
    driver_number: int
    lap_number: int
    driver: str
    race: str
    recommendation: str
    current_stint: StintAnalysis
    analysis: PaceAnalysis


# =============================================================================
# Helpers
# =============================================================================

def _to_float(value):
    """
    Convert SQLAlchemy Numeric / Decimal values to float for API responses.
    Preserve None for nullable numeric fields.
    """
    if value is None:
        return None
    return float(value)


def _driver_name(driver: models.Driver, driver_number: int) -> str:
    if driver is None:
        return f"Driver {driver_number}"

    first_name = driver.first_name or ""
    last_name = driver.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    return full_name or f"Driver {driver_number}"


def _race_name(session_obj: models.Session, meeting: models.Meeting, session_key: int) -> str:
    if meeting and meeting.meeting_name and session_obj and session_obj.session_type:
        return f"{meeting.meeting_name} - {session_obj.session_type}"

    if meeting and meeting.meeting_name:
        return meeting.meeting_name

    if session_obj and session_obj.session_type:
        return f"Session {session_key} - {session_obj.session_type}"

    return f"Session {session_key}"


def _build_stint_analysis(summary: models.StintPaceSummary) -> StintAnalysis:
    return StintAnalysis(
        stint_number=summary.stint_number,
        compound=summary.compound,
        lap_start=summary.lap_start,
        lap_end=summary.lap_end,
        clean_lap_count=summary.clean_lap_count,
        avg_clean_lap_time_seconds=_to_float(summary.avg_clean_lap_time_seconds),
        degradation_seconds_per_lap=_to_float(summary.degradation_seconds_per_lap),
    )


# =============================================================================
# Routes
# =============================================================================

@router.get("/recommendation", response_model=StrategyRecommendation)
def get_recommendation(
    driver_number: int,
    session_key: int,
    lap_number: int,
    db: Session = Depends(get_db),
):
    """
    Return the precomputed pit-window recommendation for a driver at a lap.

    This endpoint only reads persisted strategy outputs. It does not compute
    pit-window scores, tire-life estimates, or stint summaries on demand.
    """
    score = (
        db.query(models.PitWindowScore)
        .filter(
            models.PitWindowScore.session_key == session_key,
            models.PitWindowScore.driver_number == driver_number,
            models.PitWindowScore.lap_number == lap_number,
        )
        .first()
    )

    if score is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No precomputed pit-window recommendation found for "
                f"session_key={session_key}, driver_number={driver_number}, "
                f"lap_number={lap_number}. Run the pit-window scoring pipeline "
                "for this session first, or verify that this lap was eligible for scoring."
            ),
        )

    stint_summary = (
        db.query(models.StintPaceSummary)
        .filter(
            models.StintPaceSummary.session_key == score.session_key,
            models.StintPaceSummary.driver_number == score.driver_number,
            models.StintPaceSummary.stint_number == score.stint_number,
        )
        .first()
    )

    if stint_summary is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Pit-window score exists, but the matching stint pace summary "
                f"was not found for session_key={score.session_key}, "
                f"driver_number={score.driver_number}, "
                f"stint_number={score.stint_number}."
            ),
        )

    driver = (
        db.query(models.Driver)
        .filter(
            models.Driver.year == score.year,
            models.Driver.driver_number == score.driver_number,
        )
        .first()
    )

    session_obj = (
        db.query(models.Session)
        .filter(models.Session.session_key == score.session_key)
        .first()
    )

    meeting = None
    if session_obj is not None:
        meeting = (
            db.query(models.Meeting)
            .filter(models.Meeting.meeting_key == session_obj.meeting_key)
            .first()
        )

    expected_life = _to_float(score.expected_laps_before_significant_deg)
    current_age = score.current_tyre_age_laps

    tire_life_ratio = 0.0
    if expected_life and expected_life > 0:
        tire_life_ratio = current_age / expected_life

    return StrategyRecommendation(
        session_key=score.session_key,
        year=score.year,
        driver_number=score.driver_number,
        lap_number=score.lap_number,
        driver=_driver_name(driver, score.driver_number),
        race=_race_name(session_obj, meeting, score.session_key),
        recommendation=score.recommendation,
        current_stint=_build_stint_analysis(stint_summary),
        analysis=PaceAnalysis(
            current_avg_clean_lap_time_seconds=_to_float(
                score.current_avg_clean_lap_time_seconds
            ),
            current_degradation_seconds_per_lap=_to_float(
                score.current_degradation_seconds_per_lap
            ),
            current_tyre_age_laps=score.current_tyre_age_laps,
            expected_laps_before_significant_deg=expected_life,
            estimated_laps_remaining=_to_float(score.estimated_laps_remaining),
            tire_life_ratio=tire_life_ratio,
            projected_new_tire_pace=None,
        ),
    )


@router.get(
    "/stint-summary/{session_key}/{driver_number}",
    response_model=list[StintAnalysis],
)
def get_stint_summary(
    session_key: int,
    driver_number: int,
    db: Session = Depends(get_db),
):
    """
    Return all precomputed stint pace summaries for a driver in a session.
    """
    summaries = (
        db.query(models.StintPaceSummary)
        .filter(
            models.StintPaceSummary.session_key == session_key,
            models.StintPaceSummary.driver_number == driver_number,
        )
        .order_by(models.StintPaceSummary.stint_number)
        .all()
    )

    if not summaries:
        raise HTTPException(
            status_code=404,
            detail=(
                "No precomputed stint summaries found for "
                f"session_key={session_key}, driver_number={driver_number}. "
                "Run the stint pace computation pipeline for this session first, "
                "or verify that the driver has eligible stints."
            ),
        )

    return [_build_stint_analysis(summary) for summary in summaries]