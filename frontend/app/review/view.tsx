"use client";
import { useEffect, useMemo, useState } from "react";
import { Badge, Callout, EmptyState, ErrorState, Field, LoadingRows, PageHeader } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { ReviewEntry, ReviewDecision } from "@/lib/api/types";
import { LANGUAGES } from "@/lib/languages";
import {
  buildDecisionsFile, draftProblems, loadDrafts, loadReviewer, saveDrafts, saveReviewer,
  type LocalDecision, type ReviewAction, type YesNo,
} from "@/lib/review";
import { useApi } from "@/lib/hooks";

const LANGS = ["kn", "hi", "ta", "te", "en"] as const;
const CATEGORY_LABEL: Record<string, string> = {
  negation: "Negation", condition: "Condition", constraint: "Constraint", question: "Question", entity: "Names & titles",
  quantity: "Numbers, units & dates", redundant_expression: "Redundant expression", shortening: "Shorter wording",
  register: "Formal / informal", romanized: "Romanized",
};
const DECISION_TONE: Record<ReviewDecision, "neutral" | "blue" | "red" | "outline"> = {
  pending_review: "neutral", approved: "blue", rejected: "red", corrected: "blue",
};

function blankDecision(id: string, decision: ReviewAction): LocalDecision {
  return { id, decision, notes: "", correction: {}, preserves_meaning: "", changes_register: "", safe_for_auto: "" };
}

