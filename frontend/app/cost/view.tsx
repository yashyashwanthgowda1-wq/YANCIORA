"use client";
import { useMemo, useState } from "react";
import { TokenizerSelect } from "@/components/domain";
import { IconPlus, IconTrash } from "@/components/icons";
import { Badge, Callout, ErrorState, Field, InactiveFeature, PageHeader, Segmented, TokenizerTag } from "@/components/ui";
import { api } from "@/lib/api/client";
import { PLANNED_ENDPOINTS } from "@/lib/api/planned";
import { MAX_TEXT_CHARS } from "@/lib/api/types";
import { estimateCost, validateCostInput } from "@/lib/cost";
import { fmtInt, fmtMoney } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { logActivity } from "@/lib/storage";

interface PriceRow { id: number; model: string; input: string; output: string }

const UNITS = [{ value: "1000000", label: "per 1M tokens" }, { value: "1000", label: "per 1K tokens" }] as const;

export default function CostView() {
  const [source, setSource] = useState<"count" | "manual">("count");
  const [text, setText] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [manualIn, setManualIn] = useState("");
  const [outTokens, setOutTokens] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [unit, setUnit] = useState<string>("1000000");
  const [priceSource, setPriceSource] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [rows, setRows] = useState<PriceRow[]>([{ id: 1, model: "", input: "", output: "" }]);
  const [nextId, setNextId] = useState(2);

  const count = useAction(async (signal) => api.tokenize({ text, tokenizer }, { signal }));
  const inTokens = source === "count" ? count.data?.token_count ?? null : manualIn === "" ? null : Number(manualIn);
  const outN = outTokens === "" ? null : Number(outTokens);

  const results = useMemo(() => rows.map((r) => {
    if (inTokens === null || outN === null || r.input === "" || r.output === "") return { row: r, errors: [] as string[], res: null };
    const input = { inputTokens: inTokens, outputTokens: outN, inputPrice: Number(r.input), outputPrice: Number(r.output), billingUnit: Number(unit) };
    const errors = validateCostInput(input);
    return { row: r, errors, res: errors.length ? null : estimateCost(input) };
  }), [rows, inTokens, outN, unit]);

  const first = results[0];
  const unitLabel = unit === "1000" ? "1K" : "1M";
  const updateRow = (id: number, patch: Partial<PriceRow>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F04</Badge> <Badge tone="outline">Partly available</Badge></>}
        title="Cost Calculator"
        lede="Estimate request cost from token counts and per-token prices (PRD §10.3). REDUTAX has no price registry yet, so prices are ones you enter. Results are labelled as user-entered estimates, never as provider billing."
      />

      <div className="workbench">
        <div className="stack-lg">
          <section className="panel">
            <div className="panel-head"><div><h2>1 · Tokens</h2><p>Input from a live count or a number you type; output is your assumption</p></div>
              <Segmented label="Input token source" value={source} onChange={setSource} options={[{ value: "count", label: "Count text" }, { value: "manual", label: "Enter number" }]} />
            </div>
            <div className="panel-body stack">
              {source === "count" ? (
                <>
                  <textarea className="textarea indic" rows={5} aria-label="Prompt text" value={text} onChange={(e) => { setText(e.target.value); count.reset(); }} placeholder="Paste the prompt to estimate…" />
                  <div className="row">
                    <Field label="Encoding" htmlFor="cs-tok"><div style={{ minWidth: 180 }}><TokenizerSelect id="cs-tok" value={tokenizer} onChange={(v) => { setTokenizer(v); count.reset(); }} /></div></Field>
                    <button className="btn btn-secondary" disabled={!text.trim() || !tokenizer || text.length > MAX_TEXT_CHARS || count.loading} onClick={() => count.run()}>{count.loading && <span className="spinner" />} Count</button>
                  </div>
                  {count.error && <ErrorState error={count.error} compact />}
                  {count.data && (
                    <Callout tone="info" title={`${fmtInt(count.data.token_count)} input tokens`}>
                      <span className="btn-row" style={{ marginBottom: 4 }}><Badge tone="estimate">Estimate for any hosted model</Badge><TokenizerTag t={count.data.tokenizer} /></span>
                      Exact for the <b>{count.data.tokenizer.name}</b> encoding. Whether a given model bills with this encoding is not verified, so treat it as an estimate.
                    </Callout>
                  )}
                </>
              ) : (
                <Field label="Input tokens" htmlFor="cs-in" hint="Labelled as a user-entered estimate">
                  <input id="cs-in" className="input num" type="number" min={0} step={1} value={manualIn} onChange={(e) => setManualIn(e.target.value)} placeholder="e.g. tokens from the counter" />
                </Field>
              )}
              <Field label="Expected output tokens (assumption)" htmlFor="cs-out" hint="Responses vary; this is an assumption, not a measurement">
                <input id="cs-out" className="input num" type="number" min={0} step={1} value={outTokens} onChange={(e) => setOutTokens(e.target.value)} placeholder="Your assumption" />
              </Field>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><div><h2>2 · Prices</h2><p>From the provider's published pricing. Enter the source so the estimate can be checked.</p></div><Badge tone="mock">User-entered · unverified</Badge></div>
            <div className="panel-body stack">
              <div className="grid-2" style={{ gap: 12 }}>
                <Field label="Currency" htmlFor="cs-cur" hint="Use the provider's billing currency">
                  <input id="cs-cur" className="input" value={currency} maxLength={6} onChange={(e) => setCurrency(e.target.value.toUpperCase())} />
                </Field>
                <Field label="Billing unit" htmlFor="cs-unit">
                  <select id="cs-unit" className="select" value={unit} onChange={(e) => setUnit(e.target.value)}>{UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}</select>
                </Field>
                <Field label="Price source URL" htmlFor="cs-src"><input id="cs-src" className="input" type="url" value={priceSource} onChange={(e) => setPriceSource(e.target.value)} placeholder="https://…" /></Field>
                <Field label="Price checked on" htmlFor="cs-date"><input id="cs-date" className="input" type="date" value={checkedAt} onChange={(e) => setCheckedAt(e.target.value)} /></Field>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Model (your label)</th><th>Input / {unitLabel}</th><th>Output / {unitLabel}</th><th /></tr></thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={r.id}>
                        <td><input className="input" aria-label={`Model ${i + 1} name`} value={r.model} onChange={(e) => updateRow(r.id, { model: e.target.value })} placeholder={`Model ${i + 1}`} /></td>
                        <td><input className="input num" aria-label={`Model ${i + 1} input price`} type="number" min={0} step="any" value={r.input} onChange={(e) => updateRow(r.id, { input: e.target.value })} /></td>
                        <td><input className="input num" aria-label={`Model ${i + 1} output price`} type="number" min={0} step="any" value={r.output} onChange={(e) => updateRow(r.id, { output: e.target.value })} /></td>
                        <td><button className="btn btn-ghost btn-sm btn-icon" aria-label={`Remove model ${i + 1}`} disabled={rows.length === 1} onClick={() => setRows((rs) => rs.filter((x) => x.id !== r.id))}><IconTrash /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn btn-sm btn-secondary" style={{ alignSelf: "flex-start" }} disabled={rows.length >= 4} onClick={() => { setRows((rs) => [...rs, { id: nextId, model: "", input: "", output: "" }]); setNextId((n) => n + 1); }}><IconPlus /> Compare another model</button>
            </div>
          </section>
        </div>

        <div className="stack-lg" style={{ position: "sticky", top: 76 }}>
          <section className="panel" aria-live="polite">
            <div className="panel-head"><div><h2>3 · Estimate</h2><p>{first?.row.model || "Model 1"}</p></div></div>
            <div className="panel-body stack">
              <div className="equation" aria-label="Cost formula">
                <span className="term in">{inTokens ?? "input tokens"}</span><span className="op">÷</span><span className="term">{unitLabel}</span><span className="op">×</span><span className="term in">{first?.row.input || "input price"}</span>
                <span className="op">+</span><br />
                <span className="term out">{outN ?? "output tokens"}</span><span className="op">÷</span><span className="term">{unitLabel}</span><span className="op">×</span><span className="term out">{first?.row.output || "output price"}</span>
              </div>
              {first?.errors.length ? <Callout tone="error">{first.errors.join(" ")}</Callout> : null}
              {first?.res ? (
                <>
                  <div className="cost-bar" aria-hidden="true">
                    <span style={{ width: `${first.res.total ? (first.res.inputCost / first.res.total) * 100 : 50}%` }} />
                    <span style={{ flex: 1, marginLeft: 2 }} />
                  </div>
                  <dl className="meta-list">
                    <dt><span className="swatch" style={{ background: "var(--blue-500)", borderColor: "var(--blue-500)" }} />Input</dt><dd className="num">{fmtMoney(first.res.inputCost, currency)}</dd>
                    <dt><span className="swatch" style={{ background: "var(--red-600)", borderColor: "var(--red-600)" }} />Output</dt><dd className="num">{fmtMoney(first.res.outputCost, currency)}</dd>
                  </dl>
                  <div className="cost-total">
                    <span className="kicker">Estimated total per request</span>
                    <span className="stat-value num">{fmtMoney(first.res.total, currency)}</span>
                  </div>
                </>
              ) : !first?.errors.length && <p className="small muted">Fill in input tokens, output tokens and both prices to see the estimate.</p>}
              <div className="btn-row">
                <Badge tone="estimate">Input: {source === "count" ? "encoding estimate" : "user-entered"}</Badge>
                <Badge tone="estimate">Output: assumption</Badge>
                <Badge tone="mock">Prices: user-entered</Badge>
              </div>
              <p className="small subtle">
                Source: {priceSource || "not given"} · checked {checkedAt || "date not given"}. Cached input, tools, audio and other charges are not included.
                Actual provider usage and invoices take precedence.
              </p>
              {first?.res && <button className="btn btn-sm btn-ghost" style={{ alignSelf: "flex-start" }} onClick={() => logActivity({ kind: "cost", href: "/cost", summary: `${fmtMoney(first.res!.total, currency)} per request (user-entered prices)` })}>Save to recent activity</button>}
            </div>
          </section>

          {rows.length > 1 && (
            <section className="panel">
              <div className="panel-head"><div><h2>Model comparison</h2><p>Same token assumptions, your prices</p></div></div>
              <div className="table-wrap" style={{ border: 0 }}>
                <table className="table">
                  <thead><tr><th>Model</th><th className="num">Input</th><th className="num">Output</th><th className="num">Total</th></tr></thead>
                  <tbody>
                    {results.map(({ row, res }, i) => {
                      const min = Math.min(...results.map((x) => x.res?.total ?? Infinity));
                      return (
                        <tr key={row.id} className={res && res.total === min ? "is-best" : undefined}>
                          <td>{row.model || `Model ${i + 1}`}</td>
                          <td className="num">{fmtMoney(res?.inputCost, currency)}</td>
                          <td className="num">{fmtMoney(res?.outputCost, currency)}</td>
                          <td className="num"><b>{fmtMoney(res?.total, currency)}</b></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <InactiveFeature title="Versioned price registry" endpoint={PLANNED_ENDPOINTS.costEstimate}>
            Prices with provider, model version, currency, source URL and a last-verified timestamp. Built-in prices will appear here only once they're verified.
          </InactiveFeature>
        </div>
      </div>
    </>
  );
}
