import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { useEffect, useState } from "react";

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export function useExecution(executionId: string | null) {
  const [execution, setExecution] = useState<ExecutionMetadata | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!executionId) {
      setExecution(null);
      setError(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const fetchOnce = () => {
      orchestratorApi
        .getExecution(executionId)
        .then((result) => {
          if (cancelled) return;
          setExecution(result);
          setError(null);
          if (TERMINAL_STATUSES.has(result.status)) {
            clearInterval(timer);
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(e instanceof Error ? e : new Error(String(e)));
        });
    };

    fetchOnce();
    timer = setInterval(fetchOnce, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [executionId]);

  return { execution, error };
}
