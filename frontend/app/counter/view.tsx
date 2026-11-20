"use client";
import { useState } from "react";
import { HBarChart } from "@/components/charts";
import { TokenizerSelect, TokenPieces } from "@/components/domain";
import { IconCopy, IconRefresh } from "@/components/icons";
import { Badge, Callout, CountStatusBadge, ErrorState, Field, PageHeader, Stat, TokenizerTag } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { LANGUAGE_CODES, MAX_TEXT_CHARS, SCRIPTS, type LanguageCode, type Script, type TokenizeResponse } from "@/lib/api/types";
import { fmtDec, fmtInt } from "@/lib/format";
import { useAction, useTokenizers } from "@/lib/hooks";
import { langTag, LANGUAGES, languageLabel, SCRIPT_LABELS } from "@/lib/languages";
import { logActivity } from "@/lib/storage";

interface MultiRow { tokenizer: string; result: TokenizeResponse | null; error: ApiError | null }

export default function CounterView() {
  const [text, setText] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "auto">("auto");
  const [script, setScript] = useState<Script | "">("");
  const [showPieces, setShowPieces] = useState(true);
  const [copied, setCopied] = useState(false);
  const toks = useTokenizers();

  const tooLong = text.length > MAX_TEXT_CHARS;
  const blank = !text.trim();
  const inputError = tooLong ? `Text is longer than ${fmtInt(MAX_TEXT_CHARS)} characters (the server limit).` : null;

  const count = useAction(async (signal) => {
    const r = await api.tokenize({ text, tokenizer, language, script: script || null, include_pieces: showPieces }, { signal });
    logActivity({ kind: "count", href: "/counter", summary: `${fmtInt(r.token_count)} tokens · ${r.tokenizer.name} · ${languageLabel(r.language)}` });
    return r;
  });

  const multi = useAction(async (signal): Promise<MultiRow[]> => {
    const names = toks.data?.tokenizers ?? [];
    return Promise.all(names.map(async (name) => {
      try {
        const result = await api.tokenize({ text, tokenizer: name, language, script: script || null }, { signal });
        return { tokenizer: name, result, error: null };
      } catch (e) {
        if (e instanceof DOMException) throw e;
        return { tokenizer: name, result: null, error: e as ApiError };
      }
    }));
  });

  const r = count.data;
  const canRun = !blank && !tooLong && !!tokenizer;

  const copyResults = async () => {
    if (!r) return;
    const lines = [
      `Tokenizer: ${r.tokenizer.name} (${r.tokenizer.library} ${r.tokenizer.version}, ${r.tokenizer.kind})`,
      `Status: ${r.status}`,
      `Tokens: ${r.token_count}`, `Words: ${r.word_count}`, `Characters: ${r.char_count}`,
      `Tokens per word: ${fmtDec(r.tokens_per_word)}`,
      `Language: ${r.language ?? "unknown"} · Script: ${r.script ?? "unknown"}`,
      `Normalization: ${r.normalization} · Word count: ${r.word_count_method}`,
    ];
    try { await navigator.clipboard.writeText(lines.join("\n")); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };

  const clear = () => { setText(""); count.reset(); multi.reset(); };

  return (
    <>
      <PageHeader
        eyebrow={<>Measure <Badge tone="blue">F01 · Live</Badge></>}
        title="Token Counter"
        lede="Count tokens and words in Kannada, Hindi, Tamil, Telugu or English, in native script, Roman letters or code-mixed text. Every count names the exact tokenizer and version that produced it."
      />

      <div className="workbench">
        {/* ---- Input ---- */}
        <section className="panel" aria-label="Input">
          <div className="panel-body stack">
            <Field label="Text" htmlFor="ct-text" error={inputError}
              aside={<span className={`char-meter${tooLong ? " over" : ""}`}>{fmtInt(text.length)} / {fmtInt(MAX_TEXT_CHARS)}</span>}>
              <textarea id="ct-text" className="textarea indic" rows={9} value={text} onChange={(e) => setText(e.target.value)}
                placeholder="Type or paste text in any supported language or script…" aria-invalid={tooLong} lang={language === "auto" ? undefined : language} />
            </Field>
            <div className="grid-2" style={{ gap: 12 }}>
              <Field label="Language" htmlFor="ct-lang" hint="Auto detects from native script only">
                <select id="ct-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode | "auto")}>
                  <option value="auto">Auto-detect</option>
                  {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name} · {LANGUAGES[c].native}</option>)}
                </select>
              </Field>
              <Field label="Script" htmlFor="ct-script" hint="Leave on detect unless you know better">
                <select id="ct-script" className="select" value={script} onChange={(e) => setScript(e.target.value as Script | "")}>
                  <option value="">Detect</option>
                  {SCRIPTS.map((s) => <option key={s} value={s}>{SCRIPT_LABELS[s]}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Tokenizer / encoding" htmlFor="ct-tok" hint="Encoding baselines. Which hosted model uses which encoding is not asserted.">
              <TokenizerSelect id="ct-tok" value={tokenizer} onChange={setTokenizer} />
            </Field>
            {toks.error && <ErrorState error={toks.error} onRetry={toks.reload} compact />}
            <label className="checkbox"><input type="checkbox" checked={showPieces} onChange={(e) => setShowPieces(e.target.checked)} /> Show token segmentation</label>
          </div>
          <div className="panel-foot btn-row" style={{ justifyContent: "space-between" }}>
            <div className="btn-row">
              <button className="btn btn-primary" disabled={!canRun || count.loading} onClick={() => count.run()}>
                {count.loading && <span className="spinner" />} Count tokens
              </button>
              <button className="btn btn-secondary" disabled={!canRun || multi.loading || !toks.data?.tokenizers.length} onClick={() => multi.run()}>
                {multi.loading && <span className="spinner" />} Compare all tokenizers
              </button>
            </div>
            <button className="btn btn-ghost" onClick={clear} disabled={!text && !r}>Clear</button>
          </div>
        </section>

        {/* ---- Result ---- */}
        <section className="panel" aria-label="Result" aria-live="polite">
          {count.error && <div className="panel-body"><ErrorState error={count.error} onRetry={() => count.run()} /></div>}
          {!r && !count.error && (
            <div className="panel-body">
              <div className="empty" style={{ padding: "48px 12px" }}>
                <svg className="empty-art" viewBox="0 0 64 64" aria-hidden="true">
                  {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={6 + i * 11} y={26} width={9} height={14} rx={2} fill={i % 2 ? "#EEF3FD" : "#F3F4F6"} stroke={i === 3 ? "#F9D9DC" : "#DCDFE5"} />)}
                </svg>
                <h3>No count yet</h3>
                <p>Enter text and press <b>Count tokens</b>. You'll see the token count, words, tokens per word, and how the tokenizer split your text.</p>
              </div>
            </div>
          )}
          {r && (
            <>
              <div className="readout">
                <Stat large label="Tokens" value={fmtInt(r.token_count)} />
                <div className="readout-meta">
                  <div className="btn-row"><CountStatusBadge status={r.status} /><TokenizerTag t={r.tokenizer} /></div>
                  <span className="small subtle">{r.status === "exact" ? "Exact count for this encoding. Not provider-billed usage." : ""}</span>
                </div>
              </div>
              <div className="counter-metrics" style={{ borderBottom: "1px solid var(--border)" }}>
                <Stat label="Words" value={fmtInt(r.word_count)} />
                <Stat label="Characters" value={fmtInt(r.char_count)} />
                <Stat label="Tokens / word" value={fmtDec(r.tokens_per_word)} />
                <Stat label="Language · script" value={<span style={{ fontSize: 16 }}>{r.language ? LANGUAGES[r.language].name : "Unknown"} · {r.script ?? "—"}</span>} />
              </div>
              <div className="panel-body stack">
                {r.language === null && r.script === "Latn" && (
                  <Callout tone="info" title="Latin script: language not assumed">
                    English and Romanized Kannada, Hindi, Tamil or Telugu all use Latin letters. Choose the language above if you want it recorded.
                  </Callout>
                )}
                {r.script === "mixed" && <Callout tone="info" title="Mixed scripts detected">This looks like code-mixed text. Word count is whitespace-based; check attached punctuation.</Callout>}
                {showPieces && r.pieces && (
                  <div>
                    <div className="section-title"><h2>Segmentation</h2><span className="small subtle">{fmtInt(r.pieces.length)} pieces</span></div>
                    <TokenPieces pieces={r.pieces} lang={langTag(r.language, r.script)} />
                  </div>
                )}
                <dl className="meta-list">
                  <dt>Normalization</dt><dd className="mono">{r.normalization}</dd>
                  <dt>Word count method</dt><dd className="mono">{r.word_count_method}</dd>
                  <dt>Tokenizer kind</dt><dd>{r.tokenizer.kind}</dd>
                </dl>
              </div>
              <div className="panel-foot btn-row">
                <button className="btn btn-sm btn-secondary" onClick={copyResults}><IconCopy /> {copied ? "Copied" : "Copy results"}</button>
                <button className="btn btn-sm btn-ghost" onClick={() => count.run()} disabled={!canRun}><IconRefresh /> Recount</button>
              </div>
            </>
          )}
        </section>
      </div>

      {(multi.data || multi.error) && (
        <section className="panel" style={{ marginTop: 24 }} aria-label="Tokenizer comparison">
          <div className="panel-head">
            <div><h2>Same text, every tokenizer</h2><p>Token count of the exact same normalized text under each available encoding.</p></div>
          </div>
          <div className="panel-body stack">
            {multi.error && <ErrorState error={multi.error} />}
            {multi.data && (
              <>
                <HBarChart ariaLabel="Token count by tokenizer"
                  data={multi.data.map((m) => ({
                    key: m.tokenizer, label: m.tokenizer, sublabel: m.result ? `${m.result.tokenizer.library} ${m.result.tokenizer.version}` : "unavailable",
                    value: m.result?.token_count ?? null,
                    tooltip: m.result ? <>{m.tokenizer}<br />{fmtInt(m.result.token_count)} tokens · {fmtDec(m.result.tokens_per_word)} tokens/word</> : m.error?.message,
                  }))} />
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Tokenizer</th><th>Status</th><th className="num">Tokens</th><th className="num">Words</th><th className="num">Tokens / word</th></tr></thead>
                    <tbody>
                      {multi.data.map((m) => (
                        <tr key={m.tokenizer}>
                          <td className="mono">{m.tokenizer}</td>
                          <td>{m.result ? <CountStatusBadge status={m.result.status} /> : <span className="small" style={{ color: "var(--red-700)" }}>{m.error?.code}</span>}</td>
                          <td className="num">{fmtInt(m.result?.token_count)}</td>
                          <td className="num">{fmtInt(m.result?.word_count)}</td>
                          <td className="num">{fmtDec(m.result?.tokens_per_word)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </section>
      )}
    </>
  );
}
