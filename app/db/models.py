from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, ForeignKeyConstraint, Text, BigInteger, UniqueConstraint, Index, JSON
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Meeting(Base):
    __tablename__ = "meetings"

    meeting_key = Column(Integer, primary_key=True)
    circuit_key = Column(Integer)
    meeting_name = Column(String(255))
    location = Column(String(255))
    year = Column(Integer, nullable=False)
    date_start = Column(TIMESTAMP(timezone=True))
    date_end = Column(TIMESTAMP(timezone=True))

    sessions = relationship("Session", back_populates="meeting")


class Session(Base):
    __tablename__ = "sessions"

    session_key = Column(Integer, primary_key=True)
    meeting_key = Column(Integer, ForeignKey("meetings.meeting_key"), nullable=False)
    session_type = Column(String(50))
    date_start = Column(TIMESTAMP(timezone=True))

    meeting = relationship("Meeting", back_populates="sessions")
    laps = relationship("Lap", back_populates="session")
    stints = relationship("Stint", back_populates="session")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    driver_number = Column(Integer, nullable=False)
    first_name = Column(String(255))
    last_name = Column(String(255))
    team_name = Column(String(255))

    __table_args__ = (
        UniqueConstraint("year", "driver_number", name="uq_drivers_year_driver_number"),
    )


class Lap(Base):
    __tablename__ = "laps"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    year = Column(Integer, primary_key=True)
    driver_number = Column(Integer, primary_key=True)
    lap_number = Column(Integer, primary_key=True)
    lap_duration = Column(Numeric(8, 3))
    duration_sector_1 = Column(Numeric(8, 3))
    duration_sector_2 = Column(Numeric(8, 3))
    duration_sector_3 = Column(Numeric(8, 3))
    is_pit_out_lap = Column(Boolean)

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
    )

    session = relationship("Session", back_populates="laps")


class Stint(Base):
    __tablename__ = "stints"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    driver_number = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    stint_number = Column(Integer, primary_key=True)
    compound = Column(String(50), nullable=False)
    lap_start = Column(Integer, nullable=False)
    lap_end = Column(Integer, nullable=False)
    tyre_age_at_start = Column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
    )

    session = relationship("Session", back_populates="stints")


class PitStop(Base):
    __tablename__ = "pit_stops"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    year = Column(Integer, primary_key=True)
    driver_number = Column(Integer, primary_key=True)
    lap_number = Column(Integer, primary_key=True)
    occurred_at = Column(TIMESTAMP(timezone=True))
    lane_duration = Column(Numeric(8, 3))
    stop_duration = Column(Numeric(8, 3))

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
    )


class RaceControl(Base):
    __tablename__ = "race_control"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(Integer, ForeignKey("sessions.session_key"), nullable=False)
    year = Column(Integer)
    driver_number = Column(Integer)
    category = Column(String(100))
    message = Column(Text, nullable=False)
    flag = Column(String(50))
    scope = Column(String(50))
    sector = Column(Integer)
    lap_number = Column(Integer)
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
        Index(
            "uq_race_control_event",
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
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )


class SessionReplay(Base):
    __tablename__ = "session_replays"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    start_time = Column(TIMESTAMP(timezone=True))
    end_time = Column(TIMESTAMP(timezone=True))
    frame_interval_ms = Column(Integer, nullable=False, default=250)
    bundle_path = Column(String(512))
    built_at = Column(TIMESTAMP(timezone=True))
    error_message = Column(Text)


class CircuitTrack(Base):
    __tablename__ = "circuit_tracks"

    circuit_key = Column(Integer, primary_key=True)
    polyline = Column(JSON, nullable=False)
    source_session_key = Column(Integer, ForeignKey("sessions.session_key"))
    computed_at = Column(TIMESTAMP(timezone=True), nullable=False)


# =============================================================================
# DERIVED / COMPUTED TABLES
# =============================================================================

class StintPaceSummary(Base):
    __tablename__ = "stint_pace_summary"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    year = Column(Integer, nullable=False)
    driver_number = Column(Integer, primary_key=True)
    stint_number = Column(Integer, primary_key=True)
    compound = Column(String(50), nullable=False)
    lap_start = Column(Integer, nullable=False)
    lap_end = Column(Integer, nullable=False)
    clean_lap_count = Column(Integer, nullable=False)
    avg_clean_lap_time_seconds = Column(Numeric(8, 3), nullable=False)
    degradation_seconds_per_lap = Column(Numeric(8, 5), nullable=False)
    computed_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
    )


class TireLifeEstimate(Base):
    __tablename__ = "tire_life_estimates"

    circuit_key = Column(Integer, primary_key=True)
    compound = Column(String(50), primary_key=True)
    expected_laps_before_significant_deg = Column(Numeric(6, 2), nullable=False)
    avg_deg_onset_lap = Column(Numeric(6, 2))
    sample_stint_count = Column(Integer, nullable=False)
    avg_degradation_seconds_per_lap = Column(Numeric(8, 5))
    computed_at = Column(TIMESTAMP(timezone=True), nullable=False)


class PitWindowScore(Base):
    __tablename__ = "pit_window_scores"

    session_key = Column(Integer, ForeignKey("sessions.session_key"), primary_key=True)
    year = Column(Integer, nullable=False)
    driver_number = Column(Integer, primary_key=True)
    lap_number = Column(Integer, primary_key=True)
    stint_number = Column(Integer, nullable=False)
    compound = Column(String(50), nullable=False)
    current_tyre_age_laps = Column(Integer, nullable=False)
    current_avg_clean_lap_time_seconds = Column(Numeric(8, 3))
    current_degradation_seconds_per_lap = Column(Numeric(8, 5), nullable=False)
    expected_laps_before_significant_deg = Column(Numeric(6, 2), nullable=False)
    estimated_laps_remaining = Column(Numeric(6, 2), nullable=False)
    recommendation = Column(String(20), nullable=False)
    computed_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["year", "driver_number"],
            ["drivers.year", "drivers.driver_number"]
        ),
    )
