from __future__ import annotations

import json
import shutil
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.ingestion.client import OpenF1Client, OpenF1ClientError
from app.replay.events import build_events_payload
from app.replay.static_tracks import load_static_track
from app.replay.track import (
    compute_bounds_from_samples,
    derive_track_polyline,
    extract_circuit_outline,
    select_single_lap_samples,
    split_track_into_sectors,
)

TEAM_COLORS: dict[str, str] = {
    "Red Bull Racing": "#3671C6",
    "Mercedes": "#27F4D2",
    "Ferrari": "#E8002D",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "RB": "#6692FF",
    "Visa Cash App RB": "#6692FF",
    "Kick Sauber": "#52E252",
    "Stake F1 Team Kick Sauber": "#52E252",
    "Haas F1 Team": "#B6BABD",
}


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
    return int(_parse_timestamp(value).timestamp() * 1000)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _bundle_dir(session_key: int) -> Path:
    return Path(settings.replay_data_dir) / str(session_key)


def _get_session_context(db: Session, session_key: int) -> tuple[models.Session, models.Meeting, int]:
    session_obj = db.get(models.Session, session_key)
    if session_obj is None:
        raise ValueError(f"No session found for session_key={session_key}")

    meeting = db.get(models.Meeting, session_obj.meeting_key)
    if meeting is None:
        raise ValueError(f"No meeting found for session_key={session_key}")

    year = meeting.year
    return session_obj, meeting, year


def _get_driver_list(db: Session, client: OpenF1Client, session_key: int, year: int) -> list[dict[str, Any]]:
    raw_drivers = client.get_drivers(session_key)
    drivers: list[dict[str, Any]] = []

    for raw in raw_drivers:
        driver_number = raw["driver_number"]
        db_driver = (
            db.query(models.Driver)
            .filter(
                models.Driver.year == year,
                models.Driver.driver_number == driver_number,
            )
            .first()
        )

        team_name = raw.get("team_name") or (db_driver.team_name if db_driver else None)
        first_name = raw.get("first_name") or (db_driver.first_name if db_driver else "")
        last_name = raw.get("last_name") or (db_driver.last_name if db_driver else "")

        drivers.append(
            {
                "driver_number": driver_number,
                "name": f"{first_name} {last_name}".strip() or str(driver_number),
                "team_name": team_name,
                "team_color": raw.get("team_colour")
                or raw.get("team_color")
                or TEAM_COLORS.get(team_name or "", "#FFFFFF"),
            }
        )

    return sorted(drivers, key=lambda d: d["driver_number"])


def _resolve_time_window(
    db: Session,
    client: OpenF1Client,
    session_key: int,
    session_obj: models.Session,
) -> tuple[datetime, datetime]:
    start = session_obj.date_start
    if start is None:
        start = datetime.now(timezone.utc) - timedelta(hours=2)

    start = _parse_timestamp(start)

    end_candidates: list[datetime] = [start + timedelta(hours=3)]

    last_pit = (
        db.query(models.PitStop.occurred_at)
        .filter(models.PitStop.session_key == session_key, models.PitStop.occurred_at.isnot(None))
        .order_by(models.PitStop.occurred_at.desc())
        .first()
    )
    if last_pit and last_pit[0]:
        end_candidates.append(_parse_timestamp(last_pit[0]) + timedelta(minutes=5))

    max_lap = (
        db.query(models.Lap.lap_number)
        .filter(models.Lap.session_key == session_key)
        .order_by(models.Lap.lap_number.desc())
        .first()
    )
    if max_lap and max_lap[0]:
        end_candidates.append(start + timedelta(minutes=int(max_lap[0]) * 2))

    end = max(end_candidates)

    try:
        positions = client.get_position(session_key)
        if positions:
            position_times = [_parse_timestamp(row["date"]) for row in positions if row.get("date")]
            if position_times:
                end = max(end, max(position_times) + timedelta(seconds=30))
    except OpenF1ClientError:
        pass

    return start, end


