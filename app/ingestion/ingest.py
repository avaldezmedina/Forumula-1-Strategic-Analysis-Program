from sqlalchemy.orm import Session
from app.ingestion.client import OpenF1Client
from app.db import models


def ingest_meeting(db: Session, client: OpenF1Client, meeting_data: dict) -> models.Meeting:
    """
    Persist a single meeting to the database.

    TODO: Implement this function. It should:
    1. Check if this meeting_key already exists in the database
    2. If it does, return the existing record (do not duplicate)
    3. If it does not, create a new Meeting model instance and save it

    This pattern is called "upsert" logic. Look up SQLAlchemy's
    merge() or a manual get-or-create pattern.

    Think about: what fields from meeting_data do you actually store?
    You decided this during schema design. Map only those fields.
    """
    raise NotImplementedError


def ingest_session(db: Session, client: OpenF1Client, session_data: dict) -> models.Session | None:
    """
    Persist a single session to the database.

    TODO: Implement this function. It should:
    1. Check session_type — only persist Race sessions
    2. Apply the same get-or-create pattern as ingest_meeting
    3. Return None if the session is not a Race session

    Think about: where does the filter happen? Here, or in the caller?
    """
    raise NotImplementedError


def ingest_drivers(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all drivers for a session.

    TODO: Implement this function.
    Remember drivers are keyed by (year, driver_number) — not session.
    A driver may already exist from a previous session in the same year.
    Handle that case without raising a duplicate key error.
    """
    raise NotImplementedError


def ingest_laps(db: Session, client: OpenF1Client, session_key: int, driver_number: int, year: int) -> None:
    """
    Fetch and persist all laps for a driver in a session.

    TODO: Implement this function.
    Think about: should you re-ingest laps if they already exist?
    What's the safest behaviour if this function is called twice
    for the same session and driver?
    """
    raise NotImplementedError


def ingest_stints(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all stints for a session.

    TODO: Implement this function.
    """
    raise NotImplementedError


def ingest_pit_stops(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all pit stops for a session.

    TODO: Implement this function.
    """
    raise NotImplementedError


def ingest_race_control(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all race control messages for a session.

    TODO: Implement this function.
    """
    raise NotImplementedError


def ingest_full_session(db: Session, session_key: int) -> None:
    """
    Orchestrates full ingestion for one race session.
    This is the function Celery will call.

    TODO: Implement this function by calling the above functions
    in the correct order. Think about:
    1. What has to exist before something else can be inserted?
       (hint: foreign keys tell you the order)
    2. What happens if one step fails halfway through?
       Should you roll back? Should you retry just that step?
    3. How would you log progress so you can see what's happening?
    """
    raise NotImplementedError
