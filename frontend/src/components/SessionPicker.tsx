import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSessions, queueReplayBuild } from "../api";
import type { SessionSummary } from "../types";

export function SessionPicker() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState<number | null>(null);

  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessions();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleBuildReplay = async (sessionKey: number) => {
    setBuilding(sessionKey);
    try {
      await queueReplayBuild(sessionKey, true);
      alert(`Replay build queued for session ${sessionKey}. Refresh in a few minutes.`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to queue replay build");
    } finally {
      setBuilding(null);
    }
  };

  if (loading) {
    return <div className="panel">Loading sessions...</div>;
  }

  if (error) {
    return (
      <div className="panel error">
        <p>{error}</p>
        <button type="button" onClick={loadSessions}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="panel">
      <h1>F1 Race Replay</h1>
      <p>Select a session to watch the broadcast-style track replay.</p>
      <table className="session-table">
        <thead>
          <tr>
            <th>Session</th>
            <th>Location</th>
            <th>Year</th>
            <th>Replay</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr key={session.session_key}>
              <td>{session.meeting_name ?? session.session_key}</td>
              <td>{session.location ?? "-"}</td>
              <td>{session.year}</td>
              <td>{session.replay_status}</td>
              <td>
                {session.replay_status === "ready" ? (
                  <Link to={`/replay/${session.session_key}`}>Watch</Link>
                ) : (
                  <button
                    type="button"
                    disabled={building === session.session_key}
                    onClick={() => handleBuildReplay(session.session_key)}
                  >
                    {building === session.session_key ? "Building..." : "Build Replay"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
