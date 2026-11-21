"""Export a language's review entries as a spreadsheet (CSV, UTF-8 with BOM so Excel shows the
script correctly) for reviewers who prefer Excel / Google Sheets.

Usage:
  python research/scripts/export_review_sheet.py --language kn --out kannada_review.csv

Reviewers fill only the columns in CAPITALS (YOUR_DECISION: approve / reject / correct, plus the
corrected text, yes/no answers and notes) and send the file back. The team merges it with
apply_review_decisions.py. See docs/LINGUISTIC_REVIEW_GUIDE.md.
"""
import argparse
import csv
from pathlib import Path

import _paths  # noqa: F401
from app.linguistics import review as RV

COLUMNS = ["id", "category", "script", "expression", "english_meaning", "example_original", "proposed_shorter",
           "drafter_preserves_meaning", "drafter_changes_tone", "drafter_safe_for_automatic_use",
           "current_decision", "YOUR_DECISION", "CORRECTED_EXPRESSION", "CORRECTED_PROPOSED", "CORRECTED_MEANING",
           "PRESERVES_MEANING", "CHANGES_TONE", "SAFE_FOR_AUTOMATIC_USE", "NOTES"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--language", required=True, choices=RV.LANGUAGES)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    entries = RV.load_all()[a.language]
    with a.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for e in entries:
            w.writerow([e.id, e.category, e.script, e.expression, e.gloss, e.original or "", e.proposed or "",
                        e.preserves_meaning if e.is_rewrite else "", e.changes_register if e.is_rewrite else "",
                        ("yes" if e.safe_for_auto else "no") if e.is_rewrite else "", e.decision,
                        "", "", "", "", "", "", "", ""])
    print(f"wrote {len(entries)} entries to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
