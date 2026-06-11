import { useEffect, useRef, useState } from "react";
import type { Emission } from "../types";

export type StreamState = "connecting" | "live" | "down";

const MAX = 200;

/**
 * Subscribes to the service's SSE feed (/demo/stream). EventSource handles
 * reconnection; we de-dupe by emission seq and keep newest first.
 */
export function useEmissionStream() {
  const [emissions, setEmissions] = useState<Emission[]>([]);
  const [state, setState] = useState<StreamState>("connecting");
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    const es = new EventSource("/demo/stream");

    es.addEventListener("open", () => setState("live"));
    es.addEventListener("error", () => setState("down"));

    es.addEventListener("emission", (e) => {
      setState("live");
      try {
        const rec = JSON.parse((e as MessageEvent).data) as Emission;
        if (seen.current.has(rec.seq)) return;
        seen.current.add(rec.seq);
        setEmissions((prev) => [rec, ...prev].slice(0, MAX));
      } catch {
        /* ignore malformed frame */
      }
    });

    return () => es.close();
  }, []);

  const clear = () => {
    seen.current.clear();
    setEmissions([]);
  };

  return { emissions, state, clear };
}
