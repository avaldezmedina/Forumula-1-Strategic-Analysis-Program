import type { ActiveFlagState, ReplayEvent } from "../types";

export function computeActiveFlags(events: ReplayEvent[], currentMs: number): ActiveFlagState[] {
  // Use a Map so the same flag+sector can't stack up from repeated race control messages.
  // Key format: "YELLOW:2", "SC", "RED", etc.
  const flagMap = new Map<string, ActiveFlagState>();

  for (const event of events) {
    if (event.t_ms > currentMs) break;

    // OpenF1 uses CLEAR for sector-specific clearances and GREEN for track-wide.
    if (event.type === "CLEAR" || event.type === "GREEN") {
      if (event.sector != null) {
        flagMap.delete(`YELLOW:${event.sector}`);
        flagMap.delete(`DOUBLE_YELLOW:${event.sector}`);
      } else {
        flagMap.clear();
      }
      continue;
    }

    if (event.type === "YELLOW" || event.type === "DOUBLE_YELLOW") {
      const key = event.sector != null ? `${event.type}:${event.sector}` : event.type;
      flagMap.set(key, { type: event.type, sector: event.sector ?? undefined, message: event.message });
      continue;
    }

    if (event.type === "SC" || event.type === "VSC" || event.type === "RED") {
      // Track-wide conditions: keyed by type only, so a new SC replaces the old one.
      flagMap.set(event.type, { type: event.type, message: event.message });
    }
  }

  return Array.from(flagMap.values());
}

export function getRecentIncidents(events: ReplayEvent[], currentMs: number, windowMs = 8000) {
  return events.filter(
    (event) =>
      event.type === "INCIDENT" &&
      event.t_ms <= currentMs &&
      currentMs - event.t_ms <= windowMs,
  );
}

export function formatRaceTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
