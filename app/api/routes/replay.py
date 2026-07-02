from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas.replay import (
    ReplayEvents,
    ReplayFrames,
    ReplayMetadata,
    ReplayStatus,
    ReplayTrack,
)
from app.db.base import SessionLocal
from app.db import models
from app.replay.builder import (
    load_replay_events,
    load_replay_frames,
    load_replay_metadata,
    load_replay_track,
)

router = APIRouter(prefix="/replay", tags=["replay"])


def _get_replay_row(session_key: int) -> models.SessionReplay | None:
    db = SessionLocal()
    try:
        return db.get(models.SessionReplay, session_key)
    finally:
        db.close()


@router.get("/{session_key}/status", response_model=ReplayStatus)
def get_replay_status(session_key: int):
    replay = _get_replay_row(session_key)

    if replay is None:
        return ReplayStatus(session_key=session_key, status="not_built")

    duration_ms = None
    if replay.start_time and replay.end_time:
        duration_ms = int((replay.end_time - replay.start_time).total_seconds() * 1000)

    return ReplayStatus(
        session_key=session_key,
        status=replay.status,
        start_time=replay.start_time.isoformat() if replay.start_time else None,
        end_time=replay.end_time.isoformat() if replay.end_time else None,
        duration_ms=duration_ms,
        frame_interval_ms=replay.frame_interval_ms,
        built_at=replay.built_at.isoformat() if replay.built_at else None,
        error_message=replay.error_message,
    )


@router.get("/{session_key}/metadata", response_model=ReplayMetadata)
def get_replay_metadata(session_key: int):
    replay = _get_replay_row(session_key)
    if replay is None or replay.status != "ready":
        raise HTTPException(
            status_code=404,
            detail=f"Replay not ready for session_key={session_key}",
        )

    try:
        return load_replay_metadata(session_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_key}/track", response_model=ReplayTrack)
def get_replay_track(session_key: int):
    replay = _get_replay_row(session_key)
    if replay is None or replay.status != "ready":
        raise HTTPException(
            status_code=404,
            detail=f"Replay not ready for session_key={session_key}",
        )

    try:
        return load_replay_track(session_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_key}/events", response_model=ReplayEvents)
def get_replay_events(session_key: int):
    replay = _get_replay_row(session_key)
    if replay is None or replay.status != "ready":
        raise HTTPException(
            status_code=404,
            detail=f"Replay not ready for session_key={session_key}",
        )

    try:
        return load_replay_events(session_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_key}/frames", response_model=ReplayFrames)
def get_replay_frames(
    session_key: int,
    from_ms: int = Query(0, ge=0),
    to_ms: int = Query(60_000, ge=0),
):
    replay = _get_replay_row(session_key)
    if replay is None or replay.status != "ready":
        raise HTTPException(
            status_code=404,
            detail=f"Replay not ready for session_key={session_key}",
        )

    if to_ms < from_ms:
        raise HTTPException(status_code=400, detail="to_ms must be >= from_ms")

    try:
        return load_replay_frames(session_key, from_ms, to_ms)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
