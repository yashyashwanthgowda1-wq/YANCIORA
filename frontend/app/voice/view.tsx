"use client";
import { useRef, useState } from "react";
import { MeaningFindings, MeaningStatusBadge, OptimizeResults, ReviewBadge, visible } from "@/components/analysis";
import { SpeechInput, TokenizerSelect, type TranscriptResult } from "@/components/domain";
import { IconMic, IconPhone, IconStop, IconTrash } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, EmptyState, ErrorState, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api/client";
import { LANGUAGE_CODES, type LanguageCode, type TextEdit } from "@/lib/api/types";
import { fmtDec, fmtInt } from "@/lib/format";
import { useAction, useApi } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { useModelCatalog } from "@/lib/models";
import { logActivity } from "@/lib/storage";

const CALL_FLOW = [
  ["1", "Incoming call", "Vapi number answers"],
  ["2", "Speech", "Vapi STT / TTS"],
  ["3", "Backend", "Authenticated webhook"],
  ["4", "Language", "detect_language tool"],
  ["5", "Optimize", "optimize_prompt + check_meaning"],
  ["6", "Route", "recommend_model + estimate_cost"],
  ["7", "Respond", "Vapi model speaks the answer"],
  ["8", "Fallback", "Tool error → apology, no invented result"],
] as const;

interface Take extends TranscriptResult { id: number; at: string; source: "browser" | "server" }

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

