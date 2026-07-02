from __future__ import annotations

from datetime import datetime, timezone

from app.replay.events import normalize_race_control_events
from app.replay.track import (
    derive_track_polyline,
    extract_circuit_outline,
    rdp_simplify,
    select_single_lap_samples,
    split_track_into_sectors,
)


def test_rdp_simplify_reduces_points():
    points = [(0.0, 0.0), (0.5, 0.01), (1.0, 0.0)]
    simplified = rdp_simplify(points, epsilon=0.05)
    assert len(simplified) <= len(points)
    assert simplified[0] == points[0]
    assert simplified[-1] == points[-1]


def test_select_single_lap_samples_detects_lap_closure():
    # Simulate a square loop in time order; closure returns near the start.
    samples = []
    t = 0
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0), (0.0, 0.0)]
    for _lap in range(3):
        for x, y in square:
            samples.append({"t_ms": t, "x": x, "y": y})
            t += 1000

    lap = select_single_lap_samples(
        samples,
        skip_initial_ms=0,
        min_lap_duration_ms=3000,
        max_lap_duration_ms=60_000,
        closure_distance_factor=0.05,
    )

    assert len(lap) >= 4
    start = (lap[0]["x"], lap[0]["y"])
    end = (lap[-1]["x"], lap[-1]["y"])
    assert abs(start[0] - end[0]) < 5.0
    assert abs(start[1] - end[1]) < 5.0


def test_extract_circuit_outline_preserves_traversal_order():
    lap_samples = [
        {"x": 0.0, "y": 0.0},
        {"x": 10.0, "y": 0.0},
        {"x": 10.0, "y": 10.0},
        {"x": 0.0, "y": 10.0},
    ]
    outline = extract_circuit_outline(lap_samples)
    assert outline == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_derive_track_polyline_normalizes_and_simplifies():
    raw_outline = [(0.0, 0.0), (50.0, 0.0), (100.0, 50.0), (50.0, 100.0), (0.0, 50.0)]
    bounds = (0.0, 100.0, 0.0, 100.0)
    track = derive_track_polyline(raw_outline, bounds=bounds, target_points=20)
    assert len(track) >= 2
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in track)


def test_split_track_into_sectors_returns_three_segments():
    points = [(i / 30, 0.0) for i in range(31)]
    sectors = split_track_into_sectors(points, sector_count=3)
    assert len(sectors) == 3
    assert sectors[0]["sector"] == 1
    assert sectors[-1]["sector"] == 3


class DummyRaceControl:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class DummyQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class DummySession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, model):
        return DummyQuery(self._rows)


def test_normalize_race_control_events_maps_flags_and_incidents():
    rows = [
        DummyRaceControl(
            occurred_at=datetime(2024, 5, 26, 14, 0, 0, tzinfo=timezone.utc),
            category="Flag",
            flag="YELLOW",
            scope="Sector",
            sector=2,
            lap_number=12,
            driver_number=44,
            message="YELLOW IN SECTOR 2",
        ),
        DummyRaceControl(
            occurred_at=datetime(2024, 5, 26, 14, 1, 0, tzinfo=timezone.utc),
            category="Other",
            flag=None,
            scope=None,
            sector=None,
            lap_number=12,
            driver_number=55,
            message="CAR 55 STOPPED ON TRACK",
        ),
    ]

    session_start_ms = int(datetime(2024, 5, 26, 14, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    events = normalize_race_control_events(DummySession(rows), session_key=1, session_start_ms=session_start_ms)

    assert events[0]["type"] == "YELLOW"
    assert events[0]["sector"] == 2
    assert events[1]["type"] == "INCIDENT"
    assert events[1]["message"] == "CAR 55 STOPPED ON TRACK"
