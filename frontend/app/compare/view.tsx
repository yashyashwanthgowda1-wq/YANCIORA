"use client";
import { useState } from "react";
import { ScriptVariantsResults } from "@/components/analysis";
import { HBarChart } from "@/components/charts";
import { TokenizerSelect } from "@/components/domain";
import { IconDownload, IconPlus, IconTrash } from "@/components/icons";
import {
  Badge, Callout, CountStatusBadge, EmptyState, ErrorState, Field, LoadingRows, PageHeader, Pager, Segmented, TokenizerTag,
} from "@/components/ui";
import { api } from "@/lib/api/client";
import {
  LANGUAGE_CODES, MAX_TEXT_CHARS, MAX_VARIANTS, SCRIPTS, SPLITS, TRANSLIT_LANGUAGES, TRANSLIT_SCHEMES, VARIANT_TYPES,
  type CompareResponse, type CompareVariant, type LanguageCode, type SampleGroup, type ScriptVariant, type Split,
  type TranslitLanguage, type TranslitScheme,
} from "@/lib/api/types";
import { downloadText, toCsv } from "@/lib/csv";
import { fmtDec, fmtInt, fmtRatio } from "@/lib/format";
import { useAction, useApi } from "@/lib/hooks";
import { langTag, LANGUAGES, SCRIPT_LABELS, VARIANT_LABELS } from "@/lib/languages";
import { logActivity } from "@/lib/storage";

type Draft = CompareVariant & { id: number };
let nextId = 1;
const blank = (language: LanguageCode, variant_type: CompareVariant["variant_type"]): Draft =>
  ({ id: nextId++, language, script: LANGUAGES[language].nativeScript, variant_type, text: "" });