export default function VoiceView() {
  const [takes, setTakes] = useState<Take[]>([]);
  const [editing, setEditing] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "auto">("auto");
  const [n, setN] = useState(1);
  const [approved, setApproved] = useState<number[]>([]);
  const [recording, setRecording] = useState(false);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const catalog = useModelCatalog();
  const status = useApi((signal) => api.integrations({ signal }), []);
  const vapi = useApi((signal) => api.vapiStatus({ signal }), []);
  const sttReady = !!status.data?.speech_to_text.configured;

  const addTake = (r: TranscriptResult, source: Take["source"]) => {
    setTakes((t) => [{ ...r, id: n, at: new Date().toLocaleTimeString("en-IN"), source }, ...t].slice(0, 8));
    setN((x) => x + 1); setEditing(r.text); setLanguage(r.language); process.reset(); apply.reset(); setApproved([]);
  };

  const transcribe = useAction(async (signal, blob: Blob) => {
    const res = await api.transcribe({ audio_base64: await blobToBase64(blob), mime_type: blob.type || "audio/webm", language }, { signal });
    addTake({ text: res.text, confidence: null, language: res.language ?? (language === "auto" ? "en" : language) }, "server");
    return res;
  });

  const startServerRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
      rec.onstop = () => { stream.getTracks().forEach((t) => t.stop()); setRecording(false); transcribe.run(new Blob(chunks.current, { type: rec.mimeType })); };
      recRef.current = rec; rec.start(); setRecording(true);
    } catch { setRecording(false); }
  };

  const process = useAction(async (signal) => {
    const res = await api.analyze({ text: editing, language, tokenizer: tokenizer || "cl100k_base", mode: "safe",
      custom_models: catalog.custom, expected_output_tokens: 256 }, { signal });
    setApproved([]); apply.reset();
    logActivity({ kind: "voice", href: "/voice", summary: `Voice prompt · ${res.tokens.token_count} tokens · ${res.optimization.meaning_check.status}` });
    return res;
  });
  const apply = useAction(async (signal) => {
    const o = process.data!.optimization;
    const edits: TextEdit[] = [...o.accepted, ...approved.map((i) => o.suggestions[i]!)].map((e) => ({ start: e.start, end: e.end, after: e.after }));
    return api.applyEdits({ original: editing, edits, language, tokenizer: tokenizer || "cl100k_base" }, { signal });
  });
  const a = process.data;

  return (
    <>
      <PageHeader
        eyebrow={<>Assist <Badge tone="blue">F08 · F10</Badge> <Badge tone="outline">{vapi.data?.auth_configured ? "Webhook ready" : "Text workflow live"}</Badge></>}
        title="Voice & Calls"
        lede="Speak or type, check the transcript, then run it through REDUTAX: token count, safe optimization, meaning check, recommendation and cost. You approve every uncertain change. The telephone assistant (Vapi) calls the same backend tools."
      />

      <section style={{ marginBottom: 40 }}>
        <div className="section-title"><h2>Voice → optimized prompt</h2><span className="small subtle">Transcript first, then optimization (PRD §12.1)</span></div>
        <div className="workbench">
          <div className="panel">
            <div className="panel-body stack">
              <SpeechInput onTranscript={(r) => addTake(r, "browser")} />
              <div className="row" style={{ alignItems: "center", gap: 12 }}>
                <button type="button" className="btn btn-secondary btn-sm" disabled={!sttReady || transcribe.loading}
                  onClick={() => (recording ? recRef.current?.stop() : startServerRecording())}
                  title={sttReady ? "Record and transcribe with the server's speech-to-text provider" : "No speech-to-text provider configured on the server"}>
                  {recording ? <IconStop width={14} height={14} /> : <IconMic width={14} height={14} />} {recording ? "Stop & transcribe" : "Record for server transcription"}
                </button>
                {transcribe.loading && <span className="small"><span className="spinner" /> Transcribing…</span>}
                <span className="small subtle">{sttReady ? "Server speech-to-text configured" : "Server speech-to-text not configured: use browser voice input or type"}</span>
              </div>
              {transcribe.error && <ErrorState error={transcribe.error} compact />}
              <div className="field">
                <label className="field-label" htmlFor="vc-edit"><span>Transcript (edit before using)</span></label>
                <textarea id="vc-edit" className="textarea indic" rows={4} value={editing} onChange={(e) => { setEditing(e.target.value); process.reset(); apply.reset(); }} placeholder="Your transcript appears here. Correct it, record again, or type." />
              </div>
              <div className="row">
                <select className="select" style={{ width: 160 }} aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode | "auto")}>
                  <option value="auto">Language: auto</option>{LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
                </select>
                <div style={{ minWidth: 180 }}><TokenizerSelect value={tokenizer} onChange={setTokenizer} /></div>
                <button className="btn btn-primary" disabled={!editing.trim() || !tokenizer || process.loading} onClick={() => process.run()}>{process.loading && <span className="spinner" />} Process prompt</button>
              </div>
              {process.error && <ErrorState error={process.error} onRetry={() => process.run()} compact />}
              {a && (
                <div className="stat-strip">
                  <Stat label="Tokens" value={fmtInt(a.tokens.token_count)} />
                  <Stat label="Words" value={fmtInt(a.tokens.word_count)} />
                  <Stat label="Tokens / word" value={fmtDec(a.tokens.tokens_per_word)} />
                  <div className="stat"><span className="stat-label">Status</span><span style={{ marginTop: 6 }}><CountStatusBadge status={a.tokens.status} /></span></div>
                </div>
              )}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><div><h2>Takes</h2><p>This session only, never stored</p></div>
              {takes.length > 0 && <button className="btn btn-sm btn-ghost" onClick={() => setTakes([])}><IconTrash /> Clear</button>}</div>
            {takes.length === 0 ? (
              <EmptyState art="phone" title="No recordings yet">Press the microphone and speak, or type the prompt on the left. Each final transcript appears here.</EmptyState>
            ) : (
              <div className="table-wrap" style={{ border: 0 }}>
                <table className="table">
                  <thead><tr><th>#</th><th>Transcript</th><th>Language</th><th className="num">Confidence</th><th /></tr></thead>
                  <tbody>{takes.map((t) => (
                    <tr key={t.id}>
                      <td className="num subtle">{t.id}</td>
                      <td className="cell-text"><span className="clip indic" lang={t.language}>{t.text}</span><div className="small subtle">{t.at} · {t.source === "server" ? "server STT" : "browser"}</div></td>
                      <td>{LANGUAGES[t.language].name}</td>
                      <td className="num">{t.confidence !== null ? `${(t.confidence * 100).toFixed(0)}%` : "—"}{t.confidence !== null && t.confidence < 0.6 && <div><Badge tone="red">Low, check it</Badge></div>}</td>
                      <td><button className="btn btn-sm btn-ghost" onClick={() => { setEditing(t.text); setLanguage(t.language); process.reset(); apply.reset(); }}>Use</button></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {a && (
          <div className="stack-lg" style={{ marginTop: 24 }}>
            {a.optimization.suggestions.length > 0 && (
              <section className="panel">
                <div className="panel-head"><div><h2>Approve uncertain changes</h2><p>Nothing below is applied unless you tick it</p></div><ReviewBadge /></div>
                <div className="panel-body stack">
                  {a.optimization.suggestions.map((s, i) => (
                    <label key={i} className="checkbox small" style={{ display: "flex", alignItems: "flex-start" }}>
                      <input type="checkbox" checked={approved.includes(i)} disabled={s.kind === "script_variant"} onChange={() => { setApproved((x) => (x.includes(i) ? x.filter((y) => y !== i) : [...x, i])); apply.reset(); }} />
                      <span>{s.kind.replace(/_/g, " ")} · <code>{visible(s.before).slice(0, 50)}</code> → <code>{visible(s.after).slice(0, 50)}</code> · <MeaningStatusBadge status={s.meaning_status} /></span>
                    </label>
                  ))}
                </div>
              </section>
            )}
            <div className="btn-row">
              <button className="btn btn-primary" disabled={apply.loading} onClick={() => apply.run()}>{apply.loading && <span className="spinner" />} Apply {approved.length ? "approved edits + " : ""}safe edits and compare</button>
              <span className="small subtle">{a.next_step}</span>
            </div>
            {apply.error && <ErrorState error={apply.error} compact />}
            {apply.data && (
              <section className="panel">
                <div className="panel-head"><div><h2>Original vs final prompt</h2><p>{apply.data.tokens_before} → {apply.data.tokens_after} tokens · {apply.data.tokenizer.name}</p></div><MeaningStatusBadge status={apply.data.meaning_check.status} /></div>
                <div className="panel-body stack">
                  <div className="side-by-side">
                    <div><div className="side-label"><span className="kicker">Original</span></div><p className="indic" style={{ whiteSpace: "pre-wrap" }}>{editing}</p></div>
                    <div><div className="side-label"><span className="kicker">Final ({apply.data.applied_count} edit{apply.data.applied_count === 1 ? "" : "s"})</span></div><p className="indic" style={{ whiteSpace: "pre-wrap" }}>{apply.data.text}</p></div>
                  </div>
                  {!apply.data.allowed && <Callout tone="error" title="Not allowed">A critical detail changed; do not use this text.</Callout>}
                  {apply.data.warnings.map((w, i) => <Callout key={i} tone="warn">{w}</Callout>)}
                  <MeaningFindings mc={apply.data.meaning_check} />
                </div>
              </section>
            )}
            <OptimizeResults res={a.optimization} />
            {a.recommendation && (
              <Callout tone={a.recommendation.recommended ? "success" : "warn"} title={a.recommendation.recommended ? `Recommended model: ${a.recommendation.recommended.model_id}` : "No recommendation"}>{a.recommendation.explanation}</Callout>
            )}
          </div>
        )}
      </section>

      <section className="stack-lg">
        <div className="section-title"><h2>Telephone assistant · Vapi</h2><Badge tone={vapi.data?.auth_configured ? "blue" : "outline"}>{vapi.data?.auth_configured ? "Backend ready" : "Backend prepared · secret not set"}</Badge></div>
        <div className="flow-strip" aria-label="Inbound call flow">
          {CALL_FLOW.map(([k, t, d]) => <div className="flow-node" key={k}><span className="k">STEP {k}</span><b>{t}</b><span>{d}</span></div>)}
        </div>
        <div className="grid-2">
          <section className="panel">
            <div className="panel-head"><div><h2>Integration status</h2><p>Credentials live on the server only</p></div></div>
            <div className="panel-body">
              {vapi.error && <ErrorState error={vapi.error} compact />}
              <ul className="checklist">
                <li><span>Webhook <span className="endpoint">{vapi.data?.webhook_path ?? "/api/vapi/webhook"}</span></span><Badge tone="blue">Implemented</Badge></li>
                <li><span>Request authentication</span>{vapi.data?.auth_configured ? <Badge tone="blue">{vapi.data.auth_modes.join(" · ")}</Badge> : <Badge tone="planned">Secret not set: requests refused</Badge>}</li>
                <li><span>Tools ({vapi.data?.tools.length ?? 6})</span><span className="small mono">{vapi.data?.tools.join(", ")}</span></li>
                <li><span>Assistant config</span><span className="small mono">{vapi.data?.assistant_config}</span></li>
                <li><span>Vapi assistant + phone number</span><Badge tone="planned">Connect in Vapi (guide)</Badge></li>
                <li><span>Live call verified</span>{vapi.data?.live_call_verified ? <Badge tone="blue">Yes</Badge> : <Badge tone="outline">Not yet</Badge>}</li>
                <li><span>Raw audio retention</span><Badge tone="blue">Off: REDUTAX never stores audio</Badge></li>
              </ul>
              <p className="small subtle" style={{ marginTop: 8 }}>Guide: <code>{vapi.data?.connection_guide ?? "docs/VAPI_FINAL_CONNECTION_GUIDE.md"}</code></p>
            </div>
            <div className="panel-foot btn-row"><button className="btn btn-secondary" disabled title="Calls are placed from Vapi after you connect the assistant (see the guide)"><IconPhone /> Place test call</button><span className="small subtle">Test calls are made from Vapi once the assistant is connected.</span></div>
          </section>
          <section className="panel">
            <div className="panel-head"><div><h2>Call metrics</h2><p>Aggregates across recorded calls</p></div></div>
            <div className="stat-strip" style={{ border: 0 }}>
              <Stat label="Calls" value="—" /><Stat label="Median duration" value="—" /><Stat label="Tokens (provider)" value="—" /><Stat label="Fallbacks" value="—" />
            </div>
            <div className="panel-body"><p className="small muted">No calls yet. The webhook acknowledges end-of-call reports but REDUTAX does not store call content; metrics need an approved retention policy first.</p></div>
          </section>
        </div>
        <section className="panel">
          <div className="panel-head"><div><h2>Call log</h2><p>Phone numbers masked; transcripts shown only where policy allows</p></div></div>
          <div className="table-wrap" style={{ border: 0, borderRadius: 0 }}>
            <table className="table">
              <thead><tr><th>Call ID</th><th>Started</th><th>Duration</th><th>Language</th><th>Model</th><th>Status</th><th>Transcript</th></tr></thead>
              <tbody><tr><td colSpan={7}><EmptyState art="phone" title="No calls recorded">No live call has been made yet. After you connect Vapi, tool calls appear in the backend log by call ID (no content is logged).</EmptyState></td></tr></tbody>
            </table>
          </div>
        </section>
      </section>
    </>
  );
}