def _fetch_all_driver_locations(
    client: OpenF1Client,
    session_key: int,
    start: datetime,
    end: datetime,
) -> dict[int, list[dict[str, Any]]]:
    """
    Fetch location samples for every driver in a single set of windowed API
    calls (one call per window, all drivers included).  This is far more
    efficient than one call per driver per window.
    """
    raw_by_driver = client.get_location_all_drivers_windowed(
        session_key=session_key,
        date_gt=_format_iso(start),
        date_lt=_format_iso(end),
    )

    result: dict[int, list[dict[str, Any]]] = {}
    for driver_number, rows in raw_by_driver.items():
        parsed = [
            {
                "t_ms": _to_epoch_ms(row["date"]),
                "x": float(row["x"]),
                "y": float(row["y"]),
            }
            for row in rows
            if row.get("date") is not None
            and row.get("x") is not None
            and row.get("y") is not None
        ]
        if parsed:
            result[driver_number] = parsed

    return result


def _estimate_lap_duration_ms(db: Session, session_key: int, driver_number: int) -> int | None:
    rows = (
        db.query(models.Lap.lap_duration)
        .filter(
            models.Lap.session_key == session_key,
            models.Lap.driver_number == driver_number,
            models.Lap.lap_duration.isnot(None),
        )
        .order_by(models.Lap.lap_number.asc())
        .all()
    )
    durations = [float(row[0]) for row in rows if row and row[0] is not None]
    # Keep realistic race-lap durations only.
    durations = [d for d in durations if 45.0 <= d <= 220.0]
    if not durations:
        return None
    durations.sort()
    mid = len(durations) // 2
    median_seconds = durations[mid] if len(durations) % 2 == 1 else (durations[mid - 1] + durations[mid]) / 2.0
    return int(median_seconds * 1000)


