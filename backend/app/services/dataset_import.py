"""Pilot dataset validation (BRD §9.2–9.3).

Checks every sample against the schema, the licence register, script consistency,
duplicates and split leakage. Produces normalized samples plus a report. It never
fixes data silently: problems are listed and the import fails.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core import text as T

TO_VERIFY = "TO_VERIFY"
Use = Literal["evaluation", "tokenizer_training", "redistribution"]


class Sample(BaseModel):
    """One row, BRD §9.3."""
    sample_id: str = Field(min_length=1, max_length=200)
    language_code: Literal["kn", "hi", "ta", "te", "en"]
    script: Literal["Knda", "Deva", "Taml", "Telu", "Latn", "mixed"]
    text: str = Field(min_length=1)
    aligned_group_id: str | None = None
    domain: str = "general"
    variant_type: Literal["original", "translation", "transliteration", "code_mixed", "paraphrase"]
    source_name: str
    source_url: str | None = None
    license: str | None = None
    split: Literal["train", "validation", "test"]
    human_verified: bool = False
    quality_notes: str | None = None

    @field_validator("aligned_group_id", "source_url", "license", "quality_notes", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        return None if v == "" else v

    @field_validator("human_verified", mode="before")
    @classmethod
    def _bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"true", "1", "yes", "y"}
        return v


@dataclass
class ImportReport:
    dataset: str
    version: str
    rows_read: int = 0
    rows_valid: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {**self.__dict__, "ok": self.ok}


# ---------- licence register ----------
class RegisterError(ValueError):
    pass


def load_register(path: Path) -> list[dict]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("datasets", [])


def check_register_entry(register: list[dict], name: str, use: Use) -> dict:
    """Return the dataset's entry, or raise RegisterError explaining what is missing."""
    entry = next((d for d in register if d.get("name") == name), None)
    if entry is None:
        raise RegisterError(f"dataset '{name}' is not in the licence register")
    problems = []
    for key in ("version", "license", "source_url", "citation"):
        val = entry.get(key)
        if not val or str(val).strip() == TO_VERIFY:
            problems.append(f"{key} not verified")
    if not entry.get("accessed_at"):
        problems.append("accessed_at missing")
    if use not in (entry.get("approved_for") or []):
        problems.append(f"not approved for '{use}'")
    if problems:
        raise RegisterError(f"dataset '{name}': " + "; ".join(problems))
    return entry


# ---------- reading ----------
def read_rows(path: Path) -> Iterable[dict]:
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    elif path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
    else:
        raise ValueError(f"unsupported file type: {path.suffix} (use .jsonl or .csv)")


# ---------- validation ----------
def validate(rows: Iterable[dict], dataset: str, version: str) -> tuple[list[dict], ImportReport]:
    rep = ImportReport(dataset=dataset, version=version)
    valid: list[Sample] = []
    seen_ids: set[str] = set()

    for i, row in enumerate(rows, start=1):
        rep.rows_read += 1
        try:
            s = Sample(**row)
        except ValidationError as exc:
            e = exc.errors()[0]
            rep.errors.append(f"row {i}: {'.'.join(map(str, e['loc']))}: {e['msg']}")
            continue
        if s.sample_id in seen_ids:
            rep.errors.append(f"row {i}: duplicate sample_id {s.sample_id}")
            continue
        seen_ids.add(s.sample_id)
        if not T.normalize(s.text):
            rep.errors.append(f"row {i}: text is blank after normalization")
            continue
        detected = T.detect_script(T.normalize(s.text))
        if detected and detected != s.script:
            rep.warnings.append(f"{s.sample_id}: declared script {s.script}, detected {detected}")
        valid.append(s)

    # Duplicate text (same language + normalized text): leakage if across splits.
    by_text: dict[tuple[str, str], list[Sample]] = defaultdict(list)
    for s in valid:
        by_text[(s.language_code, T.normalize(s.text))].append(s)
    drop: set[str] = set()
    for dupes in by_text.values():
        if len(dupes) < 2:
            continue
        splits = {d.split for d in dupes}
        ids = ", ".join(d.sample_id for d in dupes)
        if len(splits) > 1:
            rep.errors.append(f"split leakage: identical text in {sorted(splits)}: {ids}")
        else:
            rep.warnings.append(f"duplicate text kept once ({dupes[0].sample_id}); dropped: "
                                + ", ".join(d.sample_id for d in dupes[1:]))
            drop.update(d.sample_id for d in dupes[1:])

    # An aligned group must stay inside one split.
    group_splits: dict[str, set[str]] = defaultdict(set)
    group_langs: dict[str, set[str]] = defaultdict(set)
    for s in valid:
        if s.aligned_group_id:
            group_splits[s.aligned_group_id].add(s.split)
            group_langs[s.aligned_group_id].add(s.language_code)
    for g, splits in group_splits.items():
        if len(splits) > 1:
            rep.errors.append(f"split leakage: aligned group {g} spans {sorted(splits)}")
    no_en = sum(1 for langs in group_langs.values() if "en" not in langs)
    if no_en:
        rep.warnings.append(f"{no_en} aligned group(s) have no English reference")

    out = []
    for s in valid:
        if s.sample_id in drop:
            continue
        d = s.model_dump()
        d.update(dataset=dataset, dataset_version=version,
                 text_normalized=T.normalize(s.text), normalization=T.NORMALIZATION_ID)
        out.append(d)

    rep.rows_valid = len(out)
    counts: dict[str, int] = defaultdict(int)
    for d in out:
        counts[f"{d['language_code']}/{d['script']}/{d['split']}"] += 1
    rep.counts = dict(sorted(counts.items()))
    return out, rep


# ---------- FLORES conversion ----------
FLORES_SPLIT_MAP = {"dev": "validation", "devtest": "test"}


def flores_rows(flores_dir: Path, flores_split: str, codes: dict[str, str],
                source_url: str, license_: str) -> list[dict]:
    """Turn line-aligned FLORES files ({code}.{split}) into sample rows.
    Line N in every language file is the same sentence, so it becomes one aligned group.
    Verify the file layout against the release you downloaded."""
    split = FLORES_SPLIT_MAP[flores_split]
    rows = []
    lengths = {}
    for lang, code in codes.items():
        path = flores_dir / flores_split / f"{code}.{flores_split}"
        lines = path.read_text(encoding="utf-8").splitlines()
        lengths[lang] = len(lines)
        script = code.split("_", 1)[1]
        for n, line in enumerate(lines, start=1):
            rows.append({
                "sample_id": f"flores-{flores_split}-{n:04d}-{lang}",
                "language_code": lang, "script": script, "text": line,
                "aligned_group_id": f"flores-{flores_split}-{n:04d}",
                "variant_type": "original" if lang == "en" else "translation",
                "source_name": "FLORES-200", "source_url": source_url, "license": license_,
                "split": split, "human_verified": False, "domain": "general",
            })
    if len(set(lengths.values())) > 1:
        raise ValueError(f"FLORES files are not line-aligned: {lengths}")
    return rows
