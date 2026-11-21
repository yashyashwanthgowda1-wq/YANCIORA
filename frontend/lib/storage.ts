/**
 * Browser-only conveniences. Nothing here has to persist reliably.
 * Every access is wrapped because storage can be unavailable (private mode, blocked site data).
 * The activity log stores metadata only (tokenizer, counts, language), never the user's text.
 */
import type { LanguageCode } from "./api/types";

export interface Preferences {
  defaultTokenizer: string | null;
  interfaceLanguages: LanguageCode[];
  recordActivity: boolean;
  voiceNoticeAccepted: boolean;
}

export const DEFAULT_PREFS: Preferences = {
  defaultTokenizer: null,
  interfaceLanguages: ["kn", "hi", "ta", "te", "en"],
  recordActivity: true,
  voiceNoticeAccepted: false,
};

export interface ActivityEntry {
  at: string;
  kind: "count" | "compare" | "optimize" | "cost" | "models" | "chat" | "voice";
  summary: string;
  href: string;
}

const PREFS_KEY = "redutax.prefs.v1";
const ACTIVITY_KEY = "redutax.activity.v1";
const MAX_ACTIVITY = 12;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(key) : null;
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: preferences simply do not persist */
  }
}

export function loadPrefs(): Preferences {
  return { ...DEFAULT_PREFS, ...read<Partial<Preferences>>(PREFS_KEY, {}) };
}

export function savePrefs(p: Preferences): void {
  write(PREFS_KEY, p);
  try { window.dispatchEvent(new Event("redutax:prefs")); } catch { /* noop */ }
}

export function loadActivity(): ActivityEntry[] {
  const v = read<ActivityEntry[]>(ACTIVITY_KEY, []);
  return Array.isArray(v) ? v : [];
}

export function logActivity(entry: Omit<ActivityEntry, "at">): void {
  if (!loadPrefs().recordActivity) return;
  write(ACTIVITY_KEY, [{ ...entry, at: new Date().toISOString() }, ...loadActivity()].slice(0, MAX_ACTIVITY));
}

export function clearLocalData(): void {
  try {
    window.localStorage.removeItem(PREFS_KEY);
    window.localStorage.removeItem(ACTIVITY_KEY);
    window.dispatchEvent(new Event("redutax:prefs"));
  } catch { /* noop */ }
}
