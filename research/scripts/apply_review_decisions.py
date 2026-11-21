"""Merge a native speaker's review decisions into backend/app/linguistics/review/<lang>.yaml.

Usage:
  python research/scripts/apply_review_decisions.py --decisions kannada_review.json --reviewer "Name"
  python research/scripts/apply_review_decisions.py --decisions kannada_review.csv --language kn \
      --reviewer "Name" [--date 2026-11-25] [--dry-run]

Accepted inputs:
  * JSON exported by the Linguistic Review screen (schema redutax-review-decisions/v1);
  * the CSV from export_review_sheet.py with the capitalised columns filled in.

Rules: a reviewer name is required; only ids that exist are accepted; 'correct' needs at least one
corrected field; rows with an empty decision are skipped. The merged file is validated with the
same loader the backend uses, and nothing is written if any check fails. Each entry stays on one
line, and only its `review: {...}` part is replaced, so the rest of the file (comments, order) is
kept and the git diff shows exactly what the reviewer decided.
"""
import argparse
import csv
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

import _paths  # noqa: F401
from app.linguistics import review as RV

DECISION_WORDS = {"approve": "approved", "approved": "approved", "reject": "rejected", "rejected": "rejected",
                  "correct": "corrected", "corrected": "corrected"}
YES_NO = {"yes": "yes", "y": "yes", "no": "no", "n": "no", "": None}


class DecisionError(ValueError):
    pass


def _yn(v: str, where: str):
    key = (v or "").strip().lower()
    if key not in YES_NO:
        raise DecisionError(f"{where}: expected yes/no, got {v!r}")
    return YES_NO[key]


def read_decisions(path: Path, language: str | None) -> tuple[str, list[dict]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "redutax-review-decisions/v1":
            raise DecisionError("JSON schema must be redutax-review-decisions/v1")
        lang = data.get("language")
        if language and language != lang:
            raise DecisionError(f"file is for '{lang}', not '{language}'")
        return lang, list(data.get("decisions") or [])
    if not language:
        raise DecisionError("--language is required for CSV input")
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            word = (row.get("YOUR_DECISION") or "").strip().lower()
            if not word:
                continue
            if word not in DECISION_WORDS:
                raise DecisionError(f"row {i}: YOUR_DECISION must be approve, reject or correct")
            corr = {k: (row.get(c) or "").strip() for k, c in (("expression", "CORRECTED_EXPRESSION"),
                                                                ("proposed", "CORRECTED_PROPOSED"),
                                                                ("gloss", "CORRECTED_MEANING"))}
            out.append({"id": row["id"].strip(), "decision": DECISION_WORDS[word],
                        "notes": (row.get("NOTES") or "").strip(),
                        "correction": {k: v for k, v in corr.items() if v},
                        "preserves_meaning": _yn(row.get("PRESERVES_MEANING", ""), f"row {i}"),
                        "changes_register": _yn(row.get("CHANGES_TONE", ""), f"row {i}"),
                        "safe_for_auto": _yn(row.get("SAFE_FOR_AUTOMATIC_USE", ""), f"row {i}")})
    return language, out


def review_block(d: dict, reviewer: str, when: str) -> str:
    decision = DECISION_WORDS.get(str(d.get("decision", "")).lower())
    if decision is None:
        raise DecisionError(f"{d.get('id')}: decision must be approved, rejected or corrected")
    parts = [f"decision: {decision}", f"reviewer: {json.dumps(reviewer, ensure_ascii=False)}",
             f"reviewed_at: {json.dumps(when)}"]
    if d.get("notes"):
        parts.append(f"notes: {json.dumps(str(d['notes']), ensure_ascii=False)}")
    for k in ("preserves_meaning", "changes_register"):
        v = d.get(k)
        if v is not None:
            parts.append(f"{k}: {json.dumps(_yn(str(v), d.get('id', '?')) if isinstance(v, str) else v)}")
    sfa = d.get("safe_for_auto")
    if sfa is not None:
        sfa_bool = sfa if isinstance(sfa, bool) else (_yn(str(sfa), d.get("id", "?")) == "yes")
        parts.append(f"safe_for_auto: {'true' if sfa_bool else 'false'}")
    if decision == "corrected":
        corr = {k: v for k, v in (d.get("correction") or {}).items() if v not in (None, "")}
        if not corr:
            raise DecisionError(f"{d.get('id')}: 'correct' needs a corrected expression, proposal or meaning")
        parts.append("correction: {" + ", ".join(f"{k}: {json.dumps(str(v), ensure_ascii=False)}"
                                                for k, v in corr.items()) + "}")
    return "review: {" + ", ".join(parts) + "}"


def merge(text: str, decisions: list[dict], reviewer: str, when: str) -> tuple[str, int]:
    applied = 0
    for d in decisions:
        eid = str(d.get("id", "")).strip()
        line_rx = re.compile(rf"^(\s*- \{{id: {re.escape(eid)},.*?)review: \{{[^{{}}\n]*(?:\{{[^{{}}\n]*\}}[^{{}}\n]*)*\}}\}}[ \t]*(?=\r?$)", re.M)
        m = line_rx.search(text)
        if not m:
            raise DecisionError(f"unknown id or unexpected line format: {eid!r}")
        new_line = m.group(1) + review_block(d, reviewer, when) + "}"
        text = text[:m.start()] + new_line + text[m.end():]
        applied += 1
    return text, applied


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--reviewer", required=True, help="the native speaker who made the decisions")
    p.add_argument("--language", choices=RV.LANGUAGES)
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--review-dir", type=Path, default=RV.REVIEW_DIR)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if not a.reviewer.strip():
        sys.exit("a reviewer name is required")
    try:
        lang, decisions = read_decisions(a.decisions, a.language)
        target = a.review_dir / f"{lang}.yaml"
        with target.open(encoding="utf-8", newline="") as fh:
            original_text = fh.read()
        merged, n = merge(original_text, decisions, a.reviewer.strip(), a.date)
        with tempfile.TemporaryDirectory() as tmp:            # validate before writing anything
            check = Path(tmp) / f"{lang}.yaml"
            check.write_text(merged, encoding="utf-8")
            RV.load_file(check)
    except (DecisionError, RV.ReviewDataError, OSError, json.JSONDecodeError) as exc:
        sys.exit(f"not applied: {exc}")
    if a.dry_run:
        print(f"dry run: {n} decisions for {lang} are valid; nothing written")
        return 0
    with target.open("w", encoding="utf-8", newline="") as fh:   # keep the file's own line endings
        fh.write(merged)
    print(f"applied {n} decisions to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
