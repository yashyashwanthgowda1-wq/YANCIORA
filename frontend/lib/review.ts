/**
 * Native-speaker review decisions (drafts kept in this browser until exported).
 * The exported file is merged by the team with research/scripts/apply_review_decisions.py;
 * nothing here approves anything on the server.
 */
export type ReviewAction = "approved" | "rejected" | "corrected";
export type YesNo = "yes" | "no" | "";

export interface LocalDecision {
  id: string;
  decision: ReviewAction;
  notes: string;
  correction: { expression?: string; proposed?: string; gloss?: string };
  preserves_meaning: YesNo;
  changes_register: YesNo;
  safe_for_auto: YesNo;
}

export interface DecisionsFile {
  schema: "redutax-review-decisions/v1";
  language: string;
  reviewer: string;
  exported_at: string;
  decisions: {
    id: string; decision: ReviewAction; notes?: string; correction?: LocalDecision["correction"];
    preserves_meaning?: "yes" | "no"; changes_register?: "yes" | "no"; safe_for_auto?: boolean;
  }[];
}

const KEY = (lang: string) => `redutax:review:${lang}`;
const REVIEWER_KEY = "redutax:review:reviewer";

export function loadDrafts(lang: string): Record<string, LocalDecision> {
  try {
    const raw = window.localStorage.getItem(KEY(lang));
    const v = raw ? JSON.parse(raw) : {};
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

export function saveDrafts(lang: string, drafts: Record<string, LocalDecision>): void {
  try { window.localStorage.setItem(KEY(lang), JSON.stringify(drafts)); } catch { /* storage unavailable */ }
}

export function loadReviewer(): string {
  try { return window.localStorage.getItem(REVIEWER_KEY) ?? ""; } catch { return ""; }
}

export function saveReviewer(name: string): void {
  try { window.localStorage.setItem(REVIEWER_KEY, name); } catch { /* storage unavailable */ }
}

/** Problems that would make the merge script refuse the file (shown before exporting). */
export function draftProblems(reviewer: string, drafts: LocalDecision[]): string[] {
  const out: string[] = [];
  if (!reviewer.trim()) out.push("Enter your name: every decision must be signed by the reviewer.");
  for (const d of drafts) {
    const corr = Object.values(d.correction ?? {}).some((v) => (v ?? "").trim());
    if (d.decision === "corrected" && !corr) out.push(`${d.id}: “Correct” needs the corrected expression, shorter form or meaning.`);
  }
  if (drafts.length === 0) out.push("No decisions yet.");
  return out;
}

export function buildDecisionsFile(language: string, reviewer: string, drafts: LocalDecision[], now = new Date()): DecisionsFile {
  const problems = draftProblems(reviewer, drafts);
  if (problems.length) throw new Error(problems.join(" "));
  return {
    schema: "redutax-review-decisions/v1",
    language,
    reviewer: reviewer.trim(),
    exported_at: now.toISOString(),
    decisions: drafts.map((d) => {
      const correction = Object.fromEntries(Object.entries(d.correction ?? {}).filter(([, v]) => (v ?? "").trim()).map(([k, v]) => [k, v!.trim()]));
      return {
        id: d.id,
        decision: d.decision,
        ...(d.notes.trim() ? { notes: d.notes.trim() } : {}),
        ...(d.decision === "corrected" ? { correction } : {}),
        ...(d.preserves_meaning ? { preserves_meaning: d.preserves_meaning } : {}),
        ...(d.changes_register ? { changes_register: d.changes_register } : {}),
        ...(d.safe_for_auto ? { safe_for_auto: d.safe_for_auto === "yes" } : {}),
      };
    }),
  };
}
