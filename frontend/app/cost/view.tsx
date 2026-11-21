"use client";
import { useMemo, useState } from "react";
import { TokenizerSelect } from "@/components/domain";
import { IconPlus, IconTrash } from "@/components/icons";
import { Badge, Callout, ErrorState, Field, PageHeader, Segmented, TokenizerTag } from "@/components/ui";
import { api } from "@/lib/api/client";
import { MAX_TEXT_CHARS, type CostEstimateResponse, type Encoding, type ModelCost, type ModelSpec } from "@/lib/api/types";
import { estimateCost, validateCostInput } from "@/lib/cost";
import { fmtInt, fmtMoney } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { useModelCatalog } from "@/lib/models";
import { logActivity } from "@/lib/storage";

interface PriceRow { id: number; model: string; input: string; output: string; encoding: "" | Encoding }

const UNITS = [{ value: "1000000", label: "per 1M tokens" }, { value: "1000", label: "per 1K tokens" }] as const;
const PRICE_STATUS: Record<ModelCost["price_status"], { label: string; tone: "blue" | "outline" | "mock" | "neutral" }> = {
  verified: { label: "Registry · verified", tone: "blue" },
  unverified: { label: "Registry · not verified", tone: "outline" },
  user_entered: { label: "User-entered", tone: "mock" },
  missing: { label: "No price", tone: "neutral" },
};

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
  const [rows, setRows] = useState<PriceRow[]>([{ id: 1, model: "", input: "", output: "", encoding: "" }]);
  const [nextId, setNextId] = useState(2);
  const [compareOptimized, setCompareOptimized] = useState(true);
  const [registryPick, setRegistryPick] = useState<string[]>([]);
  const catalog = useModelCatalog();

  const count = useAction(async (signal) => api.tokenize({ text, tokenizer }, { signal }));
  const inTokens = source === "count" ? count.data?.token_count ?? null : manualIn === "" ? null : Number(manualIn);
  const outN = outTokens === "" ? null : Number(outTokens);
  const perMillion = (v: string) => Number(v) * (1_000_000 / Number(unit));

  // Rows → user-entered models for the backend (prices converted to per 1M tokens).
  const userModels: ModelSpec[] = rows
    .filter((r) => r.input !== "" && r.output !== "")
    .map((r, i) => ({
      id: r.model.trim() || `model-${i + 1}`, provider: "User-entered", source: "user",
      encoding: r.encoding || null,
      pricing: { currency: currency || "INR", input_per_1m: perMillion(r.input), output_per_1m: perMillion(r.output),
        source_url: priceSource || null, verified_at: null },
    }));
  const rowErrors = rows.flatMap((r, i) => (r.input !== "" || r.output !== "") && (Number(r.input) < 0 || Number(r.output) < 0 || r.input === "" || r.output === "")
    ? [`Model ${i + 1}: enter both prices (≥ 0).`] : []);

  // Backend estimate (text mode): real token counts per model encoding, optional optimized comparison.
  const estimate = useAction(async (signal): Promise<{ res: CostEstimateResponse; optimized: string | null }> => {
    let optimized: string | null = null;
    if (compareOptimized) {
      const o = await api.optimize({ text, mode: "safe", tokenizers: [tokenizer || "cl100k_base"] }, { signal });
      optimized = o.changed ? o.optimized : null;
    }
    const res = await api.costEstimate({
      text, optimized_text: optimized, model_ids: registryPick, custom_models: userModels,
      expected_output_tokens: outN ?? 0,
    }, { signal });
    const best = res.models.filter((m) => m.total_cost !== null).sort((a, b) => a.total_cost! - b.total_cost!)[0];
    if (best) logActivity({ kind: "cost", href: "/cost", summary: `${best.model_id}: ${fmtMoney(best.total_cost, best.currency ?? "")} per request (estimate)` });
    return { res, optimized };
  });
  const canEstimate = source === "count" && !!text.trim() && text.length <= MAX_TEXT_CHARS && (userModels.length > 0 || registryPick.length > 0)
    && !rowErrors.length && (outN === null || outN >= 0);

  // Manual mode keeps the local formula (tokens typed by the user, no text to count).
  const results = useMemo(() => rows.map((r) => {
    if (inTokens === null || outN === null || r.input === "" || r.output === "") return { row: r, errors: [] as string[], res: null };
    const input = { inputTokens: inTokens, outputTokens: outN, inputPrice: Number(r.input), outputPrice: Number(r.output), billingUnit: Number(unit) };
    const errors = validateCostInput(input);
    return { row: r, errors, res: errors.length ? null : estimateCost(input) };
  }), [rows, inTokens, outN, unit]);
  const first = results[0];
  const unitLabel = unit === "1000" ? "1K" : "1M";
  const updateRow = (id: number, patch: Partial<PriceRow>) => { setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r))); estimate.reset(); };
  const registryModels = catalog.registry.data?.models ?? [];
  const est = estimate.data?.res;

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F04 · Live</Badge> <Badge tone="outline">Estimates only</Badge></>}
        title="Cost Calculator"
        lede="Estimate request cost from real token counts and per-token prices, and compare the original prompt with its optimized version. Prices come from the team's verified registry or from you (labelled user-entered). Results are estimates, never provider billing."
      />

      <div className="workbench">
        <div className="stack-lg">
          <section className="panel">
            <div className="panel-head"><div><h2>1 · Tokens</h2><p>Text counted by the backend with each model's encoding, or a number you type</p></div>
              <Segmented label="Input token source" value={source} onChange={(v) => { setSource(v); estimate.reset(); }} options={[{ value: "count", label: "Count text" }, { value: "manual", label: "Enter number" }]} />
            </div>
            <div className="panel-body stack">
              {source === "count" ? (
                <>
                  <textarea className="textarea indic" rows={5} aria-label="Prompt text" value={text} onChange={(e) => { setText(e.target.value); count.reset(); estimate.reset(); }} placeholder="Paste the prompt to estimate…" />
                  <div className="row">
                    <Field label="Encoding (preview count)" htmlFor="cs-tok"><div style={{ minWidth: 180 }}><TokenizerSelect id="cs-tok" value={tokenizer} onChange={(v) => { setTokenizer(v); count.reset(); }} /></div></Field>
                    <button className="btn btn-secondary" disabled={!text.trim() || !tokenizer || text.length > MAX_TEXT_CHARS || count.loading} onClick={() => count.run()}>{count.loading && <span className="spinner" />} Count</button>
                  </div>
                  <label className="checkbox"><input type="checkbox" checked={compareOptimized} onChange={(e) => { setCompareOptimized(e.target.checked); estimate.reset(); }} /> Also price the optimized prompt (safe rules, meaning-checked) and show the saving</label>
                  {count.error && <ErrorState error={count.error} compact />}
                  {count.data && (
                    <Callout tone="info" title={`${fmtInt(count.data.token_count)} input tokens`}>
                      <span className="btn-row" style={{ marginBottom: 4 }}><Badge tone="estimate">Estimate for any hosted model</Badge><TokenizerTag t={count.data.tokenizer} /></span>
                      Exact for the <b>{count.data.tokenizer.name}</b> encoding. The estimate below counts again with each model&apos;s configured encoding.
                    </Callout>
                  )}
                </>
              ) : (
                <Field label="Input tokens" htmlFor="cs-in" hint="Labelled as a user-entered estimate (local formula)">
                  <input id="cs-in" className="input num" type="number" min={0} step={1} value={manualIn} onChange={(e) => setManualIn(e.target.value)} placeholder="e.g. tokens from the counter" />
                </Field>
              )}
              <Field label="Expected output tokens (assumption)" htmlFor="cs-out" hint="Responses vary; this is an assumption, not a measurement">
                <input id="cs-out" className="input num" type="number" min={0} step={1} value={outTokens} onChange={(e) => { setOutTokens(e.target.value); estimate.reset(); }} placeholder="Your assumption" />
              </Field>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><div><h2>2 · Prices</h2><p>Registry models (team-verified) and/or prices you enter from the provider&apos;s published pricing</p></div><Badge tone="mock">User-entered · unverified</Badge></div>
            <div className="panel-body stack">
              {registryModels.length > 0 && (
                <div className="field">
                  <span className="field-label"><span>Registry models</span></span>
                  <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
                    {registryModels.map((m) => (
                      <label key={m.id} className="checkbox small"><input type="checkbox" checked={registryPick.includes(m.id)}
                        onChange={(e) => { setRegistryPick((p) => e.target.checked ? [...p, m.id] : p.filter((x) => x !== m.id)); estimate.reset(); }} /> {m.display_name || m.id}</label>
                    ))}
                  </div>
                </div>
              )}
              <div className="grid-2" style={{ gap: 12 }}>
                <Field label="Currency" htmlFor="cs-cur" hint="Use the provider's billing currency">
                  <input id="cs-cur" className="input" value={currency} maxLength={6} onChange={(e) => { setCurrency(e.target.value.toUpperCase()); estimate.reset(); }} />
                </Field>
                <Field label="Billing unit" htmlFor="cs-unit">
                  <select id="cs-unit" className="select" value={unit} onChange={(e) => { setUnit(e.target.value); estimate.reset(); }}>{UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}</select>
                </Field>
                <Field label="Price source URL" htmlFor="cs-src"><input id="cs-src" className="input" type="url" value={priceSource} onChange={(e) => setPriceSource(e.target.value)} placeholder="https://…" /></Field>
                <Field label="Price checked on" htmlFor="cs-date"><input id="cs-date" className="input" type="date" value={checkedAt} onChange={(e) => setCheckedAt(e.target.value)} /></Field>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Model (your label)</th><th>Encoding</th><th>Input / {unitLabel}</th><th>Output / {unitLabel}</th><th /></tr></thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={r.id}>
                        <td><input className="input" aria-label={`Model ${i + 1} name`} value={r.model} onChange={(e) => updateRow(r.id, { model: e.target.value })} placeholder={`Model ${i + 1}`} /></td>
                        <td><select className="select" aria-label={`Model ${i + 1} encoding`} value={r.encoding} onChange={(e) => updateRow(r.id, { encoding: e.target.value as PriceRow["encoding"] })}>
                          <option value="">Unknown (fallback o200k_base)</option><option value="cl100k_base">cl100k_base</option><option value="o200k_base">o200k_base</option></select></td>
                        <td><input className="input num" aria-label={`Model ${i + 1} input price`} type="number" min={0} step="any" value={r.input} onChange={(e) => updateRow(r.id, { input: e.target.value })} /></td>
                        <td><input className="input num" aria-label={`Model ${i + 1} output price`} type="number" min={0} step="any" value={r.output} onChange={(e) => updateRow(r.id, { output: e.target.value })} /></td>
                        <td><button className="btn btn-ghost btn-sm btn-icon" aria-label={`Remove model ${i + 1}`} disabled={rows.length === 1} onClick={() => { setRows((rs) => rs.filter((x) => x.id !== r.id)); estimate.reset(); }}><IconTrash /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="btn-row">
                <button className="btn btn-sm btn-secondary" disabled={rows.length >= 4} onClick={() => { setRows((rs) => [...rs, { id: nextId, model: "", input: "", output: "", encoding: "" }]); setNextId((n) => n + 1); }}><IconPlus /> Compare another model</button>
                <button className="btn btn-sm btn-ghost" disabled={!userModels.length} onClick={() => catalog.setCustomModels([...catalog.custom.filter((c) => !userModels.some((u) => u.id === c.id)), ...userModels])}
                  title="Save these user-entered models in this browser for Model Recommendation, Chat and Voice">Save for other screens</button>
              </div>
              {rowErrors.length > 0 && <span className="field-error">{rowErrors.join(" ")}</span>}
            </div>
          </section>
        </div>

        <div className="stack-lg" style={{ position: "sticky", top: 76 }}>
          <section className="panel" aria-live="polite">
            <div className="panel-head"><div><h2>3 · Estimate</h2><p>{source === "count" ? "Calculated by the backend" : first?.row.model || "Model 1"}</p></div></div>
            <div className="panel-body stack">
              {source === "count" ? (
                <>
                  <button className="btn btn-primary" disabled={!canEstimate || estimate.loading} onClick={() => estimate.run()}>{estimate.loading && <span className="spinner" />} Calculate estimate</button>
                  {!canEstimate && !estimate.loading && <p className="small muted">Enter the prompt text and at least one model with both prices (or pick a registry model).</p>}
                  {estimate.error && <ErrorState error={estimate.error} onRetry={() => estimate.run()} compact />}
                  {est && est.models.map((m) => (
                    <div key={m.model_id} className="stack" style={{ gap: 6, borderTop: "1px solid var(--grey-100)", paddingTop: 10 }}>
                      <div className="btn-row"><b>{m.display_name || m.model_id}</b><Badge tone={PRICE_STATUS[m.price_status].tone}>{PRICE_STATUS[m.price_status].label}</Badge>
                        <Badge tone="estimate">{m.encoding_used}{m.encoding_status === "fallback_encoding" ? " (fallback)" : ""}</Badge></div>
                      <dl className="meta-list">
                        <dt>Input tokens</dt><dd className="num">{fmtInt(m.input_tokens)}{m.optimized_input_tokens !== null ? ` → ${fmtInt(m.optimized_input_tokens)} optimized` : ""}</dd>
                        <dt>Output tokens (assumed)</dt><dd className="num">{fmtInt(m.output_tokens)}</dd>
                        <dt>Input cost</dt><dd className="num">{fmtMoney(m.input_cost, m.currency ?? "")}</dd>
                        <dt>Output cost</dt><dd className="num">{fmtMoney(m.output_cost, m.currency ?? "")}</dd>
                      </dl>
                      <div className="cost-total"><span className="kicker">Estimated total per request</span><span className="stat-value num">{fmtMoney(m.total_cost, m.currency ?? "")}</span></div>
                      {m.optimized_total_cost !== null && (
                        <Callout tone="success" title={`Optimized prompt: ${fmtMoney(m.optimized_total_cost, m.currency ?? "")}`}>
                          Estimated saving {fmtMoney(m.savings, m.currency ?? "")} per request{m.savings_pct !== null ? ` (${m.savings_pct.toFixed(2)}%)` : ""}.
                        </Callout>
                      )}
                      {m.warnings.length > 0 && <ul className="small subtle" style={{ margin: 0, paddingLeft: 18 }}>{m.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
                      <p className="small subtle">Price source: {m.price_source_url || "not given"}{m.price_verified_at ? ` · verified ${m.price_verified_at}` : " · not verified"}</p>
                    </div>
                  ))}
                  {est && estimate.data?.optimized === null && compareOptimized && <p className="small subtle">The optimizer found no safe edit, so there is no optimized price to compare.</p>}
                  {est && <p className="small subtle">{est.warnings[0]}</p>}
                </>
              ) : (
                <>
                  <div className="equation" aria-label="Cost formula">
                    <span className="term in">{inTokens ?? "input tokens"}</span><span className="op">÷</span><span className="term">{unitLabel}</span><span className="op">×</span><span className="term in">{first?.row.input || "input price"}</span>
                    <span className="op">+</span><br />
                    <span className="term out">{outN ?? "output tokens"}</span><span className="op">÷</span><span className="term">{unitLabel}</span><span className="op">×</span><span className="term out">{first?.row.output || "output price"}</span>
                  </div>
                  {first?.errors.length ? <Callout tone="error">{first.errors.join(" ")}</Callout> : null}
                  {first?.res ? (
                    <div className="cost-total"><span className="kicker">Estimated total per request</span><span className="stat-value num">{fmtMoney(first.res.total, currency)}</span></div>
                  ) : !first?.errors.length && <p className="small muted">Fill in input tokens, output tokens and both prices to see the estimate.</p>}
                  <div className="btn-row"><Badge tone="estimate">Input: user-entered</Badge><Badge tone="estimate">Output: assumption</Badge><Badge tone="mock">Prices: user-entered</Badge></div>
                </>
              )}
              <p className="small subtle">Source: {priceSource || "not given"} · checked {checkedAt || "date not given"}. Cached input, tools, audio and other charges are not included. Actual provider usage and invoices take precedence.</p>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><div><h2>Model price registry</h2><p>Verified models from config/models.yaml</p></div>
              <Badge tone={registryModels.length ? "blue" : "outline"}>{registryModels.length} model{registryModels.length === 1 ? "" : "s"}</Badge></div>
            <div className="panel-body stack">
              {catalog.registry.error && <ErrorState error={catalog.registry.error} compact />}
              {catalog.registry.loading && <p className="small muted">Loading registry…</p>}
              {registryModels.length === 0 && !catalog.registry.loading && !catalog.registry.error && (
                <p className="small muted">The registry is empty: REDUTAX ships no built-in prices. The team adds models with a pricing source URL and a verification date to <code>config/models.yaml</code>. Until then, enter prices above (labelled user-entered).</p>
              )}
              {registryModels.map((m) => (
                <div key={m.id} className="small"><b>{m.display_name || m.id}</b> · {m.provider} · {m.pricing ? `${m.pricing.input_per_1m}/${m.pricing.output_per_1m} ${m.pricing.currency} per 1M` : "no price"} · {m.pricing?.verified_at ? `verified ${m.pricing.verified_at}` : "not verified"}</div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
