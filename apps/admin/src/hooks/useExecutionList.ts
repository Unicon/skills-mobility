import type { ExecutionSummary } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { useEffect, useState } from "react";

const POLL_INTERVAL_MS = 3000;

export function useExecutionList({ correlationId }: { correlationId?: string } = {}) {
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = () => {
      orchestratorApi
        .listExecutions({ correlationId })
        .then((result) => {
          if (cancelled) return;
          setExecutions(result);
          setError(null);
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(e instanceof Error ? e : new Error(String(e)));
        });
    };

    fetchOnce();
    const timer = setInterval(fetchOnce, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [correlationId]);

  return { executions, error };
}
