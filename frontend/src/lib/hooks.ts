"use client";
import { useCallback, useEffect, useState } from "react";

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    loading: boolean;
  }>({ loading: true });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function run() {
      // Schedule state with the asynchronous request, not during effect setup/render.
      await Promise.resolve();
      if (controller.signal.aborted) return;
      setState({ loading: true });
      try {
        const data = await load(controller.signal);
        if (!controller.signal.aborted) setState({ data, loading: false });
      } catch (error) {
        if (!controller.signal.aborted)
          setState({
            error:
              error instanceof Error
                ? error.message
                : "Unable to load records.",
            loading: false,
          });
      }
    }
    void run();
    return () => controller.abort();
  }, [load, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  return { ...state, reload };
}
