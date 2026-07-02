import type { ActiveFlagState, ReplayEvent } from "../types";

const CLEARING_TYPES = new Set(["GREEN"]);

export function computeActiveFlags(events: ReplayEvent[], currentMs: number): ActiveFlagState[] {
  const active: ActiveFlagState[] = [];

  for (const event of events) {
    if (event.t_ms > currentMs) {
      break;
    }

    if (CLEARING_TYPES.has(event.type)) {
      if (event.type === "GREEN") {
        active.length = 0;
      }
      continue;
    }

    if (event.type === "YELLOW" || event.type === "DOUBLE_YELLOW") {
      active.push({
        type: event.type,
        sector: event.sector ?? undefined,
        message: event.message,
      });
      continue;
    }

    if (event.type === "SC" || event.type === "VSC" || event.type === "RED") {
      active.push({
        type: event.type,
        message: event.message,
      });
    }
  }

  return active;
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
