import { formatRaceTime } from "../utils/events";

interface TimelineProps {
  currentMs: number;
  durationMs: number;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onSeek: (ms: number) => void;
}

export function Timeline({
  currentMs,
  durationMs,
  isPlaying,
  onTogglePlay,
  onSeek,
}: TimelineProps) {
  const progress = durationMs === 0 ? 0 : (currentMs / durationMs) * 100;

  return (
    <div className="timeline">
      <button type="button" className="play-button" onClick={onTogglePlay}>
        {isPlaying ? "Pause" : "Play"}
      </button>
      <span className="time-label">{formatRaceTime(currentMs)}</span>
      <input
        type="range"
        min={0}
        max={durationMs}
        value={currentMs}
        onChange={(event) => onSeek(Number(event.target.value))}
        className="scrubber"
      />
      <span className="time-label">{formatRaceTime(durationMs)}</span>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