export default function ReviewView() {
  const [lang, setLang] = useState<(typeof LANGS)[number]>("kn");
  const [reviewer, setReviewer] = useState("");
  const [drafts, setDrafts] = useState<Record<string, LocalDecision>>({});
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("pending_review");
  const [query, setQuery] = useState("");
  const [exportMsg, setExportMsg] = useState("");
  const data = useApi((signal) => api.reviewLanguage(lang, { signal }), [lang]);
  const summary = useApi((signal) => api.reviewSummary({ signal }), []);

  useEffect(() => { setReviewer(loadReviewer()); }, []);
  useEffect(() => { setDrafts(loadDrafts(lang)); setExportMsg(""); }, [lang]);
  const update = (next: Record<string, LocalDecision>) => { setDrafts(next); saveDrafts(lang, next); };
  const setDraft = (id: string, patch: Partial<LocalDecision> | null) => {
    const next = { ...drafts };
    if (patch === null) delete next[id];
    else next[id] = { ...(next[id] ?? blankDecision(id, "approved")), ...patch };
    update(next);
  };

  const entries = data.data?.entries ?? [];
  const categories = useMemo(() => [...new Set(entries.map((e) => e.category))], [entries]);
  const shown = entries.filter((e) =>
    (category === "all" || e.category === category)
    && (status === "all" || (status === "drafted" ? !!drafts[e.id] : e.decision === status))
    && (!query.trim() || `${e.expression} ${e.gloss} ${e.id} ${e.original ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())));
  const draftList = Object.values(drafts);
  const problems = draftProblems(reviewer, draftList);

  const download = () => {
    try {
      const file = buildDecisionsFile(lang, reviewer, draftList);
      const blob = new Blob([JSON.stringify(file, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `redutax-review-${lang}-${file.exported_at.slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      setExportMsg(`Exported ${file.decisions.length} decisions. Send the file to the team; nothing is approved until they merge it.`);
    } catch (err) {
      setExportMsg((err as Error).message);
    }
  };

  const counts = data.data?.counts;
  return (
    <>
      <PageHeader
        eyebrow={<>Research <Badge tone="blue">Native-speaker review</Badge> <Badge tone="outline">No code needed</Badge></>}
        title="Linguistic Review"
        lede="Kannada, Hindi, Tamil, Telugu and English speakers check the word lists and shorter wordings REDUTAX would use. Every entry was drafted by an AI assistant and is pending review. Your decisions stay in this browser until you export them; the team then merges the file. Nothing is approved automatically."
      />

      <Callout tone="info" title="How your decisions are used">
        Word lists (negation, conditions, constraints, question words, numbers, dates, titles, formality) only <b>protect</b> text: approving them lets the meaning check vouch for that language.
        A shorter wording is applied automatically only if you approve it <b>and</b> say it keeps the meaning, does not change the tone and is safe for automatic use. Otherwise it stays a suggestion that users must approve.
      </Callout>

      <section className="panel" style={{ margin: "16px 0" }}>
        <div className="panel-body row" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 16 }}>
          <Field label="Language" htmlFor="rv-lang">
            <select id="rv-lang" className="select" value={lang} onChange={(e) => setLang(e.target.value as (typeof LANGS)[number])}>
              {LANGS.map((l) => <option key={l} value={l}>{LANGUAGES[l].name} · {LANGUAGES[l].native}</option>)}
            </select>
          </Field>
          <Field label="Your name (signs every decision)" htmlFor="rv-name">
            <input id="rv-name" className="input" value={reviewer} placeholder="e.g. Kavya R." onChange={(e) => { setReviewer(e.target.value); saveReviewer(e.target.value); }} />
          </Field>
          <Field label="Category" htmlFor="rv-cat">
            <select id="rv-cat" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="all">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c] ?? c}</option>)}
            </select>
          </Field>
          <Field label="Show" htmlFor="rv-status">
            <select id="rv-status" className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="pending_review">Pending review</option>
              <option value="drafted">My draft decisions</option>
              <option value="approved">Approved</option>
              <option value="corrected">Corrected</option>
              <option value="rejected">Rejected</option>
              <option value="all">All</option>
            </select>
          </Field>
          <Field label="Search" htmlFor="rv-q">
            <input id="rv-q" className="input indic" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="word, meaning or id" />
          </Field>
        </div>
        {counts && (
          <div className="panel-foot btn-row" aria-label="Review status">
            <span className="small">In the project data:</span>
            <Badge tone="neutral">{counts.pending_review ?? 0} pending</Badge>
            <Badge tone="blue">{(counts.approved ?? 0) + (counts.corrected ?? 0)} approved</Badge>
            <Badge tone="red">{counts.rejected ?? 0} rejected</Badge>
            <span className="small">· your drafts in this browser: <b>{draftList.length}</b></span>
            {summary.data && <span className="small subtle">· automatic wording rules for {LANGUAGES[lang].name}: {summary.data.languages[lang]?.auto_rules ?? 0}</span>}
          </div>
        )}
      </section>

      {data.error && <ErrorState error={data.error} onRetry={data.reload} />}
      {data.loading && <LoadingRows rows={6} />}
      {!data.loading && data.data && shown.length === 0 && <EmptyState title="Nothing to show">No entries match these filters.</EmptyState>}

      <div className="stack">
        {shown.map((e) => <EntryCard key={e.id} e={e} draft={drafts[e.id]} onChange={(p) => setDraft(e.id, p)} />)}
      </div>

      <section className="panel" style={{ marginTop: 24 }} aria-label="Export decisions">
        <div className="panel-head"><div><h2>Send your decisions</h2><p>{data.data?.how_to_submit}</p></div></div>
        <div className="panel-body stack">
          {problems.length > 0 && draftList.length > 0 && <Callout tone="warn" title="Before exporting">{problems.join(" ")}</Callout>}
          <div className="btn-row">
            <button className="btn btn-primary" disabled={problems.length > 0} onClick={download}>Export {draftList.length} decisions (JSON)</button>
            <button className="btn btn-ghost btn-sm" disabled={draftList.length === 0} onClick={() => update({})}>Clear my drafts</button>
          </div>
          {exportMsg && <p className="small" role="status">{exportMsg}</p>}
          <p className="small subtle">Prefer a spreadsheet? Ask the team for the {LANGUAGES[lang].name} sheet (export_review_sheet.py); fill the columns in capitals and send it back.</p>
        </div>
      </section>
    </>
  );
}

function YesNoPick({ label, value, onChange, name }: { label: string; value: YesNo; onChange: (v: YesNo) => void; name: string }) {
  return (
    <div className="small" role="radiogroup" aria-label={label}>
      <span>{label}: </span>
      {(["yes", "no"] as const).map((v) => (
        <label key={v} className="checkbox" style={{ display: "inline-flex", marginRight: 8 }}>
          <input type="radio" name={name} checked={value === v} onChange={() => onChange(v)} /> {v}
        </label>
      ))}
    </div>
  );
}

