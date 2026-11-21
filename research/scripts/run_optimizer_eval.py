"""Reproducible token-minimization evaluation (Feature 3 optimizer + Feature 5 meaning check).

Usage:
  python research/scripts/run_optimizer_eval.py \
      --input research/data/processed/FLORES-200/2022-07-14/samples.jsonl \
      [--modes safe balanced aggressive] [--tokenizers cl100k_base o200k_base] [--limit N]

Conditions (per sample, per mode):
  natural   the FLORES-200 sentence exactly as stored.
  prompt    a synthetic prompt: an English instruction around the native-script sentence.
            'prompt_clean' is the tidy form; 'prompt_noisy' adds only lossless noise
            (extra spaces, blank lines, a long separator line, a zero-width space, and the
            instruction repeated at the end). Both are optimized. Per tokenizer:
              noise_tokens    = noisy tokens before − clean prompt tokens after optimization
              noise_removed   = noisy tokens before − noisy tokens after
              recovered       = the noisy prompt ends at or below the optimized clean prompt
            Byte-identical recovery is not expected: edits that save no tokens (e.g. a blank-line
            run that the encoding already stores as one token) are correctly skipped.

Measured with the SAME encoding before and after: token counts per tokenizer, characters,
meaning-check status (input vs output), and whether every critical detail's count is unchanged.
Token counts are tokenizer counts, not provider billing. FLORES-200 is used for evaluation only
(licence register gate); nothing is trained and no FLORES text is written to the outputs.

Writes research/reports/opt_eval_<run_id>/: run.json, rows.csv.gz (no text), summary.csv.
"""
import argparse
import csv
import gzip
import hashlib
import json
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import _paths  # noqa: F401
from app.core import details as D
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer
from app.services.dataset_import import check_register_entry, load_register
from app.tokenizers import get_tokenizer

INSTRUCTION = "Summarise the text below in one sentence."
LANG_ORDER = ["en", "kn", "hi", "ta", "te"]


def prompt_clean(text: str) -> str:
    return f"{INSTRUCTION}\n\n---\n{text}"


def prompt_noisy(text: str) -> str:
    """Deterministic, information-preserving noise around and inside the sentence."""
    words = text.split(" ")
    noisy_words = []
    for i, w in enumerate(words):
        noisy_words.append(w + ("​" if i == 0 else ""))     # one zero-width space
    body = ""
    for i, w in enumerate(noisy_words):
        body += w if i == 0 else ("  " if i % 3 == 0 else " ") + w   # every 3rd gap doubled
    return f"  {INSTRUCTION}  \n\n\n\n\n----------\n{body}\n\n\n{INSTRUCTION}\n"


def detail_counts(text: str, lang: str) -> Counter:
    lexes = D.active_lexicons(lang, text)
    return Counter((d.category, d.value) for d in D.extract_details(text, lexicons=lexes))


