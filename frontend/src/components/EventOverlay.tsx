import type { ActiveFlagState, ReplayEvent } from "../types";

interface EventOverlayProps {
  activeFlags: ActiveFlagState[];
  incidents: ReplayEvent[];
}

function bannerForFlag(flag: ActiveFlagState): string | null {
  if (flag.type === "SC") {
    return "SAFETY CAR";
  }
  if (flag.type === "VSC") {
    return "VIRTUAL SAFETY CAR";
  }
  if (flag.type === "RED") {
    return "RED FLAG";
  }
  if (flag.type === "YELLOW" || flag.type === "DOUBLE_YELLOW") {
    return flag.sector ? `YELLOW FLAG — SECTOR ${flag.sector}` : "YELLOW FLAG";
  }
  return null;
}

export function EventOverlay({ activeFlags, incidents }: EventOverlayProps) {
  const primaryFlag = activeFlags.find(
    (flag) => flag.type === "SC" || flag.type === "VSC" || flag.type === "RED",
  );
  const yellowFlag = activeFlags.find(
    (flag) => flag.type === "YELLOW" || flag.type === "DOUBLE_YELLOW",
  );

  const banner = primaryFlag
    ? bannerForFlag(primaryFlag)
    : yellowFlag
      ? bannerForFlag(yellowFlag)
      : null;

  return (
    <div className="event-overlay">
      {banner && <div className="flag-banner">{banner}</div>}
      <div className="incident-list">
        {incidents.slice(-3).map((incident, index) => (
          <div key={`${incident.t_ms}-${index}`} className="incident-toast">
            {incident.message}
          </div>
        ))}
      </div>
    </div>
  );
}
