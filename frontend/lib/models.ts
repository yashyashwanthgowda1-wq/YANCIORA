"use client";
/**
 * User-entered models (Features 4, 7, 8, 9), kept in this browser only and sent to the backend
 * with `source: "user"` so every result labels them as unverified. The team's verified models
 * live in config/models.yaml on the server (GET /api/models).
 */
import { useCallback, useEffect, useState } from "react";
import type { ModelSpec } from "./api/types";
import { useApi } from "./hooks";
import { api } from "./api/client";

const KEY = "redutax:custom-models";
const EVENT = "redutax:custom-models";

export function loadCustomModels(): ModelSpec[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as ModelSpec[]) : [];
    return Array.isArray(list) ? list.filter((m) => m && typeof m.id === "string" && typeof m.provider === "string") : [];
  } catch {
    return [];
  }
}

export function saveCustomModels(list: ModelSpec[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list.map((m) => ({ ...m, source: "user" }))));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* storage unavailable (private mode): the list lives for this page only */
  }
}

/** Registry models (server) + this browser's user-entered models. */
export function useModelCatalog() {
  const registry = useApi((signal) => api.models({ signal }), []);
  const [custom, setCustom] = useState<ModelSpec[]>([]);
  useEffect(() => {
    const update = () => setCustom(loadCustomModels());
    update();
    window.addEventListener(EVENT, update);
    window.addEventListener("storage", update);
    return () => { window.removeEventListener(EVENT, update); window.removeEventListener("storage", update); };
  }, []);
  const setCustomModels = useCallback((list: ModelSpec[]) => { setCustom(list); saveCustomModels(list); }, []);
  return { registry, custom, setCustomModels, all: [...(registry.data?.models ?? []), ...custom] };
}
