// UI tests for the Round 1 integration: drives the real frontend (http://localhost:3000) in the
// installed Microsoft Edge against the real backend. Records API calls made by the browser,
// what the page displays, and full-page screenshots.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://localhost:3000";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const consoleErrors = [];
let apiLog = [];

const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(`${page.url()} :: ${m.text()}`); });
page.on("response", (r) => { if (r.url().includes(":8000/")) apiLog.push(`${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`); });

function record(name, ok, details) {
  results.push({ name, ok, details, api: apiLog });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${details ? "  — " + JSON.stringify(details) : ""}`);
  apiLog = [];
}
async function shot(name) { await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true }); }
async function waitTokenizers(sel) {
  await page.waitForFunction((s) => { const el = document.querySelector(s); return el && !el.disabled && el.value; }, sel, { timeout: 30000 });
}
async function step(name, fn) {
  try { await fn(); } catch (e) { record(name, false, { error: String(e).slice(0, 300) }); await shot(`ERR-${name.replace(/\W+/g, "_")}`); }
}

const TEXT = {
  en: "Please   summarise this report!!!   Do not include names. Deadline: 12 Jan 2026, budget ₹5,000.",
  kn: "ದಯವಿಟ್ಟು   ಈ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ!!!   ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ. ಬಜೆಟ್ ₹೫೦೦೦.",
  hi: "कृपया   इस रिपोर्ट का सारांश दें!!!   नाम शामिल न करें। बजट ₹5000 है।",
  ta: "தயவுசெய்து   இந்த அறிக்கையைச் சுருக்கவும்!!!   பெயர்களைச் சேர்க்க வேண்டாம்.",
  te: "దయచేసి   ఈ నివేదికను సంగ్రహించండి!!!   పేర్లు చేర్చవద్దు.",
};

// ---------------------------------------------------------------- Home / health
await step("Home loads and reports backend health", async () => {
  await page.goto(BASE, { waitUntil: "networkidle" });
  const body = await page.textContent("body");
  record("Home loads and reports backend health", /REDUTAX/.test(body), { healthCall: apiLog.find((a) => a.includes("/health")) });
  await shot("01-home");
});

// ---------------------------------------------------------------- Feature 1: Token Counter
for (const [lang, text] of Object.entries(TEXT)) {
  await step(`Counter · ${lang} · cl100k_base`, async () => {
    await page.goto(`${BASE}/counter`, { waitUntil: "networkidle" });
    await waitTokenizers("#ct-tok");
    await page.selectOption("#ct-tok", "cl100k_base");
    await page.fill("#ct-text", text);
    await page.getByRole("button", { name: "Count tokens" }).click();
    await page.waitForSelector(".readout .stat-value", { timeout: 30000 });
    const tokens = (await page.textContent(".readout .stat-value")).trim();
    const tag = (await page.textContent(".readout .badge.mono")).trim();
    record(`Counter · ${lang} · cl100k_base`, /^\d[\d,]*$/.test(tokens) && tag.includes("cl100k_base"), { tokens, tokenizer: tag });
    if (lang === "kn") await shot("02-counter-kannada");
  });
}
await step("Counter · tokenizer selection changes the count (Kannada, o200k_base)", async () => {
  await page.goto(`${BASE}/counter`, { waitUntil: "networkidle" });
  await waitTokenizers("#ct-tok");
  await page.fill("#ct-text", TEXT.kn);
  const counts = {};
  for (const tok of ["cl100k_base", "o200k_base"]) {
    await page.selectOption("#ct-tok", tok);
    await page.getByRole("button", { name: "Count tokens" }).click();
    await page.waitForFunction((t) => document.querySelector(".readout .badge.mono")?.textContent?.includes(t), tok, { timeout: 30000 });
    counts[tok] = (await page.textContent(".readout .stat-value")).trim();
  }
  record("Counter · tokenizer selection changes the count (Kannada, o200k_base)", counts.cl100k_base !== counts.o200k_base, counts);
  await shot("03-counter-o200k");
});
await step("Counter · over-limit input is blocked client-side", async () => {
  await page.goto(`${BASE}/counter`, { waitUntil: "networkidle" });
  await waitTokenizers("#ct-tok");
  await page.fill("#ct-text", "a".repeat(20001));
  const disabled = await page.getByRole("button", { name: "Count tokens" }).isDisabled();
  record("Counter · over-limit input is blocked client-side", disabled, { countButtonDisabled: disabled });
});

// ---------------------------------------------------------------- Feature 2: Language Comparison
await step("Compare · English vs Kannada vs Hindi", async () => {
  await page.goto(`${BASE}/compare`, { waitUntil: "networkidle" });
  await waitTokenizers("#cmp-tok");
  await page.fill('textarea[aria-label="Variant 1 text"]', "Please send the report today.");
  await page.fill('textarea[aria-label="Variant 2 text"]', "ದಯವಿಟ್ಟು ಇಂದು ವರದಿಯನ್ನು ಕಳುಹಿಸಿ.");
  await page.getByRole("button", { name: "Add variant" }).click();
  await page.selectOption('select[aria-label="Variant 3 language"]', "hi");
  await page.fill('textarea[aria-label="Variant 3 text"]', "कृपया आज रिपोर्ट भेजें।");
  const resp = page.waitForResponse((r) => r.url().includes("/api/compare-languages"), { timeout: 30000 });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await resp;
  await page.waitForTimeout(500);
  const body = await page.textContent("body");
  record("Compare · English vs Kannada vs Hindi", /Unaligned|unaligned/.test(body) && /cl100k_base/.test(body), { warningShown: /not verified as meaning-equivalent/.test(body) });
  await shot("04-compare-results");
});

// ---------------------------------------------------------------- Feature 6: Script variants (on Compare)
await step("Script variants · Kannada → ISO + Baraha, review + add to comparison", async () => {
  await page.getByLabel("Baraha (ASCII)").check();
  const svResp = page.waitForResponse((r) => r.url().includes("/api/script-variants"), { timeout: 30000 });
  await page.getByRole("button", { name: "Generate script variants" }).click();
  await svResp;
  await page.waitForSelector("text=Needs your review", { timeout: 30000 });
  const body = await page.textContent("body");
  const before = await page.locator('textarea[aria-label$=" text"]').count();
  await shot("05-script-variants-kannada");
  await page.getByRole("button", { name: "Add to comparison" }).first().click();
  const after = await page.locator('textarea[aria-label$=" text"]').count();
  record("Script variants · Kannada → ISO + Baraha, review + add to comparison",
    /Lossless/.test(body) && /Needs your review/.test(body) && after === before + 1,
    { hasIso: /dayaviṭṭu/.test(body), hasBaraha: /dayaviTTu/.test(body), variantsBefore: before, variantsAfter: after,
      schemeWarning: /everyday Romanized typing/.test(body) });
});
await step("Script variants · Tamil shows the Sanskrit-style warning", async () => {
  await page.goto(`${BASE}/compare`, { waitUntil: "networkidle" });
  await waitTokenizers("#cmp-tok");
  await page.selectOption('select[aria-label="Variant 2 language"]', "ta");
  await page.fill('textarea[aria-label="Variant 2 text"]', TEXT.ta);
  await page.getByRole("button", { name: "Generate script variants" }).click();
  await page.waitForSelector("text=Transliteration warnings", { timeout: 30000 });
  const body = await page.textContent("body");
  record("Script variants · Tamil shows the Sanskrit-style warning", /Sanskrit-style/.test(body) && /Needs your review/.test(body), {});
  await shot("06-script-variants-tamil");
});
await step("Script variants · Hindi and Telugu", async () => {
  const out = {};
  for (const [lang, text] of [["hi", TEXT.hi], ["te", TEXT.te]]) {
    await page.goto(`${BASE}/compare`, { waitUntil: "networkidle" });
    await waitTokenizers("#cmp-tok");
    await page.selectOption('select[aria-label="Variant 2 language"]', lang);
    await page.fill('textarea[aria-label="Variant 2 text"]', text);
    await page.getByRole("button", { name: "Generate script variants" }).click();
    await page.waitForSelector("text=Needs your review", { timeout: 30000 });
    out[lang] = (await page.locator("table.table tbody tr td.indic").first().textContent()).trim().slice(0, 60);
  }
  record("Script variants · Hindi and Telugu", !!out.hi && !!out.te, out);
});
await step("Script variants · casual Romanized → native is unsupported", async () => {
  await page.goto(`${BASE}/compare`, { waitUntil: "networkidle" });
  await waitTokenizers("#cmp-tok");
  await page.selectOption('select[aria-label="Variant 2 script"]', "Latn");
  await page.fill('textarea[aria-label="Variant 2 text"]', "naanu naale baruvudilla");
  await page.getByRole("button", { name: "Romanized → native" }).click();
  await page.getByRole("button", { name: "Generate script variants" }).click();
  await page.waitForSelector(".callout strong:has-text('Not supported')", { timeout: 30000 });
  const body = await page.textContent("body");
  record("Script variants · casual Romanized → native is unsupported", /follows no standard scheme/.test(body), {});
  await shot("07-script-variants-casual-unsupported");
});

// ---------------------------------------------------------------- Features 3 + 5: Optimizer + meaning check
for (const [lang, text] of Object.entries(TEXT)) {
  await step(`Optimizer · ${lang}`, async () => {
    await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
    await waitTokenizers("#op-tok");
    await page.fill('textarea[aria-label="Original prompt"]', text);
    await page.selectOption("#op-lang", lang);
    await page.getByRole("button", { name: "Optimize", exact: true }).click();
    await page.waitForSelector("text=Optimization result", { timeout: 60000 });
    const body = await page.textContent("body");
    const accepted = (await page.locator("section.panel h2", { hasText: "Accepted edits" }).textContent()).replace(/\D+/g, "");
    const suggested = (await page.locator("section.panel h2", { hasText: "Suggestions — not applied" }).textContent()).replace(/\D+/g, "");
    const ok = /Before/.test(body) && /Meaning check — original vs optimized/.test(body) && /Critical details in the original/.test(body);
    record(`Optimizer · ${lang}`, ok, {
      accepted, suggested,
      finalStatus: (await page.locator(".btn-row .badge").filter({ hasText: /Preserved|At risk|Changed/ }).first().textContent()).trim(),
      reviewShown: /Needs your review/.test(body), billingNote: /not provider billing/.test(body),
      criticalDetailChips: await page.locator("section.panel:has-text('Critical details in the original') .badge-outline").count(),
    });
    await shot(`08-optimizer-${lang}`);
  });
}
await step("Optimizer · aggressive mode offers script variants as suggestions only (Kannada)", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', TEXT.kn);
  await page.selectOption("#op-lang", "kn");
  await page.getByLabel(/Allow script or language alternatives/).check();
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  const body = await page.textContent("body");
  const optimized = await page.locator(".side-by-side > div").nth(1).locator("p").textContent();
  record("Optimizer · aggressive mode offers script variants as suggestions only (Kannada)",
    /script_variant/.test(body) && /ದಯವಿಟ್ಟು/.test(optimized), { optimizedStillKannada: /ದಯವಿಟ್ಟು/.test(optimized) });
  await shot("09-optimizer-aggressive-kannada");
});
await step("Optimizer · Kannada at_risk edit is a suggestion that needs review", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  const text = "ದಯವಿಟ್ಟು​   ವರದಿ ಕಳುಹಿಸಿ!!!!!! ಹೆಸರು ಸೇರಿಸಬೇಡಿ";
  await page.fill('textarea[aria-label="Original prompt"]', text);
  await page.selectOption("#op-lang", "kn");
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  const body = await page.textContent("body");
  const optimized = await page.locator(".side-by-side > div").nth(1).locator("p").textContent();
  const suggested = (await page.locator("section.panel h2", { hasText: "Suggestions — not applied" }).textContent()).replace(/\D+/g, "");
  record("Optimizer · Kannada at_risk edit is a suggestion that needs review",
    Number(suggested) >= 1 && /Needs your review/.test(body) && /At risk/.test(body) && optimized.includes("!!!!!!"),
    { suggested, exclamationsKeptInOutput: optimized.includes("!!!!!!"), riskText: /not yet approved by native speakers/.test(body) });
  await shot("09b-optimizer-kannada-at-risk-suggestion");
});
await step("Optimizer · gate rejects an edit that would change a detail", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', "Pay Rs.   500 now.");
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  const body = await page.textContent("body");
  record("Optimizer · gate rejects an edit that would change a detail", /Original kept/.test(body) && /meaning check: changed/.test(body), {});
  await shot("10-optimizer-gate-rejection");
});
await step("Meaning check · user rewrite that drops a number and a negation is rejected", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', "Do not pay more than ₹500 before 5 pm.");
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await page.fill('textarea[aria-label="Rewrite 1"]', "Pay before 5 pm.");
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await page.fill('textarea[aria-label="Rewrite 2"]', "Don't pay more than Rs. 500 before 5 pm.");
  await page.getByRole("button", { name: /Count original/ }).click();
  await page.waitForSelector("text=Candidate ledger", { timeout: 60000 });
  const rows = await page.locator("table.table tbody tr").allTextContents();
  await page.getByRole("button", { name: "View", exact: true }).first().click();
  const body = await page.textContent("body");
  record("Meaning check · user rewrite that drops a number and a negation is rejected",
    rows.some((r) => /rewrite 1/i.test(r) && /Changed/.test(r) && /Rejected/.test(r)) && rows.some((r) => /rewrite 2/i.test(r) && /Preserved/.test(r)),
    { rewrite1: rows.find((r) => /rewrite 1/i.test(r))?.slice(0, 200), rewrite2: rows.find((r) => /rewrite 2/i.test(r))?.slice(0, 200), findingsShown: /missing/.test(body) });
  await shot("11-meaning-check-rewrites");
});

// ---------------------------------------------------------------- Loading + duplicate submissions (slowed network)
await step("Loading state and duplicate-submission prevention", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  let calls = 0;
  await page.route("**/api/optimize", async (route) => { calls++; await new Promise((r) => setTimeout(r, 2000)); await route.continue(); });
  await page.fill('textarea[aria-label="Original prompt"]', TEXT.en);
  const btn = page.getByRole("button", { name: "Optimize", exact: true });
  await btn.click();
  await page.waitForTimeout(300);
  const disabledWhileLoading = await btn.isDisabled();
  const spinner = await btn.locator(".spinner").count();
  await btn.click({ force: true, timeout: 1000 }).catch(() => {});
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  await page.unroute("**/api/optimize");
  record("Loading state and duplicate-submission prevention", disabledWhileLoading && spinner === 1 && calls === 1,
    { disabledWhileLoading, spinnerShown: spinner === 1, optimizeRequests: calls });
});

// ---------------------------------------------------------------- Errors
await step("Error · backend unreachable shows a clear message", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.route("**/api/optimize", (route) => route.abort("connectionrefused"));
  await page.fill('textarea[aria-label="Original prompt"]', TEXT.en);
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Could not reach the REDUTAX backend", { timeout: 30000 });
  await page.unroute("**/api/optimize");
  const body = await page.textContent("body");
  record("Error · backend unreachable shows a clear message (simulated by aborting the request)", /network_error/.test(body) && /Retry/.test(body), {});
  await shot("12-error-backend-unreachable");
});
await step("Error · real backend validation error is displayed", async () => {
  // The UI only offers valid tokenizers, so the outgoing request is altered to name an unknown one;
  // the REAL backend then answers HTTP 400 unknown_tokenizer and the UI must display it.
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', "Hello   there");
  await page.evaluate(() => {
    const orig = window.fetch;
    window.fetch = (url, init) => {
      if (String(url).includes("/api/optimize") && init?.body) {
        const b = JSON.parse(init.body); b.tokenizers = ["not_a_tokenizer"]; init = { ...init, body: JSON.stringify(b) };
      }
      return orig(url, init);
    };
  });
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=unknown_tokenizer", { timeout: 30000 });
  const body = await page.textContent("body");
  record("Error · real backend error (unknown tokenizer, HTTP 400) is displayed", /HTTP 400/.test(body) && /Unknown tokenizer/.test(body), {});
  await shot("13-error-unknown-tokenizer");
});


// ---------------------------------------------------------------- Added for post-Round-1 validation
await step("Optimizer · balanced mode reports that no phrase list is reviewed", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', "Practise daily in order to   improve.");
  await page.selectOption("#op-lang", "en");
  await page.getByRole("button", { name: "+ Reviewed phrase lists" }).click();
  await page.getByRole("button", { name: "Optimize", exact: true }).click();
  await page.waitForSelector("text=Optimization result", { timeout: 60000 });
  const body = await page.textContent("body");
  const optimized = await page.locator(".side-by-side > div").nth(1).locator("p").textContent();
  record("Optimizer · balanced mode reports that no phrase list is reviewed",
    /balanced mode/.test(body) && /No reviewed phrase list/.test(body) && /in order to/.test(optimized),
    { phraseNotApplied: /in order to/.test(optimized), listStatus: /en — developer curated, 11 entries, not applied/.test(body) });
  await shot("14-optimizer-balanced-mode");
});
await step("Meaning check (rules_v2) · unit change 5 kg → 5 g is rejected in the UI", async () => {
  await page.goto(`${BASE}/optimize`, { waitUntil: "networkidle" });
  await waitTokenizers("#op-tok");
  await page.fill('textarea[aria-label="Original prompt"]', "Add 5 kg of rice and wait 3 days.");
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await page.fill('textarea[aria-label="Rewrite 1"]', "Add 5 g of rice and wait 3 days.");
  await page.getByRole("button", { name: "Add rewrite" }).click();
  await page.fill('textarea[aria-label="Rewrite 2"]', "Add 5kg of rice and wait 3 days.");
  await page.getByRole("button", { name: /Count original/ }).click();
  await page.waitForSelector("text=Candidate ledger", { timeout: 60000 });
  const rows = await page.locator("table.table tbody tr").allTextContents();
  const r1 = rows.find((r) => /rewrite 1/i.test(r)) ?? "";
  const r2 = rows.find((r) => /rewrite 2/i.test(r)) ?? "";
  await page.getByRole("button", { name: "View", exact: true }).first().click();
  const body = await page.textContent("body");
  record("Meaning check (rules_v2) · unit change 5 kg → 5 g is rejected in the UI",
    /Changed/.test(r1) && /Rejected/.test(r1) && /Preserved/.test(r2) && /rules_v2/.test(body),
    { rewrite1: r1.slice(0, 140), rewrite2: r2.slice(0, 140) });
  await shot("15-meaning-check-units-v2");
});


// ---------------------------------------------------------------- Database-backed screens (Neon)
await step("Research Dashboard shows the stored PostgreSQL run, values match the API", async () => {
  const api = await (await fetch("http://127.0.0.1:8000/api/benchmarks")).json();
  const run = api.items[0];
  await page.goto(`${BASE}/research`, { waitUntil: "networkidle" });
  await page.waitForSelector(`text=${run.run_id}`, { timeout: 60000 });
  await page.waitForSelector("text=Summary table", { timeout: 60000 });
  const table = page.locator("section:has(h2:has-text('Summary table')) table tbody tr");
  const rows = await table.allTextContents();
  const fmt = (n) => new Intl.NumberFormat("en-IN").format(n);
  let matched = 0;
  const problems = [];
  for (const s of run.summaries) {
    const row = rows.find((r) => r.includes(s.tokenizer.name) && r.includes(fmt(s.total_tokens)));
    const ratio = `${s.ratio_vs_reference.toFixed(2)}×`;
    if (row && row.includes(ratio) && row.includes(s.fertility_mean.toFixed(2))) matched++;
    else problems.push(`${s.tokenizer.name}/${s.language}`);
  }
  const body = await page.textContent("body");
  record("Research Dashboard shows the stored PostgreSQL run, values match the API",
    matched === run.summaries.length && rows.length === run.summaries.length && !/database_not_configured/.test(body),
    { runId: run.run_id, summaryRowsShown: rows.length, matchedApiValues: matched, problems });
  await shot("16-research-dashboard-stored-run");
});
await step("Research Dashboard per-sample results load from the database", async () => {
  await page.waitForSelector("text=Per-sample results", { timeout: 60000 });
  await page.waitForFunction(() => /flores-devtest-\d{4}-(en|hi|kn|ta|te)/.test(document.body.innerText), null, { timeout: 60000 });
  const body = await page.textContent("body");
  record("Research Dashboard per-sample results load from the database", /flores-devtest-\d{4}/.test(body), {});
  await shot("17-research-per-sample-results");
});
await step("Language Comparison loads an aligned FLORES-200 group from the database", async () => {
  await page.goto(`${BASE}/compare`, { waitUntil: "networkidle" });
  await waitTokenizers("#cmp-tok");
  await page.getByRole("button", { name: "Load aligned sample" }).click();
  await page.waitForSelector("text=flores-devtest-0001", { timeout: 60000 });
  await page.getByRole("button", { name: "Use", exact: true }).first().click();
  await page.waitForSelector("text=Aligned group", { timeout: 30000 });
  const cards = await page.locator('textarea[aria-label$=" text"]').count();
  const resp = page.waitForResponse((r) => r.url().includes("/api/compare-languages"), { timeout: 30000 });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const cmp = await (await resp).json();
  const body = await page.textContent("body");
  record("Language Comparison loads an aligned FLORES-200 group from the database",
    /Aligned group/.test(body) && cards === 5 && cmp.aligned === true && !/database_not_configured/.test(body),
    { variantCards: cards, compareAligned: cmp.aligned, languages: cmp.rows.map((r) => r.language).join(",") });
  await shot("18-compare-aligned-sample-loader");
});


// ---------------------------------------------------------------- Phase 2 screens (Features 4, 7, 8, 9, 10)
// Test models are user-entered fixtures with made-up ids and prices (not real model data).
await step("Cost Calculator · backend estimate with optimized comparison (Kannada)", async () => {
  await page.goto(`${BASE}/cost`, { waitUntil: "networkidle" });
  await waitTokenizers("#cs-tok");
  await page.fill('textarea[aria-label="Prompt text"]', "ದಯವಿಟ್ಟು   ಈ ವರದಿಯನ್ನು ಕಳುಹಿಸಿ!!!!!! ಬಜೆಟ್ ₹೫೦೦೦.");
  await page.fill("#cs-out", "200");
  await page.fill('input[aria-label="Model 1 name"]', "test-model-a");
  await page.selectOption('select[aria-label="Model 1 encoding"]', "o200k_base");
  await page.fill('input[aria-label="Model 1 input price"]', "100");
  await page.fill('input[aria-label="Model 1 output price"]', "400");
  const resp = page.waitForResponse((r) => r.url().includes("/api/cost/estimate"), { timeout: 60000 });
  await page.getByRole("button", { name: "Calculate estimate" }).click();
  const est = await (await resp).json();
  await page.waitForSelector("text=Estimated total per request", { timeout: 30000 });
  const body = await page.textContent("body");
  const m = est.models[0];
  record("Cost Calculator · backend estimate with optimized comparison (Kannada)",
    m.model_id === "test-model-a" && m.price_status === "user_entered" && /User-entered/.test(body) && m.total_cost > 0,
    { inputTokens: m.input_tokens, optimizedTokens: m.optimized_input_tokens, total: m.total_cost, savingsPct: m.savings_pct, encoding: m.encoding_used });
  await shot("19-cost-calculator");
});
await step("Model Recommendation · add user models, recommend, lock", async () => {
  await page.goto(`${BASE}/models`, { waitUntil: "networkidle" });
  for (const [id, ctx, inp, out, sup] of [["test-model-cheap", "8000", "0.5", "1.5", "unknown"], ["test-model-kn", "16000", "2", "8", "claimed"]]) {
    await page.fill("#am-id", id); await page.fill("#am-p", "TestProvider");
    await page.selectOption("#am-enc", "o200k_base"); await page.fill("#am-ctx", ctx);
    await page.fill("#am-in", inp); await page.fill("#am-out", out); await page.selectOption("#am-sup", sup);
    await page.getByRole("button", { name: "Add user-entered model" }).click();
  }
  await page.fill("#md-text", "ದಯವಿಟ್ಟು ಈ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ.");
  await page.selectOption("#md-pref", "lowest");
  const resp = page.waitForResponse((r) => r.url().includes("/api/models/recommend"), { timeout: 60000 });
  await page.getByRole("button", { name: "Recommend", exact: true }).click();
  const r1 = await (await resp).json();
  await page.waitForSelector("text=Recommended:", { timeout: 30000 });
  await page.selectOption("#md-sup", "claimed");
  const resp2 = page.waitForResponse((r) => r.url().includes("/api/models/recommend"), { timeout: 60000 });
  await page.getByRole("button", { name: "Recommend", exact: true }).click();
  const r2 = await (await resp2).json();
  await page.waitForTimeout(300);
  const body = await page.textContent("body");
  record("Model Recommendation · add user models, recommend, lock",
    r1.recommended?.model_id === "test-model-cheap" && r2.recommended?.model_id === "test-model-kn" && /Excluded model/.test(body),
    { lowestCost: r1.recommended?.model_id, claimedSupport: r2.recommended?.model_id, excluded: r2.excluded.map((c) => c.model_id) });
  await shot("20-model-recommendation");
});
await step("AI Chat · analysis mode, approval, LLM not configured is explicit", async () => {
  await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });
  await page.fill('textarea[aria-label="Message"]', "ದಯವಿಟ್ಟು   ನಾಳೆ ₹೫೦೦ ಪಾವತಿಸಬೇಡಿ!!!!!!");
  await page.selectOption('select[aria-label="Language"]', "kn");
  const resp = page.waitForResponse((r) => r.url().includes("/api/chat") && r.request().method() === "POST", { timeout: 60000 });
  await page.getByRole("button", { name: "Analyse" }).click();
  const a = await (await resp).json();
  await page.waitForSelector("text=REDUTAX analysis — not an AI reply", { timeout: 30000 });
  const boxes = page.locator(".turn-bubble input[type=checkbox]");
  if (await boxes.count()) await boxes.first().check();
  await page.getByRole("button", { name: "Apply approved edits" }).click();
  await page.waitForSelector("text=Prompt to send:", { timeout: 30000 });
  const sendDisabled = await page.getByRole("button", { name: /Send to model/ }).isDisabled();
  const body = await page.textContent("body");
  record("AI Chat · analysis mode, approval, LLM not configured is explicit",
    a.mode === "analysis" && a.llm_available === false && sendDisabled && /No LLM provider is configured/.test(body) && !/As an AI/.test(body),
    { sessionId: a.session_id.slice(0, 6) + "…", suggestions: a.analysis.optimization.suggestions.length, sendDisabled });
  await shot("21-chat-analysis-mode");
});
await step("Voice · text workflow: process, approve, final comparison; Vapi status", async () => {
  await page.goto(`${BASE}/voice`, { waitUntil: "networkidle" });
  await waitTokenizers("select.select:not([aria-label])");
  await page.fill("#vc-edit", "नमस्ते   कल ₹500 मत भेजो!!!!!!");
  await page.selectOption('select[aria-label="Language"]', "hi");
  const resp = page.waitForResponse((r) => r.url().includes("/api/pipeline/analyze"), { timeout: 60000 });
  await page.getByRole("button", { name: "Process prompt" }).click();
  const a = await (await resp).json();
  await page.waitForSelector("text=Optimization result", { timeout: 30000 });
  const sugg = page.locator("section:has(h2:has-text('Approve uncertain changes')) input[type=checkbox]:not([disabled])");
  if (await sugg.count()) await sugg.first().check();
  const resp2 = page.waitForResponse((r) => r.url().includes("/api/pipeline/apply"), { timeout: 60000 });
  await page.getByRole("button", { name: /Apply .*safe edits and compare/ }).click();
  const ap = await (await resp2).json();
  await page.waitForSelector("text=Original vs final prompt", { timeout: 30000 });
  const body = await page.textContent("body");
  record("Voice · text workflow: process, approve, final comparison; Vapi status",
    a.language === "hi" && ap.allowed === true && /Implemented/.test(body) && /Secret not set/.test(body) && /Not yet/.test(body),
    { tokens: a.tokens.token_count, applied: ap.applied_count, meaning: ap.meaning_check.status, before: ap.tokens_before, after: ap.tokens_after });
  await shot("22-voice-workflow");
});
await step("Settings · real provider status (no secrets)", async () => {
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Chat LLM provider", { timeout: 30000 });
  await page.waitForFunction(() => /analysis mode/.test(document.body.innerText), null, { timeout: 30000 });
  const body = await page.textContent("body");
  record("Settings · real provider status (no secrets)", /Prepared · secret not set/.test(body) && /Empty · add verified models/.test(body) && !/sk-|npg_/.test(body), {});
  await shot("23-settings-providers");
});

fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify({ results, consoleErrors }, null, 2));
console.log(`\n${results.filter((r) => r.ok).length}/${results.length} passed; console errors: ${consoleErrors.length}`);
consoleErrors.slice(0, 10).forEach((e) => console.log("  console:", e));
await browser.close();
