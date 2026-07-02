from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db import models


def _parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_epoch_ms(value: datetime | str) -> int:
    dt = _parse_timestamp(value)
    return int(dt.timestamp() * 1000)


def _normalize_flag(flag: str | None, message: str) -> str | None:
    if not flag:
        return None

    normalized = flag.strip().upper()
    message_upper = message.upper()

    if normalized in {"YELLOW", "DOUBLE YELLOW", "DOUBLE_YELLOW"}:
        return "DOUBLE_YELLOW" if "DOUBLE" in normalized or "DOUBLE" in message_upper else "YELLOW"
    if normalized in {"RED"}:
        return "RED"
    if normalized in {"GREEN"}:
        return "GREEN"
    if normalized in {"SC", "SAFETY CAR", "SAFETY_CAR"}:
        return "SC"
    if normalized in {"VSC", "VIRTUAL SAFETY CAR", "VIRTUAL_SAFETY_CAR"}:
        return "VSC"
    return normalized


def normalize_race_control_events(
    db: Session,
    session_key: int,
    session_start_ms: int,
) -> list[dict[str, Any]]:
    rows = (
        db.query(models.RaceControl)
        .filter(models.RaceControl.session_key == session_key)
        .order_by(models.RaceControl.occurred_at.asc())
        .all()
    )

    events: list[dict[str, Any]] = []

    for row in rows:
        occurred_ms = _to_epoch_ms(row.occurred_at)
        offset_ms = occurred_ms - session_start_ms

        if row.category and row.category.lower() == "flag":
            event_type = _normalize_flag(row.flag, row.message)
            if event_type is None:
                continue
        else:
            event_type = "INCIDENT"

        events.append(
            {
                "t_ms": offset_ms,
                "type": event_type,
                "category": row.category,
                "flag": row.flag,
                "scope": row.scope,
                "sector": row.sector,
                "lap_number": row.lap_number,
                "driver_number": row.driver_number,
                "message": row.message,
            }
        )

    return events


def build_events_payload(
    db: Session,
    session_key: int,
    session_start_ms: int,
) -> dict[str, Any]:
    events = normalize_race_control_events(db, session_key, session_start_ms)
    return {"events": events}
