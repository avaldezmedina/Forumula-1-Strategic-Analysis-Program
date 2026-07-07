import { useEffect, useState } from "react";
import { fetchDriverPanel } from "../api";
import type { DriverPanel, LapScore, StintAnalysis } from "../types";

interface DriverStrategyPanelProps {
  sessionKey: number;
  driverNumber: number;
  currentMs: number;
  onClose: () => void;
}

const COMPOUND_COLOR: Record<string, string> = {
  SOFT: "#e8002d",
  MEDIUM: "#f6d32d",
  HARD: "#e8edf5",
  INTERMEDIATE: "#52e252",
  WET: "#4fc3f7",
};

const RECOMMENDATION_CONFIG: Record<string, { label: string; className: string }> = {
  PIT_NOW:      { label: "PIT NOW",      className: "rec-pit-now" },
  CONSIDER_PIT: { label: "CONSIDER PIT", className: "rec-consider" },
  EXTEND:       { label: "EXTEND",       className: "rec-extend" },
  MONITOR:      { label: "MONITOR",      className: "rec-monitor" },
};

function formatLapTime(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(3).padStart(6, "0");
  return `${m}:${s}`;
}

function TyreBar({ ratio }: { ratio: number }) {
  const pct = Math.min(100, Math.round(ratio * 100));
  const color = pct < 60 ? "#52e252" : pct < 85 ? "#f6d32d" : "#e8002d";
  return (
    <div className="tyre-bar-track">
      <div className="tyre-bar-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
      <span className="tyre-bar-label">{pct}%</span>
    </div>
  );
}

function StintRow({ stint }: { stint: StintAnalysis }) {
  const color = COMPOUND_COLOR[stint.compound] ?? "#fff";
  return (
    <tr>
      <td>S{stint.stint_number}</td>
      <td>
        <span className="compound-dot" style={{ backgroundColor: color }} />
        {stint.compound}
      </td>
      <td>L{stint.lap_start}–{stint.lap_end}</td>
      <td>{formatLapTime(stint.avg_clean_lap_time_seconds)}</td>
      <td>+{stint.degradation_seconds_per_lap.toFixed(3)}s/lap</td>
    </tr>
  );
}

export function DriverStrategyPanel({
  sessionKey,
  driverNumber,
  currentMs,
  onClose,
}: DriverStrategyPanelProps) {
  const [panel, setPanel] = useState<DriverPanel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPanel(null);

    fetchDriverPanel(sessionKey, driverNumber)
      .then((data) => { if (!cancelled) { setPanel(data); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err.message); setLoading(false); } });

    return () => { cancelled = true; };
  }, [sessionKey, driverNumber]);

  // Derive estimated current lap from elapsed time.
  const estimatedLap = (() => {
    if (!panel?.estimated_lap_duration_ms) return null;
    return Math.max(1, Math.round(currentMs / panel.estimated_lap_duration_ms));
  })();

  // Find the closest scored lap at or before the current estimated lap.
  const currentScore: LapScore | null = (() => {
    if (!panel?.scores.length || estimatedLap == null) return null;
    const eligible = panel.scores.filter((s) => s.lap_number <= estimatedLap);
    return eligible.length ? eligible[eligible.length - 1] : panel.scores[0];
  })();

  const recConfig = currentScore
    ? (RECOMMENDATION_CONFIG[currentScore.recommendation] ?? { label: currentScore.recommendation, className: "rec-monitor" })
    : null;

  const teamColor = panel?.team_color ?? "#fff";

  return (
    <div className="driver-strategy-panel">
      <div className="dsp-header" style={{ borderLeftColor: teamColor }}>
        <div className="dsp-header-info">
          <span className="dsp-number" style={{ color: teamColor }}>{driverNumber}</span>
          <div>
            <div className="dsp-name">{panel?.driver_name ?? `Driver ${driverNumber}`}</div>
            <div className="dsp-team">{panel?.team_name ?? ""}</div>
          </div>
        </div>
        <button type="button" className="dsp-close" onClick={onClose} aria-label="Close">×</button>
      </div>

      {loading && <div className="dsp-state">Loading strategy data…</div>}
      {error && <div className="dsp-state dsp-error">No strategy data — run the analytics pipeline for this session first.</div>}

      {!loading && !error && panel && (
        <>
          {estimatedLap != null && (
            <div className="dsp-lap-badge">
              ~Lap {estimatedLap}
              {currentScore && (
                <>
                  <span className="dsp-sep">·</span>
                  Stint {currentScore.stint_number}
                  <span className="dsp-sep">·</span>
                  <span className="compound-dot" style={{ backgroundColor: COMPOUND_COLOR[currentScore.compound] ?? "#fff" }} />
                  {currentScore.compound}
                  <span className="dsp-sep">·</span>
                  Age: {currentScore.current_tyre_age_laps} laps
                </>
              )}
            </div>
          )}

          {currentScore && (
            <div className="dsp-section">
              <div className="dsp-section-label">TYRE LIFE</div>
              <TyreBar ratio={currentScore.tire_life_ratio} />
              <div className="dsp-tyre-meta">
                {currentScore.estimated_laps_remaining.toFixed(1)} laps remaining
                &nbsp;·&nbsp;
                deg {currentScore.current_degradation_seconds_per_lap.toFixed(3)}s/lap
              </div>
            </div>
          )}

          {recConfig && currentScore && (
            <div className="dsp-section">
              <div className="dsp-section-label">RECOMMENDATION</div>
              <div className={`dsp-rec ${recConfig.className}`}>
                {recConfig.label}
              </div>
              {currentScore.current_avg_clean_lap_time_seconds != null && (
                <div className="dsp-tyre-meta">
                  Current avg: {formatLapTime(currentScore.current_avg_clean_lap_time_seconds)}
                </div>
              )}
            </div>
          )}

          {panel.stints.length > 0 && (
            <div className="dsp-section">
              <div className="dsp-section-label">STINT HISTORY</div>
              <table className="dsp-stint-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tyre</th>
                    <th>Laps</th>
                    <th>Avg</th>
                    <th>Deg</th>
                  </tr>
                </thead>
                <tbody>
                  {panel.stints.map((stint) => (
                    <StintRow key={stint.stint_number} stint={stint} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {panel.scores.length === 0 && (
            <div className="dsp-state">No pit-window scores computed for this driver.</div>
          )}
        </>
      )}
    </div>
  );
}
