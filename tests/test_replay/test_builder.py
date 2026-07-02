import json
from pathlib import Path

from app.replay.builder import _DriverTimeline, _build_frames
from app.replay.static_tracks import load_static_track


def test_driver_timeline_interpolates_location():
    timeline = _DriverTimeline(
        locations=[
            {"t_ms": 0, "x": 0.0, "y": 0.0},
            {"t_ms": 1000, "x": 10.0, "y": 20.0},
        ],
        positions=[],
        intervals=[],
        bounds=(0.0, 10.0, 0.0, 20.0),
    )

    result = timeline.interpolate_location(500)
    assert result == (0.5, 0.5)


def test_build_frames_are_monotonic_and_include_positions():
    drivers = [{"driver_number": 1, "name": "Test Driver", "team_name": "Test", "team_color": "#fff"}]
    driver_locations = {
        1: [
            {"t_ms": 1000, "x": 0.0, "y": 0.0},
            {"t_ms": 2000, "x": 10.0, "y": 10.0},
        ]
    }
    position_timeline = {
        1: [
            {"t_ms": 1000, "position": 2},
            {"t_ms": 2000, "position": 1},
        ]
    }
    interval_timeline = {1: [{"t_ms": 1000, "interval": "+1.2"}]}

    frames = _build_frames(
        drivers=drivers,
        driver_locations=driver_locations,
        position_timeline=position_timeline,
        interval_timeline=interval_timeline,
        bounds=(0.0, 10.0, 0.0, 10.0),
        start_ms=1000,
        end_ms=1500,
        frame_interval_ms=250,
    )

    assert len(frames) == 3
    assert frames[0]["t_ms"] == 0
    assert frames[1]["t_ms"] == 250
    assert frames[2]["t_ms"] == 500
    assert "1" in frames[0]["cars"]
    assert frames[-1]["cars"]["1"]["position"] == 2


def test_load_static_track_bahrain():
    track = load_static_track(63)
    assert track is not None
    assert len(track["points"]) > 100
    assert track["bounds"][0] < track["bounds"][1]
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in track["points"])


def test_static_track_catalog_covers_current_calendar():
    tracks_dir = Path(__file__).resolve().parents[2] / "data" / "tracks"
    track_files = sorted(tracks_dir.glob("*.json"))
    assert len(track_files) >= 24
    for path in track_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("circuit_key") == int(path.stem)
        assert len(payload.get("points", [])) >= 50
