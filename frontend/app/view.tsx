"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { IconArrowRight, IconRefresh } from "@/components/icons";
import { Badge, Skeleton } from "@/components/ui";
import { API_BASE_URL } from "@/lib/api/client";
import { NAV } from "@/lib/api/planned";
import { fmtDateTime } from "@/lib/format";
import { useHealth, useTokenizers } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { loadActivity, type ActivityEntry } from "@/lib/storage";

/** Snapshot of docs/STATUS.md (2026-11-20). Update together with that file. */
const PHASES: { id: string; title: string; state: "done" | "now" | "next"; note: string }[] = [
  { id: "0", title: "Repository, config, database schema, health", state: "done", note: "Done" },
  { id: "1", title: "Normalization, counters, comparison, licence register, benchmark", state: "now", note: "Code complete; FLORES-200 licence and first baseline run pending" },
  { id: "2", title: "SentencePiece Unigram research tokenizer", state: "next", note: "Not started" },
  { id: "3", title: "Prompt optimizer + meaning checks", state: "next", note: "Not started" },
  { id: "4", title: "Model registry, cost, routing, chat", state: "next", note: "Not started" },
  { id: "5", title: "Browser voice + Vapi telephone", state: "next", note: "Not started" },
  { id: "6", title: "Evaluation report and demo", state: "next", note: "Not started" },
];

const STEPS = [
  { n: "01", t: "Normalize", d: "NFC, whitespace policy nfc_ws_v1. Zero-width joiners kept for Indic conjuncts." },
  { n: "02", t: "Count", d: "Exact counts from named, versioned tokenizers, with words and characters." },
  { n: "03", t: "Compare", d: "Meaning-aligned variants across languages and scripts, against a reference." },
  { n: "04", t: "Reduce", d: "Shorter same-language candidates, kept only if meaning and protected details survive." },
  { n: "05", t: "Evaluate", d: "Reproducible runs: dataset version, tokenizer version, policy IDs, code commit." },
];

