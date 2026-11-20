"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { API_BASE_URL } from "@/lib/api/client";
import { NAV } from "@/lib/api/planned";
import { useHealth, useTokenizers } from "@/lib/hooks";
import { BrandMark, IconMenu, IconX } from "./icons";

function currentTitle(path: string): { group: string; label: string } | null {
  for (const g of NAV) for (const i of g.items) if (i.href === path) return { group: g.label, label: i.label };
  return null;
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  const t = currentTitle(path);

  return (
    <div className={`shell${open ? " nav-open" : ""}`}>
      <a className="skip-link" href="#main">Skip to content</a>
      <aside className="sidebar" aria-label="Primary">
        <Link href="/" className="brand">
          <BrandMark />
          <span>
            <span className="brand-name">REDUTAX</span>
            <span className="brand-sub">Indic token efficiency</span>
          </span>
        </Link>
        <nav className="nav">
          {NAV.map((g) => (
            <div className="nav-group" key={g.label}>
              <div className="nav-group-label">{g.label}</div>
              {g.items.map((i) => (
                <Link key={i.href} href={i.href} className="nav-link" aria-current={path === i.href ? "page" : undefined} title={i.note}>
                  <span>{i.label}</span>
                  <span className={`avail avail-${i.availability}`} aria-label={i.availability} />
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="legend-row"><span className="avail avail-live" /> Live backend</div>
          <div className="legend-row"><span className="avail avail-partial" /> Partly available</div>
          <div className="legend-row"><span className="avail avail-planned" /> Planned phase</div>
          <div style={{ marginTop: 10 }}>Team YANCIORA · No. 46</div>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost btn-icon menu-btn" onClick={() => setOpen((o) => !o)} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open}>
            {open ? <IconX width={20} height={20} /> : <IconMenu width={20} height={20} />}
          </button>
          <span className="topbar-title">{t ? <>{t.group} <span className="subtle">/</span> <b style={{ color: "var(--ink)", fontWeight: 600 }}>{t.label}</b></> : "REDUTAX"}</span>
          <span className="topbar-spacer" />
          <SystemPills />
        </header>
        <main id="main" className="content">{children}</main>
      </div>
    </div>
  );
}

function SystemPills() {
  const health = useHealth();
  const toks = useTokenizers();
  const api = health.loading ? { dot: "", text: "Checking API…" }
    : health.error ? { dot: "dot-err", text: "API offline" }
      : health.data?.status === "ok" ? { dot: "dot-ok", text: `API ${health.data.version}` } : { dot: "dot-warn", text: "API degraded" };
  const dbs = health.data?.database.status;
  const db = !health.data ? { dot: "", text: "Database —" }
    : dbs === "ok" ? { dot: "dot-ok", text: "Database ok" }
      : dbs === "not_configured" ? { dot: "dot-warn", text: "No database" } : { dot: "dot-err", text: "Database error" };
  return (
    <>
      <span className="status-pill" title={`Backend: ${API_BASE_URL}`}><span className={`dot ${api.dot}`} /><span className="pill-text">{api.text}</span></span>
      <span className="status-pill" title="From GET /health"><span className={`dot ${db.dot}`} /><span className="pill-text">{db.text}</span></span>
      {toks.data && <span className="status-pill" title={toks.data.tokenizers.join(", ")}><span className="dot dot-ok" /><span className="pill-text">{toks.data.tokenizers.length} tokenizers</span></span>}
    </>
  );
}
