# Manual Replay Validation Checklist

Use this checklist after running the full pipeline for a known race session.

## Setup

1. Start services: `docker compose up --build`
2. Run migration: `docker compose exec api alembic upgrade head`
3. Queue pipeline for a race session with OpenF1 location data:
   `curl -X POST http://localhost:8000/sessions/pipeline/{session_key}`
4. Poll task status until `replay.status` is `success` or `skipped`.

## Validation

- [ ] `GET /replay/{session_key}/status` returns `ready`
- [ ] `GET /replay/{session_key}/metadata` includes drivers and chunk index
- [ ] `GET /replay/{session_key}/track` returns polyline points and 3 sectors
- [ ] `GET /replay/{session_key}/events` includes flag and incident entries
- [ ] `GET /replay/{session_key}/frames?from_ms=0&to_ms=60000` returns frames with car positions
- [ ] Frontend session list shows replay status
- [ ] Replay viewer renders track outline and moving car dots
- [ ] Playback works at 1x, 2x, and 5x
- [ ] Timeline scrubber jumps to selected race time
- [ ] Yellow flag period highlights affected sector
- [ ] SC/VSC period shows banner overlay
- [ ] Incident messages appear as toasts near the track map

## Known limitations

- OpenF1 location data is session-specific and sampled at ~3.7 Hz without lateral placement.
- Replay build time depends on OpenF1 API rate limits and session length.
