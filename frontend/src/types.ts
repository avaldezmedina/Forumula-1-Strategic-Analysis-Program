export interface ReplayDriver {
  driver_number: number;
  name: string;
  team_name?: string;
  team_color: string;
}

export interface ReplayChunk {
  index: number;
  file: string;
  start_ms: number;
  end_ms: number;
}

export interface ReplayMetadata {
  session_key: number;
  year: number;
  meeting_name?: string;
  location?: string;
  duration_ms: number;
  frame_interval_ms: number;
  chunk_duration_ms: number;
  drivers: ReplayDriver[];
  chunks: ReplayChunk[];
}

export interface TrackPoint {
  x: number;
  y: number;
}

export interface TrackSector {
  sector: number;
  start_index: number;
  end_index: number;
  start_dist: number;
  end_dist: number;
}

export interface ReplayTrack {
  points: TrackPoint[];
  sectors: TrackSector[];
}

export interface ReplayEvent {
  t_ms: number;
  type: string;
  category?: string;
  flag?: string;
  scope?: string;
  sector?: number;
  lap_number?: number;
  driver_number?: number;
  message: string;
}

export interface CarState {
  x: number;
  y: number;
  position?: number;
  interval?: string | number | null;
}

export interface ReplayFrame {
  t_ms: number;
  cars: Record<string, CarState>;
}

export interface SessionSummary {
  session_key: number;
  meeting_name?: string;
  location?: string;
  year: number;
  date_start?: string;
  replay_status: string;
}

export interface ActiveFlagState {
  type: string;
  sector?: number;
  message: string;
}

export interface StintAnalysis {
  stint_number: number;
  compound: string;
  lap_start: number;
  lap_end: number;
  clean_lap_count: number;
  avg_clean_lap_time_seconds: number;
  degradation_seconds_per_lap: number;
}

export interface LapScore {
  lap_number: number;
  stint_number: number;
  compound: string;
  current_tyre_age_laps: number;
  current_avg_clean_lap_time_seconds: number | null;
  current_degradation_seconds_per_lap: number;
  expected_laps_before_significant_deg: number;
  estimated_laps_remaining: number;
  recommendation: string;
  tire_life_ratio: number;
}

export interface DriverPanel {
  session_key: number;
  driver_number: number;
  driver_name: string;
  team_name: string | null;
  team_color: string | null;
  estimated_lap_duration_ms: number | null;
  stints: StintAnalysis[];
  scores: LapScore[];
}
