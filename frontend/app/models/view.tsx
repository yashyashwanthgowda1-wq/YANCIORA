"use client";
import { useState } from "react";
import { IconLock, IconPlus, IconTrash, IconUnlock } from "@/components/icons";
import { Badge, Callout, EmptyState, ErrorState, Field, PageHeader, Segmented } from "@/components/ui";
import { api } from "@/lib/api/client";
import {
  LANGUAGE_CODES, MAX_TEXT_CHARS, TASK_TYPES, type Candidate, type CostPreference, type Encoding, type LanguageCode,
  type ModelSpec, type SupportLevel, type TaskType,
} from "@/lib/api/types";
import { fmtInt, fmtMoney } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { useModelCatalog } from "@/lib/models";
import { logActivity } from "@/lib/storage";

const ROUTE_STEPS = [
  ["Estimate input tokens", "Count the prompt with the model's configured encoding; otherwise use a fallback encoding and label it an estimate."],
  ["Filter ineligible models", "Drop models that fail the language-support requirement, context size, documented tasks or minimum team quality tier."],
  ["Estimate cost", "Configured prices × input tokens and your expected output tokens."],
  ["Rank by your preference", "Lowest cost, highest team quality tier, or balanced (documented language support, then cost)."],
  ["Explain or fall back", "If nothing qualifies, show which requirement each model failed. Unknown data is a limitation, never a guess."],
  ["Show the decision", "Selected model + reasons. A locked model is never switched silently."],
] as const;

const SUPPORT_TONE: Record<SupportLevel, "blue" | "outline" | "neutral" | "red"> = { verified: "blue", claimed: "outline", unknown: "neutral", unsupported: "red" };

