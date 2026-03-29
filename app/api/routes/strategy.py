from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db import models
from pydantic import BaseModel

router = APIRouter(prefix="/strategy", tags=["strategy"])


# =============================================================================
# Response schemas
# These define the shape of data your API returns.
# Pydantic validates the output automatically.
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
    raw_pace: float
    delta_from_baseline: float
    expected_drop_off: float
    projected_new_tire_pace: float
    expected_tire_life: float


class StrategyRecommendation(BaseModel):
    driver: str
    race: str
    recommendation: str
    current_stint: StintAnalysis
    analysis: PaceAnalysis


# =============================================================================
# Routes
# =============================================================================

@router.get("/recommendation", response_model=StrategyRecommendation)
def get_recommendation(
    driver_number: int,
    session_key: int,
    lap_number: int,
    db: Session = Depends(get_db)
):
    """
    Return the pit window recommendation for a driver at a specific lap.

    TODO: Implement this endpoint. It should:
    1. Look up the PitWindowScore for this (session_key, driver_number, lap_number)
    2. If not found, raise HTTPException(status_code=404)
    3. Look up the StintPaceSummary for the current stint
    4. Look up the driver name from the drivers table
    5. Look up the meeting name from sessions -> meetings
    6. Assemble and return a StrategyRecommendation

    This endpoint reads precomputed data only — it does NOT run
    calculations on the fly. That already happened in the workers.
    """
    raise NotImplementedError


@router.get("/stint-summary/{session_key}/{driver_number}")
def get_stint_summary(
    session_key: int,
    driver_number: int,
    db: Session = Depends(get_db)
):
    """
    Return all stint pace summaries for a driver in a session.

    TODO: Implement this endpoint.
    Return a list of StintAnalysis objects, one per stint.
    """
    raise NotImplementedError
