"use client";
import { useState } from "react";
import { CriticalDetailChips, MeaningFindings, MeaningStatusBadge, NegationLists, OptimizeResults } from "@/components/analysis";
import { TokenizerSelect } from "@/components/domain";
import { IconCopy, IconLock, IconPlus, IconTrash } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, ErrorState, Field, PageHeader, Segmented, TokenizerTag } from "@/components/ui";
import { api } from "@/lib/api/client";
import {
  LANGUAGE_CODES, MAX_PROTECTED_TERMS, MAX_TEXT_CHARS, type ApplyEditsResponse, type LanguageCode, type MeaningCheckResponse,
  type OptimizeMode, type OptimizeResponse, type TextEdit, type TokenizeResponse,
} from "@/lib/api/types";
import { fmtDec, fmtInt, fmtPct, pctChange } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { logActivity } from "@/lib/storage";
import { editsForDecision } from "@/lib/optimize";

/** What the rule-based meaning check (rules_v2) covers today for each protected category. */
const PROTECTED: { name: string; checked: "yes" | "partly" | "no"; note: string }[] = [
  { name: "Names", checked: "partly", note: "Latin-script capitalised names and acronyms; Indic names only if you list them as protected terms" },
  { name: "Numbers & amounts", checked: "yes", note: "digits in any script, ₹/Rs/$ amounts" },
  { name: "Dates & times", checked: "partly", note: "numeric and English formats" },
  { name: "Locations", checked: "partly", note: "Latin-script capitalised place names only (same heuristic as names)" },
  { name: "Units & quantities", checked: "partly", note: "Latin units (kg, km, GB, days…) compared; Indic-script units not yet" },
  { name: "Negation", checked: "partly", note: "word lists; Indic lists await native-speaker review" },
  { name: "Conditions", checked: "partly", note: "English words (if, unless, until, otherwise…); Indic words not yet" },
  { name: "Questions", checked: "yes", note: "each question mark is kept" },
  { name: "Safety instructions", checked: "no", note: "not checked yet" },
  { name: "Output format", checked: "no", note: "not checked yet" },
  { name: "Explicit constraints", checked: "partly", note: "English must/only/at least/at most…, plus quoted text, code, URLs and emails" },
];

const MODES: { value: OptimizeMode; label: string; risk: string }[] = [
  { value: "safe", label: "Safe", risk: "Lossless formatting only: spaces, blank lines, invisible characters, repeated punctuation, long separator lines. Repeated sentences are only suggested." },
  { value: "balanced", label: "Balanced", risk: "Also removes exact repeats of an earlier sentence or line that contain no critical detail, and applies wording rules approved in the Linguistic Review (none approved yet). Wording is changed only in the prompt's own language." },
  { value: "aggressive", label: "Aggressive", risk: "Same automatic edits as balanced, plus suggestions that may change meaning (wording still pending native-speaker review, script variants). Nothing extra is applied without your approval." },
];
const ENCODING_PAIR: Record<string, string> = { cl100k_base: "o200k_base", o200k_base: "cl100k_base" };

interface Counted { label: string; text: string; result: TokenizeResponse; meaning: MeaningCheckResponse | null }

function parseTerms(s: string): string[] {
  return [...new Set(s.split(",").map((t) => t.trim()).filter(Boolean))].slice(0, MAX_PROTECTED_TERMS);
}

