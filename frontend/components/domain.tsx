"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LanguageCode } from "@/lib/api/types";
import { useTokenizers } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { pieceStats, toDisplayPieces } from "@/lib/pieces";
import { loadPrefs, savePrefs } from "@/lib/storage";
import { IconMic, IconStop } from "./icons";
import { Callout, Segmented } from "./ui";

// ---------------------------------------------------------------- Token segmentation
export function TokenPieces({ pieces, lang }: { pieces: string[]; lang?: string }) {
  const [mode, setMode] = useState<"chips" | "inline">("chips");
  const items = useMemo(() => toDisplayPieces(pieces), [pieces]);
  const stats = useMemo(() => pieceStats(pieces), [pieces]);
  const MAX = 1500;
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div className="piece-legend">
          <span><span className="swatch" style={{ background: "var(--blue-50)" }} />Token</span>
          <span><span className="swatch" style={{ background: "var(--red-50)", borderColor: "var(--red-100)" }} />Byte fragment ({stats.fragments})</span>
          <span><span className="swatch" style={{ background: "var(--white)" }} />· = space</span>
        </div>
        <Segmented label="Segmentation view" value={mode} onChange={setMode}
          options={[{ value: "chips", label: "Chips" }, { value: "inline", label: "Inline" }]} />
      </div>
      <div className={`pieces${mode === "inline" ? " is-plain" : ""}`} lang={lang} aria-label={`${pieces.length} token pieces`}>
        {items.slice(0, MAX).map((p) => (
          <span key={p.index} tabIndex={0}
            className={`piece${p.kind === "space" ? " piece-space" : ""}${p.kind === "fragment" ? " piece-fragment" : ""}`}
            title={`#${p.index + 1}${p.kind === "fragment" ? " · partial UTF-8 bytes of a character" : ""} · ${JSON.stringify(p.raw)}`}>
            {p.display}
          </span>
        ))}
      </div>
      {items.length > MAX && <p className="small subtle">Showing the first {MAX} of {items.length} pieces.</p>}
      {stats.fragments > 0 && (
        <p className="small muted">
          {Math.round(stats.fragmentShare * 100)}% of tokens are <b>byte fragments</b>: the tokenizer splits a single character
          into several byte-level tokens. Byte-level BPE vocabularies do this for scripts they cover poorly.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Tokenizer selector
export function TokenizerSelect({ id, value, onChange, disabled }: {
  id?: string; value: string; onChange: (v: string) => void; disabled?: boolean;
}) {
  const { data, error, loading } = useTokenizers();
  const list = data?.tokenizers ?? [];
  useEffect(() => {
    if (!list.length || list.includes(value)) return;
    const pref = loadPrefs().defaultTokenizer;
    onChange(pref && list.includes(pref) ? pref : list[0] ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.join(","), value]);
  return (
    <>
      <select id={id} className="select" value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled || loading || !!error || !list.length}>
        {loading && <option value="">Loading tokenizers…</option>}
        {error && <option value="">Tokenizers unavailable</option>}
        {list.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      {error && (
        <p className="field-error" role="alert">
          Could not load tokenizers from the backend: {error instanceof Error ? error.message : String(error)}.
          Check that the API is running and that this page&apos;s address ({typeof window !== "undefined" ? window.location.origin : "this origin"}) is allowed in REDUTAX_CORS_ORIGINS.
        </p>
      )}
    </>
  );
}

// ---------------------------------------------------------------- Browser speech input (F08)
/* Minimal typing for the Web Speech API (not in lib.dom for all browsers). */
interface SRAlternative { transcript: string; confidence: number }
interface SRResult { isFinal: boolean; 0: SRAlternative; length: number }
interface SREvent { resultIndex: number; results: { length: number; [i: number]: SRResult } }
interface SRInstance {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: SREvent) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type SRCtor = new () => SRInstance;

function getRecognition(): SRCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const SPEECH_LOCALES: Record<LanguageCode, string> = { kn: "kn-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN", en: "en-IN" };

export interface TranscriptResult { text: string; confidence: number | null; language: LanguageCode }

/**
 * Browser speech recognition. The audio is processed by the browser vendor's speech service
 * (third party), so an explicit notice must be accepted first (PRD §17).
 */
export function SpeechInput({ onTranscript, compact }: { onTranscript: (r: TranscriptResult) => void; compact?: boolean }) {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [lang, setLang] = useState<LanguageCode>("kn");
  const [live, setLive] = useState(false);
  const [interim, setInterim] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const recRef = useRef<SRInstance | null>(null);

  useEffect(() => {
    setSupported(getRecognition() !== null);
    setAccepted(loadPrefs().voiceNoticeAccepted);
    return () => recRef.current?.abort();
  }, []);

  const accept = () => {
    savePrefs({ ...loadPrefs(), voiceNoticeAccepted: true });
    setAccepted(true);
  };

  const start = () => {
    const Ctor = getRecognition();
    if (!Ctor) return;
    setErr(null);
    setInterim("");
    const rec = new Ctor();
    rec.lang = SPEECH_LOCALES[lang];
    rec.continuous = false;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let finalText = "";
      let conf: number | null = null;
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (!r) continue;
        if (r.isFinal) { finalText += r[0].transcript; conf = r[0].confidence || null; } else interimText += r[0].transcript;
      }
      setInterim(interimText);
      if (finalText) onTranscript({ text: finalText.trim(), confidence: conf, language: lang });
    };
    rec.onerror = (e) => setErr(e.error === "not-allowed" ? "Microphone permission was denied." : `Speech recognition error: ${e.error}`);
    rec.onend = () => { setLive(false); setInterim(""); };
    recRef.current = rec;
    try { rec.start(); setLive(true); } catch { setErr("Could not start speech recognition."); }
  };

  const stop = () => recRef.current?.stop();

  if (supported === false) {
    return <Callout tone="neutral" title="Voice input is not available in this browser">The Web Speech API is not supported here (e.g. Firefox). Type your text instead.</Callout>;
  }
  if (!accepted) {
    return (
      <Callout tone="info" title="Before using voice input">
        Your browser sends the audio to its own speech service (a third party, e.g. Google for Chrome, Microsoft for Edge)
        to make the transcript. REDUTAX does not record or store audio. Transcription quality for Kannada, Hindi, Tamil and Telugu has not been measured.
        <div style={{ marginTop: 8 }}><button className="btn btn-sm btn-secondary" onClick={accept}>I understand, enable voice input</button></div>
      </Callout>
    );
  }
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="row" style={{ alignItems: "center", gap: 12 }}>
        <button type="button" className={`${compact ? "btn btn-secondary btn-sm" : "mic-btn"}${live && !compact ? " is-live" : ""}`}
          onClick={live ? stop : start} aria-pressed={live} aria-label={live ? "Stop recording" : "Start recording"}>
          {live ? <IconStop width={compact ? 14 : 26} height={compact ? 14 : 26} /> : <IconMic width={compact ? 14 : 28} height={compact ? 14 : 28} />}
          {compact && (live ? "Stop" : "Speak")}
        </button>
        <label className="field" style={{ minWidth: 150 }}>
          <span className="field-label">Speech language</span>
          <select className="select" value={lang} onChange={(e) => setLang(e.target.value as LanguageCode)} disabled={live}>
            {Object.values(LANGUAGES).map((l) => <option key={l.code} value={l.code}>{l.name} ({SPEECH_LOCALES[l.code]})</option>)}
          </select>
        </label>
        <span className="small subtle" aria-live="polite">{live ? (interim ? `Hearing: ${interim}` : "Listening…") : "Browser speech service · not verified for Indic languages"}</span>
      </div>
      {err && <Callout tone="error">{err}</Callout>}
    </div>
  );
}
