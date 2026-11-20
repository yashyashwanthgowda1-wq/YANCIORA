"""Baseline tokenization benchmark over validated samples.

Usage:
  python research/scripts/run_benchmark.py \
      --input research/data/processed/FLORES-200/<version>/samples.jsonl \
      --tokenizers cl100k_base o200k_base --split test [--store-db]

Writes research/reports/<run_id>/: run.json (metadata), rows.csv (every count),
summary.csv (per tokenizer x language x script) and, if matplotlib is installed,
ratio_chart.png. Every number is tied to its tokenizer version and run ID.

--store-db also stores the run (metadata, every count, summaries) in PostgreSQL
(DATABASE_URL), after the files are written. The dataset must have been loaded with
import_pilot.py --load-db. Exit code 3 if storing fails (the report files remain).
"""
import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

import _paths  # noqa: F401
from app.services.benchmark import count_rows, run_metadata, summarize_rows
from app.tokenizers import TokenizerUnavailable, get_tokenizer

LANG_ORDER = ["en", "hi", "kn", "ta", "te"]


def write_csv(path: Path, dicts: list[dict]) -> None:
    if not dicts:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dicts[0].keys()))
        w.writeheader()
        w.writerows(dicts)


def chart(summary: list[dict], out: Path, run_id: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    data = [r for r in summary if r["ratio_vs_reference"] is not None]
    if not data:
        return False
    labels = sorted({f"{r['language_code']}/{r['script']}" for r in data},
                    key=lambda s: (LANG_ORDER.index(s.split('/')[0]) if s.split('/')[0] in LANG_ORDER else 99, s))
    toks = sorted({r["tokenizer"] for r in data})
    width = 0.8 / len(toks)
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 4))
    for i, tok in enumerate(toks):
        vals = {f"{r['language_code']}/{r['script']}": r["ratio_vs_reference"] for r in data if r["tokenizer"] == tok}
        xs = [j + i * width for j in range(len(labels))]
        ax.bar(xs, [vals.get(l, 0) for l in labels], width, label=tok)
    ax.axhline(1.0, color="grey", linewidth=0.8)
    ax.set_xticks([j + width * (len(toks) - 1) / 2 for j in range(len(labels))], labels)
    ax.set_ylabel("Fertility ratio vs English (paired groups)")
    ax.set_title(f"Tokenization ratio vs English — run {run_id}\n(not a cost multiplier)", fontsize=10)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--tokenizers", nargs="+", default=["cl100k_base", "o200k_base"])
    p.add_argument("--split", choices=["train", "validation", "test"], default="test")
    p.add_argument("--reference", default="en")
    p.add_argument("--out-root", type=Path, default=_paths.RESEARCH / "reports")
    p.add_argument("--store-db", action="store_true", help="also store the run in PostgreSQL")
    a = p.parse_args()

    samples = [json.loads(l) for l in a.input.read_text(encoding="utf-8").splitlines() if l.strip()]
    samples = [s for s in samples if s["split"] == a.split]
    if not samples:
        print(f"no samples in split '{a.split}'", file=sys.stderr)
        return 1

    try:
        toks = [get_tokenizer(n) for n in a.tokenizers]
        for t in toks:
            t.encode("check")
    except TokenizerUnavailable as exc:
        print(f"tokenizer unavailable: {exc}", file=sys.stderr)
        return 2

    meta = run_metadata(input_file=a.input, samples=samples, tokenizers=toks,
                        split=a.split, reference_language=a.reference, repo=_paths.REPO)
    rows = count_rows(samples, toks)
    summary = summarize_rows(rows, a.reference)

    out = a.out_root / meta["run_id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out / "rows.csv", [asdict(r) for r in rows])
    write_csv(out / "summary.csv", summary)
    made_chart = chart(summary, out / "ratio_chart.png", meta["run_id"])

    print(f"run {meta['run_id']}: {len(samples)} samples x {len(toks)} tokenizers -> {out}")
    for r in summary:
        ratio = f"{r['ratio_vs_reference']:.2f}" if r["ratio_vs_reference"] is not None else "n/a"
        fm = f"{r['fertility_mean']:.2f}" if r["fertility_mean"] is not None else "n/a"
        print(f"  {r['tokenizer']:<12} {r['language_code']}/{r['script']:<5} n={r['n_samples']:<5} "
              f"fertility={fm:<6} ratio_vs_{a.reference}={ratio}")
    if not made_chart:
        print("  (no chart: matplotlib missing or no paired groups)")
    if a.store_db:
        return store_db(meta, samples, rows, summary, toks)
    return 0


def store_db(meta, samples, rows, summary, toks) -> int:
    from app.core.config import get_settings
    from app.db.session import get_engine
    from app.services.benchmark_store import BenchmarkStoreError, store_run

    url = get_settings().database_url
    if not url:
        print("DB STORE FAILED: DATABASE_URL is not set (see .env.example)", file=sys.stderr)
        return 3
    try:
        res = store_run(get_engine(url), meta=meta, samples=samples, rows=rows,
                        summary=summary, tokenizers=toks)
    except BenchmarkStoreError as exc:
        print(f"DB STORE FAILED (rolled back): {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # never print the URL
        print(f"DB STORE FAILED (rolled back): {type(exc).__name__}", file=sys.stderr)
        return 3
    print(f"DB: stored run {res['run_id']} ({res['rows']} rows, {res['summaries']} summaries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
