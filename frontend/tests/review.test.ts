import { describe, expect, it } from "vitest";
import { buildDecisionsFile, draftProblems, type LocalDecision } from "@/lib/review";

const d = (over: Partial<LocalDecision>): LocalDecision => ({
  id: "kn-red-002", decision: "approved", notes: "", correction: {}, preserves_meaning: "", changes_register: "", safe_for_auto: "", ...over,
});

describe("review decisions export", () => {
  it("requires a reviewer name and at least one decision", () => {
    expect(draftProblems("", [d({})]).join(" ")).toMatch(/Enter your name/);
    expect(draftProblems("Kavya", []).join(" ")).toMatch(/No decisions/);
    expect(() => buildDecisionsFile("kn", " ", [d({})])).toThrow(/name/);
  });

  it("'Correct' needs a corrected field", () => {
    expect(draftProblems("Kavya", [d({ decision: "corrected" })]).join(" ")).toMatch(/needs the corrected/);
    const f = buildDecisionsFile("kn", "Kavya", [d({ decision: "corrected", correction: { proposed: " ಕೆಳಗಿನ " } })]);
    expect(f.decisions[0]).toMatchObject({ decision: "corrected", correction: { proposed: "ಕೆಳಗಿನ" } });
  });

  it("writes the schema the merge script accepts, with yes/no answers mapped", () => {
    const f = buildDecisionsFile("hi", "  Ravi  ", [
      d({ id: "hi-red-001", preserves_meaning: "yes", changes_register: "no", safe_for_auto: "yes", notes: " ok " }),
      d({ id: "hi-q-001", decision: "rejected" }),
    ], new Date("2026-11-21T00:00:00Z"));
    expect(f).toMatchObject({ schema: "redutax-review-decisions/v1", language: "hi", reviewer: "Ravi", exported_at: "2026-11-21T00:00:00.000Z" });
    expect(f.decisions[0]).toEqual({ id: "hi-red-001", decision: "approved", notes: "ok", preserves_meaning: "yes", changes_register: "no", safe_for_auto: true });
    expect(f.decisions[1]).toEqual({ id: "hi-q-001", decision: "rejected" });
  });
});
