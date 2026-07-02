# Formula 1 Strategic Analysis Program

A full-stack platform for **historical F1 race strategy analysis** and **broadcast-style race replay**. The backend ingests telemetry and timing data from the [OpenF1 API](https://openf1.org), computes stint pace, tire degradation, and pit-window recommendations, and precomputes frame-by-frame replay bundles for an interactive track map viewer.

---

## Features

### Strategy analytics
- Ingests sessions, laps, stints, pit stops, and race control messages from OpenF1
- Computes stint pace summaries and tire-life estimates per circuit/compound
- Pit-window scoring with strategy recommendations via REST API

### Live race replay (historical)
- SVG track map with team-colored car markers moving in real time (from historical data)
- Playback at **0.5×, 1×, 2×, 5×, 10×** with smooth interpolation between frames
- Live leaderboard with position and gap to car ahead
- Race control overlays: sector yellow flags, safety car / VSC banners, incident toasts
- Precomputed, chunked replay bundles for efficient streaming to the browser

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  OpenF1 API │────▶│ Celery Worker│────▶│ PostgreSQL      │
└─────────────┘     │  (ingestion, │     │ (raw + derived) │
                    │   analytics, │     └─────────────────┘
                    │   replay)    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌─────────────────┐
                    │ Replay       │────▶│ data/replays/   │
                    │ Bundle Builder│     │ {session_key}/  │
                    └──────┬───────┘     └─────────────────┘
                           │
┌─────────────┐     ┌──────▼───────┐     ┌─────────────────┐
│ React SPA   │◀───▶│ FastAPI      │     │ data/tracks/    │
│ (Vite)      │     │ /replay/*    │     │ {circuit_key}.json
└─────────────┘     └──────────────┘     └─────────────────┘
```

| Layer | Stack |
|-------|-------|
| API | FastAPI, SQLAlchemy, Alembic |
| Workers | Celery, Redis |
| Database | PostgreSQL 15 |
| Frontend | React 18, TypeScript, Vite |
| Data source | OpenF1 API v1 |

---

## Race replay — technical design

The replay system is **not** a real-time simulation. It is an **offline compile + client playback** pipeline: the worker fetches telemetry once, resamples it into uniform time steps, writes JSON bundles to disk, and the browser plays them back like a scrubbable video.

### 1. Canonical circuit geometry (`data/tracks/`)

Track outlines are **not** inferred from noisy multi-lap telemetry at runtime. Each circuit has a pre-authored polyline keyed by OpenF1 `circuit_key`:

```
data/tracks/63.json   # Bahrain (Sakhir)
data/tracks/46.json   # Suzuka
data/tracks/22.json   # Monaco (Monte Carlo)
… (24 circuits on the 2024–2026 calendar)
```

**Source:** [MultiViewer](https://api.multiviewer.app) circuit info, linked from each meeting's `circuit_info_url` in OpenF1. This is the same coordinate system F1 uses for car positioning.

Each track file contains:
- `bounds` — raw `(min_x, max_x, min_y, max_y)` for normalizing telemetry
- `points` — ordered polyline normalized to `[0, 1] × [0, 1]`
- `sectors` — three arc-length segments for yellow-flag highlighting

Regenerate all tracks:

```bash
python3 scripts/generate_static_tracks.py
```

### 2. Coordinate system correction

OpenF1 `location` samples expose three axes: `x`, `y`, `z`. For track maps, the horizontal plane is **`(x, y)`** — not `(x, z)`. The `z` axis has a narrow range (~160 units vs ~8000 for `x`/`y`) and does not represent position on the circuit. Car positions and the static track polyline both normalize against the same `bounds` using independent per-axis scaling so cars align with the outline.

### 3. Replay bundle build (`app/replay/builder.py`)

Triggered by Celery after analytics complete (`build_session_replay_task`), or standalone via `POST /sessions/replay/{session_key}`.

**Pipeline steps:**

1. **Bulk location fetch** — all drivers per 5-minute time window (one API call per window, not per driver) to stay within OpenF1 rate limits
2. **Load static track** — `load_static_track(circuit_key)` from `data/tracks/{circuit_key}.json`
3. **Position & interval timelines** — race position and gap-to-ahead from OpenF1
4. **Frame resampling** — every 250 ms from session start to last telemetry sample (+ 30 s padding)
5. **Per-driver indexed timelines** (`_DriverTimeline`) — pre-built timestamp arrays with O(log n) `bisect` lookups; avoids rebuilding lists inside the hot frame loop
6. **Chunked JSON output** — 60-second frame chunks for lazy loading

**Bundle layout:**

```
data/replays/{session_key}/
├── metadata.json    # drivers, duration, chunk index
├── track.json       # polyline + sectors
├── events.json      # normalized race control timeline
└── frames/
    ├── 000.json     # ~60 s of frames at 250 ms intervals
    ├── 001.json
    └── …
```

### 4. Race control events (`app/replay/events.py`)

`RaceControl` rows from the database are normalized into a flat timeline with `t_ms` offsets from session start. Flag types (`YELLOW`, `DOUBLE_YELLOW`, `RED`, `SC`, `VSC`, `GREEN`) drive sector highlighting and full-track overlays in the UI.

### 5. Frontend playback (`frontend/`)

| Component | Role |
|-----------|------|
| `useFrameLoader` | Lazy-loads 60 s frame chunks ahead of the playhead |
| `usePlaybackEngine` | `requestAnimationFrame` loop; interpolates car `(x, y)` between bracketing frames |
| `TrackMap` | SVG circuit outline, sector underlays, team-colored car dots |
| `EventOverlay` | Flag banners and incident toasts |
| `Leaderboard` | Position + interval from interpolated frame state |
| `Timeline` | Play/pause, scrubber, elapsed time |
| `SpeedControl` | 0.5× – 10× presets |

The SVG uses a fixed square `viewBox` (`0 0 1 1` with padding) because both axes are independently normalized to `[0, 1]`.

---

## Quick start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone and configure

```bash
git clone https://github.com/avaldezmedina/Forumula-1-Strategic-Analysis-Program.git
cd Forumula-1-Strategic-Analysis-Program   # or your local directory name

cp .env.example .env
# Edit .env if you want non-default credentials
```

### 2. Start services

```bash
docker compose up --build -d
```

This starts:
- **PostgreSQL** on `localhost:5432`
- **Redis** on `localhost:6379`
- **API** on `http://localhost:8000`
- **Celery worker** (ingestion, analytics, replay builds)
- **Frontend dev server** on `http://localhost:5173`

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Ingest and build a race session

Use a **Race** session key from OpenF1 (not Qualifying or Practice):

```bash
# Full pipeline: ingest → analytics → replay bundle
curl -X POST http://localhost:8000/sessions/pipeline/9472
```

Poll worker logs:

```bash
docker compose logs -f worker
```

Check replay status:

```bash
curl http://localhost:8000/replay/9472/status
```

When `"status": "ready"`, open the viewer:

```bash
open http://localhost:5173/replay-view/9472
```

Or browse all sessions at `http://localhost:5173/`.

### 5. Replay-only rebuild (skip re-ingestion)

```bash
docker compose restart worker
curl -X POST "http://localhost:8000/sessions/replay/9472?force=true"
```

---

## Example session keys (2024 Race)

| Grand Prix | `session_key` | `circuit_key` |
|------------|---------------|---------------|
| Bahrain | 9472 | 63 |
| Japanese GP (Suzuka) | 9496 | 46 |
| Monaco | 9523 | 22 |

Find more:

```bash
curl "https://api.openf1.org/v1/sessions?year=2024&session_type=Race"
```

---

## API reference

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions/` | List ingested sessions with replay status |
| `POST` | `/sessions/pipeline/{session_key}` | Full ingest + analytics + replay |
| `POST` | `/sessions/replay/{session_key}?force=true` | Replay bundle only |
| `GET` | `/sessions/ingest/status/{task_id}` | Celery task status |

### Replay

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/replay/{session_key}/status` | Build state, duration, errors |
| `GET` | `/replay/{session_key}/metadata` | Drivers, chunks, timing |
| `GET` | `/replay/{session_key}/track` | Circuit polyline + sectors |
| `GET` | `/replay/{session_key}/events` | Flags and incidents |
| `GET` | `/replay/{session_key}/frames?from_ms=0&to_ms=60000` | Frame chunk |

### Strategy

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/strategy/recommendation?session_key=…&driver_number=…&lap_number=…` | Pit window recommendation |

Interactive API docs: `http://localhost:8000/docs`

---

## Project structure

```
app/
├── api/routes/          # FastAPI routers (sessions, replay, strategy)
├── db/                  # SQLAlchemy models + Alembic migrations
├── ingestion/           # OpenF1 client + ingest pipeline
├── replay/
│   ├── builder.py       # Replay bundle orchestration + frame generation
│   ├── static_tracks.py # Load canonical circuit polylines
│   ├── track.py         # Telemetry fallback (lap extraction, RDP)
│   └── events.py        # Race control normalization
├── strategy/            # Pace, tire life, pit window scoring
└── workers/             # Celery tasks

frontend/
├── src/components/      # TrackMap, Timeline, Leaderboard, EventOverlay, …
├── src/hooks/           # usePlaybackEngine, useFrameLoader
└── src/pages/           # ReplayViewer, SessionPicker

data/
├── tracks/              # Static circuit polylines ({circuit_key}.json)
└── replays/             # Generated replay bundles (gitignored)

scripts/
└── generate_static_tracks.py   # Fetch + build all circuit JSON files
```

---

## Development

### Run tests

```bash
python3 -m pytest tests/ -q
```

### Tear down and reset database

```bash
docker compose down -v
docker compose up --build -d
docker compose exec api alembic upgrade head
```

### Known limitations

- Replay build time depends on OpenF1 API rate limits (HTTP 429); the worker retries with exponential backoff
- OpenF1 location data is sampled at ~3–4 Hz; playback interpolates between samples
- Madrid (`circuit_key=153`) has no MultiViewer geometry yet; falls back to telemetry-derived outline
- Generated replay bundles (`data/replays/`) are not committed; rebuild per session after clone

---

## License

See repository for license details.
