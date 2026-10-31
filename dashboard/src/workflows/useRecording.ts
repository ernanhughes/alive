import { useEffect, useState } from "react";
import type { Recording } from "./contracts";
import { recording } from "./client";

export function useRecording(
  id: string,
  token: string,
  live = true,
  refresh = 0,
) {
  const [state, setState] = useState<{
    key: string;
    data: Recording | null;
    error: string;
    loading: boolean;
  }>({ key: "", data: null, error: "", loading: false });
  const key = token + "|" + id;
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false,
      delay = 2000,
      failures = 0,
      inflight = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setState({ key, data: null, error: "", loading: !!id });
    async function load() {
      if (!id || !token || document.visibilityState === "hidden" || inflight)
        return;
      inflight = true;
      try {
        const data = await recording(id, token, controller.signal);
        if (disposed) return;
        setState({ key, data, error: "", loading: false });
        delay = 2000;
        failures = 0;
        if (live && !data.run.terminal) timer = setTimeout(load, delay);
      } catch {
        if (disposed) return;
        setState((s) => ({
          ...s,
          key,
          error:
            "History unavailable, disconnected or integrity check failed. Refresh to retry.",
          loading: false,
        }));
        failures++;
        delay = Math.min(delay * 2, 30000);
        if (live && failures < 5) timer = setTimeout(load, delay);
      } finally {
        inflight = false;
      }
    }
    function visibility() {
      clearTimeout(timer);
      if (document.visibilityState === "visible") void load();
    }
    void load();
    document.addEventListener("visibilitychange", visibility);
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [id, token, live, refresh]);
  return state.key === key
    ? state
    : { key, data: null, error: "", loading: !!id };
}
