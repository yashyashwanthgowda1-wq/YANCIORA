"use client";
/**
 * Result views for Feature 3 (optimizer), Feature 5 (meaning check) and Feature 6 (script
 * variants). Presentation only: every number and status shown comes from the backend response.
 * Built from the existing design-system classes (panel, table, badge, callout); no new styles.
 */
import { useState } from "react";
import type {
  CriticalDetail, DetailCategory, EditReport, MeaningCheckResponse, MeaningStatus, OptimizeResponse,
  RejectedEdit, ScriptVariant, ScriptVariantsResponse, TokenizerRef,
} from "@/lib/api/types";
import { fmtDec, fmtInt, fmtRatio } from "@/lib/format";
import { IconCopy } from "./icons";
import { Badge, Callout, CountStatusBadge, TokenizerTag } from "./ui";

// ---------------------------------------------------------------- labels
export const CATEGORY_LABELS: Record<DetailCategory, string> = {
  code: "Code", url: "URL", email: "Email", quoted: "Quoted text", money: "Money", datetime: "Date / time",
  number: "Number", condition: "Condition", constraint: "Constraint", question: "Question",
  negation: "Negation", entity: "Name (Latin script)", protected_term: "Protected term",
};

const STATUS_TEXT: Record<MeaningStatus, { label: string; tone: "blue" | "neutral" | "red"; title: string }> = {
  preserved: { label: "Preserved", tone: "blue", title: "No rule found a problem. This is not a guarantee that the meaning is unchanged." },
  at_risk: { label: "At risk · review", tone: "neutral", title: "Critical details are kept, but a heuristic warning applies. Review before use." },
  changed: { label: "Changed", tone: "red", title: "A critical detail is missing, added or altered." },
};

export function MeaningStatusBadge({ status }: { status: MeaningStatus }) {
  const s = STATUS_TEXT[status];
  return <Badge tone={s.tone} title={s.title}>{s.label}</Badge>;
}

export function ReviewBadge() {
  return <Badge tone="outline" title="Not applied automatically. You decide.">Needs your review</Badge>;
}

/** Makes whitespace edits visible: space → ·, tab → →, newline → ↵. */
export function visible(s: string): string {
  if (s === "") return "∅ (removed)";
  return s.replace(/ /g, "·").replace(/\t/g, "→").replace(/\n/g, "↵").replace(/​/g, "[ZWSP]").replace(/­/g, "[SHY]");
}