export default function CompareView() {
  const [tokenizer, setTokenizer] = useState("");
  const [variants, setVariants] = useState<Draft[]>(() => [blank("en", "original"), blank("kn", "translation")]);
  const [refIndex, setRefIndex] = useState(0);
  const [aligned, setAligned] = useState<{ id: string; dataset: string } | null>(null);
  const [showLoader, setShowLoader] = useState(false);

  const update = (id: number, patch: Partial<CompareVariant>) => {
    setVariants((vs) => vs.map((v) => (v.id === id ? { ...v, ...patch } : v)));
    // Editing a stored sample breaks the verified alignment.
    if (patch.text !== undefined || patch.language !== undefined) setAligned(null);
  };
  const remove = (idx: number) => {
    setVariants((vs) => vs.filter((_, i) => i !== idx));
    setRefIndex((r) => (idx === r ? 0 : idx < r ? r - 1 : r));
    setAligned(null);
  };
  const add = () => {
    const used = new Set(variants.map((v) => v.language));
    const next = LANGUAGE_CODES.find((c) => !used.has(c)) ?? "kn";
    setVariants((vs) => [...vs, blank(next, "translation")]);
  };

  const errors = variants.map((v) => (!v.text.trim() ? "Text is required." : v.text.length > MAX_TEXT_CHARS ? `Over ${fmtInt(MAX_TEXT_CHARS)} characters.` : null));
  const canRun = !!tokenizer && variants.length >= 2 && errors.every((e) => !e);

  const compare = useAction(async (signal) => {
    const r = await api.compareLanguages({
      tokenizer, reference_index: refIndex, aligned_group_id: aligned?.id ?? null,
      variants: variants.map(({ language, script, variant_type, text }) => ({ language, script, variant_type, text })),
    }, { signal });
    logActivity({ kind: "compare", href: "/compare", summary: `${r.rows.length} variants · ${r.tokenizer.name} · ${r.aligned ? "aligned" : "unaligned"}` });
    return { res: r, refIndex };
  });

  const loadGroup = (g: SampleGroup) => {
    const order = (c: LanguageCode) => (c === "en" ? -1 : LANGUAGE_CODES.indexOf(c));
    const samples = [...g.samples].sort((a, b) => order(a.language) - order(b.language)).slice(0, MAX_VARIANTS);
    setVariants(samples.map((s) => ({ id: nextId++, language: s.language, script: s.script, variant_type: s.variant_type, text: s.text })));
    setRefIndex(Math.max(0, samples.findIndex((s) => s.language === "en")));
    setAligned({ id: g.aligned_group_id, dataset: `${g.dataset.name}@${g.dataset.version}` });
    setShowLoader(false);
    compare.reset();
  };


  return (
    <>
      <PageHeader
        eyebrow={<>Measure <Badge tone="blue">F02 · F06 · Live</Badge></>}
        title="Language Comparison"
        lede="Compare how one tokenizer splits the same meaning in different languages and scripts. Ratios are only meaningful for meaning-aligned text; load an aligned group from a dataset, or the comparison is labelled unaligned."
        meta={<button className="btn btn-secondary" onClick={() => setShowLoader((s) => !s)}>{showLoader ? "Close sample loader" : "Load aligned sample"}</button>}
      />

      {showLoader && <SampleLoader onPick={loadGroup} />}

      <section className="panel" style={{ marginBottom: 24 }}>
        <div className="panel-head">
          <div>
            <h2>Variants <span className="subtle num" style={{ fontWeight: 400 }}>{variants.length} / {MAX_VARIANTS}</span></h2>
            <p>{aligned ? <>Aligned group <code>{aligned.id}</code> from {aligned.dataset}. Editing a text removes the alignment.</>
              : "Unaligned: texts you enter are not verified as meaning-equivalent."}</p>
          </div>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <Field label="Tokenizer" htmlFor="cmp-tok"><div style={{ minWidth: 180 }}><TokenizerSelect id="cmp-tok" value={tokenizer} onChange={setTokenizer} /></div></Field>
            {aligned ? <Badge tone="blue">Aligned</Badge> : <Badge tone="outline">Unaligned</Badge>}
          </div>
        </div>
        <div className="panel-body">
          <div className="variant-grid">
            {variants.map((v, i) => (
              <div key={v.id} className={`variant-card${i === refIndex ? " is-ref" : ""}`}>
                <div className="variant-card-head">
                  <select className="select" aria-label={`Variant ${i + 1} language`} value={v.language}
                    onChange={(e) => { const l = e.target.value as LanguageCode; update(v.id, { language: l, script: LANGUAGES[l].nativeScript }); }}>
                    {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
                  </select>
                  <select className="select" aria-label={`Variant ${i + 1} script`} value={v.script} onChange={(e) => update(v.id, { script: e.target.value as CompareVariant["script"] })}>
                    {SCRIPTS.map((s) => <option key={s} value={s}>{SCRIPT_LABELS[s]}</option>)}
                  </select>
                  <select className="select" aria-label={`Variant ${i + 1} type`} value={v.variant_type} onChange={(e) => update(v.id, { variant_type: e.target.value as CompareVariant["variant_type"] })}>
                    {VARIANT_TYPES.map((t) => <option key={t} value={t}>{VARIANT_LABELS[t]}</option>)}
                  </select>
                </div>
                <textarea className="textarea indic" aria-label={`Variant ${i + 1} text`} lang={langTag(v.language, v.script)} value={v.text}
                  onChange={(e) => update(v.id, { text: e.target.value })} placeholder={`${LANGUAGES[v.language].name} text…`} aria-invalid={!!errors[i] && v.text.length > 0} />
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center", padding: "6px 10px", borderTop: "1px solid var(--grey-100)" }}>
                  <label className="checkbox small">
                    <input type="radio" name="ref" checked={i === refIndex} onChange={() => setRefIndex(i)} /> Reference
                  </label>
                  <span className="small subtle num">{fmtInt(v.text.length)} chars</span>
                  <button className="btn btn-ghost btn-sm btn-icon" onClick={() => remove(i)} disabled={variants.length <= 2} aria-label={`Remove variant ${i + 1}`}><IconTrash /></button>
                </div>
              </div>
            ))}
            {variants.length < MAX_VARIANTS && (
              <button className="variant-add" onClick={add}><IconPlus width={18} height={18} />&nbsp;Add variant</button>
            )}
          </div>
        </div>
        <div className="panel-foot btn-row" style={{ justifyContent: "space-between" }}>
          <button className="btn btn-primary" disabled={!canRun || compare.loading} onClick={() => compare.run()}>
            {compare.loading && <span className="spinner" />} Compare
          </button>
          {!canRun && <span className="small subtle">Every variant needs text, and you need a tokenizer.</span>}
        </div>
      </section>

      <ScriptVariantsTool tokenizer={tokenizer} variants={variants} canAdd={variants.length < MAX_VARIANTS}
        onAdd={(v) => { setVariants((vs) => [...vs, { ...v, id: nextId++ }]); setAligned(null); compare.reset(); }} />

      {compare.error && <ErrorState error={compare.error} onRetry={() => compare.run()} />}
      {compare.data && <CompareResults res={compare.data.res} refIndex={compare.data.refIndex} />}
    </>
  );
}

const SCHEME_LABELS: Record<TranslitScheme, string> = {
  iso: "ISO 15919 (default)",
  itrans_dravidian: "ITRANS Dravidian (ASCII)",
  hk_dravidian: "Harvard-Kyoto Dravidian (ASCII)",
  optitrans_dravidian: "Optitrans Dravidian (ASCII)",
  baraha: "Baraha (ASCII)",
};

/** Feature 6: script variants of one variant's text (POST /api/script-variants). Never applied automatically. */
function ScriptVariantsTool({ tokenizer, variants, canAdd, onAdd }: {
  tokenizer: string; variants: Draft[]; canAdd: boolean; onAdd: (v: CompareVariant) => void;
}) {
  const eligible = variants.map((v, i) => ({ v, i }))
    .filter(({ v }) => (TRANSLIT_LANGUAGES as readonly string[]).includes(v.language) && v.text.trim());
  const [srcId, setSrcId] = useState<number | null>(null);
  const [direction, setDirection] = useState<"native_to_roman" | "roman_to_native">("native_to_roman");
  const [schemes, setSchemes] = useState<TranslitScheme[]>(["iso"]);
  const [sourceScheme, setSourceScheme] = useState<TranslitScheme | "casual">("casual");
  const chosen = eligible.find((e) => e.v.id === srcId) ?? eligible[0];
  const tooLong = !!chosen && chosen.v.text.length > MAX_TEXT_CHARS;
  const canRun = !!chosen && !!tokenizer && !tooLong && (direction === "roman_to_native" || schemes.length > 0);

  const run = useAction(async (signal) => {
    const src = chosen!.v;
    const res = await api.scriptVariants({
      text: src.text, language: src.language as TranslitLanguage, direction,
      source_scheme: direction === "roman_to_native" ? sourceScheme : null,
      target_schemes: direction === "native_to_roman" ? schemes : undefined,
      tokenizers: [tokenizer],
    }, { signal });
    logActivity({ kind: "compare", href: "/compare", summary: `Script variants · ${LANGUAGES[src.language].name} · ${res.variants.length} variant(s) · ${tokenizer}` });
    return { res, language: src.language };
  });

  const toggle = (s: TranslitScheme) => setSchemes((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  const add = (v: ScriptVariant) => run.data && onAdd({
    language: run.data.language, script: v.script, variant_type: "transliteration", text: v.text,
  });

  return (
    <section className="panel" style={{ marginBottom: 24 }}>
      <div className="panel-head">
        <div>
          <h2>Script variants <Badge tone="blue">F06</Badge></h2>
          <p>Same text in another script (<code>POST /api/script-variants</code>). Variants are never applied automatically; fewer tokens does not mean a model understands the text equally well.</p>
        </div>
      </div>
      <div className="panel-body stack">
        {eligible.length === 0 ? (
          <p className="small muted">Enter text in a Kannada, Hindi, Tamil or Telugu variant above to see its script variants. English has no script variants.</p>
        ) : (
          <>
            <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
              <Field label="Source variant" htmlFor="sv-src">
                <select id="sv-src" className="select" value={chosen?.v.id ?? ""} onChange={(e) => { setSrcId(Number(e.target.value)); run.reset(); }}>
                  {eligible.map(({ v, i }) => <option key={v.id} value={v.id}>Variant {i + 1} · {LANGUAGES[v.language].name} ({v.script})</option>)}
                </select>
              </Field>
              <Field label="Direction">
                <Segmented label="Direction" value={direction} onChange={(d) => { setDirection(d); run.reset(); }}
                  options={[{ value: "native_to_roman", label: "Native → Romanized" }, { value: "roman_to_native", label: "Romanized → native" }]} />
              </Field>
              {direction === "roman_to_native" && (
                <Field label="Source scheme" htmlFor="sv-scheme" hint="Name the scheme the text was written in">
                  <select id="sv-scheme" className="select" value={sourceScheme} onChange={(e) => setSourceScheme(e.target.value as TranslitScheme | "casual")}>
                    <option value="casual">Everyday Romanized typing (not supported)</option>
                    {TRANSLIT_SCHEMES.map((s) => <option key={s} value={s}>{SCHEME_LABELS[s]}</option>)}
                  </select>
                </Field>
              )}
            </div>
            {direction === "native_to_roman" && (
              <div className="row" style={{ flexWrap: "wrap", gap: 12 }} role="group" aria-label="Romanization schemes">
                {TRANSLIT_SCHEMES.map((s) => (
                  <label key={s} className="checkbox small"><input type="checkbox" checked={schemes.includes(s)} onChange={() => toggle(s)} /> {SCHEME_LABELS[s]}</label>
                ))}
              </div>
            )}
            {direction === "roman_to_native" && (
              <Callout tone="info">Romanized → native always needs your review. English words in mixed text are converted too, and Tamil is always lossy.</Callout>
            )}
          </>
        )}
        {run.error && <ErrorState error={run.error} onRetry={() => run.run()} compact />}
        {run.data && <ScriptVariantsResults res={run.data.res} onAdd={canAdd ? add : undefined} />}
        {run.data && !canAdd && <p className="small subtle">The comparison already has {MAX_VARIANTS} variants; remove one to add a script variant.</p>}
      </div>
      <div className="panel-foot btn-row">
        <button className="btn btn-primary" disabled={!canRun || run.loading} onClick={() => run.run()}>{run.loading && <span className="spinner" />} Generate script variants</button>
        {eligible.length > 0 && direction === "native_to_roman" && schemes.length === 0 && <span className="small subtle">Pick at least one scheme.</span>}
        {tooLong && <span className="field-error">Over {fmtInt(MAX_TEXT_CHARS)} characters.</span>}
        {!tokenizer && <span className="small subtle">Waiting for a tokenizer.</span>}
      </div>
    </section>
  );
}

function CompareResults({ res, refIndex }: { res: CompareResponse; refIndex: number }) {
  const refRow = res.rows[refIndex] ?? null;
  const label = (r: CompareResponse["rows"][number]) => `${LANGUAGES[r.language].name}${r.script !== LANGUAGES[r.language].nativeScript ? ` (${r.script})` : ""}`;
  const ratioOf = (r: CompareResponse["rows"][number]) => r.ratio_vs_reference;
  const exportCsv = () => downloadText(`redutax-compare-${res.tokenizer.name}.csv`, toCsv(
    ["language", "script", "variant_type", "token_count", "word_count", "tokens_per_word", "tpw_ratio_vs_reference", "tokenizer", "tokenizer_version", "status", "aligned"],
    res.rows.map((r) => [r.language, r.script, r.variant_type, r.token_count, r.word_count, r.tokens_per_word, r.ratio_vs_reference, res.tokenizer.name, res.tokenizer.version, res.status, res.aligned]),
  ), "text/csv;charset=utf-8");
  const exportJson = () => downloadText(`redutax-compare-${res.tokenizer.name}.json`, JSON.stringify(res, null, 2), "application/json");

  return (
    <section className="stack-lg" aria-live="polite">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div className="btn-row">
          <h2 style={{ fontSize: 20 }}>Results</h2>
          <CountStatusBadge status={res.status} /><TokenizerTag t={res.tokenizer} />
          {res.aligned ? <Badge tone="blue">Aligned group</Badge> : <Badge tone="red">Unaligned</Badge>}
        </div>
        <div className="btn-row">
          <button className="btn btn-sm btn-secondary" onClick={exportCsv}><IconDownload /> CSV</button>
          <button className="btn btn-sm btn-secondary" onClick={exportJson}><IconDownload /> JSON</button>
        </div>
      </div>

      {res.warnings.length > 0 && (
        <div className="warn-rail">
          {res.warnings.map((w, i) => <Callout key={i} tone={w.includes("not cost multipliers") ? "info" : "warn"}>{w}</Callout>)}
        </div>
      )}

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><div><h2>Token count</h2><p>Raw tokens per variant</p></div></div>
          <div className="panel-body">
            <HBarChart ariaLabel="Token count per variant" data={res.rows.map((r, i) => ({
              key: String(i), label: label(r), sublabel: VARIANT_LABELS[r.variant_type], value: r.token_count, isReference: r === refRow,
              tooltip: <>{label(r)} · {VARIANT_LABELS[r.variant_type]}<br />{fmtInt(r.token_count)} tokens · {fmtInt(r.word_count)} words</>,
            }))} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-head"><div><h2>Tokens-per-word ratio vs reference</h2><p>Tokenization ratio, not a cost multiplier</p></div></div>
          <div className="panel-body">
            <HBarChart ariaLabel="Tokens-per-word ratio versus reference" refLine={1} refLineLabel="reference = 1.00×" valueFormat={(v) => `${v.toFixed(2)}×`}
              data={res.rows.map((r, i) => ({
                key: String(i), label: label(r), sublabel: VARIANT_LABELS[r.variant_type], value: ratioOf(r), isReference: r === refRow,
                tooltip: <>{label(r)}<br />{fmtDec(r.tokens_per_word)} tokens/word · {fmtRatio(r.ratio_vs_reference)} of reference</>,
              }))} />
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead><tr>
            <th>Language</th><th>Script</th><th>Variant</th><th>Text</th>
            <th className="num">Tokens</th><th className="num">Words</th><th className="num">Tokens / word</th><th className="num">Ratio vs ref</th>
          </tr></thead>
          <tbody>
            {res.rows.map((r, i) => (
              <tr key={i} className={r === refRow ? "is-ref" : undefined}>
                <td><b>{LANGUAGES[r.language].name}</b>{r === refRow && <> <Badge tone="blue">ref</Badge></>}</td>
                <td>{r.script}</td>
                <td>{VARIANT_LABELS[r.variant_type]}</td>
                <td className="cell-text"><span className="clip indic" lang={langTag(r.language, r.script)}>{r.text}</span></td>
                <td className="num">{fmtInt(r.token_count)}</td>
                <td className="num">{fmtInt(r.word_count)}</td>
                <td className="num">{fmtDec(r.tokens_per_word)}</td>
                <td className="num">{fmtRatio(r.ratio_vs_reference)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SampleLoader({ onPick }: { onPick: (g: SampleGroup) => void }) {
  const [dataset, setDataset] = useState("");
  const [split, setSplit] = useState<Split | "">("");
  const [langs, setLangs] = useState<LanguageCode[]>([]);
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const q = useApi((signal) => api.sampleGroups({
    dataset: dataset.trim() || undefined, split: split || undefined, language: langs.length ? langs : undefined, page, page_size: pageSize,
  }, { signal }), [dataset, split, langs.join(","), page]);
  const toggle = (c: LanguageCode) => { setLangs((ls) => (ls.includes(c) ? ls.filter((l) => l !== c) : [...ls, c])); setPage(1); };

  return (
    <section className="panel panel-sunken" style={{ marginBottom: 24 }} aria-label="Aligned sample loader">
      <div className="panel-head"><div><h2>Aligned sample groups</h2><p>From imported datasets via <code>GET /api/samples/groups</code>. A group shares one meaning across languages.</p></div></div>
      <div className="panel-body stack">
        <div className="row">
          <Field label="Dataset" htmlFor="sl-ds" hint="Exact name, e.g. FLORES-200"><input id="sl-ds" className="input" value={dataset} onChange={(e) => { setDataset(e.target.value); setPage(1); }} placeholder="Any dataset" /></Field>
          <Field label="Split" htmlFor="sl-split">
            <select id="sl-split" className="select" value={split} onChange={(e) => { setSplit(e.target.value as Split | ""); setPage(1); }}>
              <option value="">Any split</option>{SPLITS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <div className="field"><span className="field-label">Must include</span>
            <div className="chip-select">{LANGUAGE_CODES.map((c) => <button key={c} type="button" className="chip" aria-pressed={langs.includes(c)} onClick={() => toggle(c)}>{LANGUAGES[c].name}</button>)}</div>
          </div>
        </div>
        {q.loading && <LoadingRows rows={3} />}
        {q.error && <ErrorState error={q.error} onRetry={q.reload} />}
        {q.data && q.data.items.length === 0 && (
          <EmptyState title="No aligned groups found">
            No dataset has been imported yet, or nothing matches these filters. Imports are blocked until the team verifies the dataset licence (see <code>research/configs/datasets.yaml</code>).
          </EmptyState>
        )}
        {q.data && q.data.items.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Group</th><th>Dataset</th><th>Split</th><th>Languages</th><th>Preview</th><th /></tr></thead>
                <tbody>
                  {q.data.items.map((g) => {
                    const en = g.samples.find((s) => s.language === "en") ?? g.samples[0];
                    return (
                      <tr key={`${g.dataset.name}-${g.dataset.version}-${g.aligned_group_id}`}>
                        <td className="mono">{g.aligned_group_id}</td>
                        <td>{g.dataset.name} <span className="subtle">@{g.dataset.version}</span>{g.dataset.license && <div className="small subtle">{g.dataset.license}</div>}</td>
                        <td>{g.split}</td>
                        <td>{g.languages.join(", ")}</td>
                        <td className="cell-text"><span className="clip" lang={en?.language}>{en?.text}</span></td>
                        <td><button className="btn btn-sm btn-secondary" onClick={() => onPick(g)}>Use</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={page} pageSize={pageSize} total={q.data.total} onPage={setPage} />
          </>
        )}
      </div>
    </section>
  );
}
