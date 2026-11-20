"""Baseline tokenization benchmark (BRD §10).

Counts every sample with every tokenizer, then reports per language/script:
fertility (tokens per word) and the relative tokenization ratio against English,
computed only over aligned groups that have an English member. Ratios are
tokenization ratios, not cost multipliers.
"""
from __future__ import annotations

import hashlib
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core import text as T
from app.core.metrics import fertility, summarize
from app.tokenizers import TokenizerAdapter


@dataclass
class Row:
    sample_id: str
    aligned_group_id: str | None
    language_code: str
    script: str
    variant_type: str
    domain: str
    tokenizer: str
    tokenizer_version: str
    token_count: int
    word_count: int
    char_count: int
    fertility: float | None


def count_rows(samples: list[dict], tokenizers: list[TokenizerAdapter]) -> list[Row]:
    rows = []
    for tok in tokenizers:
        for s in samples:
            norm = s.get("text_normalized") or T.normalize(s["text"])
            t, w = tok.count(norm), T.word_count(norm)
            rows.append(Row(
                s["sample_id"], s.get("aligned_group_id"), s["language_code"], s["script"],
                s["variant_type"], s.get("domain", "general"), tok.info.name, tok.info.version,
                t, w, len(norm), fertility(t, w),
            ))
    return rows


def summarize_rows(rows: list[Row], reference_language: str = "en") -> list[dict]:
    """One summary line per tokenizer × language × script."""
    out = []
    for tok in sorted({r.tokenizer for r in rows}):
        trows = [r for r in rows if r.tokenizer == tok]
        ref_groups = {r.aligned_group_id for r in trows
                      if r.language_code == reference_language and r.aligned_group_id}
        ref = [r for r in trows if r.language_code == reference_language and r.aligned_group_id]

        buckets: dict[tuple[str, str], list[Row]] = defaultdict(list)
        for r in trows:
            buckets[(r.language_code, r.script)].append(r)

        for (lang, script), rs in sorted(buckets.items()):
            s = summarize([r.fertility for r in rs if r.fertility is not None])
            paired = [r for r in rs if r.aligned_group_id in ref_groups]
            groups = {r.aligned_group_id for r in paired}
            ref_sub = [r for r in ref if r.aligned_group_id in groups]
            ratio = None
            if paired and ref_sub:
                lang_fert = sum(r.token_count for r in paired) / max(1, sum(r.word_count for r in paired))
                ref_fert = sum(r.token_count for r in ref_sub) / max(1, sum(r.word_count for r in ref_sub))
                ratio = lang_fert / ref_fert if ref_fert else None
            out.append({
                "tokenizer": tok, "tokenizer_version": rs[0].tokenizer_version,
                "language_code": lang, "script": script,
                "n_samples": len(rs),
                "total_tokens": sum(r.token_count for r in rs),
                "total_words": sum(r.word_count for r in rs),
                "fertility_mean": s.mean, "fertility_median": s.median, "fertility_stdev": s.stdev,
                "fertility_ci95_low": s.ci95_low, "fertility_ci95_high": s.ci95_high,
                "paired_groups_with_reference": len(groups),
                "ratio_vs_reference": ratio,
            })
    return out


def git_commit(repo: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def run_metadata(*, input_file: Path, samples: list[dict], tokenizers: list[TokenizerAdapter],
                 split: str | None, reference_language: str, repo: Path) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "run_at": now.isoformat(),
        "code_version": git_commit(repo),
        "input_file": str(input_file),
        "input_sha256": sha256_file(input_file),
        "datasets": sorted({f"{s.get('dataset')}@{s.get('dataset_version')}" for s in samples}),
        "split": split,
        "n_samples": len(samples),
        "tokenizers": [asdict(t.info) for t in tokenizers],
        "normalization": T.NORMALIZATION_ID,
        "word_count_method": T.WORD_COUNT_METHOD,
        "reference_language": reference_language,
        "note": "Ratios are tokenization ratios under each tokenizer, not cost multipliers.",
    }