export default function OptimizeView() {
  const [original, setOriginal] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "auto">("auto");
  const [mode, setMode] = useState<OptimizeMode>("safe");
  const [bothEncodings, setBothEncodings] = useState(true);
  const [termsText, setTermsText] = useState("");
  const terms = parseTerms(termsText);
  const encodings = bothEncodings && ENCODING_PAIR[tokenizer] ? [tokenizer, ENCODING_PAIR[tokenizer]!] : [tokenizer];
  const termTooLong = terms.some((t) => t.length > 200);
  const [candidates, setCandidates] = useState<{ id: number; text: string }[]>([]);
  const [nextId, setNextId] = useState(1);
  const [viewIdx, setViewIdx] = useState(1);
  const [copied, setCopied] = useState(false);

  const tooLong = [original, ...candidates.map((c) => c.text)].some((t) => t.length > MAX_TEXT_CHARS);
  const canCount = !!original.trim() && !!tokenizer && !tooLong && !termTooLong && candidates.every((c) => c.text.trim());

  const count = useAction(async (signal): Promise<Counted[]> => {
    const items = [{ label: "Original", text: original }, ...candidates.map((c, i) => ({ label: `Your rewrite ${i + 1}`, text: c.text }))];
    const out = await Promise.all(items.map(async (it, i) => ({
      ...it,
      result: await api.tokenize({ text: it.text, tokenizer, language }, { signal }),
      meaning: i === 0 ? null : await api.meaningCheck({ original, candidate: it.text, language, protected_terms: terms }, { signal }),
    })));
    const o = out[0]!.result.token_count;
    const best = Math.min(...out.slice(1).map((c) => c.result.token_count), o);
    logActivity({ kind: "optimize", href: "/optimize", summary: `Original ${fmtInt(o)} tokens · best rewrite ${fmtInt(best)} · ${tokenizer}` });
    setViewIdx(out.length > 1 ? 1 : 0);
    return out;
  });

  const optimize = useAction(async (signal) => {
    const [res, details] = await Promise.all([
      api.optimize({ text: original, language, mode, tokenizers: encodings, protected_terms: terms }, { signal }),
      api.criticalDetails({ text: original, language, protected_terms: terms }, { signal }),
    ]);
    const t = res.token_counts[0];
    logActivity({ kind: "optimize", href: "/optimize", summary: `Optimizer ${res.mode}: ${fmtInt(t?.before)} → ${fmtInt(t?.after)} tokens · ${res.accepted.length} accepted · ${res.suggestions.length} suggested · ${tokenizer}` });
    return { res, details };
  });
  const canOptimize = !!original.trim() && !!tokenizer && original.length <= MAX_TEXT_CHARS && !termTooLong;

  const rows = count.data;
  const orig = rows?.[0];
  const viewing = rows?.[viewIdx] ?? null;

  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch { /* blocked */ } };

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F03 · F05 · Live</Badge> <Badge tone="outline">Rules-based</Badge></>}
        title="Prompt Optimizer"
        lede="Shorter prompts, same meaning. Deterministic rules propose edits; an edit is applied only if it saves tokens and the rule-based meaning check finds every critical detail intact. Anything uncertain is returned as a suggestion for you to review, and the original is kept when nothing qualifies. You can also measure and check your own rewrites."
      />

      <div className="grid-2" style={{ marginBottom: 24, alignItems: "start" }}>
        <section className="panel">
          <div className="panel-head"><div><h2>Original prompt</h2><p>Always kept unchanged</p></div></div>
          <div className="panel-body stack">
            <textarea className="textarea indic" rows={8} aria-label="Original prompt" value={original} onChange={(e) => setOriginal(e.target.value)} placeholder="Paste the prompt you want to shorten…" />
            <div className="row">
              <Field label="Target tokenizer" htmlFor="op-tok" hint="Candidates are counted with this encoding"><div style={{ minWidth: 200 }}><TokenizerSelect id="op-tok" value={tokenizer} onChange={setTokenizer} /></div></Field>
              <Field label="Language" htmlFor="op-lang" hint="Needed for Romanized or code-mixed text">
                <select id="op-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode | "auto")}>
                  <option value="auto">Auto (from script)</option>
                  {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Protected terms" htmlFor="op-terms" hint="Comma-separated names or phrases that must stay exactly as written" error={termTooLong ? "Each term must be at most 200 characters." : undefined}>
              <input id="op-terms" className="input indic" value={termsText} onChange={(e) => setTermsText(e.target.value)} placeholder="e.g. Bengaluru One, Ramesh" />
            </Field>
            <div className="row" style={{ alignItems: "center" }}>
              <Segmented label="Optimization mode" value={mode} onChange={setMode}
                options={MODES.map((m) => ({ value: m.value, label: m.label }))} />
            </div>
            <p className="small muted" aria-live="polite">{MODES.find((m) => m.value === mode)?.risk}</p>
            <label className="checkbox"><input type="checkbox" checked={bothEncodings} onChange={(e) => setBothEncodings(e.target.checked)} disabled={!ENCODING_PAIR[tokenizer]} /> Also measure with {ENCODING_PAIR[tokenizer] ?? "the other encoding"} (an edit must save tokens under one encoding and add none under the other)</label>
          </div>
        </section>

        <section className="stack">
          <div className="panel">
            <div className="panel-head">
              <div><h2>Automatic optimization</h2><p><code>POST /api/optimize</code> · {mode} mode · every edit measured with {tokenizer || "the selected tokenizer"} and checked for meaning</p></div>
            </div>
            <div className="panel-body stack">
              <p className="small muted">
                Deterministic rules only; nothing is paraphrased or summarised. Every edit is measured with {encodings.join(" and ") || "the selected tokenizer"} and kept only if it saves tokens and the meaning check passes.
              </p>
              {optimize.data && (
                <div className="btn-row">
                  <MeaningStatusBadge status={optimize.data.res.meaning_check.status} />
                  <span className="small num">{fmtInt(optimize.data.res.token_counts[0]?.before)} → {fmtInt(optimize.data.res.token_counts[0]?.after)} tokens</span>
                  <span className="small subtle">{optimize.data.res.accepted.length} accepted · {optimize.data.res.suggestions.length} suggested · {optimize.data.res.rejected.length} rejected</span>
                </div>
              )}
            </div>
            <div className="panel-foot btn-row">
              <button className="btn btn-primary" disabled={!canOptimize || optimize.loading} onClick={() => optimize.run()}>{optimize.loading && <span className="spinner" />} Optimize</button>
              {!original.trim() && <span className="small subtle">Enter a prompt first.</span>}
              {original.length > MAX_TEXT_CHARS && <span className="field-error">Over {fmtInt(MAX_TEXT_CHARS)} characters.</span>}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head">
              <div><h2>Your rewrites</h2><p>Human concise rewrites (a PRD §7.6 condition), counted with the live tokenizer</p></div>
              <button className="btn btn-sm btn-secondary" disabled={candidates.length >= 5} onClick={() => { setCandidates((c) => [...c, { id: nextId, text: original }]); setNextId((n) => n + 1); }}><IconPlus /> Add rewrite</button>
            </div>
            <div className="panel-body stack">
              {candidates.length === 0 && <p className="small muted">No rewrites yet. Add one to measure how many tokens a shorter version saves. It starts as a copy of the original.</p>}
              {candidates.map((c, i) => (
                <div key={c.id} className="field">
                  <div className="field-label"><span>Rewrite {i + 1}</span>
                    <button className="btn btn-ghost btn-sm btn-icon" aria-label={`Remove rewrite ${i + 1}`} onClick={() => setCandidates((cs) => cs.filter((x) => x.id !== c.id))}><IconTrash /></button>
                  </div>
                  <textarea className="textarea indic" style={{ minHeight: 80 }} value={c.text} aria-label={`Rewrite ${i + 1}`} onChange={(e) => setCandidates((cs) => cs.map((x) => (x.id === c.id ? { ...x, text: e.target.value } : x)))} />
                </div>
              ))}
            </div>
            <div className="panel-foot btn-row">
              <button className="btn btn-primary" disabled={!canCount || count.loading} onClick={() => count.run()}>{count.loading && <span className="spinner" />} Count original{candidates.length ? " + rewrites" : ""}</button>
              {tooLong && <span className="field-error">A text is over {fmtInt(MAX_TEXT_CHARS)} characters.</span>}
            </div>
          </div>
        </section>
      </div>

      {optimize.error && <ErrorState error={optimize.error} onRetry={() => optimize.run()} />}
      {optimize.data && <div style={{ marginBottom: 32 }}><OptimizeResults res={optimize.data.res} /></div>}
      {optimize.data && <DecisionPanel key={optimize.data.res.original + optimize.data.res.mode + optimize.data.res.optimized} res={optimize.data.res} language={language} tokenizer={tokenizer} terms={terms} />}

      {count.error && <ErrorState error={count.error} onRetry={() => count.run()} />}

      {rows && orig && (
        <section className="stack-lg" aria-live="polite">
          <div className="btn-row"><h2 style={{ fontSize: 20 }}>Candidate ledger</h2><CountStatusBadge status={orig.result.status} /><TokenizerTag t={orig.result.tokenizer} /></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Candidate</th><th className="num">Tokens</th><th className="num">Change</th><th className="num">Tokens / word</th><th>Critical details</th><th>Semantic score</th><th>Decision</th><th /></tr></thead>
              <tbody>
                {rows.map((r, i) => {
                  const d = pctChange(orig.result.token_count, r.result.token_count);
                  return (
                    <tr key={i} className={i === 0 ? "is-ref" : undefined}>
                      <td><b>{r.label}</b><div className="small subtle clip" style={{ maxWidth: 320 }}>{r.text}</div></td>
                      <td className="num">{fmtInt(r.result.token_count)}</td>
                      <td className="num">{i === 0 ? "—" : <span className={d !== null && d < 0 ? "delta-neg" : d !== null && d > 0 ? "delta-pos" : ""}>{fmtPct(d)}</span>}</td>
                      <td className="num">{fmtDec(r.result.tokens_per_word)}</td>
                      <td>{i === 0 || !r.meaning ? "—" : <><MeaningStatusBadge status={r.meaning.status} /><div className="small subtle">{r.meaning.missing_count} missing · {r.meaning.added_count} added</div></>}</td>
                      <td>{i === 0 ? "—" : <Badge tone="planned" title="rules_v2 compares critical details only; no semantic similarity model is used">Not measured</Badge>}</td>
                      <td>{i === 0 ? <Badge tone="blue">Retained</Badge> : <Decision meaning={r.meaning} fewer={r.result.token_count < orig.result.token_count} />}</td>
                      <td>{i > 0 && <button className="btn btn-sm btn-ghost" onClick={() => setViewIdx(i)} aria-pressed={viewIdx === i}>View</button>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {rows.length > 1 && (
            <Callout tone="info" title="Nothing is sent or replaced automatically">
              A rewrite is shown as eligible only when it uses fewer tokens and the rule-based check found every critical detail intact. That check compares
              numbers, amounts, dates, negations, quotes, code, URLs, emails and protected terms; it is not a semantic score and not a guarantee of equal meaning.
              An increase in tokens is reported, not hidden.
            </Callout>
          )}

          {viewing && viewIdx > 0 && (
            <div className="side-by-side">
              <div>
                <div className="side-label"><span className="kicker">Original</span><span className="num small">{fmtInt(orig.result.token_count)} tokens</span></div>
                <p className="indic" style={{ whiteSpace: "pre-wrap" }}>{orig.text}</p>
              </div>
              <div>
                <div className="side-label">
                  <span className="kicker">{viewing.label}</span>
                  <span className="btn-row"><span className="num small">{fmtInt(viewing.result.token_count)} tokens</span>
                    <button className="btn btn-sm btn-ghost" onClick={() => copy(viewing.text)}><IconCopy /> {copied ? "Copied" : "Copy"}</button></span>
                </div>
                <p className="indic" style={{ whiteSpace: "pre-wrap" }}>{viewing.text}</p>
              </div>
            </div>
          )}
          {viewing && viewIdx > 0 && viewing.meaning && (
            <section className="panel">
              <div className="panel-head"><div><h2>Meaning check — {viewing.label}</h2><p>Original vs this rewrite (rules_v2)</p></div></div>
              <div className="panel-body"><MeaningFindings mc={viewing.meaning} /></div>
            </section>
          )}
        </section>
      )}

      <section style={{ marginTop: 32 }} className="stack">
        <div className="section-title"><h2>Meaning preservation</h2></div>
        <section className="panel">
          <div className="panel-head"><div><h2>Critical details in the original</h2><p><code>POST /api/critical-details</code> · found when you run Optimize; these are never edited</p></div></div>
          <div className="panel-body stack">
            {optimize.data ? (
              <>
                <CriticalDetailChips details={optimize.data.details.details} />
                <NegationLists mc={optimize.data.details} />
                {optimize.data.details.warnings.length > 0 && <Callout tone="info">{optimize.data.details.warnings.join(" ")}</Callout>}
              </>
            ) : <p className="small muted">Run Optimize to list the numbers, amounts, dates, negations, quotes, code, URLs, emails and protected terms found in your prompt.</p>}
          </div>
        </section>
        <ul className="check-list" aria-label="Protected detail categories">
          {PROTECTED.map((p) => (
            <li key={p.name}><span className="dot" />
              <span>{p.name}
                <span className="small subtle" style={{ display: "block" }}>{p.checked === "yes" ? "Checked" : p.checked === "partly" ? "Partly checked" : "Not checked yet"}{p.checked === "no" ? "" : `: ${p.note}`}</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="btn-row">
          <span className="small subtle"><IconLock /> Approval is required by default (PRD §22): choose the version to use in “Your decision” above and copy it. Sending to a model happens in AI Chat (needs a configured LLM).</span>
        </div>
      </section>
    </>
  );
}

function Decision({ meaning, fewer }: { meaning: MeaningCheckResponse | null; fewer: boolean }) {
  if (!meaning) return <Badge tone="outline">Not checked</Badge>;
  if (meaning.status === "changed") return <Badge tone="red" title="A critical detail is missing, added or altered">Rejected · details changed</Badge>;
  if (meaning.status === "at_risk") return <Badge tone="neutral" title={meaning.risks.join(" ")}>Needs your review</Badge>;
  if (!fewer) return <Badge tone="outline" title="Details intact, but not fewer tokens">No token saving</Badge>;
  return <Badge tone="blue" title="Fewer tokens and no critical-detail change found (not a guarantee of meaning)">Eligible · your choice</Badge>;
}

/** Accept or reject the optimized version, optionally approving suggestions (re-checked by the backend). */
function DecisionPanel({ res, language, tokenizer, terms }: { res: OptimizeResponse; language: LanguageCode | "auto"; tokenizer: string; terms: string[] }) {
  const [choice, setChoice] = useState<"original" | "optimized">(res.changed ? "optimized" : "original");
  const [approved, setApproved] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);
  const approvable = res.suggestions.map((s, i) => ({ s, i })).filter(({ s }) => s.kind !== "script_variant");
  const apply = useAction(async (signal): Promise<ApplyEditsResponse> => {
    const chosen = approvable.filter(({ i }) => approved.has(i)).map(({ s }) => s);
    const edits: TextEdit[] = editsForDecision(res.accepted, chosen);
    return api.applyEdits({ original: res.original, edits, language, tokenizer, protected_terms: terms }, { signal });
  });
  const final = choice === "original" ? res.original : apply.data && approved.size ? apply.data.text : res.optimized;
  const first = res.token_counts[0];
  const copy = async () => { try { await navigator.clipboard.writeText(final); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch { /* blocked */ } };
  const toggle = (i: number) => setApproved((prev) => { const n = new Set(prev); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  return (
    <section className="panel" style={{ marginBottom: 32 }} aria-label="Your decision">
      <div className="panel-head"><div><h2>Your decision</h2><p>Nothing is used until you choose. Approved suggestions are applied by the backend and checked again.</p></div></div>
      <div className="panel-body stack">
        <div className="btn-row" role="radiogroup" aria-label="Version to use">
          <label className="checkbox"><input type="radio" name="op-choice" checked={choice === "original"} onChange={() => setChoice("original")} /> Keep the original</label>
          <label className="checkbox"><input type="radio" name="op-choice" checked={choice === "optimized"} onChange={() => setChoice("optimized")} disabled={!res.changed && approvable.length === 0} /> Use the optimized version{res.changed ? "" : " (no automatic change)"}</label>
        </div>
        {choice === "optimized" && approvable.length > 0 && (
          <div className="stack">
            <span className="small">Also apply these suggestions (each needs your approval):</span>
            {approvable.map(({ s, i }) => (
              <label key={i} className="checkbox small">
                <input type="checkbox" checked={approved.has(i)} onChange={() => toggle(i)} />
                <span><b>{s.kind.replace(/_/g, " ")}</b> · “{s.before.trim().slice(0, 60) || "∅"}” → “{s.after.slice(0, 60) || "removed"}” · {s.reason}{s.risks.length ? ` · ${s.risks.join(" ")}` : ""}</span>
              </label>
            ))}
            <div className="btn-row">
              <button className="btn btn-secondary btn-sm" disabled={approved.size === 0 || apply.loading} onClick={() => apply.run()}>{apply.loading && <span className="spinner" />} Apply approved suggestions</button>
              {apply.data && approved.size > 0 && (
                <span className="small">
                  <MeaningStatusBadge status={apply.data.meaning_check.status} /> {fmtInt(apply.data.tokens_before)} → {fmtInt(apply.data.tokens_after)} tokens ({apply.data.tokenizer.name}) · {apply.data.applied_count} edits
                  {!apply.data.allowed && <span className="field-error"> · the meaning check reports a changed critical detail (removing a repeated copy lowers that detail's count); check the result before using it</span>}
                </span>
              )}
            </div>
            {apply.error && <ErrorState error={apply.error} onRetry={() => apply.run()} />}
          </div>
        )}
        <div className="side-label"><span className="kicker">Final prompt ({choice === "original" ? "original" : apply.data && approved.size ? "optimized + approved suggestions" : "optimized"})</span>
          <button className="btn btn-sm btn-ghost" onClick={copy}><IconCopy /> {copied ? "Copied" : "Copy"}</button></div>
        <p className="indic" style={{ whiteSpace: "pre-wrap" }} aria-label="Final prompt">{final}</p>
        {choice === "optimized" && !(apply.data && approved.size) && first && (
          <p className="small subtle num">{first.tokenizer.name}: {fmtInt(first.before)} → {fmtInt(first.after)} tokens ({fmtDec(first.saved_pct)}% saved)</p>
        )}
      </div>
    </section>
  );
}
