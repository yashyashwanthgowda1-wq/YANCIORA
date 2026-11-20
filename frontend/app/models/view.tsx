"use client";
import { useState } from "react";
import { IconLock, IconUnlock } from "@/components/icons";
import { Badge, EmptyState, Field, InactiveFeature, MockBanner, PageHeader, Segmented } from "@/components/ui";
import { PLANNED_ENDPOINTS } from "@/lib/api/planned";
import { LANGUAGE_CODES, type LanguageCode } from "@/lib/api/types";
import { LANGUAGES } from "@/lib/languages";

const ROUTE_STEPS = [
  ["Estimate input tokens", "Count the optimized prompt with the model's own tokenizer where possible; otherwise label it an estimate."],
  ["Filter ineligible models", "Drop models that fail the task/modality, language, context size, minimum quality or maximum latency."],
  ["Estimate cost", "Current registry prices × expected input and output tokens."],
  ["Choose the lowest cost", "Measured latency, then quality, break ties."],
  ["Explain or fall back", "If nothing qualifies, say which constraint failed and ask, or use a configured fallback."],
  ["Show the decision", "Selected model + reason. A manually locked model is never switched silently."],
] as const;

/** Clearly fictional rows for the layout preview. No real model names, prices or scores. */
const MOCK_ROWS = [
  { id: "mock-model-a", provider: "Mock provider 1", eligible: true, reason: "Meets every constraint (mock)", pick: true },
  { id: "mock-model-b", provider: "Mock provider 2", eligible: true, reason: "Eligible; higher mock cost", pick: false },
  { id: "mock-model-c", provider: "Mock provider 1", eligible: false, reason: "Excluded: language support not tested (mock)", pick: false },
  { id: "mock-model-d", provider: "Mock provider 3", eligible: false, reason: "Excluded: context limit below requirement (mock)", pick: false },
];

export default function ModelsView() {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [language, setLanguage] = useState<LanguageCode>("kn");
  const [task, setTask] = useState("general");
  const [context, setContext] = useState("8000");
  const [quality, setQuality] = useState(70);
  const [latency, setLatency] = useState("3000");
  const [locked, setLocked] = useState(false);
  const [mock, setMock] = useState(false);

  return (
    <>
      <PageHeader
        eyebrow={<>Reduce <Badge tone="blue">F07</Badge> <Badge tone="planned">Planned · Phase 4</Badge></>}
        title="Model Recommendation"
        lede="Auto mode filters models against your language, task, context, quality and latency requirements, then picks the lowest-cost eligible model and explains why. It's never claimed to be the best without measured evidence."
        meta={<label className="checkbox small"><input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} /> Show layout preview with mock data</label>}
      />

      <div className="split-aside">
        <section className="panel" aria-label="Requirements">
          <div className="panel-head"><div><h2>Requirements</h2><p>What the answer must meet</p></div></div>
          <div className="panel-body stack">
            <Field label="Selection mode">
              <Segmented label="Selection mode" value={mode} onChange={setMode} options={[{ value: "auto", label: "Auto" }, { value: "manual", label: "Manual" }]} />
            </Field>
            <Field label="Language" htmlFor="md-lang">
              <select id="md-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode)}>
                {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
              </select>
            </Field>
            <Field label="Task / domain" htmlFor="md-task">
              <select id="md-task" className="select" value={task} onChange={(e) => setTask(e.target.value)}>
                <option value="general">General</option><option value="education">Education</option><option value="agriculture">Agriculture</option><option value="support">Customer support</option>
              </select>
            </Field>
            <Field label="Minimum context (tokens)" htmlFor="md-ctx"><input id="md-ctx" className="input num" type="number" min={0} value={context} onChange={(e) => setContext(e.target.value)} /></Field>
            <Field label="Minimum task quality" hint="Score on the team's evaluation set (not defined yet)">
              <div className="range-row"><input type="range" min={0} max={100} value={quality} onChange={(e) => setQuality(Number(e.target.value))} aria-label="Minimum task quality" /><span className="num small">{quality}</span></div>
            </Field>
            <Field label="Maximum latency (ms, p95)" htmlFor="md-lat"><input id="md-lat" className="input num" type="number" min={0} value={latency} onChange={(e) => setLatency(e.target.value)} /></Field>
          </div>
          <div className="panel-foot btn-row">
            <button className="btn btn-primary" disabled title="Needs POST /api/models/recommend (Phase 4)">Recommend</button>
            <button className="btn btn-ghost" onClick={() => setLocked((l) => !l)} aria-pressed={locked}>{locked ? <IconLock /> : <IconUnlock />} {locked ? "Model locked" : "Lock model"}</button>
          </div>
        </section>

        <div className="stack-lg" style={{ minWidth: 0 }}>
          <InactiveFeature title="Model registry and recommendation" endpoint={PLANNED_ENDPOINTS.modelsRecommend}>
            Needs a registry of providers, model IDs and versions, verified prices, context limits, documented or tested language support, quality scores and measured latency.
          </InactiveFeature>

          <section className={`panel${mock ? " mock-region" : ""}`}>
            <div className="panel-head"><div><h2>Eligible models</h2><p>{mode === "auto" ? "Auto: lowest-cost eligible model" : "Manual: you pick; Auto is overridden"} · {LANGUAGES[language].name} · {task}</p></div></div>
            {!mock ? (
              <EmptyState title="No models registered">
                The model registry arrives in Phase 4. Models will be added only with verified prices and tested language support.
              </EmptyState>
            ) : (
              <div className="panel-body stack">
                <MockBanner />
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Model</th><th>Provider</th><th>Language</th><th>Context</th><th>Quality</th><th>Latency p95</th><th>Est. cost</th><th>Decision</th></tr></thead>
                    <tbody>
                      {MOCK_ROWS.map((r) => (
                        <tr key={r.id} className={r.pick ? "is-best" : undefined}>
                          <td className="mono" style={{ whiteSpace: "nowrap" }}>{r.id}</td><td>{r.provider}</td>
                          {[0, 1, 2, 3, 4].map((k) => <td key={k}><Badge tone="mock">Mock</Badge></td>)}
                          <td>{r.pick ? <Badge tone="blue">Selected (mock)</Badge> : r.eligible ? <Badge tone="outline">Eligible</Badge> : <Badge tone="neutral">Excluded</Badge>}<div className="small subtle">{r.reason}</div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head"><div><h2>How Auto routing decides</h2><p>PRD §10.2</p></div></div>
            <div className="panel-body"><div className="route-flow">
              {ROUTE_STEPS.map(([t, d]) => <div className="route-step" key={t}><div><h3>{t}</h3><p>{d}</p></div></div>)}
            </div></div>
          </section>
        </div>
      </div>
    </>
  );
}
