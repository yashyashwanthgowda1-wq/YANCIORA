"use client";
import { useEffect, useState } from "react";
import { SpeechInput } from "@/components/domain";
import { IconLock, IconSend, IconUnlock } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, InactiveFeature, PageHeader, Segmented } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { PLANNED_ENDPOINTS } from "@/lib/api/planned";
import { MAX_TEXT_CHARS, type TokenizeResponse } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";
import { useTokenizers } from "@/lib/hooks";
import { loadPrefs } from "@/lib/storage";

/** Debounced live count of the draft with the real tokenizer. */
function useLiveCount(text: string) {
  const toks = useTokenizers();
  const [res, setRes] = useState<TokenizeResponse | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const tokenizer = (() => {
    const list = toks.data?.tokenizers ?? [];
    const pref = typeof window !== "undefined" ? loadPrefs().defaultTokenizer : null;
    return pref && list.includes(pref) ? pref : list[0] ?? null;
  })();
  useEffect(() => {
    if (!text.trim() || !tokenizer || text.length > MAX_TEXT_CHARS) { setRes(null); return; }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api.tokenize({ text, tokenizer }, { signal: ctrl.signal }).then((r) => { setRes(r); setErr(null); })
        .catch((e) => { if (e instanceof ApiError) setErr(e); });
    }, 450);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [text, tokenizer]);
  return { res, err, tokenizer };
}

export default function ChatView() {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [locked, setLocked] = useState(false);
  const [dynamic, setDynamic] = useState(false);
  const [draft, setDraft] = useState("");
  const [voiceMeta, setVoiceMeta] = useState<string | null>(null);
  const live = useLiveCount(draft);

  return (
    <>
      <PageHeader
        eyebrow={<>Assist <Badge tone="blue">F09</Badge> <Badge tone="planned">Planned · Phase 4</Badge></>}
        title="AI Chat"
        lede="Multi-turn chat in your language, through the same optimizer and model router as the rest of REDUTAX. Each turn will show the model used, token usage, cost and why that model was chosen."
      />

      <div className="chat-layout">
        <section className="chat-main" aria-label="Conversation">
          <div className="chat-bar">
            <Segmented label="Model selection" value={mode} onChange={setMode} options={[{ value: "auto", label: "Auto" }, { value: "manual", label: "Manual" }]} />
            <select className="select" style={{ width: 200, height: 32 }} disabled aria-label="Model"><option>{mode === "auto" ? "Auto: router decides" : "No models registered"}</option></select>
            <button className="btn btn-sm btn-ghost" aria-pressed={locked} onClick={() => setLocked((l) => !l)}>{locked ? <IconLock /> : <IconUnlock />} {locked ? "Locked" : "Lock"}</button>
            <label className="checkbox small"><input type="checkbox" checked={dynamic} disabled={locked} onChange={(e) => setDynamic(e.target.checked)} /> Allow dynamic switching</label>
            <span style={{ flex: 1 }} />
            <button className="btn btn-sm btn-ghost" onClick={() => { setDraft(""); setVoiceMeta(null); }}>New chat</button>
          </div>

          <div className="chat-transcript">
            <div className="turn-anatomy" aria-label="What each turn will show">
              <p className="kicker" style={{ textAlign: "center", marginBottom: 18 }}>No messages · the chat service is not connected yet</p>
              <div className="turn-row user">
                <div className="turn-bubble" style={{ width: "62%" }}>
                  <div className="turn-bar" style={{ width: "90%" }} /><div className="turn-bar" style={{ width: "60%" }} />
                  <div className="turn-meta"><Badge tone="outline">Your text, kept as written</Badge><Badge tone="outline">Optimized version, after approval</Badge></div>
                </div>
              </div>
              <div className="turn-row">
                <div className="turn-bubble" style={{ width: "74%" }}>
                  <div className="turn-bar" style={{ width: "95%" }} /><div className="turn-bar" style={{ width: "88%" }} /><div className="turn-bar" style={{ width: "50%" }} />
                  <div className="turn-meta"><Badge tone="outline">Model + version</Badge><Badge tone="outline">Provider-reported tokens</Badge><Badge tone="outline">Estimated / actual cost</Badge><Badge tone="outline">Routing reason</Badge></div>
                </div>
              </div>
            </div>
          </div>

          <div className="composer">
            <textarea className="textarea indic" aria-label="Message" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Write in Kannada, Hindi, Tamil, Telugu, English, or mix them…" />
            <div className="composer-foot">
              <div className="btn-row" aria-live="polite">
                {live.res ? (
                  <><span className="small num"><b>{fmtInt(live.res.token_count)}</b> tokens · {live.res.tokenizer.name}</span><CountStatusBadge status={live.res.status} /></>
                ) : live.err ? <span className="small" style={{ color: "var(--red-700)" }}>Count unavailable: {live.err.code}</span>
                  : <span className="small subtle">{live.tokenizer ? `Live count with ${live.tokenizer}` : "Live count needs the backend"}</span>}
                {voiceMeta && <Badge tone="blue">{voiceMeta}</Badge>}
              </div>
              <button className="btn btn-primary" disabled title="POST /api/chat is not implemented yet (Phase 4)"><IconSend /> Send</button>
            </div>
            <div style={{ marginTop: 10 }}>
              <SpeechInput compact onTranscript={(r) => {
                setDraft((d) => (d ? `${d} ${r.text}` : r.text));
                setVoiceMeta(`Voice · ${r.language}${r.confidence !== null ? ` · confidence ${(r.confidence * 100).toFixed(0)}%` : ""}`);
              }} />
            </div>
          </div>
        </section>

        <aside className="stack">
          <InactiveFeature title="Chat service" endpoint={PLANNED_ENDPOINTS.chat}>Model replies appear only from a real model call. Nothing is simulated.</InactiveFeature>
          <section className="panel">
            <div className="panel-head"><h2>Session rules</h2></div>
            <div className="panel-body">
              <ul className="checklist">
                <li><span>Mode</span><b>{mode === "auto" ? "Auto" : "Manual"}</b></li>
                <li><span>Model lock</span><b>{locked ? "Locked" : "Unlocked"}</b></li>
                <li><span>Dynamic switching</span><b>{locked ? "Off (locked)" : dynamic ? "Allowed" : "Off"}</b></li>
                <li><span>Optimizer approval</span><b>Required</b></li>
              </ul>
              <p className="small subtle" style={{ marginTop: 10 }}>A switch only happens when the conversation context can be carried over safely. A locked model is never switched silently.</p>
            </div>
          </section>
          <Callout tone="info" title="Third-party notice">Once connected, messages will be sent to the selected model provider. The provider is shown on every turn.</Callout>
        </aside>
      </div>
    </>
  );
}
