import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = process.argv[2], OUT = process.argv[3], P = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
fs.mkdirSync(OUT, { recursive: true });
const SCRIPT = { en: /[A-Za-z]/, kn: /[\u0C80-\u0CFF]/, hi: /[\u0900-\u097F]/, ta: /[\u0B80-\u0BFF]/, te: /[\u0C00-\u0C7F]/, kn_roman: /[A-Za-z]/, en_long: /[A-Za-z]/ };
const LANG = { en: "en", en_long: "en", kn: "auto", hi: "auto", ta: "auto", te: "auto", kn_roman: "kn" };
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
const errors = []; page.on("console", (m) => m.type() === "error" && errors.push(m.text())); page.on("pageerror", (e) => errors.push(String(e)));
const rows = []; let pass = 0, total = 0;
async function open() {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => { const el = document.querySelector("#op-tok"); return el && !el.disabled && el.value; }, null, { timeout: 30000 });
}
for (const [key, text] of Object.entries(P)) {
  for (const mode of ["Safe", "Balanced", "Aggressive"]) {
    total++;
    try {
      await open();
      await page.fill('textarea[aria-label="Original prompt"]', text);
      await page.selectOption("#op-lang", LANG[key]);
      await page.getByRole("button", { name: mode, exact: true }).click();
      const [resp] = await Promise.all([
        page.waitForResponse((r) => r.url().endsWith("/api/optimize") && r.request().method() === "POST", { timeout: 60000 }),
        page.getByRole("button", { name: "Optimize", exact: true }).click(),
      ]);
      const o = await resp.json();
      await page.waitForSelector("text=Optimization result", { timeout: 60000 });
      const shown = (await page.locator('[aria-label="Final prompt"]').textContent()) ?? "";
      const body = await page.textContent("body");
      const t = o.token_counts[0];
      const scriptOk = SCRIPT[key].test(o.optimized);
      const shrinkOk = mode === "Safe" || key === "kn_roman" || t.after < t.before;
      const ok = resp.status() === 200 && shown.trim() === o.optimized.trim() && scriptOk && shrinkOk
        && o.meaning_check.status !== "changed" && /Meaning check \(rule-based/.test(body);
      if (ok) pass++;
      rows.push({ key, mode, ok, tokenizer: t.tokenizer.name, before: t.before, after: t.after, saved: t.saved, pct: t.saved_pct,
        meaning: o.meaning_check.status, language: o.language, accepted: o.accepted.map((a) => a.rule), suggestions: o.suggestions.length,
        shown_matches_api: shown.trim() === o.optimized.trim(), script_ok: scriptOk, optimized: o.optimized.slice(0, 600) });
      if (key === "en_long" || key === "kn") await page.screenshot({ path: `${OUT}/accept-${key}-${mode.toLowerCase()}.png`, fullPage: true });
    } catch (e) { rows.push({ key, mode, ok: false, error: String(e).slice(0, 300) }); }
  }
}
// Aggressive: Select all → Apply approved suggestions builds one shorter alternative
total++;
try {
  await open();
  await page.fill('textarea[aria-label="Original prompt"]', "Could you please summarise this report in order to save time? I would like you to keep it under 100 words. Do not include names.");
  await page.selectOption("#op-lang", "en");
  await page.getByRole("button", { name: "Aggressive", exact: true }).click();
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  await page.getByRole("radio", { name: /Use the optimized version/ }).check();
  await page.getByRole("button", { name: /Select all/ }).click();
  const [ap] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/pipeline/apply"), { timeout: 60000 }),
    page.getByRole("button", { name: "Apply approved suggestions" }).click(),
  ]);
  const a = await ap.json();
  await page.waitForTimeout(300);
  const finalText = (await page.locator('[aria-label="Final prompt"]').textContent()) ?? "";
  const ok = ap.status() === 200 && a.tokens_after < a.tokens_before && finalText.trim() === a.text.trim() && /not include names/.test(finalText);
  if (ok) pass++;
  rows.push({ select_all: ok, before: a.tokens_before, after: a.tokens_after, allowed: a.allowed, text: a.text });
  await page.screenshot({ path: `${OUT}/accept-aggressive-select-all.png`, fullPage: true });
} catch (e) { rows.push({ select_all: false, error: String(e).slice(0, 300) }); }
// Editing still works
total++;
try {
  await open();
  await page.fill('textarea[aria-label="Original prompt"]', "Please summarize this report in three bullet points.");
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/meaning-check"), { timeout: 60000 }), page.getByRole("button", { name: /Count original/ }).click()]);
  await page.waitForTimeout(400);
  const ok = /Your rewrite 1/.test(await page.textContent("body")); if (ok) pass++; rows.push({ editing: ok });
} catch (e) { rows.push({ editing: false, error: String(e).slice(0, 300) }); }
fs.writeFileSync(`${OUT}/accept.json`, JSON.stringify({ base: BASE, pass, total, errors, rows }, null, 2));
console.log(`${pass}/${total} passed; console/page errors: ${errors.length}`);
await browser.close();