def write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--dataset", default="FLORES-200")
    p.add_argument("--modes", nargs="+", default=["safe", "balanced", "aggressive"],
                   choices=["safe", "balanced", "aggressive"])
    p.add_argument("--tokenizers", nargs="+", default=["cl100k_base", "o200k_base"])
    p.add_argument("--limit", type=int, default=0, help="first N aligned groups only (0 = all)")
    p.add_argument("--out-root", type=Path, default=_paths.RESEARCH / "reports")
    a = p.parse_args()

    entry = check_register_entry(load_register(_paths.RESEARCH / "configs" / "datasets.yaml"),
                                 a.dataset, "evaluation")
    raw = a.input.read_bytes()
    samples = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    if a.limit:
        groups = sorted({s["aligned_group_id"] for s in samples})[: a.limit]
        samples = [s for s in samples if s["aligned_group_id"] in set(groups)]
    toks = [get_tokenizer(n) for n in a.tokenizers]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out_root / f"opt_eval_{run_id}"
    out.mkdir(parents=True)

    def run(text: str, lang: str, mode: str):
        return optimizer.optimize(OptimizeRequest(text=text, language=lang, mode=mode,
                                                  tokenizers=a.tokenizers), toks)

    rows: list[dict] = []
    t0 = time.time()
    for s in samples:
        lang, text = s["language_code"], s["text"]
        for mode in a.modes:
            inputs = {"natural": text, "prompt_clean": prompt_clean(text), "prompt_noisy": prompt_noisy(text)}
            results = {c: run(t, lang, mode) for c, t in inputs.items()}
            for cond, res in results.items():
                kept = detail_counts(res.optimized, lang) == detail_counts(inputs[cond], lang)
                clean_after = {t.tokenizer.name: t.after for t in results["prompt_clean"].token_counts}
                for tc in res.token_counts:
                    noisy = cond == "prompt_noisy"
                    noise = tc.before - clean_after[tc.tokenizer.name] if noisy else ""
                    removed = tc.before - tc.after if noisy else ""
                    recovered = int(tc.after <= clean_after[tc.tokenizer.name]) if noisy else ""
                    rows.append({
                        "sample_id": s["sample_id"], "aligned_group_id": s["aligned_group_id"],
                        "language_code": lang, "script": s["script"], "mode": mode, "condition": cond,
                        "tokenizer": tc.tokenizer.name, "tokenizer_version": tc.tokenizer.version,
                        "tokens_before": tc.before, "tokens_after": tc.after, "tokens_saved": tc.saved,
                        "saved_pct": tc.saved_pct, "chars_before": res.original_chars,
                        "chars_after": res.optimized_chars, "changed": int(res.changed),
                        "accepted_edits": len(res.accepted), "suggestions": len(res.suggestions),
                        "meaning_status": res.meaning_check.status, "details_kept": int(kept),
                        "noise_tokens": noise, "noise_removed": removed, "recovered": recovered,
                        "rules": "|".join(sorted({e.rule for e in res.accepted})),
                    })
    elapsed = time.time() - t0

    agg: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        agg[(r["language_code"], r["mode"], r["condition"], r["tokenizer"])].append(r)
    summary = []
    for (lang, mode, cond, tok), rs in sorted(agg.items(), key=lambda kv: (
            LANG_ORDER.index(kv[0][0]) if kv[0][0] in LANG_ORDER else 9, kv[0][1:])):
        before = sum(r["tokens_before"] for r in rs)
        after = sum(r["tokens_after"] for r in rs)
        pcts = [r["saved_pct"] for r in rs]
        rec = [r["recovered"] for r in rs if r["recovered"] != ""]
        noise = sum(r["noise_tokens"] for r in rs if r["noise_tokens"] != "")
        removed = sum(r["noise_removed"] for r in rs if r["noise_removed"] != "")
        summary.append({
            "language_code": lang, "mode": mode, "condition": cond, "tokenizer": tok, "n": len(rs),
            "tokens_before": before, "tokens_after": after, "tokens_saved": before - after,
            "reduction_pct_total": round(100 * (before - after) / before, 3) if before else 0.0,
            "reduction_pct_mean": round(statistics.mean(pcts), 3),
            "reduction_pct_median": round(statistics.median(pcts), 3),
            "chars_before": sum(r["chars_before"] for r in rs), "chars_after": sum(r["chars_after"] for r in rs),
            "changed_n": sum(r["changed"] for r in rs), "token_increase_n": sum(r["tokens_saved"] < 0 for r in rs),
            "preserved_n": sum(r["meaning_status"] == "preserved" for r in rs),
            "at_risk_n": sum(r["meaning_status"] == "at_risk" for r in rs),
            "changed_meaning_n": sum(r["meaning_status"] == "changed" for r in rs),
            "details_kept_n": sum(r["details_kept"] for r in rs),
            "suggestions_total": sum(r["suggestions"] for r in rs),
            "noise_tokens": noise if rec else "", "noise_removed": removed if rec else "",
            "noise_removed_pct": round(100 * removed / noise, 2) if rec and noise else "",
            "recovered_n": sum(rec) if rec else "",
        })

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=_paths.REPO).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                    cwd=_paths.REPO).stdout.strip())
    except OSError:
        commit, dirty = "unknown", True
    meta = {
        "run_id": run_id, "kind": "optimizer_evaluation", "optimizer_method": R.METHOD_ID,
        "meaning_method": D.METHOD_ID, "modes": a.modes,
        "tokenizers": [{"name": t.info.name, "library": t.info.library, "version": t.info.version} for t in toks],
        "dataset": {"name": a.dataset, "version": entry.get("version"), "license": entry.get("license"),
                    "approved_for": entry.get("approved_for"), "input_sha256": hashlib.sha256(raw).hexdigest(),
                    "samples": len(samples)},
        "conditions": {"natural": "sentence as stored", "prompt_clean": prompt_clean("{text}"),
                       "prompt_noisy": prompt_noisy("{text}").replace("​", "<U+200B>")},
        "code_commit": commit, "working_tree_dirty": dirty, "elapsed_seconds": round(elapsed, 1),
        "note": "Tokenizer counts, not provider billing. Meaning status is the rule-based rules_v3 "
                "check (critical details only), not semantic equivalence.",
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out / "rows.csv.gz", rows)   # ~90k rows: gzip keeps the committed file small
    write_csv(out / "summary.csv", summary)
    print(f"run {run_id}: {len(samples)} samples x {len(a.modes)} modes in {elapsed:.0f}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
