"use client";
import { useState } from "react";
import { SpeechInput, TokenizerSelect, type TranscriptResult } from "@/components/domain";
import { IconPhone, IconTrash } from "@/components/icons";
import { Badge, CountStatusBadge, EmptyState, ErrorState, InactiveFeature, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api/client";
import { PLANNED_ENDPOINTS } from "@/lib/api/planned";
import { fmtDec, fmtInt } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";

const CALL_FLOW = [
  ["1", "Incoming call", "Vapi number answers"],
  ["2", "Speech", "Vapi STT / TTS"],
  ["3", "Backend", "Secured server URL / tool"],
  ["4", "Optimize", "Language, safe candidate"],
  ["5", "Route", "Precomputed profiles"],
  ["6", "Respond", "Text for spoken playback"],
  ["7", "Complete", "Metadata per retention policy"],
  ["8", "Fallback", "Retry, timeout, human handoff"],
] as const;

interface Take extends TranscriptResult { id: number; at: string }

export default function VoiceView() {
  const [takes, setTakes] = useState<Take[]>([]);
  const [editing, setEditing] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [n, setN] = useState(1);
  const count = useAction(async (signal) => api.tokenize({ text: editing, tokenizer, language: takes[0]?.language ?? "auto" }, { signal }));

  const onTranscript = (r: TranscriptResult) => {
    setTakes((t) => [{ ...r, id: n, at: new Date().toLocaleTimeString("en-IN") }, ...t].slice(0, 8));
    setN((x) => x + 1);
    setEditing(r.text);
    count.reset();
  };

  return (
    <>
      <PageHeader
        eyebrow={<>Assist <Badge tone="blue">F08 · F10</Badge> <Badge tone="outline">Partly available</Badge></>}
        title="Voice & Calls"
        lede="Speak instead of typing, then check the transcript before it goes anywhere. The telephone assistant (Vapi) will use the same optimizer and router as web chat; it's an integration layer, not a separate engine."
      />

      <section style={{ marginBottom: 40 }}>
        <div className="section-title"><h2>Browser voice input</h2><span className="small subtle">Transcript first, then optimization (PRD §12.1)</span></div>
        <div className="workbench">
          <div className="panel">
            <div className="panel-body stack">
              <SpeechInput onTranscript={onTranscript} />
              <div className="field">
                <label className="field-label" htmlFor="vc-edit"><span>Transcript (edit before using)</span></label>
                <textarea id="vc-edit" className="textarea indic" rows={4} value={editing} onChange={(e) => { setEditing(e.target.value); count.reset(); }} placeholder="Your transcript appears here. Correct it, or record again if it's wrong." />
              </div>
              <div className="row">
                <div style={{ minWidth: 180 }}><TokenizerSelect value={tokenizer} onChange={setTokenizer} /></div>
                <button className="btn btn-secondary" disabled={!editing.trim() || !tokenizer || count.loading} onClick={() => count.run()}>{count.loading && <span className="spinner" />} Count tokens</button>
              </div>
              {count.error && <ErrorState error={count.error} compact />}
              {count.data && (
                <div className="stat-strip">
                  <Stat label="Tokens" value={fmtInt(count.data.token_count)} />
                  <Stat label="Words" value={fmtInt(count.data.word_count)} />
                  <Stat label="Tokens / word" value={fmtDec(count.data.tokens_per_word)} />
                  <div className="stat"><span className="stat-label">Status</span><span style={{ marginTop: 6 }}><CountStatusBadge status={count.data.status} /></span></div>
                </div>
              )}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><div><h2>Takes</h2><p>This session only, never stored</p></div>
              {takes.length > 0 && <button className="btn btn-sm btn-ghost" onClick={() => setTakes([])}><IconTrash /> Clear</button>}</div>
            {takes.length === 0 ? (
              <EmptyState art="phone" title="No recordings yet">Press the microphone and speak. Each final transcript appears here with the detected confidence, if the browser gives one.</EmptyState>
            ) : (
              <div className="table-wrap" style={{ border: 0 }}>
                <table className="table">
                  <thead><tr><th>#</th><th>Transcript</th><th>Language</th><th className="num">Confidence</th><th /></tr></thead>
                  <tbody>{takes.map((t) => (
                    <tr key={t.id}>
                      <td className="num subtle">{t.id}</td>
                      <td className="cell-text"><span className="clip indic" lang={t.language}>{t.text}</span><div className="small subtle">{t.at}</div></td>
                      <td>{LANGUAGES[t.language].name}</td>
                      <td className="num">{t.confidence !== null ? `${(t.confidence * 100).toFixed(0)}%` : "—"}{t.confidence !== null && t.confidence < 0.6 && <div><Badge tone="red">Low, check it</Badge></div>}</td>
                      <td><button className="btn btn-sm btn-ghost" onClick={() => { setEditing(t.text); count.reset(); }}>Use</button></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="stack-lg">
        <div className="section-title"><h2>Telephone assistant · Vapi admin</h2><Badge tone="planned">Phase 5</Badge></div>
        <div className="flow-strip" aria-label="Inbound call flow">
          {CALL_FLOW.map(([k, t, d]) => <div className="flow-node" key={k}><span className="k">STEP {k}</span><b>{t}</b><span>{d}</span></div>)}
        </div>
        <div className="grid-2">
          <section className="panel">
            <div className="panel-head"><div><h2>Integration status</h2><p>Credentials live on the server only</p></div></div>
            <div className="panel-body">
              <ul className="checklist">
                <li><span>Vapi phone number / assistant</span><Badge tone="planned">Not configured</Badge></li>
                <li><span>Webhook <span className="endpoint">{PLANNED_ENDPOINTS.vapiWebhook.path}</span></span><Badge tone="planned">Not implemented</Badge></li>
                <li><span>Signature verification</span><Badge tone="planned">Not implemented</Badge></li>
                <li><span>Answer endpoint <span className="endpoint">{PLANNED_ENDPOINTS.vapiAnswer.path}</span></span><Badge tone="planned">Not implemented</Badge></li>
                <li><span>Indic speech providers</span><Badge tone="outline">Open decision</Badge></li>
                <li><span>Raw audio retention</span><Badge tone="blue">Off by default</Badge></li>
              </ul>
            </div>
            <div className="panel-foot btn-row"><button className="btn btn-secondary" disabled title="Needs the Vapi integration (Phase 5)"><IconPhone /> Place test call</button></div>
          </section>
          <section className="panel">
            <div className="panel-head"><div><h2>Call metrics</h2><p>Aggregates across recorded calls</p></div></div>
            <div className="stat-strip" style={{ border: 0 }}>
              <Stat label="Calls" value="—" /><Stat label="Median duration" value="—" /><Stat label="Tokens (provider)" value="—" /><Stat label="Fallbacks" value="—" />
            </div>
            <div className="panel-body"><p className="small muted">No calls yet. Metrics will come from stored call metadata, linked by the Vapi call ID.</p></div>
          </section>
        </div>
        <section className="panel">
          <div className="panel-head"><div><h2>Call log</h2><p>Phone numbers masked; transcripts shown only where policy allows</p></div></div>
          <div className="table-wrap" style={{ border: 0, borderRadius: 0 }}>
            <table className="table">
              <thead><tr><th>Call ID</th><th>Started</th><th>Duration</th><th>Language</th><th>Model</th><th>Status</th><th>Transcript</th></tr></thead>
              <tbody><tr><td colSpan={7}><EmptyState art="phone" title="No calls recorded">The call log fills once the Vapi integration is live.</EmptyState></td></tr></tbody>
            </table>
          </div>
        </section>
        <InactiveFeature title="Vapi optimize-and-answer pipeline" endpoint={PLANNED_ENDPOINTS.vapiAnswer}>
          No tokenizer training or benchmark ever runs during a live call; routing uses precomputed model profiles.
        </InactiveFeature>
      </section>
    </>
  );
}