function EntryCard({ e, draft, onChange }: { e: ReviewEntry; draft?: LocalDecision; onChange: (p: Partial<LocalDecision> | null) => void }) {
  const rewrite = e.original !== null;
  return (
    <section className="panel" aria-label={`Entry ${e.id}`}>
      <div className="panel-head">
        <div>
          <h2 className="indic" style={{ fontSize: 18 }}>{e.expression}</h2>
          <p>{e.gloss}</p>
        </div>
        <div className="btn-row">
          <Badge tone="outline">{CATEGORY_LABEL[e.category] ?? e.category}</Badge>
          <Badge tone="outline">{e.script}</Badge>
          <Badge tone={DECISION_TONE[e.decision]}>{e.decision.replace("_", " ")}</Badge>
          {draft && <Badge tone="blue">your draft: {draft.decision}</Badge>}
        </div>
      </div>
      <div className="panel-body stack">
        {rewrite && (
          <div className="side-by-side">
            <div><div className="side-label"><span className="kicker">Original wording</span></div><p className="indic">{e.original}</p></div>
            <div><div className="side-label"><span className="kicker">Proposed shorter wording</span></div><p className="indic">{e.proposed || "(removed)"}</p></div>
          </div>
        )}
        {rewrite && <p className="small subtle">Drafter&apos;s guess (please check): keeps meaning <b>{e.preserves_meaning}</b> · changes tone <b>{e.changes_register}</b> · safe for automatic use <b>{e.safe_for_auto ? "yes" : "no"}</b></p>}
        {!rewrite && <p className="small subtle">Used to {e.detect_as === "register" ? "notice changes of politeness or formality" : `recognise ${e.detect_as}`} ({e.match} match). </p>}
        <p className="small"><b>Used today:</b> {e.use}</p>
        {e.note && <p className="small subtle">Note: {e.note}</p>}
        {e.reviewer && <p className="small">Reviewed by {e.reviewer} on {e.reviewed_at}{e.review_notes ? ` — ${e.review_notes}` : ""}</p>}
        <p className="small subtle">{e.provenance} · <code>{e.id}</code></p>

        <div className="btn-row" role="group" aria-label={`Decision for ${e.id}`}>
          {(["approved", "rejected", "corrected"] as const).map((d) => (
            <button key={d} className={`btn btn-sm ${draft?.decision === d ? "btn-primary" : "btn-secondary"}`} aria-pressed={draft?.decision === d}
              onClick={() => onChange({ decision: d })}>{d === "approved" ? "Approve" : d === "rejected" ? "Reject" : "Correct"}</button>
          ))}
          {draft && <button className="btn btn-sm btn-ghost" onClick={() => onChange(null)}>Undo</button>}
        </div>
        {draft && (
          <div className="stack">
            {draft.decision === "corrected" && (
              <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
                <Field label="Correct expression" htmlFor={`c-ex-${e.id}`}><input id={`c-ex-${e.id}`} className="input indic" value={draft.correction.expression ?? ""} onChange={(ev) => onChange({ correction: { ...draft.correction, expression: ev.target.value } })} /></Field>
                {rewrite && <Field label="Correct shorter wording" htmlFor={`c-pr-${e.id}`}><input id={`c-pr-${e.id}`} className="input indic" value={draft.correction.proposed ?? ""} onChange={(ev) => onChange({ correction: { ...draft.correction, proposed: ev.target.value } })} /></Field>}
                <Field label="Correct English meaning" htmlFor={`c-gl-${e.id}`}><input id={`c-gl-${e.id}`} className="input" value={draft.correction.gloss ?? ""} onChange={(ev) => onChange({ correction: { ...draft.correction, gloss: ev.target.value } })} /></Field>
              </div>
            )}
            {rewrite && draft.decision !== "rejected" && (
              <div className="row" style={{ flexWrap: "wrap", gap: 16 }}>
                <YesNoPick name={`pm-${e.id}`} label="Keeps the meaning" value={draft.preserves_meaning} onChange={(v) => onChange({ preserves_meaning: v })} />
                <YesNoPick name={`cr-${e.id}`} label="Changes tone or politeness" value={draft.changes_register} onChange={(v) => onChange({ changes_register: v })} />
                <YesNoPick name={`sa-${e.id}`} label="Safe to apply without asking" value={draft.safe_for_auto} onChange={(v) => onChange({ safe_for_auto: v })} />
              </div>
            )}
            <Field label="Notes (optional)" htmlFor={`n-${e.id}`}><textarea id={`n-${e.id}`} className="textarea indic" rows={2} value={draft.notes} onChange={(ev) => onChange({ notes: ev.target.value })} /></Field>
          </div>
        )}
      </div>
    </section>
  );
}
