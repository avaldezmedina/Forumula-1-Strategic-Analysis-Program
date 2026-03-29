from sqlalchemy.orm import Session
from app.db import models


def get_clean_laps(db: Session, session_key: int, driver_number: int, stint_number: int) -> list[models.Lap]:
    """
    Query laps for a driver's stint and filter to clean laps only.

    A clean lap excludes:
    - Pit in laps
    - Pit out laps (is_pit_out_lap = True)
    - The first 3 laps of a stint (warm-up laps)
    - Any lap where a yellow flag, red flag, or safety car was active
      (join with race_control to check this)

    TODO: Implement this function.
    Think about how to join laps with race_control to filter flag laps.
    This is a non-trivial SQL query — you need to check if any race
    control event with a flag was active during each lap's time window.
    Hint: laps have a lap_number, race_control has a lap_number.
    """
    raise NotImplementedError


def compute_stint_pace_summary(db: Session, session_key: int, driver_number: int, stint_number: int) -> models.StintPaceSummary:
    """
    Compute and persist the pace summary for a single stint.

    TODO: Implement this function. It should:
    1. Call get_clean_laps() to get filtered laps
    2. Calculate average clean lap time across those laps
    3. Calculate degradation rate (seconds per lap)
       Hint: fit a linear trend to the lap times — the slope is degradation.
       Look up numpy.polyfit for a simple linear regression approach.
    4. Create and persist a StintPaceSummary record
    5. Return the record

    Think about: what if there are fewer than 3 clean laps in a stint?
    That's not enough data to calculate meaningful degradation.
    How do you handle that case?
    """
    raise NotImplementedError


def compute_all_stint_summaries(db: Session, session_key: int) -> None:
    """
    Compute pace summaries for all driver stints in a session.
    This is what the Celery task calls.

    TODO: Implement this function.
    Query all unique (driver_number, stint_number) combinations
    for this session from the stints table, then call
    compute_stint_pace_summary for each.
    """
    raise NotImplementedError
