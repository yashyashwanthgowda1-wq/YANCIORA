"""Convert a downloaded FLORES-200 release into REDUTAX sample rows (JSONL).

Usage:
  python research/scripts/flores_to_jsonl.py --flores-dir PATH/flores200_dataset --split devtest \
      --out research/data/raw/flores200_devtest.jsonl

Requires the FLORES-200 entry in research/configs/datasets.yaml to be fully verified and
approved for 'evaluation'. The script does not download anything.
"""
import argparse
import json
import sys
from pathlib import Path

import _paths  # noqa: F401
from app.services.dataset_import import RegisterError, check_register_entry, flores_rows, load_register


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--flores-dir", type=Path, required=True)
    p.add_argument("--split", choices=["dev", "devtest"], default="devtest")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--register", type=Path, default=_paths.RESEARCH / "configs" / "datasets.yaml")
    a = p.parse_args()

    try:
        entry = check_register_entry(load_register(a.register), "FLORES-200", "evaluation")
    except RegisterError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    rows = flores_rows(a.flores_dir, a.split, entry["language_codes_in_source"],
                       entry["source_url"], entry["license"])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
