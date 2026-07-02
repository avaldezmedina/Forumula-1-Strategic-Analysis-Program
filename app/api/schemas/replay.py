from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReplayDriver(BaseModel):
    driver_number: int
    name: str
    team_name: str | None = None
    team_color: str


class ReplayChunk(BaseModel):
    index: int
    file: str
    start_ms: int
    end_ms: int


class ReplayMetadata(BaseModel):
    session_key: int
    year: int
    meeting_name: str | None = None
    location: str | None = None
    circuit_key: int | None = None
    start_time: str
    end_time: str
    duration_ms: int
    frame_interval_ms: int
    chunk_duration_ms: int
    drivers: list[ReplayDriver]
    chunks: list[ReplayChunk]


class ReplayStatus(BaseModel):
    session_key: int
    status: str
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: int | None = None
    frame_interval_ms: int | None = None
    built_at: str | None = None
    error_message: str | None = None
    playback_speeds: list[float] = Field(default_factory=lambda: [0.5, 1, 2, 5, 10])


class TrackPoint(BaseModel):
    x: float
    y: float


class TrackSector(BaseModel):
    sector: int
    start_index: int
    end_index: int
    start_dist: float
    end_dist: float


class ReplayTrack(BaseModel):
    points: list[TrackPoint]
    sectors: list[TrackSector]


class ReplayEvent(BaseModel):
    t_ms: int
    type: str
    category: str | None = None
    flag: str | None = None
    scope: str | None = None
    sector: int | None = None
    lap_number: int | None = None
    driver_number: int | None = None
    message: str


class ReplayEvents(BaseModel):
    events: list[ReplayEvent]


class ReplayCarState(BaseModel):
    x: float
    y: float
    position: int | None = None
    interval: str | float | None = None


class ReplayFrame(BaseModel):
    t_ms: int
    cars: dict[str, ReplayCarState]


class ReplayFrames(BaseModel):
    frames: list[ReplayFrame]
