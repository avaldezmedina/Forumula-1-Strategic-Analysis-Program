import type { InterpolatedCar } from "../hooks/usePlaybackEngine";
import type { ActiveFlagState, ReplayDriver, ReplayTrack, TrackPoint } from "../types";

interface TrackMapProps {
  track: ReplayTrack;
  cars: InterpolatedCar[];
  drivers: ReplayDriver[];
  activeFlags: ActiveFlagState[];
  selectedDriver?: number | null;
  onSelectDriver?: (driverNumber: number) => void;
}

function pointsToPath(points: TrackPoint[]): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  return `M ${first.x} ${first.y} ` + rest.map((p) => `L ${p.x} ${p.y}`).join(" ");
}

function sectorPath(points: TrackPoint[], startIndex: number, endIndex: number): string {
  return pointsToPath(points.slice(startIndex, endIndex + 1));
}

// Both axes are now independently normalised to [0, 1], so a fixed square
// viewBox always fits the track.  A small padding keeps the car circles from
// being clipped at the edges.
const PAD = 0.03;
const VB = `-${PAD} -${PAD} ${1 + 2 * PAD} ${1 + 2 * PAD}`;

// Element sizes relative to the [0, 1] coordinate space.
const CAR_RADIUS = 0.018;
const TRACK_STROKE = 0.010;
const SECTOR_STROKE = 0.016;
const FONT_SIZE = 0.014;

export function TrackMap({ track, cars, drivers, activeFlags, selectedDriver, onSelectDriver }: TrackMapProps) {
  const driverMap = new Map(drivers.map((d) => [d.driver_number, d]));
  const trackPath = pointsToPath(track.points);

  const yellowSectors = new Set(
    activeFlags
      .filter((f) => f.type === "YELLOW" || f.type === "DOUBLE_YELLOW")
      .map((f) => f.sector)
      .filter((s): s is number => s !== undefined),
  );

  const hasSafetyCar = activeFlags.some((f) => f.type === "SC" || f.type === "VSC");
  const hasRedFlag = activeFlags.some((f) => f.type === "RED");

  return (
    <svg viewBox={VB} className="track-map" preserveAspectRatio="xMidYMid meet">
      {/* Background */}
      <rect x={-PAD} y={-PAD} width={1 + 2 * PAD} height={1 + 2 * PAD} fill="#0b0f14" />

      {/* Sector colour underlays */}
      {track.sectors.map((sector) => {
        const isYellow = yellowSectors.has(sector.sector);
        return (
          <path
            key={sector.sector}
            d={sectorPath(track.points, sector.start_index, sector.end_index)}
            stroke={isYellow ? "#f6d32d" : "#2c3a4f"}
            strokeWidth={isYellow ? SECTOR_STROKE : TRACK_STROKE * 1.8}
            fill="none"
            strokeLinecap="round"
            opacity={isYellow ? 1 : 0.6}
          />
        );
      })}

      {/* Main track outline */}
      <path
        d={trackPath}
        stroke="#d7dde7"
        strokeWidth={TRACK_STROKE}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Car dots */}
      {cars.map((car) => {
        const driver = driverMap.get(car.driverNumber);
        const color = driver?.team_color ?? "#ffffff";
        const isSelected = selectedDriver === car.driverNumber;
        return (
          <g
            key={car.driverNumber}
            onClick={() => onSelectDriver?.(car.driverNumber)}
            style={{ cursor: onSelectDriver ? "pointer" : "default" }}
          >
            {isSelected && (
              <circle
                cx={car.x}
                cy={car.y}
                r={CAR_RADIUS * 1.7}
                fill="none"
                stroke="#fff"
                strokeWidth={CAR_RADIUS * 0.25}
                opacity={0.85}
              />
            )}
            <circle
              cx={car.x}
              cy={car.y}
              r={CAR_RADIUS}
              fill={color}
              stroke={isSelected ? "#fff" : "#000"}
              strokeWidth={CAR_RADIUS * 0.2}
            />
            <text
              x={car.x}
              y={car.y + FONT_SIZE * 0.38}
              textAnchor="middle"
              fontSize={FONT_SIZE}
              fill="#fff"
              fontWeight="700"
            >
              {car.driverNumber}
            </text>
          </g>
        );
      })}

      {/* Safety car / VSC full-track amber border */}
      {hasSafetyCar && (
        <rect
          x={-PAD}
          y={-PAD}
          width={1 + 2 * PAD}
          height={1 + 2 * PAD}
          fill="none"
          stroke="#ffb000"
          strokeWidth={TRACK_STROKE * 1.5}
          opacity={0.9}
        />
      )}

      {/* Red flag overlay */}
      {hasRedFlag && (
        <rect x={-PAD} y={-PAD} width={1 + 2 * PAD} height={1 + 2 * PAD} fill="#ff0000" opacity={0.15} />
      )}
    </svg>
  );
}
