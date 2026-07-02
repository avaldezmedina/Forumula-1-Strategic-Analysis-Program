const SPEEDS = [0.5, 1, 2, 5, 10];

interface SpeedControlProps {
  playbackRate: number;
  onChange: (rate: number) => void;
}

export function SpeedControl({ playbackRate, onChange }: SpeedControlProps) {
  return (
    <div className="speed-control">
      <span className="speed-label">Speed</span>
      {SPEEDS.map((speed) => (
        <button
          key={speed}
          type="button"
          className={speed === playbackRate ? "speed-button active" : "speed-button"}
          onClick={() => onChange(speed)}
        >
          {speed}x
        </button>
      ))}
    </div>
  );
}
