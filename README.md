# Formula 1 Strategic Analysis Program

A full-stack platform that answers two questions every F1 strategist cares about:

1. **When should a driver pit or extend their stint?** — analytics from historical lap, stint, and tyre-life data.
2. **What did the race actually look like?** — a broadcast-style replay with cars on a real circuit map, flags, and per-driver strategy guidance synced to playback time.

Built with **FastAPI**, **Celery**, **PostgreSQL**, **React**, and **TypeScript**, sourcing live historical data from the [OpenF1 API](https://openf1.org).

---

## In plain English

Imagine you're watching an F1 race on TV — track map, dots for each car, leaderboard, yellow flags — but it's a **past race** you can rewind, speed up, and scrub through. Click any driver and a panel appears telling you whether they should **pit now**, **consider pitting**, **extend the stint**, or **keep monitoring** tyre wear, based on precomputed analytics for that exact lap.

That's what this app does. The backend pulls real F1 data, runs strategy models offline, and pre-builds a "filmstrip" of car positions. The browser plays it back smoothly while overlaying pit recommendations as you move through the race.

---

## What you can do in the UI

| Feature | How |
|---------|-----|
| **Browse races** | Open `http://localhost:5173` — pick a session with replay status `ready` |
| **Watch the replay** | Circuit map, moving cars, leaderboard, play/pause, scrubber |
| **Change speed** | 0.5×, 1×, 2×, 5×, 10× |
| **See flags & incidents** | Sector yellows on the map; SC/VSC banners; incident toasts |
| **Track a driver** | Click a car on the map or a row in the leaderboard |
| **Pit / extend guidance** | Strategy panel shows tyre life %, recommendation, and stint history — updates as you scrub through the race |

**Example race URLs** (after pipeline completes):

- Bahrain 2024: `http://localhost:5173/replay-view/9472`
- Suzuka 2024: `http://localhost:5173/replay-view/9496`
- Monaco 2024: `http://localhost:5173/replay-view/9523`

---

## Technical highlights (for recruiters)

- **Event-driven data pipeline** — Celery workers ingest OpenF1 telemetry, compute stint pace / tyre degradation / pit-window scores, then build replay bundles asynchronously.
- **Precomputed playback architecture** — Race "simulation" is offline frame generation (250 ms intervals, chunked JSON); the client interpolates with `requestAnimationFrame` for smooth 60 fps rendering without streaming raw telemetry.
- **Canonical circuit geometry** — 24 F1 circuits ship as static polylines (`data/tracks/`) from MultiViewer, aligned to OpenF1 `(x, y)` coordinates — not derived from noisy telemetry at runtime.
- **O(log n) frame lookups** — `_DriverTimeline` pre-indexes per-driver location arrays; bisect-based interpolation avoids GC pressure in the hot frame-build loop.
- **Strategy + replay integration** — `GET /strategy/driver-panel/{session}/{driver}` returns all per-lap scores; the UI maps playback time → estimated lap → live recommendation.
- **Race control state machine** — Frontend flag overlay handles `YELLOW`, `DOUBLE_YELLOW`, `CLEAR`, `GREEN`, `SC`, `VSC`, `RED` with sector-scoped Map deduplication (OpenF1 uses `CLEAR` for sector lifts, not `GREEN`).

**Stack:** FastAPI · SQLAlchemy · Alembic · Celery · Redis · PostgreSQL 15 · React 18 · TypeScript · Vite · SVG

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  OpenF1 API │────▶│ Celery Worker│────▶│ PostgreSQL      │
└─────────────┘     │  ingest      │     │ laps, stints,   │
                    │  analytics   │     │ pit scores, RC  │
                    │  replay build│     └─────────────────┘
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     data/replays/   data/tracks/   strategy tables
     {session}/      {circuit}.json  (pit_window_scores)
              │
┌─────────────┐     ┌──────▼───────┐
│ React SPA   │◀───▶│ FastAPI      │
│ localhost:  │     │ /replay/*    │
│ 5173        │     │ /strategy/*  │
└─────────────┘     └──────────────┘
```

---

## UI components

| Component | File | Purpose |
|-----------|------|---------|
| **SessionPicker** | `SessionPicker.tsx` | Lists sessions and replay build status |
| **ReplayViewer** | `ReplayViewer.tsx` | Main page: orchestrates playback, selection, layout |
| **TrackMap** | `TrackMap.tsx` | SVG circuit, sector underlays, clickable car dots, flag overlays |
| **Leaderboard** | `Leaderboard.tsx` | Live positions and gaps; click to select driver |
| **DriverStrategyPanel** | `DriverStrategyPanel.tsx` | Tyre life bar, PIT/EXTEND recommendation, stint table |
| **Timeline** | `Timeline.tsx` | Play/pause, scrubber, elapsed time |
| **SpeedControl** | `SpeedControl.tsx` | 0.5× – 10× playback presets |
| **EventOverlay** | `EventOverlay.tsx` | SC/VSC banners and incident toasts |

**Hooks:**

- `useFrameLoader` — lazy-loads 60-second frame chunks ahead of the playhead
- `usePlaybackEngine` — RAF loop; linear interpolation of car `(x, y)` between 250 ms frames

---

## Driver strategy panel (pit tracker)

When you select a driver, the panel loads all precomputed strategy data in one API call and updates as playback time advances.

**Backend:** `GET /strategy/driver-panel/{session_key}/{driver_number}`

Returns:
- All stint pace summaries (compound, lap range, avg pace, deg/lap)
- All per-lap pit-window scores (`PIT_NOW`, `CONSIDER_PIT`, `EXTEND`, `MONITOR`)
- Estimated lap duration (median clean lap time) for mapping replay time → lap number

**Frontend logic:**
1. `estimatedLap = currentMs / estimatedLapDurationMs`
2. Find the nearest scored lap ≤ estimated lap
3. Display tyre life ratio bar, recommendation badge, and stint history

**Requirements:** Run the **full pipeline** (`POST /sessions/pipeline/{key}`) so analytics tables are populated — replay-only rebuild is not enough for strategy data.

**Recommendation colors:**

| Badge | Meaning |
|-------|---------|
| `EXTEND` | Tyre life healthy — stay out |
| `MONITOR` | Watch degradation |
| `CONSIDER PIT` | Approaching pit window |
| `PIT NOW` | Significant deg or window closing |

---

## Race replay (historical simulation)

This is **not** a physics engine. It is an **offline compile + client playback** pipeline:

1. Worker fetches all drivers' location data from OpenF1 (bulk, 5-minute windows)
2. Loads static circuit polyline from `data/tracks/{circuit_key}.json`
3. Resamples telemetry to 250 ms frames with position, gap, and normalized `(x, y)`
4. Writes chunked JSON bundles to `data/replays/{session_key}/`
5. Browser plays frames like a scrubbable video with interpolation

### Circuit maps (`data/tracks/`)

Track outlines come from [MultiViewer](https://api.multiviewer.app) circuit geometry — the same coordinate system OpenF1 uses. **24 circuits** are included (2024–2026 calendar). Cars use OpenF1 **`(x, y)`** for the map plane (not `x, z`).

Regenerate tracks:

```bash
python3 scripts/generate_static_tracks.py
```

### Flag overlays

Race control messages are normalized to a timeline (`events.json`). The UI applies:

- **Sector yellow / double yellow** — highlighted sector on the map
- **CLEAR / GREEN** — lifts sector or track-wide conditions (OpenF1 uses `CLEAR` for sector clears)
- **SC / VSC** — amber border + banner
- **RED** — red tint overlay
- **Incidents** — 8-second toast notifications

---

## Getting started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Git

### Step 1 — Clone and configure

```bash
git clone https://github.com/avaldezmedina/Forumula-1-Strategic-Analysis-Program.git
cd Forumula-1-Strategic-Analysis-Program

cp .env.example .env
```

Default credentials in `.env.example` work for local development.

### Step 2 — Start all services

```bash
docker compose up --build -d
```

Wait ~15 seconds, then run migrations:

```bash
docker compose exec api alembic upgrade head
```

| Service | URL |
|---------|-----|
| **Frontend (UI)** | http://localhost:5173 |
| **API** | http://localhost:8000 |
| **API docs (Swagger)** | http://localhost:8000/docs |

Verify health:

```bash
curl http://localhost:8000/health
```

### Step 3 — Build a race session

Use a **Race** session key (not Qualifying or Practice):

```bash
curl -X POST http://localhost:8000/sessions/pipeline/9472
```

This runs: **ingest → analytics → replay bundle**. Takes **5–15+ minutes** (OpenF1 rate limits).

Watch progress:

```bash
docker compose logs -f worker
```

Check when done:

```bash
curl http://localhost:8000/replay/9472/status
```

Wait for `"status": "ready"`.

### Step 4 — Open the viewer and test

```bash
open http://localhost:5173/replay-view/9472
```

**Try this:**

1. Press play — cars move around the Bahrain circuit
2. Change speed to 2× or 5×
3. Scrub to ~4:00 — brief double-yellow in sector 2, then clears
4. Click a car (e.g. Verstappen #1) — strategy panel appears below leaderboard
5. Scrub through the race — recommendation and tyre bar update per lap

### Fresh reset (wipe database)

```bash
docker compose down -v
docker compose up --build -d
sleep 15
docker compose exec api alembic upgrade head
curl -X POST http://localhost:8000/sessions/pipeline/9472
```

### Replay-only rebuild (after code changes to replay/frontend)

```bash
docker compose restart worker frontend
curl -X POST "http://localhost:8000/sessions/replay/9472?force=true"
```

Hard-refresh the browser: `Cmd + Shift + R` (Mac) or `Ctrl + Shift + R` (Windows/Linux).

---

## Example session keys (2024 Race)

| Grand Prix | `session_key` | `circuit_key` | Direct link |
|------------|---------------|---------------|-------------|
| Bahrain | 9472 | 63 | `/replay-view/9472` |
| Japanese GP (Suzuka) | 9496 | 46 | `/replay-view/9496` |
| Monaco | 9523 | 22 | `/replay-view/9523` |

Find more sessions:

```bash
curl "https://api.openf1.org/v1/sessions?year=2024&session_type=Race"
```

---

## API reference

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions/` | List sessions with replay status |
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
| `GET` | `/strategy/recommendation?session_key=&driver_number=&lap_number=` | Single-lap recommendation |
| `GET` | `/strategy/driver-panel/{session_key}/{driver_number}` | All stints + scores for replay UI |
| `GET` | `/strategy/stint-summary/{session_key}/{driver_number}` | Stint pace summaries |

Interactive docs: **http://localhost:8000/docs**

---

## Project structure

```
app/
├── api/routes/           # sessions, replay, strategy endpoints
├── db/                   # SQLAlchemy models + Alembic migrations
├── ingestion/            # OpenF1 client (rate limiting, bulk location fetch)
├── replay/
│   ├── builder.py        # Frame generation, bundle writer, _DriverTimeline
│   ├── static_tracks.py  # Load canonical circuit polylines
│   ├── track.py          # Telemetry fallback for circuits without static data
│   └── events.py         # Race control → replay event timeline
├── strategy/             # Pace, tyre life, pit-window scoring
└── workers/              # Celery tasks (pipeline, replay build)

frontend/src/
├── components/
│   ├── TrackMap.tsx           # SVG map + cars + flags
│   ├── Leaderboard.tsx        # Positions; driver selection
│   ├── DriverStrategyPanel.tsx # Pit/extend tracker per driver
│   ├── EventOverlay.tsx       # Flag banners, incident toasts
│   ├── Timeline.tsx           # Scrubber + play controls
│   └── SpeedControl.tsx       # Playback speed presets
├── hooks/
│   ├── usePlaybackEngine.ts   # RAF interpolation loop
│   └── useFrameLoader.ts      # Lazy chunk loading
├── pages/
│   ├── ReplayViewer.tsx       # Main replay + strategy layout
│   └── SessionPicker.tsx      # Session list
└── utils/events.ts            # Flag state machine (YELLOW/CLEAR/GREEN/SC)

data/
├── tracks/               # Static circuit polylines (24 circuits, committed)
└── replays/              # Generated bundles per session (gitignored)

scripts/
└── generate_static_tracks.py
```

---

## Development

### Run tests

```bash
python3 -m pytest tests/ -q
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Frontend can't reach API | Ensure `docker compose ps` shows `api` and `frontend` running |
| Replay stuck / `failed` | Check `docker compose logs -f worker`; retry pipeline or replay curl |
| Strategy panel empty | Run full pipeline, not replay-only |
| Yellow flag stuck on map | Hard-refresh browser; ensure latest `events.ts` (handles `CLEAR`) |
| Stale code in worker | `docker compose restart worker` |

### Known limitations

- Replay build time depends on OpenF1 API rate limits (HTTP 429); worker retries with exponential backoff
- Location data ~3–4 Hz; playback interpolates between samples
- Madrid (`circuit_key=153`) has no MultiViewer geometry yet
- Replay bundles are not committed to git — rebuild per session after clone
- Estimated lap in strategy panel is approximate (±1 lap) from median lap time

---

## License

See repository for license details.
