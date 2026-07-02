from __future__ import annotations

import math
from typing import Any, Sequence

Point2D = tuple[float, float]


def _perpendicular_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x0 - (x1 + t * dx), y0 - (y1 + t * dy))


def rdp_simplify(points: Sequence[Point2D], epsilon: float) -> list[Point2D]:
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) <= 2:
        return list(points)
    start, end = points[0], points[-1]
    max_dist, index = 0.0, 0
    for i in range(1, len(points) - 1):
        d = _perpendicular_distance(points[i], start, end)
        if d > max_dist:
            max_dist, index = d, i
    if max_dist > epsilon:
        left = rdp_simplify(points[: index + 1], epsilon)
        right = rdp_simplify(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def select_single_lap_samples(
    samples: Sequence[dict[str, Any]],
    *,
    skip_initial_ms: int = 300_000,
    expected_lap_ms: int | None = None,
    min_lap_duration_ms: int = 45_000,
    max_lap_duration_ms: int = 220_000,
    closure_distance_factor: float = 0.03,
) -> list[dict[str, Any]]:
    """
    Extract one clean racing lap from time-ordered location samples.

    Skips the formation/grid period, then walks forward until the car returns
    near the lap start position after traveling a meaningful distance along the
    path.  This preserves true circuit traversal order — unlike angular sorting
    from a centroid, which fails on concave circuits with hairpins.
    """
    if not samples:
        return []

    ordered = sorted(samples, key=lambda s: s["t_ms"])
    if len(ordered) < 20:
        return list(ordered)

    if expected_lap_ms is not None:
        min_lap_duration_ms = max(min_lap_duration_ms, int(expected_lap_ms * 0.70))
        max_lap_duration_ms = min(max_lap_duration_ms, int(expected_lap_ms * 1.40))

    first_t = ordered[0]["t_ms"]
    start_idx = next(
        (i for i, s in enumerate(ordered) if s["t_ms"] >= first_t + skip_initial_ms),
        max(len(ordered) // 10, 0),
    )
    if start_idx >= len(ordered) - 10:
        start_idx = max(0, len(ordered) // 10)

    lap_start = ordered[start_idx]
    ref_x = float(lap_start["x"])
    ref_y = float(lap_start["y"])

    xs = [float(s["x"]) for s in ordered]
    ys = [float(s["y"]) for s in ordered]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    close_threshold = max(span * closure_distance_factor, 5.0)
    # Require the car to travel a meaningful distance before allowing closure.
    # Using a fraction of "remaining race path" is unstable and can reject all
    # valid closures in long sessions.
    min_path = max(span * 2.0, close_threshold * 8.0)
    cumulative = 0.0

    for i in range(start_idx + 1, len(ordered)):
        prev = ordered[i - 1]
        curr = ordered[i]
        cumulative += math.hypot(
            float(curr["x"]) - float(prev["x"]),
            float(curr["y"]) - float(prev["y"]),
        )
        elapsed = curr["t_ms"] - lap_start["t_ms"]

        if elapsed < min_lap_duration_ms:
            continue
        if elapsed > max_lap_duration_ms:
            break

        dist_to_ref = math.hypot(float(curr["x"]) - ref_x, float(curr["y"]) - ref_y)
        if cumulative >= min_path and dist_to_ref <= close_threshold:
            return ordered[start_idx : i + 1]

    # Fallback: one expected lap (or ~100 s) from the selected start point.
    fallback_end = lap_start["t_ms"] + (expected_lap_ms or 100_000)
    fallback = [s for s in ordered[start_idx:] if s["t_ms"] <= fallback_end]
    if len(fallback) >= 20:
        return fallback

    return ordered[start_idx : min(start_idx + 500, len(ordered))]


def extract_circuit_outline(
    lap_samples: Sequence[dict[str, Any]],
    *,
    max_points: int = 1200,
) -> list[Point2D]:
    """
    Convert a single lap's time-ordered telemetry into a raw (x, z) outline.

    Samples are already in along-track order; we only downsample if the lap is
    very dense.  No spatial binning or angular sorting is applied.
    """
    if not lap_samples:
        return []

    points: list[Point2D] = [(float(s["x"]), float(s["y"])) for s in lap_samples]

    if len(points) > max_points:
        step = len(points) / max_points
        indices = [min(int(i * step), len(points) - 1) for i in range(max_points)]
        points = [points[i] for i in indices]

    return points


def derive_track_polyline(
    raw_outline: list[Point2D],
    bounds: tuple[float, float, float, float],
    target_points: int = 400,
) -> list[Point2D]:
    """
    Normalize a raw circuit outline to [0,1]×[0,1] and simplify with RDP.

    Uses independent normalization per axis so both dimensions span [0, 1].
    This matches car-position normalization in the replay builder.
    """
    if not raw_outline:
        return []

    min_x, max_x, min_y, max_y = bounds
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0

    normalized: list[Point2D] = [
        ((x - min_x) / span_x, (y - min_y) / span_y)
        for x, y in raw_outline
    ]

    epsilon = 0.005
    simplified = normalized
    for _ in range(12):
        candidate = rdp_simplify(simplified, epsilon)
        simplified = candidate
        if len(simplified) <= target_points:
            break
        epsilon *= 1.5

    return simplified


def cumulative_arc_lengths(points: Sequence[Point2D]) -> list[float]:
    lengths = [0.0]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    return lengths


def split_track_into_sectors(
    points: Sequence[Point2D],
    sector_count: int = 3,
) -> list[dict]:
    if len(points) < 2:
        return []
    arc = cumulative_arc_lengths(points)
    total = arc[-1]
    if total == 0:
        return []

    sectors = []
    boundaries = [total * i / sector_count for i in range(sector_count + 1)]

    for idx in range(sector_count):
        s_dist, e_dist = boundaries[idx], boundaries[idx + 1]

        s_index = next((i for i, d in enumerate(arc) if d >= s_dist), 0)
        e_index = next((i for i in range(len(arc) - 1, -1, -1) if arc[i] <= e_dist), len(arc) - 1)

        sectors.append({
            "sector": idx + 1,
            "start_index": s_index,
            "end_index": e_index,
            "start_dist": s_dist / total,
            "end_dist": e_dist / total,
        })

    return sectors


def compute_bounds_from_samples(samples: Sequence[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs = [float(s["x"]) for s in samples]
    ys = [float(s["y"]) for s in samples]
    return min(xs), max(xs), min(ys), max(ys)
