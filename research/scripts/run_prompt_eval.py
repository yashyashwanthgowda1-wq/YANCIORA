"""Everyday-prompt token-minimization evaluation (separate from the FLORES-200 evaluation).

Usage:
  python research/scripts/run_prompt_eval.py \
      [--input research/datasets/team_prompts/prompts_v1.jsonl] [--modes safe balanced aggressive]

For every prompt, mode and tokenizer (same encoding before and after) it records characters,
tokens, rules applied, meaning-check status, whether every critical detail survived, suggestions
(approval required) and edits rejected by the meaning check. Romanized and code-mixed prompts are
run twice: with the language given, and with language 'auto' (what happens when users do not
set it). The input is synthetic, AI-drafted data (see its README): results describe the optimizer
on that data, not real-world savings, and token counts are not provider billing.

Writes research/reports/prompt_eval_<run_id>/: run.json, rows.csv, summary.csv, examples.json.
"""
import argparse
import csv
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
from app.linguistics import review as RV
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer
from app.tokenizers import get_tokenizer

TOKENIZERS = ["cl100k_base", "o200k_base"]


def details(text: str, lang: str | None) -> Counter:
    lexes = D.active_lexicons(lang, text)
    return Counter((d.category, d.value) for d in D.extract_details(text, lexicons=lexes, markers=D.active_markers(lang, text)))


def pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    if not s:
        return 0.0
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 3)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path, default=_paths.RESEARCH / "datasets" / "team_prompts" / "prompts_v1.jsonl")
    p.add_argument("--modes", nargs="+", default=["safe", "balanced", "aggressive"])
    p.add_argument("--out-root", type=Path, default=_paths.RESEARCH / "reports")
    a = p.parse_args()

    raw = a.input.read_bytes()
    prompts = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    toks = [get_tokenizer(n) for n in TOKENIZERS]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out_root / f"prompt_eval_{run_id}"
    out.mkdir(parents=True)

    jobs = []
    for pr in prompts:
        jobs.append((pr, pr["variant"], pr["language"]))
        if pr["variant"].endswith("_roman") or pr["variant"] == "code_mixed":
            jobs.append((pr, pr["variant"] + "_auto", "auto"))

    rows, examples = [], []
    t0 = time.time()
    for pr, variant, lang in jobs:
        for mode in a.modes:
            res = optimizer.optimize(OptimizeRequest(text=pr["text"], language=lang, mode=mode,
                                                     tokenizers=TOKENIZERS), toks)
            dl = None if lang == "auto" else lang
            kept = details(res.optimized, dl) == details(pr["text"], dl)
            meaning_rejected = sum(1 for x in res.rejected if x.stage == "meaning")
            for tc in res.token_counts:
                rows.append({
                    "prompt_id": pr["id"], "variant": variant, "language": pr["language"], "language_param": lang,
                    "script": pr["script"], "category": pr["category"], "provenance": pr["provenance"],
                    "review_status": pr["review_status"], "mode": mode, "tokenizer": tc.tokenizer.name,
                    "tokenizer_version": tc.tokenizer.version, "chars_before": res.original_chars,
                    "chars_after": res.optimized_chars, "tokens_before": tc.before, "tokens_after": tc.after,
                    "tokens_saved": tc.saved, "saved_pct": tc.saved_pct, "changed": int(res.changed),
                    "rules_applied": "|".join(sorted({x.rule for x in res.accepted})),
                    "suggestions": len(res.suggestions), "suggestion_kinds": "|".join(sorted({s.kind for s in res.suggestions})),
                    "meaning_rejected_edits": meaning_rejected, "meaning_status": res.meaning_check.status,
                    "details_kept": int(kept),
                })
            if mode == "balanced" and (res.changed or res.suggestions):
                examples.append({"prompt_id": pr["id"], "variant": variant, "mode": mode, "original": res.original,
                                 "optimized": res.optimized, "meaning_status": res.meaning_check.status,
                                 "token_counts": {t.tokenizer.name: [t.before, t.after] for t in res.token_counts},
                                 "accepted": [{"rule": x.rule, "risk": x.risk, "before": x.before, "after": x.after} for x in res.accepted],
                                 "suggestions": [{"kind": s.kind, "risk": s.risk, "before": s.before, "after": s.after,
                                                  "status": s.meaning_status, "source": s.source} for s in res.suggestions],
                                 "rejected_by_meaning": [{"rule": x.rule, "before": x.before, "after": x.after, "reason": x.reason}
                                                         for x in res.rejected if x.stage == "meaning"]})
    elapsed = time.time() - t0

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["variant"], r["mode"], r["tokenizer"])].append(r)
    summary = []
    for (variant, mode, tok), rs in sorted(groups.items()):
        n = len(rs)
        pcts = [r["saved_pct"] for r in rs]
        success = [r for r in rs if r["changed"] and r["tokens_saved"] > 0 and r["meaning_status"] != "changed" and r["details_kept"]]
        summary.append({
            "variant": variant, "mode": mode, "tokenizer": tok, "n": n,
            "no_change_rate": round(100 * sum(1 for r in rs if not r["changed"]) / n, 1),
            "success_rate": round(100 * len(success) / n, 1),
            "reduction_mean_pct": round(statistics.mean(pcts), 3), "reduction_median_pct": round(statistics.median(pcts), 3),
            "reduction_p75_pct": pct(pcts, 0.75), "reduction_max_pct": round(max(pcts), 3),
            "tokens_before": sum(r["tokens_before"] for r in rs), "tokens_after": sum(r["tokens_after"] for r in rs),
            "chars_before": sum(r["chars_before"] for r in rs), "chars_after": sum(r["chars_after"] for r in rs),
            "token_increase_rate": round(100 * sum(1 for r in rs if r["tokens_saved"] < 0) / n, 1),
            "meaning_rejection_rate": round(100 * sum(1 for r in rs if r["meaning_rejected_edits"]) / n, 1),
            "approval_required_rate": round(100 * sum(1 for r in rs if r["suggestions"]) / n, 1),
            "status_preserved": sum(1 for r in rs if r["meaning_status"] == "preserved"),
            "status_at_risk": sum(1 for r in rs if r["meaning_status"] == "at_risk"),
            "status_changed": sum(1 for r in rs if r["meaning_status"] == "changed"),
            "details_kept_rate": round(100 * sum(r["details_kept"] for r in rs) / n, 1),
        })

    def write(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=_paths.REPO).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=_paths.REPO).stdout.strip())
    except OSError:
        commit, dirty = "unknown", True
    rsum = RV.summary()
    meta = {"run_id": run_id, "kind": "everyday_prompt_evaluation", "optimizer_method": R.METHOD_ID,
            "meaning_method": D.METHOD_ID, "modes": a.modes,
            "tokenizers": [{"name": t.info.name, "library": t.info.library, "version": t.info.version} for t in toks],
            "input": {"path": str(a.input.relative_to(_paths.REPO)) if a.input.is_relative_to(_paths.REPO) else str(a.input),
                      "sha256": hashlib.sha256(raw).hexdigest(), "prompts": len(prompts),
                      "provenance": sorted({p["provenance"] for p in prompts}),
                      "review_status": sorted({p["review_status"] for p in prompts})},
            "review_data": {lang: {"total": v["total"], **v["decisions"], "auto_rules": v["auto_rules"]} for lang, v in rsum.items()},
            "code_commit": commit, "working_tree_dirty": dirty, "elapsed_seconds": round(elapsed, 1),
            "note": "Synthetic AI-drafted prompts; tokenizer counts, not provider billing; rule-based meaning check."}
    (out / "run.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write(out / "rows.csv", rows)
    write(out / "summary.csv", summary)
    (out / "examples.json").write_text(json.dumps(examples, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"run {run_id}: {len(jobs)} prompt runs x {len(a.modes)} modes in {elapsed:.0f}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
