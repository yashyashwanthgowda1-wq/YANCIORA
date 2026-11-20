"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import type { HealthResponse, TokenizersResponse } from "./api/types";
import { loadPrefs, type Preferences } from "./storage";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
}

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, "client_error", e instanceof Error ? e.message : String(e));
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

/** Runs `fn` on mount and whenever `deps` change; aborts stale requests. */
export function useApi<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    fn(ctrl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => {
        if (isAbort(e)) return;
        setState({ data: null, error: toApiError(e), loading: false });
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

/** Button-triggered action; starting a new call aborts the previous one. */
export function useAction<A extends unknown[], T>(fn: (signal: AbortSignal, ...args: A) => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: false });
  const ctrlRef = useRef<AbortController | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(async (...args: A): Promise<T | null> => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current(ctrl.signal, ...args);
      setState({ data, error: null, loading: false });
      return data;
    } catch (e) {
      if (isAbort(e)) return null;
      setState({ data: null, error: toApiError(e), loading: false });
      return null;
    }
  }, []);
  const reset = useCallback(() => {
    ctrlRef.current?.abort();
    setState({ data: null, error: null, loading: false });
  }, []);
  useEffect(() => () => ctrlRef.current?.abort(), []);
  return { ...state, run, reset };
}

export function useHealth() {
  return useApi<HealthResponse>((signal) => api.health({ signal }), []);
}

export function useTokenizers() {
  return useApi<TokenizersResponse>((signal) => api.tokenizers({ signal }), []);
}

/** Preferences from localStorage; null until mounted (avoids hydration mismatch). */
export function usePrefs(): Preferences | null {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  useEffect(() => {
    const update = () => setPrefs(loadPrefs());
    update();
    window.addEventListener("redutax:prefs", update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener("redutax:prefs", update);
      window.removeEventListener("storage", update);
    };
  }, []);
  return prefs;
}
