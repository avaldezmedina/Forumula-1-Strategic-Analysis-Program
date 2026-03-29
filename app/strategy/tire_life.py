from sqlalchemy.orm import Session
from app.db import models


def compute_tire_life_estimate(db: Session, circuit_key: int, compound: str) -> models.TireLifeEstimate:
    """
    Compute expected tire life for a compound at a circuit using
    historical race stint data.

    Algorithm (implement this):
    1. Query all StintPaceSummary records for this circuit_key and compound
       across all historical sessions
    2. Exclude stints that ended early (lap_end - lap_start significantly
       less than average) — these likely ended due to safety car or strategy,
       not actual tire failure
    3. Calculate average laps per stint (this is your expected tire life)
    4. Calculate average degradation rate across those stints
    5. Persist and return a TireLifeEstimate record

    TODO: Implement this function.

    Think about: how many historical stints do you need before this estimate
    is meaningful? What do you do if sample_stint_count is very low (1 or 2)?
    Should you flag low-confidence estimates somehow?
    """
    raise NotImplementedError


def get_tire_life_estimate(db: Session, circuit_key: int, compound: str) -> models.TireLifeEstimate | None:
    """
    Retrieve a precomputed tire life estimate.
    Returns None if no estimate exists for this circuit/compound combination.

    TODO: Implement this simple query function.
    This is what the pit window scorer calls — it reads precomputed data,
    it does not recompute on the fly.
    """
    raise NotImplementedError