def _fetch_position_timeline(
    client: OpenF1Client,
    session_key: int,
    drivers: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    timeline: dict[int, list[dict[str, Any]]] = {d["driver_number"]: [] for d in drivers}

    try:
        rows = client.get_position(session_key)
    except OpenF1ClientError:
        return timeline

    for row in rows:
        driver_number = row.get("driver_number")
        if driver_number is None or driver_number not in timeline:
            continue
        if row.get("date") is None or row.get("position") is None:
            continue

        timeline[driver_number].append(
            {
                "t_ms": _to_epoch_ms(row["date"]),
                "position": int(row["position"]),
            }
        )

    for driver_number in timeline:
        timeline[driver_number].sort(key=lambda item: item["t_ms"])

    return timeline


def _fetch_interval_timeline(
    client: OpenF1Client,
    session_key: int,
    drivers: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    timeline: dict[int, list[dict[str, Any]]] = {d["driver_number"]: [] for d in drivers}

    try:
        rows = client.get_intervals(session_key)
    except OpenF1ClientError:
        return timeline

    for row in rows:
        driver_number = row.get("driver_number")
        if driver_number is None or driver_number not in timeline:
            continue
        if row.get("date") is None:
            continue

        timeline[driver_number].append(
            {
                "t_ms": _to_epoch_ms(row["date"]),
                "interval": row.get("interval"),
            }
        )

    for driver_number in timeline:
        timeline[driver_number].sort(key=lambda item: item["t_ms"])

    return timeline


class _DriverTimeline:
    """
    Pre-indexed per-driver data for O(log n) lookups without rebuilding lists.

    All per-driver timestamp lists are built exactly once and reused across all
    frames, avoiding the massive GC pressure of rebuilding lists inside the
    frame loop.
    """

    __slots__ = (
        "loc_times", "loc_x", "loc_y",
        "pos_times", "pos_values",
        "int_times", "int_values",
        "_min_x", "_scale_x", "_min_y", "_scale_y",
    )

    def __init__(
        self,
        locations: list[dict[str, Any]],
        positions: list[dict[str, Any]],
        intervals: list[dict[str, Any]],
        bounds: tuple[float, float, float, float],
    ) -> None:
        min_x, max_x, min_y, max_y = bounds
        # Independent normalization: each axis spans the full [0, 1] range.
        self._min_x = float(min_x)
        self._scale_x = float(max_x - min_x) or 1.0
        self._min_y = float(min_y)
        self._scale_y = float(max_y - min_y) or 1.0

        self.loc_times: list[int] = [s["t_ms"] for s in locations]
        self.loc_x: list[float] = [s["x"] for s in locations]
        self.loc_y: list[float] = [s["y"] for s in locations]

        self.pos_times: list[int] = [e["t_ms"] for e in positions]
        self.pos_values: list[Any] = [e.get("position") for e in positions]

        self.int_times: list[int] = [e["t_ms"] for e in intervals]
        self.int_values: list[Any] = [e.get("interval") for e in intervals]

    def interpolate_location(self, t_ms: int) -> tuple[float, float] | None:
        times = self.loc_times
        if not times:
            return None

        idx = bisect_left(times, t_ms)

        if idx == 0:
            if times[0] == t_ms:
                raw_x, raw_y = self.loc_x[0], self.loc_y[0]
            else:
                return None
        elif idx >= len(times):
            raw_x, raw_y = self.loc_x[-1], self.loc_y[-1]
        else:
            t0, t1 = times[idx - 1], times[idx]
            ratio = (t_ms - t0) / (t1 - t0) if t1 != t0 else 0.0
            raw_x = self.loc_x[idx - 1] + ratio * (self.loc_x[idx] - self.loc_x[idx - 1])
            raw_y = self.loc_y[idx - 1] + ratio * (self.loc_y[idx] - self.loc_y[idx - 1])

        norm_x = (raw_x - self._min_x) / self._scale_x
        norm_y = (raw_y - self._min_y) / self._scale_y
        return norm_x, norm_y

    def position_at(self, t_ms: int) -> Any | None:
        if not self.pos_times:
            return None
        idx = bisect_left(self.pos_times, t_ms) - 1
        return self.pos_values[idx] if idx >= 0 else None

    def interval_at(self, t_ms: int) -> Any | None:
        if not self.int_times:
            return None
        idx = bisect_left(self.int_times, t_ms) - 1
        return self.int_values[idx] if idx >= 0 else None


def _build_frames(
    drivers: list[dict[str, Any]],
    driver_locations: dict[int, list[dict[str, Any]]],
    position_timeline: dict[int, list[dict[str, Any]]],
    interval_timeline: dict[int, list[dict[str, Any]]],
    bounds: tuple[float, float, float, float],
    start_ms: int,
    end_ms: int,
    frame_interval_ms: int,
) -> list[dict[str, Any]]:
    # Build per-driver indexed timelines once — avoids recreating timestamp
    # lists inside the hot frame loop, which causes severe GC pressure.
    timelines: dict[int, _DriverTimeline] = {
        driver["driver_number"]: _DriverTimeline(
            locations=driver_locations.get(driver["driver_number"], []),
            positions=position_timeline.get(driver["driver_number"], []),
            intervals=interval_timeline.get(driver["driver_number"], []),
            bounds=bounds,
        )
        for driver in drivers
    }

    frames: list[dict[str, Any]] = []
    t_ms = start_ms

    while t_ms <= end_ms:
        cars: dict[str, dict[str, Any]] = {}

        for driver in drivers:
            driver_number = driver["driver_number"]
            tl = timelines[driver_number]
            loc = tl.interpolate_location(t_ms)
            if loc is None:
                continue

            norm_x, norm_y = loc
            cars[str(driver_number)] = {
                "x": round(norm_x, 5),
                "y": round(norm_y, 5),
                "position": tl.position_at(t_ms),
                "interval": tl.interval_at(t_ms),
            }

        frames.append({"t_ms": t_ms - start_ms, "cars": cars})
        t_ms += frame_interval_ms

    return frames


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))


