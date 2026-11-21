import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = process.argv[2], OUT = process.argv[3];
fs.mkdirSync(OUT, { recursive: true });
const EX = {
  kn: "ನಾಳೆ ಸಭೆಗೆ ಬರುವುದಿಲ್ಲ. ವರದಿಯನ್ನು ಸಂಜೆ 5 ಗಂಟೆಯೊಳಗೆ ಕಳುಹಿಸಿ.",
  hi: "कृपया इस रिपोर्ट का तीन बिंदुओं में सारांश दें।",
  ta: "இந்த அறிக்கையை மூன்று முக்கிய அம்சங்களாக சுருக்கவும்.",
  te: "ఈ నివేదికను మూడు ముఖ్యమైన అంశాలుగా సంక్షిప్తం చేయండి.",
  en: "Please summarize this report in three bullet points and do not remove any important dates or figures.",
};
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
const errors = []; page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
const rows = []; let pass = 0, total = 0;
for (const [lang, text] of Object.entries(EX)) {
  for (const mode of ["Safe", "Balanced", "Aggressive"]) {
    total++;
    try {
      await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => { const el = document.querySelector("#op-tok"); return el && !el.disabled && el.value; }, null, { timeout: 30000 });
      const tok = await page.inputValue("#op-tok");
      await page.fill('textarea[aria-label="Original prompt"]', text);
      await page.selectOption("#op-lang", "auto");
      await page.getByRole("button", { name: mode, exact: true }).click();
      const btn = page.getByRole("button", { name: "Optimize", exact: true });
      const enabled = await btn.isEnabled();
      const [optRes, cdRes] = await Promise.all([
        page.waitForResponse((r) => r.url().endsWith("/api/optimize") && r.request().method() === "POST", { timeout: 60000 }),
        page.waitForResponse((r) => r.url().endsWith("/api/critical-details"), { timeout: 60000 }),
        btn.click(),
      ]);
      const o = await optRes.json(), cd = await cdRes.json();
      await page.waitForSelector("text=Optimization result", { timeout: 60000 });
      const body = await page.textContent("body");
      const tc = Object.fromEntries(o.token_counts.map((t) => [t.tokenizer.name, `${t.before}->${t.after} (saved ${t.saved})`]));
      const ok = enabled && optRes.status() === 200 && o.mode === mode.toLowerCase() && o.language === lang
        && /Meaning check — original vs optimized/.test(body) && /Critical details in the original/.test(body);
      if (ok) pass++;
      rows.push({ lang, mode, ok, ui_tokenizer: tok, detected_language: o.language, tokens: tc, changed: o.changed,
        optimized: o.optimized, accepted: o.accepted.map((a) => a.rule), suggestions: o.suggestions.map((s) => `${s.kind}: "${s.before}" -> "${s.after}" [${s.meaning_status}]`),
        rejected: o.rejected.length, meaning: o.meaning_check.status, risks: o.meaning_check.risks.map((r) => r.slice(0, 90)),
        critical_details: (cd.details || []).map((d) => `${d.category}:${d.text}`) });
      if (lang === "kn") await page.screenshot({ path: `${OUT}/e2e-kn-${mode.toLowerCase()}.png`, fullPage: true });
    } catch (e) { rows.push({ lang, mode, ok: false, error: String(e).slice(0, 300) }); }
  }
}
// Editing workflow still works (Count original + rewrite)
total++;
try {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => { const el = document.querySelector("#op-tok"); return el && !el.disabled && el.value; }, null, { timeout: 30000 });
  await page.fill('textarea[aria-label="Original prompt"]', EX.en);
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await page.getByRole("button", { name: /Count original/ }).click();
  await page.waitForResponse((r) => r.url().endsWith("/api/meaning-check"), { timeout: 60000 });
  await page.waitForTimeout(500);
  const ok = /Your rewrite 1/.test(await page.textContent("body")); if (ok) pass++;
  rows.push({ editing: ok });
} catch (e) { rows.push({ editing: false, error: String(e).slice(0, 300) }); }
fs.writeFileSync(`${OUT}/e2e.json`, JSON.stringify({ base: BASE, pass, total, consoleErrors: errors, rows }, null, 2));
console.log(`${pass}/${total} passed at ${BASE}; console errors: ${errors.length}`);
await browser.close();