export default function HomeView() {
  const health = useHealth();
  const toks = useTokenizers();
  const [activity, setActivity] = useState<ActivityEntry[] | null>(null);
  useEffect(() => setActivity(loadActivity()), []);

  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">The Token Tax · AI Research Track</div>
          <h1>The same meaning can cost <em>more tokens</em> in Indian languages. REDUTAX measures it, then reduces it.</h1>
          <p className="lede">
            A research platform and prompt toolkit for Kannada, Hindi, Tamil, Telugu and English, in native script, Roman letters and code-mixed text.
            Every number names its tokenizer and says whether it is exact, estimated or experimental.
          </p>
          <div className="btn-row" style={{ marginTop: 20 }}>
            <Link href="/counter" className="btn btn-primary">Count tokens <IconArrowRight /></Link>
            <Link href="/compare" className="btn btn-secondary">Compare languages</Link>
          </div>
        </div>
        <div className="script-specimen" aria-label="Supported languages">
          {(["kn", "hi", "ta", "te", "en"] as const).map((c) => (
            <div className="script-specimen-row" key={c}>
              <span>{LANGUAGES[c].name}</span>
              <span lang={c}>{LANGUAGES[c].native}</span>
            </div>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: 40 }} aria-labelledby="how">
        <div className="section-title"><h2 id="how">How REDUTAX measures</h2><span className="small subtle">Fertility ratios are tokenization ratios, never bill multipliers</span></div>
        <div className="pipeline">
          {STEPS.map((s) => (
            <div className="pipeline-step" key={s.n}>
              <span className="n">{s.n}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid-2" style={{ marginBottom: 40 }}>
        <section className="panel" aria-labelledby="sys">
          <div className="panel-head">
            <div><h2 id="sys">System status</h2><p>Live from the backend at <code>{API_BASE_URL}</code></p></div>
            <button className="btn btn-sm btn-ghost" onClick={() => { health.reload(); toks.reload(); }}><IconRefresh /> Refresh</button>
          </div>
          <div className="panel-body">
            {health.loading ? <div className="stack"><Skeleton h={16} /><Skeleton h={16} w="70%" /><Skeleton h={16} w="80%" /></div> : (
              <div className="health-grid">
                <span className="muted">API</span>
                <span>{health.error ? <Badge tone="red">Offline</Badge> : <><Badge tone={health.data?.status === "ok" ? "blue" : "red"}>{health.data?.status}</Badge> <span className="small subtle">{health.data?.app} {health.data?.version} · {health.data?.env}</span></>}</span>
                <span className="muted">Database</span>
                <span>{health.data ? (
                  health.data.database.status === "ok" ? <Badge tone="blue">Connected</Badge>
                    : health.data.database.status === "not_configured" ? <><Badge tone="outline">Not configured</Badge> <span className="small subtle">Datasets and benchmarks unavailable</span></>
                      : <><Badge tone="red">Error</Badge> <span className="small subtle">{health.data.database.error}</span></>
                ) : "—"}</span>
                <span className="muted">Tokenizers</span>
                <span>{toks.data ? <span className="btn-row">{toks.data.tokenizers.map((t) => <span key={t} className="badge badge-outline mono">{t}</span>)}</span> : toks.error ? <Badge tone="red">Unavailable</Badge> : "—"}</span>
                <span className="muted">Research tokenizer</span>
                <span><Badge tone="planned">Phase 2 · not trained</Badge></span>
              </div>
            )}
            {health.error && <p className="small muted" style={{ marginTop: 12 }}>Start the backend: <code>cd backend && uvicorn app.main:app --reload</code></p>}
          </div>
        </section>

        <section className="panel" aria-labelledby="road">
          <div className="panel-head"><div><h2 id="road">Delivery roadmap</h2><p>Snapshot of docs/STATUS.md · 20 Nov 2026</p></div></div>
          <div className="panel-body">
            <ol className="timeline">
              {PHASES.map((p) => (
                <li key={p.id}>
                  <span className={`ph ${p.state === "done" ? "done" : p.state === "now" ? "now" : ""}`}>P{p.id}</span>
                  <span>{p.title}<div className="small subtle">{p.note}</div></span>
                  {p.state === "done" ? <Badge tone="blue">Done</Badge> : p.state === "now" ? <Badge tone="red">In progress</Badge> : <Badge tone="planned">Planned</Badge>}
                </li>
              ))}
            </ol>
          </div>
        </section>
      </div>

      <section style={{ marginBottom: 40 }} aria-labelledby="start">
        <div className="section-title"><h2 id="start">Start a task</h2></div>
        <div className="quick">
          {NAV.flatMap((g) => g.items).filter((i) => i.href !== "/").map((i) => (
            <Link key={i.href} href={i.href}>
              <span className="q-head">{i.label}<span className={`avail avail-${i.availability}`} aria-label={i.availability} /></span>
              <p>{i.note}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="recent">
        <div className="section-title"><h2 id="recent">Recent activity</h2><span className="small subtle">Stored in this browser only · metadata, never your text</span></div>
        <div className="panel">
          {activity === null ? <div className="panel-body"><Skeleton h={16} /></div>
            : activity.length === 0 ? <div className="panel-body muted small">Nothing yet. Counts and comparisons you run will appear here.</div>
              : (
                <ul className="timeline" style={{ padding: "4px 18px" }}>
                  {activity.map((a, i) => (
                    <li key={i}>
                      <span className="ph">{a.kind === "count" ? "CT" : a.kind === "compare" ? "CM" : a.kind === "optimize" ? "OP" : "$"}</span>
                      <Link href={a.href}>{a.summary}</Link>
                      <span className="small subtle">{fmtDateTime(a.at)}</span>
                    </li>
                  ))}
                </ul>
              )}
        </div>
      </section>
    </>
  );
}
