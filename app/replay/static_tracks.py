from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings


def _tracks_dir() -> Path:
    return Path(settings.static_tracks_dir)


def _bounds_tuple(bounds: dict[str, float]) -> tuple[float, float, float, float]:
    return (
        float(bounds["min_x"]),
        float(bounds["max_x"]),
        float(bounds["min_y"]),
        float(bounds["max_y"]),
    )


def load_static_track(circuit_key: int) -> dict[str, Any] | None:
    """
    Load a pre-authored canonical circuit outline keyed by OpenF1 circuit_key.

    Returns normalized points (0-1), sector metadata, and raw bounds for
  aligning telemetry coordinates.
    """
    path = _tracks_dir() / f"{circuit_key}.json"
    if not path.exists():
        return None

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    points = payload.get("points", [])
    bounds = payload.get("bounds")
    if not points or bounds is None:
        return None

    normalized_points = [
        (float(p["x"]), float(p["y"]))
        for p in points
        if p.get("x") is not None and p.get("y") is not None
    ]
    if len(normalized_points) < 2:
        return None

    return {
        "circuit_key": circuit_key,
        "name": payload.get("name"),
        "short_name": payload.get("short_name"),
        "source": payload.get("source", "static"),
        "bounds": _bounds_tuple(bounds),
        "points": normalized_points,
        "sectors": payload.get("sectors", []),
    }