def _write_frame_chunks(
    bundle_dir: Path,
    frames: list[dict[str, Any]],
    chunk_duration_ms: int,
) -> list[dict[str, int]]:
    chunks: list[dict[str, int]] = []
    if not frames:
        return chunks

    chunk_index = 0
    chunk_start = frames[0]["t_ms"]
    current_chunk: list[dict[str, Any]] = []

    for frame in frames:
        if current_chunk and frame["t_ms"] - chunk_start >= chunk_duration_ms:
            filename = f"{chunk_index:03d}.json"
            _write_json(bundle_dir / "frames" / filename, {"frames": current_chunk})
            chunks.append(
                {
                    "index": chunk_index,
                    "file": filename,
                    "start_ms": chunk_start,
                    "end_ms": current_chunk[-1]["t_ms"],
                }
            )
            chunk_index += 1
            chunk_start = frame["t_ms"]
            current_chunk = []

        current_chunk.append(frame)

    if current_chunk:
        filename = f"{chunk_index:03d}.json"
        _write_json(bundle_dir / "frames" / filename, {"frames": current_chunk})
        chunks.append(
            {
                "index": chunk_index,
                "file": filename,
                "start_ms": chunk_start,
                "end_ms": current_chunk[-1]["t_ms"],
            }
        )

    return chunks


def build_session_replay(
    db: Session,
    session_key: int,
    force: bool = False,
) -> dict[str, Any]:
    existing = db.get(models.SessionReplay, session_key)
    if existing and existing.status == "ready" and not force:
        return {
            "status": "skipped",
            "session_key": session_key,
            "message": "Replay already built. Use force=true to rebuild.",
        }

    session_obj, meeting, year = _get_session_context(db, session_key)
    bundle_dir = _bundle_dir(session_key)

    if force and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    replay_row = existing or models.SessionReplay(session_key=session_key)
    replay_row.status = "building"
    replay_row.frame_interval_ms = settings.replay_frame_interval_ms
    replay_row.error_message = None
    replay_row.bundle_path = str(bundle_dir)
    db.add(replay_row)
    db.flush()

    client = OpenF1Client()

    try:
        drivers = _get_driver_list(db, client, session_key, year)
        if not drivers:
            raise ValueError(f"No drivers found for session_key={session_key}")

        start_dt, end_dt = _resolve_time_window(db, client, session_key, session_obj)
        start_ms = _to_epoch_ms(start_dt)
        end_ms = _to_epoch_ms(end_dt)

        # Fetch all drivers' location data in bulk (one API call per time window,
        # not one call per driver per window).  This is the single most
        # API-call-intensive step; doing it in bulk keeps us well inside
        # OpenF1's rate limits.
        driver_locations = _fetch_all_driver_locations(client, session_key, start_dt, end_dt)

        # Tighten end_ms to the last actual location sample so we don't generate
        # thousands of empty frames after the chequered flag.
        if driver_locations:
            last_sample_ms = max(
                samples[-1]["t_ms"]
                for samples in driver_locations.values()
                if samples
            )
            # Give 30 s of padding so the final positions are visible briefly.
            end_ms = min(end_ms, last_sample_ms + 30_000)

        if not driver_locations:
            raise ValueError("No location samples found for any driver.")

        all_raw_samples: list[dict[str, float]] = [
            {"x": s["x"], "y": s["y"]}
            for samples in driver_locations.values()
            for s in samples
        ]

        static_track = load_static_track(meeting.circuit_key) if meeting.circuit_key is not None else None
        if static_track:
            bounds = static_track["bounds"]
            track_points = static_track["points"]
            sectors = static_track["sectors"] or split_track_into_sectors(track_points)
        else:
            bounds = compute_bounds_from_samples(all_raw_samples)
            reference_driver = max(driver_locations, key=lambda dn: len(driver_locations[dn]))
            expected_lap_ms = _estimate_lap_duration_ms(db, session_key, reference_driver)
            lap_samples = select_single_lap_samples(
                driver_locations[reference_driver],
                expected_lap_ms=expected_lap_ms,
            )
            if len(lap_samples) < 20:
                raise ValueError(
                    f"Insufficient samples to derive track for session_key={session_key} "
                    f"(driver {reference_driver}, {len(lap_samples)} lap samples)."
                )
            raw_outline = extract_circuit_outline(lap_samples)
            track_points = derive_track_polyline(raw_outline, bounds=bounds)
            sectors = split_track_into_sectors(track_points)

        position_timeline = _fetch_position_timeline(client, session_key, drivers)
        interval_timeline = _fetch_interval_timeline(client, session_key, drivers)

        frames = _build_frames(
            drivers=drivers,
            driver_locations=driver_locations,
            position_timeline=position_timeline,
            interval_timeline=interval_timeline,
            bounds=bounds,
            start_ms=start_ms,
            end_ms=end_ms,
            frame_interval_ms=settings.replay_frame_interval_ms,
        )

        chunks = _write_frame_chunks(bundle_dir, frames, settings.replay_chunk_duration_ms)

        metadata = {
            "session_key": session_key,
            "year": year,
            "meeting_name": meeting.meeting_name,
            "location": meeting.location,
            "circuit_key": meeting.circuit_key,
            "start_time": _format_iso(start_dt),
            "end_time": _format_iso(end_dt),
            "duration_ms": end_ms - start_ms,
            "frame_interval_ms": settings.replay_frame_interval_ms,
            "chunk_duration_ms": settings.replay_chunk_duration_ms,
            "drivers": drivers,
            "chunks": chunks,
        }

        track_payload = {
            "points": [{"x": round(x, 5), "y": round(y, 5)} for x, y in track_points],
            "sectors": sectors,
        }

        events_payload = build_events_payload(db, session_key, start_ms)

        _write_json(bundle_dir / "metadata.json", metadata)
        _write_json(bundle_dir / "track.json", track_payload)
        _write_json(bundle_dir / "events.json", events_payload)

        if meeting.circuit_key is not None:
            circuit_track = db.get(models.CircuitTrack, meeting.circuit_key)
            if circuit_track is None:
                circuit_track = models.CircuitTrack(circuit_key=meeting.circuit_key)
            circuit_track.polyline = track_payload["points"]
            circuit_track.source_session_key = session_key
            circuit_track.computed_at = datetime.now(timezone.utc)
            db.add(circuit_track)

        replay_row.status = "ready"
        replay_row.start_time = start_dt
        replay_row.end_time = end_dt
        replay_row.built_at = datetime.now(timezone.utc)
        replay_row.error_message = None

        return {
            "status": "success",
            "session_key": session_key,
            "frame_count": len(frames),
            "chunk_count": len(chunks),
            "driver_count": len(drivers),
            "event_count": len(events_payload.get("events", [])),
        }

    except Exception as exc:
        replay_row.status = "failed"
        replay_row.error_message = str(exc)
        db.commit()
        raise

    finally:
        client.close()


