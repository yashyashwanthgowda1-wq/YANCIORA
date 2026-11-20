"""Validate a pilot dataset file and write normalized samples + an import report.

Usage:
  python research/scripts/import_pilot.py --input research/data/raw/flores200_devtest.jsonl \
      --dataset FLORES-200 [--use evaluation] [--load-db]

Input: .jsonl or .csv with the BRD §9.3 fields (see research/README.md).
Output: research/data/processed/<dataset>/<version>/samples.jsonl and import_report.json.
Exit code 1 if any error is found (nothing is written in that case except the report).

--load-db also loads the validated samples into PostgreSQL (DATABASE_URL) in one
transaction. Re-running it is safe: unchanged rows are skipped, changed rows are refused.
Exit code 3 if the database load fails (the processed files are still written).
"""
import argparse
import json
import sys
from pathlib import Path

import _paths  # noqa: F401
from app.services.dataset_import import (
    RegisterError, check_register_entry, load_register, read_rows, validate,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--dataset", required=True, help="name as in datasets.yaml")
    p.add_argument("--use", default="evaluation", choices=["evaluation", "tokenizer_training"])
    p.add_argument("--register", type=Path, default=_paths.RESEARCH / "configs" / "datasets.yaml")
    p.add_argument("--out-root", type=Path, default=_paths.RESEARCH / "data" / "processed")
    p.add_argument("--load-db", action="store_true", help="also load samples into PostgreSQL")
    a = p.parse_args()

    try:
        entry = check_register_entry(load_register(a.register), a.dataset, a.use)
    except RegisterError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    version = str(entry["version"])
    samples, report = validate(read_rows(a.input), a.dataset, version)
    out_dir = a.out_root / a.dataset / version
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "import_report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    for w in report.warnings[:20]:
        print(f"warning: {w}")
    if not report.ok:
        for e in report.errors[:50]:
            print(f"error: {e}", file=sys.stderr)
        print(f"FAILED: {len(report.errors)} error(s). See {out_dir / 'import_report.json'}", file=sys.stderr)
        return 1

    with (out_dir / "samples.jsonl").open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"OK: {report.rows_valid}/{report.rows_read} rows -> {out_dir / 'samples.jsonl'}")
    for k, v in report.counts.items():
        print(f"  {k}: {v}")
    if a.load_db:
        return load_db(a)
    return 0


def load_db(a) -> int:
    from app.core.config import get_settings
    from app.db.session import get_engine
    from app.services.benchmark import git_commit, sha256_file
    from app.services.dataset_import import RegisterError
    from app.services.dataset_store import DatasetImportError, load_samples

    url = get_settings().database_url
    if not url:
        print("DB LOAD FAILED: DATABASE_URL is not set (see .env.example)", file=sys.stderr)
        return 3
    try:
        res = load_samples(get_engine(url), load_register(a.register), a.dataset,
                           read_rows(a.input), use=a.use, input_sha256=sha256_file(a.input),
                           code_version=git_commit(_paths.REPO))
    except (RegisterError, DatasetImportError) as exc:
        print(f"DB LOAD FAILED (rolled back): {exc}", file=sys.stderr)
        for e in getattr(exc, "errors", [])[:50]:
            print(f"error: {e}", file=sys.stderr)
        return 3
    except Exception as exc:  # connection problems etc.; never print the URL
        print(f"DB LOAD FAILED (rolled back): {type(exc).__name__}", file=sys.stderr)
        return 3
    print(f"DB: {res.dataset}@{res.version} inserted={res.rows_inserted} "
          f"unchanged={res.rows_unchanged} skipped={res.rows_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
