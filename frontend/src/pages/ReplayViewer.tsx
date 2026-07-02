import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchReplayEvents,
  fetchReplayMetadata,
  fetchReplayTrack,
} from "../api";
import { EventOverlay } from "../components/EventOverlay";
import { Leaderboard } from "../components/Leaderboard";
import { SpeedControl } from "../components/SpeedControl";
import { Timeline } from "../components/Timeline";
import { TrackMap } from "../components/TrackMap";
import { useFrameLoader } from "../hooks/useFrameLoader";
import { usePlaybackEngine } from "../hooks/usePlaybackEngine";
import type { ReplayEvent, ReplayMetadata, ReplayTrack } from "../types";
import { computeActiveFlags, getRecentIncidents } from "../utils/events";

export function ReplayViewer() {
  const { sessionKey = "" } = useParams();
  const numericSessionKey = Number(sessionKey);

  const [metadata, setMetadata] = useState<ReplayMetadata | null>(null);
  const [track, setTrack] = useState<ReplayTrack | null>(null);
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadReplayData() {
      setLoading(true);
      setError(null);

      try {
        const [meta, trackData, eventData] = await Promise.all([
          fetchReplayMetadata(numericSessionKey),
          fetchReplayTrack(numericSessionKey),
          fetchReplayEvents(numericSessionKey),
        ]);

        if (!cancelled) {
          setMetadata(meta);
          setTrack(trackData);
          setEvents(eventData);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load replay");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (!Number.isNaN(numericSessionKey)) {
      loadReplayData();
    }

    return () => {
      cancelled = true;
    };
  }, [numericSessionKey]);

  const { frames, loading: framesLoading, ensureRangeLoaded } = useFrameLoader(
    numericSessionKey,
    metadata?.chunk_duration_ms ?? 60_000,
    metadata?.duration_ms ?? 0,
  );

  const driverNumbers = metadata?.drivers.map((driver) => driver.driver_number) ?? [];

  const playback = usePlaybackEngine(frames, driverNumbers, metadata?.duration_ms ?? 0);

  useEffect(() => {
    if (!metadata) {
      return;
    }

    ensureRangeLoaded(playback.currentMs).catch(() => {
      // Frame prefetch failures should not stop playback.
    });
  }, [metadata, playback.currentMs, ensureRangeLoaded]);

  if (loading) {
    return <div className="panel">Loading replay...</div>;
  }

  if (error || !metadata || !track) {
    return (
      <div className="panel error">
        <p>{error ?? "Replay unavailable"}</p>
        <Link to="/">Back to sessions</Link>
      </div>
    );
  }

  const activeFlags = computeActiveFlags(events, playback.currentMs);
  const incidents = getRecentIncidents(events, playback.currentMs);

  return (
    <div className="replay-layout">
      <header className="replay-header">
        <div>
          <Link to="/">← Sessions</Link>
          <h1>
            {metadata.meeting_name} — {metadata.location} ({metadata.year})
          </h1>
        </div>
        <SpeedControl playbackRate={playback.playbackRate} onChange={playback.setPlaybackRate} />
      </header>

      <div className="replay-main">
        <div className="track-panel">
          <TrackMap
            track={track}
            cars={playback.cars}
            drivers={metadata.drivers}
            activeFlags={activeFlags}
          />
          <EventOverlay activeFlags={activeFlags} incidents={incidents} />
          {framesLoading && <div className="loading-badge">Loading frames...</div>}
        </div>
        <Leaderboard cars={playback.cars} drivers={metadata.drivers} />
      </div>

      <Timeline
        currentMs={playback.currentMs}
        durationMs={metadata.duration_ms}
        isPlaying={playback.isPlaying}
        onTogglePlay={() => playback.setIsPlaying(!playback.isPlaying)}
        onSeek={playback.seek}
      />
    </div>
  );
}