export default function ModelsView() {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [language, setLanguage] = useState<LanguageCode>("kn");
  const [task, setTask] = useState<TaskType>("general");
  const [text, setText] = useState("");
  const [context, setContext] = useState("");
  const [quality, setQuality] = useState("");
  const [preference, setPreference] = useState<CostPreference>("balanced");
  const [support, setSupport] = useState<"any" | "claimed" | "verified">("any");
  const [outTokens, setOutTokens] = useState("256");
  const [locked, setLocked] = useState<string | null>(null);
  const [manualPick, setManualPick] = useState("");
  const catalog = useModelCatalog();

  const lockId = mode === "manual" ? manualPick || null : locked;
  const run = useAction(async (signal) => {
    const res = await api.recommend({
      text, language, task_type: task, cost_preference: preference, require_language_support: support,
      min_context_tokens: context ? Number(context) : null, min_quality_tier: quality ? Number(quality) : null,
      expected_output_tokens: Number(outTokens) || 0, custom_models: catalog.custom, locked_model_id: lockId,
    }, { signal });
    logActivity({ kind: "models", href: "/models", summary: res.recommended ? `Recommended ${res.recommended.model_id} (${LANGUAGES[language].name})` : "No eligible model" });
    return res;
  });
  const canRun = !!text.trim() && text.length <= MAX_TEXT_CHARS && (mode === "auto" || !!manualPick) && Number(outTokens) >= 0;
  const r = run.data;
  const ranked: Candidate[] = r ? [...(r.recommended ? [r.recommended] : []), ...r.alternatives] : [];

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F07 · Live</Badge> <Badge tone="outline">Rule-based</Badge></>}
        title="Model Recommendation"
        lede="Filters models against your language, task, context and quality requirements, ranks the eligible ones by your preference, and explains every decision. It uses only configured model data, so unknown capabilities are shown as limitations, never claimed."
      />

      <div className="split-aside">
        <section className="panel" aria-label="Requirements">
          <div className="panel-head"><div><h2>Requirements</h2><p>What the answer must meet</p></div></div>
          <div className="panel-body stack">
            <Field label="Prompt" htmlFor="md-text" hint="Counted with each model's encoding to check context fit and cost">
              <textarea id="md-text" className="textarea indic" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="The prompt you want to send…" />
            </Field>
            <Field label="Selection mode">
              <Segmented label="Selection mode" value={mode} onChange={setMode} options={[{ value: "auto", label: "Auto" }, { value: "manual", label: "Manual" }]} />
            </Field>
            {mode === "manual" && (
              <Field label="Model (manual)" htmlFor="md-pick" hint="Kept even if it fails a requirement; the failures are shown">
                <select id="md-pick" className="select" value={manualPick} onChange={(e) => setManualPick(e.target.value)}>
                  <option value="">Choose a model…</option>
                  {catalog.all.map((m) => <option key={m.id} value={m.id}>{m.display_name || m.id}{m.source === "user" ? " (user-entered)" : ""}</option>)}
                </select>
              </Field>
            )}
            <Field label="Language" htmlFor="md-lang">
              <select id="md-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode)}>
                {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
              </select>
            </Field>
            <Field label="Task" htmlFor="md-task">
              <select id="md-task" className="select" value={task} onChange={(e) => setTask(e.target.value as TaskType)}>
                {TASK_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Preference" htmlFor="md-pref">
              <select id="md-pref" className="select" value={preference} onChange={(e) => setPreference(e.target.value as CostPreference)}>
                <option value="balanced">Balanced (language support, then cost)</option><option value="lowest">Lowest cost</option><option value="quality">Highest team quality tier</option>
              </select>
            </Field>
            <Field label="Language support required" htmlFor="md-sup">
              <select id="md-sup" className="select" value={support} onChange={(e) => setSupport(e.target.value as typeof support)}>
                <option value="any">Any (exclude only "unsupported")</option><option value="claimed">Documented by provider or measured</option><option value="verified">Measured by the team</option>
              </select>
            </Field>
            <Field label="Expected output tokens" htmlFor="md-out"><input id="md-out" className="input num" type="number" min={0} value={outTokens} onChange={(e) => setOutTokens(e.target.value)} /></Field>
            <Field label="Minimum context (tokens)" htmlFor="md-ctx" hint="Optional"><input id="md-ctx" className="input num" type="number" min={1} value={context} onChange={(e) => setContext(e.target.value)} /></Field>
            <Field label="Minimum team quality tier" htmlFor="md-q" hint="1–5 from the team's own evaluation; optional">
              <select id="md-q" className="select" value={quality} onChange={(e) => setQuality(e.target.value)}><option value="">No minimum</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select>
            </Field>
            <Field label="Maximum latency (ms, p95)" hint="Not used: no measured latency data exists yet">
              <input className="input num" disabled placeholder="No measured data" />
            </Field>
          </div>
          <div className="panel-foot btn-row">
            <button className="btn btn-primary" disabled={!canRun || run.loading} onClick={() => run.run()}>{run.loading && <span className="spinner" />} Recommend</button>
            <button className="btn btn-ghost" disabled={mode === "manual" || (!locked && !r?.recommended)} aria-pressed={!!locked}
              onClick={() => setLocked((l) => (l ? null : r?.recommended?.model_id ?? null))}>
              {locked ? <IconLock /> : <IconUnlock />} {locked ? `Locked: ${locked}` : "Lock model"}
            </button>
          </div>
        </section>

        <div className="stack-lg" style={{ minWidth: 0 }}>
          {run.error && <ErrorState error={run.error} onRetry={() => run.run()} />}
          <section className="panel">
            <div className="panel-head"><div><h2>Eligible models</h2><p>{mode === "auto" ? "Auto: ranked by your preference" : "Manual: your pick is kept"} · {LANGUAGES[language].name} · {task}</p></div>
              {r && <Badge tone="outline">{r.method}</Badge>}</div>
            {!r ? (
              <EmptyState title={catalog.all.length ? "No recommendation yet" : "No models configured"}>
                {catalog.all.length
                  ? "Enter a prompt and press Recommend."
                  : "The registry (config/models.yaml) ships empty and REDUTAX never invents model data. Add a model below (labelled user-entered) or ask the team to add verified models."}
              </EmptyState>
            ) : (
              <div className="panel-body stack">
                <Callout tone={r.recommended ? "success" : "warn"} title={r.recommended ? `Recommended: ${r.recommended.display_name || r.recommended.model_id}` : "No model selected"}>
                  {r.explanation}
                </Callout>
                {r.warnings.slice(1).map((w, i) => <Callout key={i} tone="warn">{w}</Callout>)}
                {ranked.length > 0 && (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Model</th><th>Language</th><th className="num">Context</th><th className="num">Tokens needed</th><th>Quality</th><th className="num">Est. cost</th><th>Decision</th></tr></thead>
                      <tbody>
                        {ranked.map((c) => (
                          <tr key={c.model_id} className={c.model_id === r.recommended?.model_id ? "is-best" : undefined}>
                            <td><b>{c.display_name || c.model_id}</b><div className="small subtle">{c.provider}{c.source === "user" ? " · user-entered" : ""}</div></td>
                            <td><Badge tone={SUPPORT_TONE[c.language_support]}>{c.language_support}</Badge></td>
                            <td className="num">{c.context_window_tokens ? fmtInt(c.context_window_tokens) : "unknown"}</td>
                            <td className="num">{fmtInt(c.required_tokens)}</td>
                            <td>{c.quality_tier ?? "—"}</td>
                            <td className="num">{c.cost.total_cost !== null ? fmtMoney(c.cost.total_cost, c.cost.currency ?? "") : "no price"}</td>
                            <td>{c.model_id === r.recommended?.model_id ? <Badge tone="blue">{r.locked ? "Locked" : "Selected"}</Badge> : <Badge tone="outline">#{c.rank} eligible</Badge>}
                              <ul className="small subtle" style={{ margin: "4px 0 0", paddingLeft: 16 }}>{c.reasons.map((x, i) => <li key={i}>{x}</li>)}{c.limitations.map((x, i) => <li key={`l${i}`}>Limitation: {x}</li>)}{c.exclusions.map((x, i) => <li key={`e${i}`}>Fails: {x}</li>)}</ul></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {r.excluded.filter((c) => c.model_id !== r.recommended?.model_id).length > 0 && (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Excluded model</th><th>Why</th></tr></thead>
                      <tbody>{r.excluded.filter((c) => c.model_id !== r.recommended?.model_id).map((c) => (
                        <tr key={c.model_id}><td>{c.display_name || c.model_id}</td><td className="small">{c.exclusions.join(" ")}</td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <AddModelPanel custom={catalog.custom} onChange={catalog.setCustomModels} registryCount={catalog.registry.data?.count ?? 0} />

          <section className="panel">
            <div className="panel-head"><div><h2>How Auto routing decides</h2><p>PRD §10.2 · rec_rules_v1</p></div></div>
            <div className="panel-body"><div className="route-flow">
              {ROUTE_STEPS.map(([t, d]) => <div className="route-step" key={t}><div><h3>{t}</h3><p>{d}</p></div></div>)}
            </div></div>
          </section>
        </div>
      </div>
    </>
  );
}

function AddModelPanel({ custom, onChange, registryCount }: { custom: ModelSpec[]; onChange: (l: ModelSpec[]) => void; registryCount: number }) {
  const [f, setF] = useState({ id: "", provider: "", encoding: "" as "" | Encoding, context: "", input: "", output: "", currency: "USD", source: "", lang: "kn" as LanguageCode, support: "unknown" as SupportLevel });
  const valid = f.id.trim() && f.provider.trim() && ((f.input === "" && f.output === "") || (Number(f.input) >= 0 && Number(f.output) >= 0 && f.input !== "" && f.output !== ""));
  const add = () => {
    const spec: ModelSpec = {
      id: f.id.trim(), provider: f.provider.trim(), source: "user", encoding: f.encoding || null,
      context_window_tokens: f.context ? Number(f.context) : null,
      pricing: f.input !== "" ? { currency: f.currency || "USD", input_per_1m: Number(f.input), output_per_1m: Number(f.output), source_url: f.source || null, verified_at: null } : null,
      languages: { [f.lang]: f.support },
    };
    onChange([...custom.filter((m) => m.id !== spec.id), spec]);
    setF((x) => ({ ...x, id: "", input: "", output: "", context: "" }));
  };
  return (
    <section className="panel">
      <div className="panel-head"><div><h2>Models</h2><p>{registryCount} in the verified registry · {custom.length} user-entered in this browser</p></div><Badge tone="mock">User-entered · unverified</Badge></div>
      <div className="panel-body stack">
        {custom.length > 0 && (
          <div className="table-wrap"><table className="table"><thead><tr><th>Model</th><th>Encoding</th><th className="num">Context</th><th>Price / 1M</th><th>Languages</th><th /></tr></thead>
            <tbody>{custom.map((m) => (
              <tr key={m.id}><td><b>{m.id}</b><div className="small subtle">{m.provider}</div></td><td>{m.encoding ?? "unknown"}</td><td className="num">{m.context_window_tokens ?? "unknown"}</td>
                <td>{m.pricing ? `${m.pricing.input_per_1m} / ${m.pricing.output_per_1m} ${m.pricing.currency}` : "none"}</td>
                <td className="small">{Object.entries(m.languages ?? {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "—"}</td>
                <td><button className="btn btn-ghost btn-sm btn-icon" aria-label={`Remove ${m.id}`} onClick={() => onChange(custom.filter((x) => x.id !== m.id))}><IconTrash /></button></td></tr>
            ))}</tbody></table></div>
        )}
        <div className="grid-2" style={{ gap: 10 }}>
          <Field label="Model id" htmlFor="am-id"><input id="am-id" className="input" value={f.id} onChange={(e) => setF({ ...f, id: e.target.value })} placeholder="provider's model id" /></Field>
          <Field label="Provider" htmlFor="am-p"><input id="am-p" className="input" value={f.provider} onChange={(e) => setF({ ...f, provider: e.target.value })} /></Field>
          <Field label="Encoding" htmlFor="am-enc"><select id="am-enc" className="select" value={f.encoding} onChange={(e) => setF({ ...f, encoding: e.target.value as "" | Encoding })}><option value="">Unknown</option><option value="cl100k_base">cl100k_base</option><option value="o200k_base">o200k_base</option></select></Field>
          <Field label="Context window (tokens)" htmlFor="am-ctx"><input id="am-ctx" className="input num" type="number" min={1} value={f.context} onChange={(e) => setF({ ...f, context: e.target.value })} placeholder="unknown" /></Field>
          <Field label="Input price / 1M" htmlFor="am-in"><input id="am-in" className="input num" type="number" min={0} step="any" value={f.input} onChange={(e) => setF({ ...f, input: e.target.value })} /></Field>
          <Field label="Output price / 1M" htmlFor="am-out"><input id="am-out" className="input num" type="number" min={0} step="any" value={f.output} onChange={(e) => setF({ ...f, output: e.target.value })} /></Field>
          <Field label="Currency" htmlFor="am-cur"><input id="am-cur" className="input" maxLength={6} value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} /></Field>
          <Field label="Price source URL" htmlFor="am-src"><input id="am-src" className="input" type="url" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} placeholder="https://…" /></Field>
          <Field label="Language" htmlFor="am-lang"><select id="am-lang" className="select" value={f.lang} onChange={(e) => setF({ ...f, lang: e.target.value as LanguageCode })}>{LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}</select></Field>
          <Field label="Support for that language" htmlFor="am-sup" hint="claimed = in provider docs; verified = measured by your team">
            <select id="am-sup" className="select" value={f.support} onChange={(e) => setF({ ...f, support: e.target.value as SupportLevel })}><option value="unknown">unknown</option><option value="claimed">claimed</option><option value="verified">verified</option><option value="unsupported">unsupported</option></select></Field>
        </div>
        <button className="btn btn-sm btn-secondary" style={{ alignSelf: "flex-start" }} disabled={!valid} onClick={add}><IconPlus /> Add user-entered model</button>
      </div>
    </section>
  );
}
