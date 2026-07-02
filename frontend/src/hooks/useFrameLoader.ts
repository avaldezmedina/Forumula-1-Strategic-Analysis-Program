import { useEffect, useRef, useState } from "react";
import type { ReplayFrame } from "../types";
import { fetchReplayFrames } from "../api";

export function useFrameLoader(sessionKey: number, chunkDurationMs: number, durationMs: number) {
  const [frames, setFrames] = useState<ReplayFrame[]>([]);
  const [loading, setLoading] = useState(true);
  const loadedRangesRef = useRef<Array<{ start: number; end: number }>>([]);

  const mergeFrames = (incoming: ReplayFrame[]) => {
    setFrames((prev) => {
      const map = new Map<number, ReplayFrame>();
      for (const frame of prev) {
        map.set(frame.t_ms, frame);
      }
      for (const frame of incoming) {
        map.set(frame.t_ms, frame);
      }
      return Array.from(map.values()).sort((a, b) => a.t_ms - b.t_ms);
    });
  };

  const loadRange = async (fromMs: number, toMs: number) => {
    const clampedTo = Math.min(durationMs, toMs);
    const overlaps = loadedRangesRef.current.some(
      (range) => range.start <= fromMs && range.end >= clampedTo,
    );
    if (overlaps) {
      return;
    }

    const payload = await fetchReplayFrames(sessionKey, fromMs, clampedTo);
    mergeFrames(payload);
    loadedRangesRef.current.push({ start: fromMs, end: clampedTo });
  };

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      loadedRangesRef.current = [];
      setFrames([]);

      try {
        await loadRange(0, chunkDurationMs);
        if (!cancelled && durationMs > chunkDurationMs) {
          await loadRange(chunkDurationMs, chunkDurationMs * 2);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [sessionKey, chunkDurationMs, durationMs]);

  const ensureRangeLoaded = async (currentMs: number) => {
    const buffer = chunkDurationMs;
    const fromMs = Math.max(0, currentMs - buffer / 2);
    const toMs = Math.min(durationMs, currentMs + buffer * 1.5);
    await loadRange(fromMs, toMs);
  };

  return { frames, loading, ensureRangeLoaded };
}