function clip(s: string, n = 80): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function deltaText(d: Record<string, number> | null): string {
  if (!d) return "not measured";
  return Object.entries(d).map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`).join(" · ");
}

export function Bullets({ items }: { items: string[] }) {
  if (!items.length) return null;
  return <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{items.map((w, i) => <li key={i}>{w}</li>)}</ul>;
}

export function Limitations({ items, title = "Limitations" }: { items: string[]; title?: string }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  return (
    <Callout tone="neutral" title={
      <span className="btn-row">{title}
        <button className="btn btn-sm btn-ghost" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? "Hide" : `Show ${items.length}`}</button>
      </span>}>
      {open && <Bullets items={items} />}
    </Callout>
  );
}

// ---------------------------------------------------------------- Feature 5
export function MeaningFindings({ mc }: { mc: MeaningCheckResponse }) {
  const changed = mc.findings.filter((f) => f.state !== "kept");
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="btn-row">
        <MeaningStatusBadge status={mc.status} />
        <span className="small subtle">{mc.method} · {mc.missing_count} missing · {mc.added_count} added · {mc.findings.length - changed.length} kept</span>
      </div>
      {changed.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Detail</th><th>Value</th><th className="num">Original</th><th className="num">Candidate</th><th>State</th></tr></thead>
            <tbody>
              {changed.map((f, i) => (
                <tr key={i}>
                  <td>{CATEGORY_LABELS[f.category]}</td>
                  <td className="indic"><code>{f.example}</code></td>
                  <td className="num">{f.original_count}</td>
                  <td className="num">{f.candidate_count}</td>
                  <td><Badge tone={f.state === "missing" ? "red" : "neutral"}>{f.state}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {mc.risks.length > 0 && <Callout tone="warn" title="Why review is needed"><Bullets items={mc.risks} /></Callout>}
      {mc.warnings.length > 0 && <Callout tone="info"><Bullets items={mc.warnings} /></Callout>}
      <NegationLists mc={mc} />
    </div>
  );
}

export function NegationLists({ mc }: { mc: { negation_lexicons: MeaningCheckResponse["negation_lexicons"] } }) {
  if (!mc.negation_lexicons.length) return null;
  return (
    <p className="small subtle">
      Negation word lists: {mc.negation_lexicons.map((l) => `${l.id} (${l.review_status.replace("_", " ")})`).join(", ")}
    </p>
  );
}

export function CriticalDetailChips({ details }: { details: CriticalDetail[] }) {
  if (!details.length) return <p className="small muted">No critical details were detected in this text.</p>;
  return (
    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
      {details.map((d, i) => (
        <span key={i} className="badge badge-outline" title={`${CATEGORY_LABELS[d.category]} · compared as "${d.value}" · characters ${d.start}–${d.end}`}>
          <b>{CATEGORY_LABELS[d.category]}</b>&nbsp;<span className="indic">{clip(d.text, 40)}</span>
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Feature 3
const RISK_TEXT: Record<string, { label: string; tone: "blue" | "neutral" | "outline" | "red"; title: string }> = {
  lossless: { label: "Lossless", tone: "blue", title: "Formatting only: no word changed" },
  redundancy: { label: "Redundancy", tone: "neutral", title: "Removes an exact repeat of an earlier sentence" },
  wording: { label: "Wording", tone: "outline", title: "Changes wording using an approved rule" },
  meaning_change: { label: "May change meaning", tone: "red", title: "Unreviewed wording or a script change: never applied without your approval" },
};

export function RiskBadge({ risk }: { risk?: string }) {
  const r = RISK_TEXT[risk ?? "lossless"] ?? RISK_TEXT.lossless!;
  return <Badge tone={r.tone} title={r.title}>{r.label}</Badge>;
}

function EditRows({ edits, kind }: { edits: (EditReport & { stage?: RejectedEdit["stage"]; meaning_status?: string; risks?: string[]; kind?: string })[]; kind: "accepted" | "suggested" | "rejected" }) {
  return (
    <tbody>
      {edits.map((e, i) => (
        <tr key={i}>
          <td>
            <code className="small">{e.rule}</code>
            <div className="btn-row" style={{ marginTop: 2 }}>
              <RiskBadge risk={e.risk} />
              {e.approval_required ? <Badge tone="outline" title="Not applied unless you approve it">Approval required</Badge> : null}
              {e.language && <span className="small subtle">{e.language}</span>}
            </div>
            {e.source && <div className="small subtle">rule {e.source}</div>}
            {kind === "rejected" && e.stage && <div><Badge tone={e.stage === "meaning" ? "red" : "outline"}>{e.stage}</Badge></div>}
            {kind === "suggested" && e.kind && <div className="small subtle">{e.kind.replace(/_/g, " ")}</div>}
          </td>
          <td className="indic"><code>{clip(visible(e.before))}</code> → <code>{clip(visible(e.after))}</code></td>
          <td className="num small">{deltaText(e.token_delta)}{e.tokens_before && e.tokens_after && (
            <div className="subtle">{Object.keys(e.tokens_before).map((k) => `${k} ${e.tokens_before![k]}→${e.tokens_after![k]}`).join(" · ")}</div>)}</td>
          <td className="small">
            {kind === "suggested" && e.meaning_status && <div className="btn-row" style={{ marginBottom: 4 }}><MeaningStatusBadge status={e.meaning_status as MeaningStatus} /><ReviewBadge /></div>}
            {e.reason}
            {kind === "suggested" && e.risks && e.risks.length > 0 && <Bullets items={e.risks} />}
          </td>
        </tr>
      ))}
    </tbody>
  );
}

function EditTable({ title, hint, edits, kind, limit = 50 }: {
  title: string; hint: string; edits: Parameters<typeof EditRows>[0]["edits"]; kind: "accepted" | "suggested" | "rejected"; limit?: number;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? edits : edits.slice(0, limit);
  return (
    <section className="panel">
      <div className="panel-head"><div><h2>{title} <span className="subtle num" style={{ fontWeight: 400 }}>{edits.length}</span></h2><p>{hint}</p></div></div>
      {edits.length === 0 ? (
        <div className="panel-body"><p className="small muted">None.</p></div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Rule</th><th>Edit</th><th className="num">Token change</th><th>Reason</th></tr></thead>
            <EditRows edits={shown} kind={kind} />
          </table>
          {edits.length > limit && (
            <div className="panel-foot"><button className="btn btn-sm btn-ghost" onClick={() => setAll((a) => !a)}>{all ? "Show fewer" : `Show all ${edits.length}`}</button></div>
          )}
        </div>
      )}
    </section>
  );
}

export function OptimizeResults({ res }: { res: OptimizeResponse }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(res.optimized); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch { /* blocked */ } };
  return (
    <section className="stack-lg" aria-live="polite">
      <div className="btn-row">
        <h2 style={{ fontSize: 20 }}>Optimization result</h2>
        <Badge tone="outline">{res.mode} mode</Badge>
        <MeaningStatusBadge status={res.meaning_check.status} />
        {res.requires_review && <ReviewBadge />}
        {!res.changed && <Badge tone="neutral">Original kept</Badge>}
      </div>
      <p className="small muted">{res.mode_policy}</p>
      <p className="small subtle">
        Language <b>{res.language ?? "unknown"}</b> · script <b>{res.script ?? "unknown"}</b> · characters{" "}
        <span className="num">{fmtInt(res.original_chars)} → {fmtInt(res.optimized_chars)}</span> ({fmtInt(res.chars_saved)} removed; characters are not tokens).
        Each tokenizer below counts the original and the optimized text with the same encoding.
      </p>

      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Tokenizer</th><th>Count status</th><th className="num">Before</th><th className="num">After</th><th className="num">Saved</th><th className="num">Saved %</th></tr></thead>
          <tbody>
            {res.token_counts.map((t) => (
              <tr key={t.tokenizer.name}>
                <td><TokenizerTag t={t.tokenizer} /></td>
                <td><CountStatusBadge status={t.status} /></td>
                <td className="num">{fmtInt(t.before)}</td>
                <td className="num">{fmtInt(t.after)}</td>
                <td className="num"><span className={t.saved > 0 ? "delta-neg" : ""}>{fmtInt(t.saved)}</span></td>
                <td className="num">{fmtDec(t.saved_pct)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="side-by-side">
        <div>
          <div className="side-label"><span className="kicker">Original</span></div>
          <p className="indic" style={{ whiteSpace: "pre-wrap" }}>{res.original}</p>
        </div>
        <div>
          <div className="side-label">
            <span className="kicker">{res.changed ? "Optimized (accepted edits only)" : "Optimized — unchanged"}</span>
            <button className="btn btn-sm btn-ghost" onClick={copy}><IconCopy /> {copied ? "Copied" : "Copy"}</button>
          </div>
          <p className="indic" style={{ whiteSpace: "pre-wrap" }}>{res.optimized}</p>
        </div>
      </div>

      <EditTable title="Accepted edits" kind="accepted" edits={res.accepted}
        hint="Applied: fewer tokens under at least one tokenizer, none worse, and the meaning check said preserved." />
      <EditTable title="Suggestions — not applied" kind="suggested" edits={res.suggestions}
        hint="Need your review: meaning check at risk, repeated sentences, or script changes. Never applied automatically." />
      <EditTable title="Rejected edits" kind="rejected" edits={res.rejected} limit={20}
        hint="Touched a protected detail, overlapped another edit, saved no tokens, hit the edit limit, or changed a critical detail." />

      <section className="panel">
        <div className="panel-head"><div><h2>Meaning check — original vs optimized</h2><p>Rule-based critical-detail comparison (Feature 5)</p></div></div>
        <div className="panel-body"><MeaningFindings mc={res.meaning_check} /></div>
      </section>

      {res.phrase_lists.length > 0 && (
        <p className="small subtle">Phrase lists: {res.phrase_lists.map((p) => `${p.id} — ${p.review_status.replace("_", " ")}, ${p.entries} entries, ${p.applied ? "applied" : "not applied"}`).join(" · ")}</p>
      )}
      {res.warnings.length > 0 && <Callout tone="warn" title="Notes from the optimizer"><Bullets items={res.warnings} /></Callout>}
      <Limitations items={res.limitations} />
    </section>
  );
}

// ---------------------------------------------------------------- Feature 6
function TokenCells({ v }: { v: ScriptVariant }) {
  return (
    <>
      {v.token_counts.map((t) => (
        <span key={t.tokenizer.name} className="small num" style={{ display: "block" }}>
          {fmtInt(t.tokens)} <span className={t.delta_vs_source < 0 ? "delta-neg" : t.delta_vs_source > 0 ? "delta-pos" : "subtle"}>({t.delta_vs_source > 0 ? "+" : ""}{t.delta_vs_source})</span> · {fmtRatio(t.ratio_vs_source)}
        </span>
      ))}
    </>
  );
}

export function ScriptVariantsResults({ res, onAdd }: { res: ScriptVariantsResponse; onAdd?: (v: ScriptVariant) => void }) {
  const tok: TokenizerRef | undefined = res.source.token_counts[0]?.tokenizer;
  if (res.status === "unsupported") {
    return <Callout tone="warn" title="Not supported"><Bullets items={res.warnings} /></Callout>;
  }
  return (
    <div className="stack">
      <div className="btn-row">
        <Badge tone="outline">{res.direction === "native_to_roman" ? "Native → Romanized" : "Romanized → native"}</Badge>
        <ReviewBadge />
        {tok && <TokenizerTag t={tok} />}
        {res.source.token_counts[0] && <CountStatusBadge status={res.source.token_counts[0].status} />}
        <span className="small subtle">{res.library.name} {res.library.version} · {res.method} · source: {fmtInt(res.source.token_counts[0]?.tokens)} tokens</span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Scheme</th><th>Text</th><th className="num">Tokens (Δ) · ratio</th><th>Round trip</th><th>Meaning check</th><th /></tr></thead>
          <tbody>
            {res.variants.map((v, i) => (
              <tr key={i}>
                <td><code>{v.scheme ?? v.script}</code></td>
                <td className="indic" style={{ maxWidth: 360 }}>{v.text}</td>
                <td className="num"><TokenCells v={v} /></td>
                <td className="small">
                  {v.lossless_round_trip ? <Badge tone="blue">Lossless</Badge> : <Badge tone="red">Lossy</Badge>}
                  {v.joiners.source_count > 0 && <div className="subtle">ZWJ/ZWNJ: {v.joiners.source_count} → {v.joiners.output_count}{v.joiners.preserved_in_round_trip ? " (restored)" : " (lost)"}</div>}
                  {!v.lossless_round_trip && <Bullets items={v.lossy_reasons} />}
                </td>
                <td><MeaningStatusBadge status={v.meaning_check.status} /></td>
                <td>{onAdd && <button className="btn btn-sm btn-secondary" onClick={() => onAdd(v)}>Add to comparison</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {[...new Set(res.variants.flatMap((v) => v.warnings))].length > 0 && (
        <Callout tone="warn" title="Transliteration warnings"><Bullets items={[...new Set(res.variants.flatMap((v) => v.warnings))]} /></Callout>
      )}
      {res.warnings.length > 0 && <Callout tone="info"><Bullets items={res.warnings} /></Callout>}
      <Limitations items={res.limitations} />
    </div>
  );
}
