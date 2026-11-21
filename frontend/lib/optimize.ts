/**
 * Optimizer decision helpers (Feature 3). The backend applies edits; this only chooses which.
 */
import type { EditReport, TextEdit } from "./api/types";

/**
 * Edits to send to POST /api/pipeline/apply when the user keeps the accepted edits and approves
 * some suggestions. An accepted edit that overlaps an approved suggestion is superseded by it
 * (e.g. spaces inside a removed repeated sentence), because the backend refuses overlapping edits.
 */
export function editsForDecision(accepted: EditReport[], approved: EditReport[]): TextEdit[] {
  const kept = accepted.filter((a) => !approved.some((c) => a.start < c.end && c.start < a.end));
  return [...kept, ...approved]
    .map((e) => ({ start: e.start, end: e.end, after: e.after }))
    .sort((x, y) => x.start - y.start);
}
