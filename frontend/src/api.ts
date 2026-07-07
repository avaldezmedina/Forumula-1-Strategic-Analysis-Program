import type {
  DriverPanel,
  ReplayEvent,
  ReplayFrame,
  ReplayMetadata,
  ReplayTrack,
  SessionSummary,
} from "./types";

const API_BASE = "";

export async function fetchSessions(): Promise<SessionSummary[]> {
  const response = await fetch(`${API_BASE}/sessions/`);
  if (!response.ok) {
    throw new Error("Failed to load sessions");
  }
  const payload = await response.json();
  return payload.sessions;
}

export async function fetchReplayMetadata(sessionKey: number): Promise<ReplayMetadata> {
  const response = await fetch(`${API_BASE}/replay/${sessionKey}/metadata`);
  if (!response.ok) {
    throw new Error("Replay metadata not available");
  }
  return response.json();
}

export async function fetchReplayTrack(sessionKey: number): Promise<ReplayTrack> {
  const response = await fetch(`${API_BASE}/replay/${sessionKey}/track`);
  if (!response.ok) {
    throw new Error("Replay track not available");
  }
  return response.json();
}

export async function fetchReplayEvents(sessionKey: number): Promise<ReplayEvent[]> {
  const response = await fetch(`${API_BASE}/replay/${sessionKey}/events`);
  if (!response.ok) {
    throw new Error("Replay events not available");
  }
  const payload = await response.json();
  return payload.events;
}

export async function fetchReplayFrames(
  sessionKey: number,
  fromMs: number,
  toMs: number,
): Promise<ReplayFrame[]> {
  const response = await fetch(
    `${API_BASE}/replay/${sessionKey}/frames?from_ms=${fromMs}&to_ms=${toMs}`,
  );
  if (!response.ok) {
    throw new Error("Replay frames not available");
  }
  const payload = await response.json();
  return payload.frames;
}

export async function fetchDriverPanel(sessionKey: number, driverNumber: number): Promise<DriverPanel> {
  const response = await fetch(`${API_BASE}/strategy/driver-panel/${sessionKey}/${driverNumber}`);
  if (!response.ok) {
    throw new Error(`Strategy data not available for driver ${driverNumber}`);
  }
  return response.json();
}

export async function queueReplayBuild(sessionKey: number, force = false): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/replay/${sessionKey}?force=${force}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to queue replay build");
  }
}
