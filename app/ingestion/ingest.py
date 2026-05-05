from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import models
from app.ingestion.client import OpenF1Client, OpenF1ClientError


def ingest_meeting(db: Session, client: OpenF1Client, meeting_data: dict) -> models.Meeting:
    """
    Persist a single meeting to the database.

    Idempotency:
    - meetings.meeting_key is the primary key, so ON CONFLICT DO NOTHING is safe.
    """
    stmt = (
        insert(models.Meeting)
        .values(
            meeting_key=meeting_data["meeting_key"],
            circuit_key=meeting_data.get("circuit_key"),
            meeting_name=meeting_data.get("meeting_name"),
            location=meeting_data.get("location"),
            year=meeting_data["year"],
            date_start=meeting_data.get("date_start"),
            date_end=meeting_data.get("date_end"),
        )
        .on_conflict_do_nothing(index_elements=["meeting_key"])
    )

    db.execute(stmt)

    meeting = db.get(models.Meeting, meeting_data["meeting_key"])
    if meeting is None:
        raise RuntimeError(f"Failed to load meeting {meeting_data['meeting_key']} after insert")

    return meeting


def ingest_session(db: Session, client: OpenF1Client, session_data: dict) -> models.Session | None:
    """
    Persist a single session to the database.

    Only Race sessions are persisted in this version.
    Returns None for non-Race sessions.
    """
    if session_data.get("session_type") != "Race":
        return None

    stmt = (
        insert(models.Session)
        .values(
            session_key=session_data["session_key"],
            meeting_key=session_data["meeting_key"],
            session_type=session_data.get("session_type"),
            date_start=session_data.get("date_start"),
        )
        .on_conflict_do_nothing(index_elements=["session_key"])
    )

    db.execute(stmt)

    session = db.get(models.Session, session_data["session_key"])
    if session is None:
        raise RuntimeError(f"Failed to load session {session_data['session_key']} after insert")

    return session


