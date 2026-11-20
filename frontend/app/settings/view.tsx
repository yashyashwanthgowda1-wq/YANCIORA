"use client";
import { useEffect, useState } from "react";
import { Badge, Callout, Field, PageHeader, Segmented } from "@/components/ui";
import { API_BASE_URL } from "@/lib/api/client";
import { LANGUAGE_CODES, type LanguageCode } from "@/lib/api/types";
import { useHealth, useTokenizers } from "@/lib/hooks";
import { LANGUAGES } from "@/lib/languages";
import { clearLocalData, DEFAULT_PREFS, loadPrefs, savePrefs, type Preferences } from "@/lib/storage";

export default function SettingsView() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  const [saved, setSaved] = useState(false);
  const [cleared, setCleared] = useState(false);
  const health = useHealth();
  const toks = useTokenizers();
  useEffect(() => setPrefs(loadPrefs()), []);

  const set = (patch: Partial<Preferences>) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    savePrefs(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 1200);
  };
  const toggleLang = (c: LanguageCode) => {
    const has = prefs.interfaceLanguages.includes(c);
    if (has && prefs.interfaceLanguages.length === 1) return;
    set({ interfaceLanguages: has ? prefs.interfaceLanguages.filter((l) => l !== c) : [...prefs.interfaceLanguages, c] });
  };

  const db = health.data?.database.status;

  return (
    <>
      <PageHeader
        eyebrow={<>System <Badge tone="blue">Live</Badge></>}
        title="Settings & Privacy"
        lede="Preferences are kept in this browser only. There are no accounts yet, so nothing here is sent to the server."
        meta={<span className="small subtle" aria-live="polite">{saved ? "Saved in this browser" : ""}</span>}
      />

      <div className="settings-section">
        <div><h2>Languages</h2><p>Languages you work in. They come first in selectors.</p></div>
        <div className="stack">
          <div className="chip-select">
            {LANGUAGE_CODES.map((c) => (
              <button key={c} className="chip" aria-pressed={prefs.interfaceLanguages.includes(c)} onClick={() => toggleLang(c)}>
                <span lang={c}>{LANGUAGES[c].native}</span>{c !== "en" && <span className="subtle">· {LANGUAGES[c].name}</span>}
              </button>
            ))}
          </div>
          <Field label="Default tokenizer" htmlFor="st-tok" hint="Used when a page first loads">
            <select id="st-tok" className="select" style={{ maxWidth: 280 }} value={prefs.defaultTokenizer ?? ""} onChange={(e) => set({ defaultTokenizer: e.target.value || null })}>
              <option value="">First available</option>
              {(toks.data?.tokenizers ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </Field>
        </div>
      </div>

      <div className="settings-section">
        <div><h2>Optimizer approval</h2><p>PRD §22: optimized prompts need your approval before they're sent.</p></div>
        <div className="stack">
          <Segmented label="Approval mode" value="required" onChange={() => undefined}
            options={[{ value: "required", label: "Require approval" }, { value: "auto", label: "Auto-send", disabled: true }]} />
          <p className="small muted">Auto-send stays off until the optimizer has passed quality testing and the team opts in. The original prompt is always kept.</p>
        </div>
      </div>

      <div className="settings-section">
        <div><h2>Data &amp; privacy</h2><p>What this app stores, and where.</p></div>
        <div className="stack">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Data</th><th>Where</th><th>Retention</th></tr></thead>
              <tbody>
                <tr><td>Text you count or compare</td><td>Sent to the REDUTAX backend for counting; not stored by it</td><td>Not retained</td></tr>
                <tr><td>Preferences, recent-activity metadata</td><td>This browser (localStorage)</td><td>Until you clear it</td></tr>
                <tr><td>Voice input audio</td><td>Processed by your browser's speech service (third party)</td><td>Not stored by REDUTAX</td></tr>
                <tr><td>Chat messages, call transcripts</td><td>Not collected; these features are not live yet</td><td>Policy to be set before launch (PRD §22)</td></tr>
              </tbody>
            </table>
          </div>
          <label className="checkbox"><input type="checkbox" checked={prefs.recordActivity} onChange={(e) => set({ recordActivity: e.target.checked })} /> Keep a recent-activity list in this browser (counts and settings only, never your text)</label>
          <div className="btn-row">
            <button className="btn btn-secondary" onClick={() => { clearLocalData(); setPrefs(DEFAULT_PREFS); setCleared(true); }}>Clear data stored in this browser</button>
            {cleared && <span className="small muted" role="status">Cleared.</span>}
          </div>
        </div>
      </div>

      <div className="settings-section">
        <div><h2>Provider configuration</h2><p>Credentials stay on the server. This page never sees or shows keys.</p></div>
        <div className="panel">
          <div className="panel-body">
            <ul className="checklist">
              <li><span>REDUTAX backend <span className="subtle mono small">{API_BASE_URL}</span></span>{health.loading ? <Badge tone="neutral">Checking</Badge> : health.error ? <Badge tone="red">Unreachable</Badge> : <Badge tone="blue">Reachable</Badge>}</li>
              <li><span>PostgreSQL</span>{db === "ok" ? <Badge tone="blue">Connected</Badge> : db === "not_configured" ? <Badge tone="outline">Not configured</Badge> : db === "error" ? <Badge tone="red">Error</Badge> : <Badge tone="neutral">—</Badge>}</li>
              <li><span>Tokenizers</span>{toks.data ? <Badge tone="blue">{toks.data.tokenizers.length} registered</Badge> : <Badge tone="neutral">—</Badge>}</li>
              <li><span>LLM providers (optimizer, chat)</span><Badge tone="planned">No integration yet · Phase 3–4</Badge></li>
              <li><span>Vapi telephone</span><Badge tone="planned">No integration yet · Phase 5</Badge></li>
              <li><span>Price registry</span><Badge tone="planned">No integration yet · Phase 4</Badge></li>
            </ul>
          </div>
        </div>
      </div>

      <div className="settings-section">
        <div><h2>Account &amp; session</h2><p>PRD §22 suggests lightweight session auth for the prototype.</p></div>
        <Callout tone="info" title="No authentication yet">
          The backend has no login or session endpoints. Admin and research functions must be protected before deployment (PRD §17). The UI will add sign-in once the backend defines it.
        </Callout>
      </div>
    </>
  );
}
