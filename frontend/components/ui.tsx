"use client";
import type { ReactNode } from "react";
import { ApiError, errorHint } from "@/lib/api/client";
import type { CountStatus, TokenizerRef } from "@/lib/api/types";
import type { PlannedEndpoint } from "@/lib/api/planned";
import { STATUS_LABELS } from "@/lib/languages";
import { IconAlert, IconCheck, IconInfo, IconRefresh } from "./icons";

export function PageHeader({ eyebrow, title, lede, meta }: {
  eyebrow: ReactNode; title: string; lede?: ReactNode; meta?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {meta && <div className="page-meta">{meta}</div>}
    </header>
  );
}

export function Badge({ tone = "neutral", children, title }: {
  tone?: "neutral" | "blue" | "red" | "outline" | "planned" | CountStatus; children: ReactNode; title?: string;
}) {
  return <span className={`badge badge-${tone}`} title={title}>{children}</span>;
}

/** Every count shown carries this badge (PRD §6 UI rule). */
export function CountStatusBadge({ status }: { status: CountStatus }) {
  const s = STATUS_LABELS[status];
  return <Badge tone={status} title={s.description}>{s.label}</Badge>;
}

export function TokenizerTag({ t }: { t: TokenizerRef }) {
  return (
    <span className="badge badge-outline mono" title={`${t.kind} tokenizer · library ${t.library} ${t.version}`}>
      {t.name} · {t.library} {t.version}
    </span>
  );
}

export function Callout({ tone = "neutral", title, children, icon }: {
  tone?: "neutral" | "info" | "warn" | "error" | "success"; title?: ReactNode; children?: ReactNode; icon?: ReactNode;
}) {
  const Icon = tone === "warn" || tone === "error" ? IconAlert : tone === "success" ? IconCheck : IconInfo;
  return (
    <div className={`callout callout-${tone}`} role={tone === "error" ? "alert" : undefined}>
      {icon ?? <Icon className="callout-icon" width={18} height={18} />}
      <div>
        {title && <strong>{title}</strong>}
        {children && <div style={{ marginTop: title ? 2 : 0 }}>{children}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: ApiError; onRetry?: () => void; compact?: boolean }) {
  const hint = errorHint(error.code);
  return (
    <Callout tone="error" title={compact ? undefined : `Request failed${error.status ? ` (HTTP ${error.status})` : ""}`}>
      <div>{error.message} <code>{error.code}</code></div>
      {hint && <div className="small" style={{ marginTop: 4 }}>{hint}</div>}
      {onRetry && (
        <button className="btn btn-sm btn-secondary" style={{ marginTop: 8 }} onClick={onRetry}>
          <IconRefresh /> Retry
        </button>
      )}
    </Callout>
  );
}

export function EmptyState({ title, children, art = "table", action }: {
  title: string; children?: ReactNode; art?: "table" | "chart" | "chat" | "phone"; action?: ReactNode;
}) {
  return (
    <div className="empty">
      <EmptyArt kind={art} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

function EmptyArt({ kind }: { kind: "table" | "chart" | "chat" | "phone" }) {
  const stroke = "#C3C8D1";
  return (
    <svg className="empty-art" viewBox="0 0 64 64" aria-hidden="true" fill="none" stroke={stroke} strokeWidth="1.5">
      {kind === "table" && (<><rect x="8" y="12" width="48" height="40" rx="4" /><path d="M8 22h48M8 32h48M8 42h48M24 12v40" /><rect x="8" y="12" width="48" height="10" rx="4" fill="#EEF3FD" stroke="#93AEEB" /></>)}
      {kind === "chart" && (<><path d="M10 54h46M10 10v44" /><rect x="16" y="34" width="7" height="20" fill="#EEF3FD" stroke="#93AEEB" /><rect x="28" y="24" width="7" height="30" /><rect x="40" y="40" width="7" height="14" fill="#FDF1F2" stroke="#F9D9DC" /></>)}
      {kind === "chat" && (<><rect x="8" y="12" width="34" height="20" rx="6" fill="#EEF3FD" stroke="#93AEEB" /><rect x="22" y="36" width="34" height="16" rx="6" /></>)}
      {kind === "phone" && (<><rect x="20" y="8" width="24" height="48" rx="5" /><path d="M28 48h8" /><circle cx="32" cy="26" r="7" fill="#FDF1F2" stroke="#F9D9DC" /></>)}
    </svg>
  );
}

export function Skeleton({ h = 14, w = "100%", style }: { h?: number; w?: number | string; style?: React.CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} aria-hidden="true" />;
}

export function LoadingRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="stack" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} h={18} w={`${92 - i * 9}%`} />)}
    </div>
  );
}

/** A feature whose backend endpoint does not exist yet. Shows no data, only the reason. */
export function InactiveFeature({ title, endpoint, children }: {
  title: string; endpoint?: PlannedEndpoint; children?: ReactNode;
}) {
  return (
    <section className="inactive" aria-label={`${title} (not available yet)`}>
      <div className="inactive-head">
        <div>
          <h3>{title}</h3>
          {children && <div><p>{children}</p></div>}
        </div>
        <div className="btn-row">
          <Badge tone="planned">Not available{endpoint ? ` · ${endpoint.phase}` : ""}</Badge>
          {endpoint && <span className="endpoint"><b>{endpoint.method}</b> {endpoint.path}</span>}
        </div>
      </div>
    </section>
  );
}

export function MockBanner({ children }: { children?: ReactNode }) {
  return (
    <div className="mock-banner" role="note">
      <IconAlert width={16} height={16} />
      <span>MOCK DATA — layout preview only. Fictional models and values; nothing here is measured, priced or real.{children ? " " : ""}{children}</span>
    </div>
  );
}

export function Stat({ label, value, unit, large }: { label: ReactNode; value: ReactNode; unit?: ReactNode; large?: boolean }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${large ? " lg" : ""}`}>{value}{unit && <span className="stat-unit">{unit}</span>}</span>
    </div>
  );
}

export function Field({ label, hint, error, htmlFor, children, aside }: {
  label: ReactNode; hint?: ReactNode; error?: ReactNode; htmlFor?: string; children: ReactNode; aside?: ReactNode;
}) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={htmlFor}><span>{label}</span>{aside}</label>
      {children}
      {error ? <span className="field-error" role="alert">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label, disabled }: {
  value: T; options: { value: T; label: string; disabled?: boolean }[]; onChange: (v: T) => void; label: string; disabled?: boolean;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} disabled={disabled || o.disabled} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pager">
      <span className="num">{total === 0 ? "No results" : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}</span>
      <div className="btn-row">
        <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="num">Page {page} / {pages}</span>
        <button className="btn btn-sm btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