def ingest_drivers(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all drivers for a session.

    Drivers are season-scoped by (year, driver_number).
    """
    drivers = client.get_drivers(session_key)

    for raw_driver in drivers:
        stmt = (
            insert(models.Driver)
            .values(
                year=year,
                driver_number=raw_driver["driver_number"],
                first_name=raw_driver.get("first_name"),
                last_name=raw_driver.get("last_name"),
                team_name=raw_driver.get("team_name"),
            )
            .on_conflict_do_nothing(index_elements=["year", "driver_number"])
        )
        db.execute(stmt)


def ingest_laps(
    db: Session,
    client: OpenF1Client,
    session_key: int,
    driver_number: int,
    year: int,
) -> None:
    """
    Fetch and persist all laps for a driver in a session.

    Laps are idempotent on (session_key, year, driver_number, lap_number).
    """
    laps = client.get_laps(session_key, driver_number)

    for raw_lap in laps:
        stmt = (
            insert(models.Lap)
            .values(
                session_key=session_key,
                year=year,
                driver_number=driver_number,
                lap_number=raw_lap["lap_number"],
                lap_duration=raw_lap.get("lap_duration"),
                duration_sector_1=raw_lap.get("duration_sector_1"),
                duration_sector_2=raw_lap.get("duration_sector_2"),
                duration_sector_3=raw_lap.get("duration_sector_3"),
                is_pit_out_lap=raw_lap.get("is_pit_out_lap"),
            )
            .on_conflict_do_nothing(
                index_elements=["session_key", "year", "driver_number", "lap_number"]
            )
        )
        db.execute(stmt)


def ingest_stints(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all stints for a session.

    Stints are idempotent on (session_key, driver_number, stint_number).
    """
    stints = client.get_stints(session_key)

    for raw_stint in stints:
        stmt = (
            insert(models.Stint)
            .values(
                session_key=raw_stint["session_key"],
                driver_number=raw_stint["driver_number"],
                year=year,
                stint_number=raw_stint["stint_number"],
                compound=raw_stint["compound"],
                lap_start=raw_stint["lap_start"],
                lap_end=raw_stint["lap_end"],
                tyre_age_at_start=raw_stint.get("tyre_age_at_start"),
            )
            .on_conflict_do_nothing(
                index_elements=["session_key", "driver_number", "stint_number"]
            )
        )
        db.execute(stmt)


def ingest_pit_stops(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all pit stops for a session.

    Mapping:
    - API 'date' -> DB 'occurred_at'
    - Ignore deprecated API field 'pit_duration'
    """
    pit_stops = client.get_pit_stops(session_key)

    for raw_pit_stop in pit_stops:
        stmt = (
            insert(models.PitStop)
            .values(
                session_key=raw_pit_stop["session_key"],
                year=year,
                driver_number=raw_pit_stop["driver_number"],
                lap_number=raw_pit_stop["lap_number"],
                occurred_at=raw_pit_stop.get("date"),
                lane_duration=raw_pit_stop.get("lane_duration"),
                stop_duration=raw_pit_stop.get("stop_duration"),
            )
            .on_conflict_do_nothing(
                index_elements=["session_key", "year", "driver_number", "lap_number"]
            )
        )
        db.execute(stmt)


def ingest_race_control(db: Session, client: OpenF1Client, session_key: int, year: int) -> None:
    """
    Fetch and persist all race control messages for a session.

    Idempotency:
    - race_control uses a unique index over the event identity columns.
    - NULLS NOT DISTINCT in the migration makes nullable identity fields
      participate correctly in deduplication.
    """
    messages = client.get_race_control(session_key)

    for raw_message in messages:
        stmt = (
            insert(models.RaceControl)
            .values(
                session_key=raw_message["session_key"],
                year=year,
                driver_number=raw_message.get("driver_number"),
                category=raw_message.get("category"),
                message=raw_message["message"],
                flag=raw_message.get("flag"),
                scope=raw_message.get("scope"),
                sector=raw_message.get("sector"),
                lap_number=raw_message.get("lap_number"),
                occurred_at=raw_message.get("date"),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "session_key",
                    "year",
                    "driver_number",
                    "category",
                    "message",
                    "flag",
                    "scope",
                    "sector",
                    "lap_number",
                    "occurred_at",
                ]
            )
        )

        db.execute(stmt)


def ingest_full_session(db: Session, session_key: int) -> None:
    """
    Orchestrates full ingestion for one race session.

    Flow:
    1. Fetch raw session by session_key
    2. Fetch parent meeting by meeting_key
    3. Persist meeting
    4. Persist session (only if Race)
    5. Persist drivers
    6. Persist laps for each driver
    7. Persist stints
    8. Persist pit stops (skip if endpoint returns 404)
    9. Persist race control
    10. Commit once at the end
    """
    client = OpenF1Client()

    try:
        raw_session = client.get_session(session_key)
        raw_meeting = client.get_meeting(raw_session["meeting_key"])

        ingest_meeting(db, client, raw_meeting)

        session = ingest_session(db, client, raw_session)
        if session is None:
            db.rollback()
            return

        year = raw_session["year"]

        ingest_drivers(db, client, session_key=session_key, year=year)

        drivers = client.get_drivers(session_key)
        for raw_driver in drivers:
            ingest_laps(
                db,
                client,
                session_key=session_key,
                driver_number=raw_driver["driver_number"],
                year=year,
            )

        ingest_stints(db, client, session_key=session_key, year=year)

        try:
            ingest_pit_stops(db, client, session_key=session_key, year=year)
        except OpenF1ClientError as exc:
            # Current OpenF1ClientError does not expose status_code directly,
            # so with the current design we inspect the message.
            if "HTTP 404" not in str(exc):
                raise

        ingest_race_control(db, client, session_key=session_key, year=year)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        client.close()