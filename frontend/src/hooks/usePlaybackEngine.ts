import { useCallback, useEffect, useRef, useState } from "react";
import type { CarState, ReplayFrame } from "../types";

export interface InterpolatedCar extends CarState {
  driverNumber: number;
}

export interface PlaybackState {
  currentMs: number;
  isPlaying: boolean;
  playbackRate: number;
  cars: InterpolatedCar[];
}

function interpolateCars(
  frameA: ReplayFrame,
  frameB: ReplayFrame,
  ratio: number,
  driverNumbers: number[],
): InterpolatedCar[] {
  const cars: InterpolatedCar[] = [];

  for (const driverNumber of driverNumbers) {
    const key = String(driverNumber);
    const a = frameA.cars[key];
    const b = frameB.cars[key];
    const source = a ?? b;
    if (!source) {
      continue;
    }

    if (a && b) {
      cars.push({
        driverNumber,
        x: a.x + ratio * (b.x - a.x),
        y: a.y + ratio * (b.y - a.y),
        position: b.position ?? a.position,
        interval: b.interval ?? a.interval,
      });
    } else {
      cars.push({
        driverNumber,
        x: source.x,
        y: source.y,
        position: source.position,
        interval: source.interval,
      });
    }
  }

  return cars.sort((left, right) => (left.position ?? 99) - (right.position ?? 99));
}

function findFramePair(frames: ReplayFrame[], tMs: number): [ReplayFrame, ReplayFrame, number] | null {
  if (frames.length === 0) {
    return null;
  }

  if (tMs <= frames[0].t_ms) {
    return [frames[0], frames[0], 0];
  }

  const last = frames[frames.length - 1];
  if (tMs >= last.t_ms) {
    return [last, last, 0];
  }

  for (let i = 0; i < frames.length - 1; i += 1) {
    const current = frames[i];
    const next = frames[i + 1];
    if (current.t_ms <= tMs && tMs <= next.t_ms) {
      const span = next.t_ms - current.t_ms;
      const ratio = span === 0 ? 0 : (tMs - current.t_ms) / span;
      return [current, next, ratio];
    }
  }

  return [last, last, 0];
}

export function usePlaybackEngine(
  frames: ReplayFrame[],
  driverNumbers: number[],
  durationMs: number,
) {
  const [currentMs, setCurrentMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [cars, setCars] = useState<InterpolatedCar[]>([]);
  const lastTickRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  const updateCars = useCallback(
    (tMs: number) => {
      const pair = findFramePair(frames, tMs);
      if (!pair) {
        setCars([]);
        return;
      }

      const [frameA, frameB, ratio] = pair;
      setCars(interpolateCars(frameA, frameB, ratio, driverNumbers));
    },
    [frames, driverNumbers],
  );

  useEffect(() => {
    updateCars(currentMs);
  }, [currentMs, updateCars]);

  useEffect(() => {
    if (!isPlaying) {
      lastTickRef.current = null;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
      return;
    }

    const tick = (timestamp: number) => {
      if (lastTickRef.current === null) {
        lastTickRef.current = timestamp;
      }

      const delta = timestamp - lastTickRef.current;
      lastTickRef.current = timestamp;

      setCurrentMs((prev) => {
        const next = Math.min(durationMs, prev + delta * playbackRate);
        if (next >= durationMs) {
          setIsPlaying(false);
        }
        return next;
      });

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [isPlaying, playbackRate, durationMs]);

  const seek = useCallback(
    (tMs: number) => {
      const clamped = Math.max(0, Math.min(durationMs, tMs));
      setCurrentMs(clamped);
      updateCars(clamped);
    },
    [durationMs, updateCars],
  );

  return {
    currentMs,
    isPlaying,
    playbackRate,
    cars,
    setIsPlaying,
    setPlaybackRate,
    seek,
  };
}
