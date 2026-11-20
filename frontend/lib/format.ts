/** Number and label formatting. All metrics use tabular numerals in the UI. */

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-IN").format(n);
}

export function fmtDec(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

/** A tokenization ratio, rendered as "2.31×". Callers must label it a tokenization ratio, not a cost. */
export function fmtRatio(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n.toFixed(2)}×`;
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

/** Money with enough precision for sub-cent per-request costs. */
export function fmtMoney(n: number | null | undefined, currency: string): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const digits = n !== 0 && Math.abs(n) < 0.01 ? 6 : 4;
  return `${currency} ${n.toFixed(digits)}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function shortHash(h: string | null | undefined, n = 10): string {
  if (!h) return "—";
  return h.length > n ? `${h.slice(0, n)}…` : h;
}

/** Percentage change from `from` to `to`; negative means fewer tokens. */
export function pctChange(from: number, to: number): number | null {
  if (from <= 0) return null;
  return ((to - from) / from) * 100;
}
