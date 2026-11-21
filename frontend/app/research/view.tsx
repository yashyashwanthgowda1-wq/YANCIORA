"use client";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { DotRangePlot } from "@/components/charts";
import { IconArrowRight, IconDownload } from "@/components/icons";
import {
  Badge, Callout, CountStatusBadge, EmptyState, ErrorState, Field, LoadingRows, PageHeader, Pager, Stat, TokenizerTag,
} from "@/components/ui";
import { api } from "@/lib/api/client";
import { LANGUAGE_CODES, SCRIPTS, type BenchmarkRun, type LanguageCode, type Script } from "@/lib/api/types";
import { downloadText, toCsv } from "@/lib/csv";
import { fmtDateTime, fmtDec, fmtInt, fmtRatio, shortHash } from "@/lib/format";
import { useApi, useTokenizers } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";

export default function ResearchView() {
  const [dataset, setDataset] = useState("");
  const [tokenizer, setTokenizer] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "">("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const toks = useTokenizers();
  const pageSize = 10;

  const runs = useApi((signal) => api.benchmarks({
    dataset: dataset.trim() || undefined, tokenizer: tokenizer || undefined, language: language || undefined, page, page_size: pageSize,
  }, { signal }), [dataset, tokenizer, language, page]);

  useEffect(() => {
    const items = runs.data?.items ?? [];
    if (items.length && !items.some((r) => r.run_id === selected)) setSelected(items[0]?.run_id ?? null);
  }, [runs.data, selected]);

  const run = runs.data?.items.find((r) => r.run_id === selected) ?? null;
  const filtered = !!(dataset.trim() || tokenizer || language);
  const total = runs.data?.total;
  const evalStatus = runs.error ? "Unavailable" : runs.loading && !runs.data ? "Checking…" : total ? "Runs stored" : "Awaiting first run";

  return (
    <>
      <PageHeader
        eyebrow={<>Research <Badge tone="blue">Live</Badge></>}
        title="Research Dashboard"
        lede="How tokenizers handle Kannada, Hindi, Tamil, Telugu and English, measured on stored, reproducible benchmark runs. Every number on this page comes from a stored run or the live backend."
      />

      {/* ---- A. Overview ---- */}
      <section className="dash-section" aria-labelledby="rs-a">
        <DashHead n="A" id="rs-a" title="Research overview" desc="What is measured today and where the evaluation stands." />
        <div className="stat-strip">
          <Stat label={filtered ? "Benchmark runs (filtered)" : "Benchmark runs stored"} value={total === undefined ? "—" : fmtInt(total)} />
          <Stat label="Tokenizers available" value={toks.data ? toks.data.tokenizers.length : "—"} />
          <Stat label="Languages in scope" value={LANGUAGE_CODES.length} />
          <Stat label="Evaluation status" value={<span style={{ fontSize: 18 }}>{evalStatus}</span>} />
        </div>
      </section>

      {/* ---- B. Tools ---- */}
      <section className="dash-section" aria-labelledby="rs-b">
        <DashHead n="B" id="rs-b" title="Tokenization and language research" desc="Interactive tools for measuring your own text with the live tokenizers." />
        <div className="tool-grid">
          <ToolCard href="/counter" title="Tokenizer comparison">Count one text under every available tokenizer and compare tokens and tokens per word.</ToolCard>
          <ToolCard href="/compare" title="Language comparison">Compare the same meaning across languages and scripts against a reference language.</ToolCard>
          <ToolCard href="/compare#script-variants" title="Script variant research">Generate native or Romanized versions of a text and add them to a comparison.</ToolCard>
        </div>
      </section>

      {/* ---- C. Evaluation and results ---- */}
      <section className="dash-section" aria-labelledby="rs-c">
        <DashHead n="C" id="rs-c" title="Evaluation and results" desc="Stored benchmark runs: dataset and tokenizer versions, per-language fertility with confidence intervals, and per-sample counts." />

        <div className="filter-bar" role="group" aria-label="Filter benchmark runs">
          <Field label="Dataset" htmlFor="rs-ds"><input id="rs-ds" className="input" placeholder="Any dataset" value={dataset} onChange={(e) => { setDataset(e.target.value); setPage(1); }} /></Field>
          <Field label="Tokenizer" htmlFor="rs-tok">
            <select id="rs-tok" className="select" value={tokenizer} onChange={(e) => { setTokenizer(e.target.value); setPage(1); }}>
              <option value="">Any tokenizer</option>
              {(toks.data?.tokenizers ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Language" htmlFor="rs-lang">
            <select id="rs-lang" className="select" value={language} onChange={(e) => { setLanguage(e.target.value as LanguageCode | ""); setPage(1); }}>
              <option value="">All languages</option>
              {LANGUAGE_CODES.map((c) => <option key={c} value={c}>{LANGUAGES[c].name}</option>)}
            </select>
          </Field>
        </div>

        {runs.loading && !runs.data && <LoadingRows rows={5} />}
        {runs.error && <ErrorState error={runs.error} onRetry={runs.reload} />}

        {runs.data && runs.data.items.length === 0 && (
          <div className="panel">
            <EmptyState art="chart" title="No benchmark runs stored yet">
              A run appears here after the team verifies a dataset licence, imports it, and stores a benchmark. No results are shown until then.
            </EmptyState>
            <div className="panel-foot">
              <div className="kicker" style={{ marginBottom: 6 }}>How a run gets here</div>
              <ol className="small muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.9 }}>
                <li>Verify the licence entry in <code>research/configs/datasets.yaml</code></li>
                <li><code>python research/scripts/import_pilot.py --input … --dataset FLORES-200 --load-db</code></li>
                <li><code>python research/scripts/run_benchmark.py --input … --split test --store-db</code></li>
              </ol>
            </div>
          </div>
        )}

        {runs.data && runs.data.items.length > 0 && (
          <div className="split-aside">
            <aside aria-label="Benchmark runs">
              <div className="kicker" style={{ marginBottom: 8 }}>Runs · {runs.data.total}</div>
              <div className="run-list">
                {runs.data.items.map((r) => (
                  <button key={r.run_id} className="run-item" aria-pressed={r.run_id === selected} onClick={() => setSelected(r.run_id)}>
                    <div className="rid">{r.run_id}</div>
                    <div className="small muted">{r.dataset.name}@{r.dataset.version} · {r.split ?? "all splits"}</div>
                    <div className="small subtle">{fmtDateTime(r.run_at)} · {fmtInt(r.n_samples)} samples</div>
                  </button>
                ))}
              </div>
              <Pager page={page} pageSize={pageSize} total={runs.data.total} onPage={setPage} />
            </aside>
            {run && <RunDetail run={run} />}
          </div>
        )}

        <h3 className="dash-sub">Reference reports</h3>
        <LiteratureReference />
      </section>
    </>
  );
}

function DashHead({ n, id, title, desc }: { n: string; id: string; title: string; desc: string }) {
  return (
    <div className="dash-head">
      <span className="n" aria-hidden="true">{n}</span>
      <div><h2 id={id}>{title}</h2><p>{desc}</p></div>
    </div>
  );
}

function ToolCard({ href, title, children }: { href: string; title: string; children: ReactNode }) {
  return (
    <Link href={href} className="tool-card">
      <h3>{title}</h3>
      <p>{children}</p>
      <span className="go">Open <IconArrowRight width={14} height={14} /></span>
    </Link>
  );
}

function RunDetail({ run }: { run: BenchmarkRun }) {
  const series = run.tokenizers.map((t) => t.name);
  const languages = Array.from(new Set(run.summaries.map((s) => s.language)));
  const plot = run.summaries.map((s) => ({
    category: `${LANGUAGES[s.language].name}`,
    categorySub: s.script,
    series: s.tokenizer.name,
    value: s.fertility_mean,
    low: s.fertility_ci95_low,
    high: s.fertility_ci95_high,
    tooltip: <>{LANGUAGES[s.language].name} ({s.script}) · {s.tokenizer.name}<br />mean {fmtDec(s.fertility_mean)} tokens/word{s.fertility_ci95_low !== null ? ` · 95% CI ${fmtDec(s.fertility_ci95_low)}–${fmtDec(s.fertility_ci95_high)}` : " · CI n/a (n < 30)"}<br />n = {s.n_samples}</>,
  }));

  const exportSummary = () => downloadText(`${run.run_id}-summary.csv`, toCsv(
    ["tokenizer", "tokenizer_version", "status", "language", "script", "n_samples", "total_tokens", "total_words", "fertility_mean", "fertility_median", "fertility_stdev", "ci95_low", "ci95_high", "paired_groups_with_reference", "ratio_vs_reference"],
    run.summaries.map((s) => [s.tokenizer.name, s.tokenizer.version, s.status, s.language, s.script, s.n_samples, s.total_tokens, s.total_words, s.fertility_mean, s.fertility_median, s.fertility_stdev, s.fertility_ci95_low, s.fertility_ci95_high, s.paired_groups_with_reference, s.ratio_vs_reference]),
  ), "text/csv;charset=utf-8");

  return (
    <div className="stack-lg" style={{ minWidth: 0 }}>
      <section className="panel">
        <div className="panel-head">
          <div><h2 className="mono" style={{ fontSize: 15 }}>{run.run_id}</h2><p>{fmtDateTime(run.run_at)}</p></div>
          <div className="btn-row">{run.tokenizers.map((t) => <TokenizerTag key={t.name + t.version} t={t} />)}</div>
        </div>
        <div className="stat-strip" style={{ border: 0, borderRadius: 0, borderBottom: "1px solid var(--border)" }}>
          <Stat label="Samples" value={fmtInt(run.n_samples)} />
          <Stat label="Languages" value={languages.length} />
          <Stat label="Tokenizers" value={run.tokenizers.length} />
          <Stat label="Reference" value={LANGUAGES[run.reference_language].name} />
        </div>
        <div className="panel-body">
          <dl className="meta-list">
            <dt>Dataset</dt><dd>{run.dataset.name} @ {run.dataset.version}{run.dataset.license ? ` · ${run.dataset.license}` : ""}</dd>
            <dt>Split</dt><dd>{run.split ?? "—"}</dd>
            <dt>Normalization</dt><dd className="mono">{run.normalization}</dd>
            <dt>Word count</dt><dd className="mono">{run.word_count_method}</dd>
            <dt>Code version</dt><dd className="mono">{shortHash(run.code_version, 12)}</dd>
            <dt>Input SHA-256</dt><dd className="mono" title={run.input_sha256 ?? undefined}>{shortHash(run.input_sha256, 16)}</dd>
          </dl>
        </div>
      </section>

      <Callout tone="info">{run.note}</Callout>

      <section className="panel">
        <div className="panel-head"><div><h2>Fertility by language</h2><p>Mean tokens per word, with the 95% CI where n ≥ 30</p></div></div>
        <div className="panel-body">
          {plot.length ? <DotRangePlot ariaLabel="Mean fertility by language and tokenizer" data={plot} series={series} /> : <p className="muted">No summaries match the current filter.</p>}
        </div>
      </section>

      <section>
        <div className="section-title">
          <h2>Summary table</h2>
          <button className="btn btn-sm btn-secondary" onClick={exportSummary}><IconDownload /> CSV</button>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead><tr>
              <th>Tokenizer</th><th>Language</th><th>Script</th><th>Status</th><th className="num">n</th>
              <th className="num">Tokens</th><th className="num">Words</th><th className="num">Fertility mean</th>
              <th className="num">Median</th><th className="num">95% CI</th><th className="num">Paired</th><th className="num">Ratio vs {run.reference_language}</th>
            </tr></thead>
            <tbody>
              {run.summaries.map((s, i) => (
                <tr key={i} className={s.language === run.reference_language ? "is-ref" : undefined}>
                  <td className="mono">{s.tokenizer.name}</td>
                  <td>{LANGUAGES[s.language].name}</td>
                  <td>{s.script}</td>
                  <td><CountStatusBadge status={s.status} /></td>
                  <td className="num">{fmtInt(s.n_samples)}</td>
                  <td className="num">{fmtInt(s.total_tokens)}</td>
                  <td className="num">{fmtInt(s.total_words)}</td>
                  <td className="num">{fmtDec(s.fertility_mean)}</td>
                  <td className="num">{fmtDec(s.fertility_median)}</td>
                  <td className="num" style={{ whiteSpace: "nowrap" }}>{s.fertility_ci95_low !== null ? `${fmtDec(s.fertility_ci95_low)}–${fmtDec(s.fertility_ci95_high)}` : "n/a"}</td>
                  <td className="num">{fmtInt(s.paired_groups_with_reference)}</td>
                  <td className="num">{fmtRatio(s.ratio_vs_reference)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="chart-caption">Ratio = mean fertility over the reference language's fertility, on aligned groups that include the reference. A tokenization ratio, not a cost multiplier.</p>
      </section>

      <RunResults run={run} />
    </div>
  );
}

function RunResults({ run }: { run: BenchmarkRun }) {
  const [tokenizer, setTokenizer] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "">("");
  const [script, setScript] = useState<Script | "">("");
  const [page, setPage] = useState(1);
  const pageSize = 25;
  useEffect(() => setPage(1), [run.run_id]);
  const q = useApi((signal) => api.benchmarkResults(run.run_id, {
    tokenizer: tokenizer || undefined, language: language || undefined, script: script || undefined, page, page_size: pageSize,
  }, { signal }), [run.run_id, tokenizer, language, script, page]);
  const langs = useMemo(() => Array.from(new Set(run.summaries.map((s) => s.language))), [run]);

  return (
    <section>
      <div className="section-title"><h2>Per-sample results</h2></div>
      <div className="row" style={{ marginBottom: 12 }}>
        <select className="select" style={{ width: "auto" }} aria-label="Filter by tokenizer" value={tokenizer} onChange={(e) => { setTokenizer(e.target.value); setPage(1); }}>
          <option value="">All tokenizers</option>{run.tokenizers.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
        </select>
        <select className="select" style={{ width: "auto" }} aria-label="Filter by language" value={language} onChange={(e) => { setLanguage(e.target.value as LanguageCode | ""); setPage(1); }}>
          <option value="">All languages</option>{langs.map((l) => <option key={l} value={l}>{LANGUAGES[l].name}</option>)}
        </select>
        <select className="select" style={{ width: "auto" }} aria-label="Filter by script" value={script} onChange={(e) => { setScript(e.target.value as Script | ""); setPage(1); }}>
          <option value="">All scripts</option>{SCRIPTS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {q.loading && !q.data && <LoadingRows rows={4} />}
      {q.error && <ErrorState error={q.error} onRetry={q.reload} />}
      {q.data && (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Sample</th><th>Group</th><th>Language</th><th>Script</th><th>Variant</th><th>Tokenizer</th><th className="num">Tokens</th><th className="num">Words</th><th className="num">Chars</th><th className="num">Tokens / word</th></tr></thead>
              <tbody>
                {q.data.items.length === 0 && <tr><td colSpan={10} className="muted" style={{ textAlign: "center", padding: 24 }}>No rows match these filters.</td></tr>}
                {q.data.items.map((r) => (
                  <tr key={`${r.sample_id}-${r.tokenizer.name}`}>
                    <td className="mono small">{r.sample_id}</td>
                    <td className="mono small">{r.aligned_group_id ?? "—"}</td>
                    <td>{LANGUAGES[r.language].name}</td><td>{r.script}</td><td>{r.variant_type}</td>
                    <td className="mono small">{r.tokenizer.name}</td>
                    <td className="num">{fmtInt(r.token_count)}</td><td className="num">{fmtInt(r.word_count)}</td>
                    <td className="num">{fmtInt(r.char_count)}</td><td className="num">{fmtDec(r.tokens_per_word)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={pageSize} total={q.data.total} onPage={setPage} />
        </>
      )}
    </section>
  );
}

/** PRD §8 figures. Kept apart from REDUTAX results: unverified, not reproduced, not cost multipliers. */
const LITERATURE: [string, number][] = [
  ["Malayalam", 13.04], ["Kannada", 12.06], ["Telugu", 10.68], ["Tamil", 9.89], ["Gujarati", 8.0],
  ["Punjabi", 6.69], ["Bengali", 6.52], ["Marathi", 5.84], ["Hindi", 4.08], ["Urdu", 3.45], ["English", 1.0],
];

function LiteratureReference() {
  return (
    <details className="panel">
      <summary className="panel-head" style={{ cursor: "pointer", listStyle: "none", borderBottom: 0 }}>
        <div>
          <h2>Literature reference <Badge tone="red">Unverified · not a REDUTAX result</Badge></h2>
          <p>Relative tokenization-fertility ratios vs English for cl100k_base, as carried in the team presentation (PRD §8). Click to expand.</p>
        </div>
      </summary>
      <div className="panel-body stack" style={{ borderTop: "1px solid var(--border)" }}>
        <Callout tone="warn" title="Do not cite these as REDUTAX measurements">
          These values come from Srivastava, “The Tokenizer Tax”, arXiv:2607.24276, via the team slide. They have not been checked against the paper's tables,
          denominator, corpus split or normalization, and they are <b>not API bill multipliers</b>. Don't mix them with REDUTAX runs above.
        </Callout>
        <div className="table-wrap" style={{ maxWidth: 420 }}>
          <table className="table lit-table">
            <thead><tr><th>Language</th><th className="num">Ratio (team chart)</th></tr></thead>
            <tbody>{LITERATURE.map(([l, v]) => <tr key={l}><td>{l}</td><td className="num">{v.toFixed(2)}×{l === "English" ? " (reference)" : ""}</td></tr>)}</tbody>
          </table>
        </div>
        <p className="small subtle">Source: <a href="https://arxiv.org/abs/2607.24276" target="_blank" rel="noreferrer">arxiv.org/abs/2607.24276</a></p>
      </div>
    </details>
  );
}
