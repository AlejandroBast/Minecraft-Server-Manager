"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface PollingState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/**
 * Consulta una función asíncrona al montar y, opcionalmente, cada `intervalMs`.
 *
 * La función se guarda en una referencia para que redefinirla en cada render
 * del componente no reinicie el temporizador.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 0): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const refresh = useCallback(async () => {
    try {
      setData(await fetcherRef.current());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const run = () => {
      if (active) {
        void refresh();
      }
    };

    run();
    if (intervalMs <= 0) {
      return () => {
        active = false;
      };
    }

    const timer = window.setInterval(run, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
