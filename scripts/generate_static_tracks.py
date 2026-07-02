#!/usr/bin/env python3
"""
Generate canonical static track outlines for all F1 circuits.

Data source: MultiViewer circuit info (same coordinate system as OpenF1
location x/y). Circuit list and URLs come from the OpenF1 meetings API.

Usage:
    python scripts/generate_static_tracks.py
    python scripts/generate_static_tracks.py --years 2024 2025 2026
    python scripts/generate_static_tracks.py --circuit-key 63
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OPENF1_BASE = "https://api.openf1.org/v1"
USER_AGENT = "f1-strategy-track-generator/1.0"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "tracks"


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _discover_circuits(years: list[int]) -> dict[int, dict[str, Any]]:
    circuits: dict[int, dict[str, Any]] = {}
    for year in years:
        rows = _fetch_json(f"{OPENF1_BASE}/meetings?year={year}")
        for row in rows:
            circuit_key = row.get("circuit_key")
            if circuit_key is None:
                continue
            circuits[int(circuit_key)] = {
                "circuit_key": int(circuit_key),
                "short_name": row.get("circuit_short_name"),
                "location": row.get("location"),
                "country": row.get("country_name"),
                "source_url": row.get("circuit_info_url"),
                "year": year,
            }
    return circuits


def _arc_lengths(points: list[tuple[float, float]]) -> list[float]:
    lengths = [0.0]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    return lengths


def _split_sectors(point_count: int, normalized: list[tuple[float, float]]) -> list[dict[str, Any]]:
    if point_count < 2:
        return []

    arc = _arc_lengths(normalized)
    total = arc[-1]
    if total == 0:
        return []

    sectors: list[dict[str, Any]] = []
    boundaries = [total * i / 3 for i in range(4)]

    for idx in range(3):
        s_dist, e_dist = boundaries[idx], boundaries[idx + 1]
        s_index = next((i for i, d in enumerate(arc) if d >= s_dist), 0)
        e_index = next((i for i in range(len(arc) - 1, -1, -1) if arc[i] <= e_dist), len(arc) - 1)
        sectors.append({
            "sector": idx + 1,
            "start_index": s_index,
            "end_index": e_index,
            "start_dist": round(s_dist / total, 5),
            "end_dist": round(e_dist / total, 5),
        })

    return sectors


def _build_track_payload(circuit: dict[str, Any]) -> dict[str, Any]:
    source_url = circuit.get("source_url")
    if not source_url:
        raise ValueError(f"No circuit_info_url for circuit_key={circuit['circuit_key']}")

    data = _fetch_json(source_url)
    xs = data.get("x") or []
    ys = data.get("y") or []
    if len(xs) < 2 or len(xs) != len(ys):
        raise ValueError(f"Invalid x/y arrays for circuit_key={circuit['circuit_key']}")

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0

    normalized = [((x - min_x) / span_x, (y - min_y) / span_y) for x, y in zip(xs, ys)]
    points = [
        {"x": round(x, 5), "y": round(y, 5)}
        for x, y in normalized
    ]

    name = data.get("circuitName") or circuit.get("short_name") or f"Circuit {circuit['circuit_key']}"

    return {
        "circuit_key": circuit["circuit_key"],
        "name": name,
        "short_name": circuit.get("short_name"),
        "location": circuit.get("location"),
        "country": circuit.get("country"),
        "source": "multiviewer",
        "source_url": source_url,
        "bounds": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        },
        "points": points,
        "sectors": _split_sectors(len(points), normalized),
    }


def generate_tracks(
    years: list[int],
    circuit_keys: list[int] | None = None,
    output_dir: Path = OUTPUT_DIR,
) -> tuple[list[int], list[tuple[int, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    circuits = _discover_circuits(years)

    if circuit_keys:
        circuits = {k: circuits[k] for k in circuit_keys if k in circuits}

    written: list[int] = []
    failed: list[tuple[int, str]] = []

    for circuit_key in sorted(circuits):
        circuit = circuits[circuit_key]
        try:
            payload = _build_track_payload(circuit)
            out_path = output_dir / f"{circuit_key}.json"
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            written.append(circuit_key)
            print(f"OK  {circuit_key:>3} {payload['short_name']:<20} {len(payload['points'])} pts -> {out_path.name}")
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as exc:
            failed.append((circuit_key, str(exc)))
            print(f"ERR {circuit_key:>3} {circuit.get('short_name', '?'):<20} {exc}")

    return written, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static F1 circuit track JSON files.")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2024, 2025, 2026],
        help="OpenF1 meeting years used to discover circuits (default: 2024 2025 2026)",
    )
    parser.add_argument(
        "--circuit-key",
        type=int,
        action="append",
        dest="circuit_keys",
        help="Generate only specific circuit_key(s); repeatable",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    written, failed = generate_tracks(args.years, args.circuit_keys, args.output_dir)
    print(f"\nDone: {len(written)} written, {len(failed)} failed")
    if failed:
        for circuit_key, message in failed:
            print(f"  - circuit_key={circuit_key}: {message}")
        if not written:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