def load_replay_metadata(session_key: int) -> dict[str, Any]:
    path = _bundle_dir(session_key) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Replay metadata not found for session_key={session_key}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_replay_track(session_key: int) -> dict[str, Any]:
    path = _bundle_dir(session_key) / "track.json"
    if not path.exists():
        raise FileNotFoundError(f"Replay track not found for session_key={session_key}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_replay_events(session_key: int) -> dict[str, Any]:
    path = _bundle_dir(session_key) / "events.json"
    if not path.exists():
        raise FileNotFoundError(f"Replay events not found for session_key={session_key}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_replay_frames(session_key: int, from_ms: int, to_ms: int) -> dict[str, Any]:
    metadata = load_replay_metadata(session_key)
    chunks = metadata.get("chunks", [])

    selected_frames: list[dict[str, Any]] = []
    bundle_dir = _bundle_dir(session_key)

    for chunk in chunks:
        chunk_start = chunk["start_ms"]
        chunk_end = chunk["end_ms"]
        if chunk_end < from_ms or chunk_start > to_ms:
            continue

        chunk_path = bundle_dir / "frames" / chunk["file"]
        with chunk_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        for frame in payload.get("frames", []):
            t_ms = frame["t_ms"]
            if from_ms <= t_ms <= to_ms:
                selected_frames.append(frame)

    selected_frames.sort(key=lambda frame: frame["t_ms"])
    return {"frames": selected_frames}
