"use client";
import { useEffect, useState } from "react";
import { MeaningFindings, MeaningStatusBadge, ReviewBadge, visible } from "@/components/analysis";
import { SpeechInput } from "@/components/domain";
import { IconLock, IconSend, IconUnlock } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, ErrorState, PageHeader, Segmented } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import {
  LANGUAGE_CODES, MAX_TEXT_CHARS, type AnalyzeResponse, type ApplyEditsResponse, type ChatTurn, type LanguageCode,
  type TextEdit, type TokenizeResponse,
} from "@/lib/api/types";
import { fmtInt, fmtMoney } from "@/lib/format";
import { useAction, useApi, useTokenizers } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { useModelCatalog } from "@/lib/models";
import { loadPrefs, logActivity } from "@/lib/storage";

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
  const [language, setLanguage] = useState<LanguageCode | "auto">("auto");
  const [voiceMeta, setVoiceMeta] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState<{ original: string; analysis: AnalyzeResponse } | null>(null);
  const [approved, setApproved] = useState<number[]>([]);
  const [prepared, setPrepared] = useState<ApplyEditsResponse | null>(null);
  const [manualModel, setManualModel] = useState("");
  const live = useLiveCount(draft);
  const catalog = useModelCatalog();
  const status = useApi((signal) => api.integrations({ signal }), []);
  const llmReady = !!status.data?.llm.configured;
  const lockedModel = mode === "manual" ? manualModel || null : locked ? pending?.analysis.recommendation?.recommended?.model_id ?? null : null;

  const analyze = useAction(async (signal) => {
    const text = draft;
    const res = await api.chat({ session_id: sessionId, text, language, tokenizer: live.tokenizer ?? "cl100k_base",
      mode: "safe", custom_models: catalog.custom, locked_model_id: lockedModel, expected_output_tokens: 256 }, { signal });
    setSessionId(res.session_id); setHistory(res.history); setPending({ original: text, analysis: res.analysis });
    setApproved([]); setPrepared(null); setDraft(""); setVoiceMeta(null);
    logActivity({ kind: "chat", href: "/chat", summary: `Analysed message · ${res.analysis.tokens.token_count} tokens · ${res.analysis.optimization.meaning_check.status}` });
    return res;
  });

  const prepare = useAction(async (signal) => {
    if (!pending) return null;
    const o = pending.analysis.optimization;
    const chosen = approved.map((i) => o.suggestions[i]!);
    const script = chosen.find((s) => s.kind === "script_variant");
    const edits: TextEdit[] = script ? [{ start: script.start, end: script.end, after: script.after }]
      : [...o.accepted, ...chosen].map((e) => ({ start: e.start, end: e.end, after: e.after }));
    const res = await api.applyEdits({ original: pending.original, edits, language, tokenizer: live.tokenizer ?? "cl100k_base" }, { signal });
    setPrepared(res);
    return res;
  });

  const send = useAction(async (signal) => {
    if (!sessionId || !prepared) return null;
    const res = await api.chatSend(sessionId, { text: prepared.text, language }, { signal });
    setHistory(res.history); setPending(null); setPrepared(null);
    return res;
  });

  const newChat = () => {
    if (sessionId) api.chatDelete(sessionId).catch(() => undefined);
    setSessionId(null); setHistory([]); setPending(null); setPrepared(null); setDraft(""); setVoiceMeta(null);
    analyze.reset(); send.reset(); prepare.reset();
  };
  const toggle = (i: number) => { setApproved((a) => (a.includes(i) ? a.filter((x) => x !== i) : [...a, i])); setPrepared(null); };
  const opt = pending?.analysis.optimization;
  const scriptChosen = !!opt && approved.some((i) => opt.suggestions[i]?.kind === "script_variant");

  return (
    <>
      <PageHeader
        eyebrow={<>Assist <Badge tone="blue">F09 · Live</Badge> <Badge tone="outline">{llmReady ? "LLM connected" : "Analysis mode"}</Badge></>}
        title="AI Chat"
        lede="Every message goes through REDUTAX first: token count, safe optimization, meaning check, model recommendation and cost. You approve the prompt; only then is it sent to the configured model. Without a configured model, chat stays in REDUTAX analysis mode and never invents an answer."
      />

      <div className="chat-layout">
        <section className="chat-main" aria-label="Conversation">
          <div className="chat-bar">
            <Segmented label="Model selection" value={mode} onChange={setMode} options={[{ value: "auto", label: "Auto" }, { value: "manual", label: "Manual" }]} />
            <select className="select" style={{ width: 200, height: 32 }} aria-label="Model" disabled={mode === "auto"} value={mode === "auto" ? "" : manualModel} onChange={(e) => setManualModel(e.target.value)}>
              {mode === "auto" ? <option value="">Auto: recommendation decides</option> : <><option value="">{catalog.all.length ? "Choose a model…" : "No models configured"}</option>
                {catalog.all.map((m) => <option key={m.id} value={m.id}>{m.display_name || m.id}{m.source === "user" ? " (user)" : ""}</option>)}</>}
            </select>
            <button className="btn btn-sm btn-ghost" aria-pressed={locked} disabled={mode === "manual"} onClick={() => setLocked((l) => !l)}>{locked ? <IconLock /> : <IconUnlock />} {locked ? "Locked" : "Lock"}</button>
            <label className="checkbox small"><input type="checkbox" checked={dynamic} disabled={locked} onChange={(e) => setDynamic(e.target.checked)} /> Allow dynamic switching</label>
            <select className="select" style={{ width: 150, height: 32 }} aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode | "auto")}>
              <option value="auto">Language: auto</option>{LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
            </select>
            <span style={{ flex: 1 }} />
            <button className="btn btn-sm btn-ghost" onClick={newChat}>New chat</button>
          </div>

          <div className="chat-transcript" aria-live="polite">
            {history.length === 0 && <p className="kicker" style={{ textAlign: "center", margin: "40px 0" }}>No messages yet · write below and press Analyse</p>}
            {history.map((t, i) => (
              <div key={i} className={`turn-row${t.role === "user" ? " user" : ""}`}>
                <div className="turn-bubble" style={{ maxWidth: "80%" }}>
                  <div className="indic" style={{ whiteSpace: "pre-wrap" }}>{t.content}</div>
                  <div className="turn-meta">
                    {t.kind === "analysis" && <Badge tone="outline">REDUTAX analysis — not an AI reply</Badge>}
                    {t.kind === "llm_reply" && <><Badge tone="blue">{String(t.meta.provider ?? "provider")} · {String(t.meta.model ?? "")}</Badge>
                      {t.meta.prompt_tokens != null && <Badge tone="provider_reported">{String(t.meta.prompt_tokens)} in / {String(t.meta.completion_tokens ?? "?")} out tokens (provider)</Badge>}</>}
                    {t.kind === "message" && t.meta.approved_prompt === true && <Badge tone="outline">Approved prompt, sent to model</Badge>}
                  </div>
                </div>
              </div>
            ))}

            {pending && opt && (
              <div className="turn-row"><div className="turn-bubble" style={{ width: "100%" }}>
                <div className="btn-row" style={{ marginBottom: 6 }}><b>Approve the prompt</b><MeaningStatusBadge status={opt.meaning_check.status} />{opt.requires_review && <ReviewBadge />}</div>
                <p className="small subtle">Tokens {opt.token_counts[0]?.before} → {opt.token_counts[0]?.after} · {opt.accepted.length} safe edit(s) already included · tick suggestions you approve</p>
                <p className="indic small" style={{ whiteSpace: "pre-wrap" }}><b>Optimized:</b> {opt.optimized}</p>
                {opt.suggestions.map((s, i) => (
                  <label key={i} className="checkbox small" style={{ display: "flex", alignItems: "flex-start" }}>
                    <input type="checkbox" checked={approved.includes(i)} disabled={scriptChosen && s.kind !== "script_variant" && !approved.includes(i)} onChange={() => toggle(i)} />
                    <span>{s.kind.replace(/_/g, " ")} · <code>{visible(s.before).slice(0, 40)}</code> → <code>{visible(s.after).slice(0, 40)}</code> · {s.meaning_status} · {Object.values(s.token_delta ?? {})[0] ?? 0} tokens</span>
                  </label>
                ))}
                {pending.analysis.recommendation?.recommended && (
                  <p className="small">Recommended model: <b>{pending.analysis.recommendation.recommended.model_id}</b>
                    {pending.analysis.recommendation.recommended.cost.total_cost !== null && ` · est. ${fmtMoney(pending.analysis.recommendation.recommended.cost.total_cost, pending.analysis.recommendation.recommended.cost.currency ?? "")}`}
                    {pending.analysis.recommendation.locked && " · locked"}</p>
                )}
                <div className="btn-row" style={{ marginTop: 8 }}>
                  <button className="btn btn-sm btn-secondary" disabled={prepare.loading} onClick={() => prepare.run()}>{prepare.loading && <span className="spinner" />} Apply approved edits</button>
                  {prepared && <MeaningStatusBadge status={prepared.meaning_check.status} />}
                  {prepared && <span className="small num">{prepared.tokens_before} → {prepared.tokens_after} tokens</span>}
                </div>
                {prepare.error && <ErrorState error={prepare.error} compact />}
                {prepared && (
                  <div className="stack" style={{ marginTop: 8 }}>
                    <p className="indic" style={{ whiteSpace: "pre-wrap" }}><b>Prompt to send:</b> {prepared.text}</p>
                    {!prepared.allowed && <Callout tone="error" title="Not allowed">A critical detail changed. Change your approvals and apply again.</Callout>}
                    {prepared.warnings.map((w, i) => <Callout key={i} tone="warn">{w}</Callout>)}
                    {prepared.meaning_check.status !== "preserved" && <MeaningFindings mc={prepared.meaning_check} />}
                    <div className="btn-row">
                      <button className="btn btn-primary" disabled={!prepared.allowed || !llmReady || send.loading} onClick={() => send.run()}
                        title={llmReady ? "Send the approved prompt to the configured model" : "No LLM provider configured on the server"}>{send.loading && <span className="spinner" />} <IconSend /> Send to model</button>
                      {!llmReady && <span className="small subtle">No LLM provider is configured, so nothing is sent. Copy the prompt, or configure LLM_* on the backend.</span>}
                    </div>
                    {send.error && <ErrorState error={send.error} compact />}
                  </div>
                )}
              </div></div>
            )}
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
              <button className="btn btn-primary" disabled={!draft.trim() || draft.length > MAX_TEXT_CHARS || analyze.loading} onClick={() => analyze.run()}>{analyze.loading && <span className="spinner" />} <IconSend /> Analyse</button>
            </div>
            {analyze.error && <div style={{ marginTop: 8 }}><ErrorState error={analyze.error} onRetry={() => analyze.run()} compact /></div>}
            <div style={{ marginTop: 10 }}>
              <SpeechInput compact onTranscript={(r) => {
                setDraft((d) => (d ? `${d} ${r.text}` : r.text));
                setVoiceMeta(`Voice · ${r.language}${r.confidence !== null ? ` · confidence ${(r.confidence * 100).toFixed(0)}%` : ""}`);
                setLanguage(r.language);
              }} />
            </div>
          </div>
        </section>

        <aside className="stack">
          <section className="panel">
            <div className="panel-head"><div><h2>Chat service</h2><p><code>POST /api/chat</code> · <code>/api/chat/&#123;id&#125;/send</code></p></div></div>
            <div className="panel-body stack">
              {status.error && <ErrorState error={status.error} compact />}
              <ul className="checklist">
                <li><span>REDUTAX analysis</span><Badge tone="blue">Available</Badge></li>
                <li><span>LLM provider</span>{llmReady ? <Badge tone="blue">Configured</Badge> : <Badge tone="planned">Not configured</Badge>}</li>
                <li><span>Models for recommendation</span><b>{catalog.all.length}</b></li>
              </ul>
              <p className="small subtle">{status.data?.llm.detail ?? "Checking provider status…"}</p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head"><h2>Session rules</h2></div>
            <div className="panel-body">
              <ul className="checklist">
                <li><span>Mode</span><b>{mode === "auto" ? "Auto" : "Manual"}</b></li>
                <li><span>Model lock</span><b>{mode === "manual" ? (manualModel ? `Manual: ${manualModel}` : "Manual: none") : locked ? "Locked" : "Unlocked"}</b></li>
                <li><span>Dynamic switching</span><b>{locked ? "Off (locked)" : dynamic ? "Allowed" : "Off"}</b></li>
                <li><span>Optimizer approval</span><b>Required</b></li>
                <li><span>History</span><b>{history.length} turn(s), server memory only</b></li>
              </ul>
              <p className="small subtle" style={{ marginTop: 10 }}>A locked or manually chosen model is never switched silently. History is kept in server memory for this session (up to 2 hours) and is not written to the database.</p>
            </div>
          </section>
          <Callout tone="info" title="Third-party notice">When a model provider is configured, approved prompts are sent to that provider. The provider and model are shown on every reply.</Callout>
        </aside>
      </div>
    </>
  );
}
