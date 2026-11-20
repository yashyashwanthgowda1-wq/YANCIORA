"use client";
import { useState } from "react";
import { TokenizerSelect } from "@/components/domain";
import { IconCopy, IconLock, IconPlus, IconTrash } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, ErrorState, Field, InactiveFeature, PageHeader, TokenizerTag } from "@/components/ui";
import { api } from "@/lib/api/client";
import { PLANNED_ENDPOINTS } from "@/lib/api/planned";
import { MAX_TEXT_CHARS, type TokenizeResponse } from "@/lib/api/types";
import { fmtDec, fmtInt, fmtPct, pctChange } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { logActivity } from "@/lib/storage";

const PROTECTED = ["Names", "Numbers & amounts", "Dates & times", "Locations", "Units & quantities", "Negation", "Conditions", "Safety instructions", "Output format", "Explicit constraints"];

interface Counted { label: string; text: string; result: TokenizeResponse }

export default function OptimizeView() {
  const [original, setOriginal] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [allowScript, setAllowScript] = useState(false);
  const [candidates, setCandidates] = useState<{ id: number; text: string }[]>([]);
  const [nextId, setNextId] = useState(1);
  const [viewIdx, setViewIdx] = useState(1);
  const [copied, setCopied] = useState(false);

  const tooLong = [original, ...candidates.map((c) => c.text)].some((t) => t.length > MAX_TEXT_CHARS);
  const canCount = !!original.trim() && !!tokenizer && !tooLong && candidates.every((c) => c.text.trim());

  const count = useAction(async (signal): Promise<Counted[]> => {
    const items = [{ label: "Original", text: original }, ...candidates.map((c, i) => ({ label: `Your rewrite ${i + 1}`, text: c.text }))];
    const out = await Promise.all(items.map(async (it) => ({ ...it, result: await api.tokenize({ text: it.text, tokenizer }, { signal }) })));
    const o = out[0]!.result.token_count;
    const best = Math.min(...out.slice(1).map((c) => c.result.token_count), o);
    logActivity({ kind: "optimize", href: "/optimize", summary: `Original ${fmtInt(o)} tokens · best rewrite ${fmtInt(best)} · ${tokenizer}` });
    setViewIdx(out.length > 1 ? 1 : 0);
    return out;
  });

  const rows = count.data;
  const orig = rows?.[0];
  const viewing = rows?.[viewIdx] ?? null;

  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch { /* blocked */ } };

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F03 · F05</Badge> <Badge tone="outline">Partly available</Badge></>}
        title="Prompt Optimizer"
        lede="Shorter prompts, same meaning. A candidate is accepted only if every protected detail survives and it passes the semantic threshold; otherwise the original is kept. Automatic generation and meaning checks arrive in Phase 3. For now, you can measure your own rewrites with the live tokenizer."
      />

      <div className="grid-2" style={{ marginBottom: 24, alignItems: "start" }}>
        <section className="panel">
          <div className="panel-head"><div><h2>Original prompt</h2><p>Always kept unchanged</p></div></div>
          <div className="panel-body stack">
            <textarea className="textarea indic" rows={8} aria-label="Original prompt" value={original} onChange={(e) => setOriginal(e.target.value)} placeholder="Paste the prompt you want to shorten…" />
            <div className="row">
              <Field label="Target tokenizer" htmlFor="op-tok" hint="Candidates are counted with this encoding"><div style={{ minWidth: 200 }}><TokenizerSelect id="op-tok" value={tokenizer} onChange={setTokenizer} /></div></Field>
            </div>
            <label className="checkbox"><input type="checkbox" checked={allowScript} onChange={(e) => setAllowScript(e.target.checked)} /> Allow script or language alternatives (off by default; never assumed to save tokens)</label>
          </div>
        </section>

        <section className="stack">
          <InactiveFeature title="Automatic candidate generation" endpoint={PLANNED_ENDPOINTS.optimize}>
            Concise same-language rewrites{allowScript ? ", plus optional script alternatives," : ""} generated, counted with the target tokenizer, and the rejections logged.
          </InactiveFeature>
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
                      <td>{i === 0 ? "—" : <Badge tone="planned">Not evaluated</Badge>}</td>
                      <td>{i === 0 ? "—" : <Badge tone="planned">Not evaluated</Badge>}</td>
                      <td>{i === 0 ? <Badge tone="blue">Retained</Badge> : <Badge tone="outline">Not eligible</Badge>}</td>
                      <td>{i > 0 && <button className="btn btn-sm btn-ghost" onClick={() => setViewIdx(i)} aria-pressed={viewIdx === i}>View</button>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {rows.length > 1 && (
            <Callout tone="info" title="Selected: the original prompt">
              Under PRD §9.2 a candidate is eligible only after it passes the critical-detail and semantic checks. Those checks don't exist yet, so no candidate can be
              accepted, and the token change above is a measurement only. An increase in tokens is reported, not hidden.
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
        </section>
      )}

      <section style={{ marginTop: 32 }} className="stack">
        <div className="section-title"><h2>Meaning preservation</h2></div>
        <InactiveFeature title="Critical-detail and semantic checks" endpoint={PLANNED_ENDPOINTS.evaluateMeaning}>
          Each candidate will be checked for these protected details, and scored with a recorded multilingual similarity method and threshold.
        </InactiveFeature>
        <ul className="check-list" aria-label="Protected detail categories">
          {PROTECTED.map((p) => <li key={p}><span className="dot" />{p}</li>)}
        </ul>
        <div className="btn-row">
          <button className="btn btn-primary" disabled title="Needs meaning checks (Phase 3)"><IconLock /> Approve &amp; send</button>
          <span className="small subtle">Approval is required by default (PRD §22). It unlocks once a candidate can pass the checks.</span>
        </div>
      </section>
    </>
  );
}
