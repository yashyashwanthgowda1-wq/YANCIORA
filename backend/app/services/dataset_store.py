"""Load validated dataset samples into PostgreSQL and read aligned groups back.

The loader always re-runs the licence register gate and `dataset_import.validate`
itself, so it cannot be used to bypass either. One import = one transaction: any
error rolls everything back. Re-importing the same rows is a no-op (idempotent);
re-importing a sample_id with *different* content is an error (bump the version).

Framework-free: takes a SQLAlchemy Engine, never imports FastAPI.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from app.core import text as T
from app.services.dataset_import import Use, check_register_entry, validate

# Fields that define a sample's content. Changing any of them changes content_sha256.
CONTENT_FIELDS = (
    "sample_id", "language_code", "script", "text", "aligned_group_id", "domain",
    "variant_type", "source_name", "source_url", "license", "split",
    "human_verified", "quality_notes",
)
# Register fields that must not change for an already-imported dataset version.
FROZEN_REGISTER_FIELDS = ("license", "source_url", "citation", "accessed_at")


class DatasetImportError(ValueError):
    """Import refused. `errors` lists every problem found; nothing was written."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


@dataclass
class LoadResult:
    dataset: str
    version: str
    dataset_id: int
    rows_received: int = 0
    rows_inserted: int = 0
    rows_unchanged: int = 0
    rows_skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def content_hash(sample: dict) -> str:
    payload = {k: sample.get(k) for k in CONTENT_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


# ---------- write path ----------
def load_samples(
    engine: Engine,
    register: list[dict],
    dataset: str,
    rows: Iterable[dict],
    *,
    use: Use = "evaluation",
    input_sha256: str | None = None,
    code_version: str | None = None,
) -> LoadResult:
    """Gate → validate → insert, in one transaction. Raises RegisterError or DatasetImportError."""
    entry = check_register_entry(register, dataset, use)  # raises RegisterError when unverified
    version = str(entry["version"])
    samples, report = validate(rows, dataset, version)
    if not report.ok:
        raise DatasetImportError(
            f"validation failed with {len(report.errors)} error(s)", report.errors)
    if not samples:
        raise DatasetImportError("no valid samples to import")

    errors: list[str] = []
    allowed_langs = set(entry.get("languages") or [])
    reg_license = str(entry["license"])
    for s in samples:
        if allowed_langs and s["language_code"] not in allowed_langs:
            errors.append(f"{s['sample_id']}: language {s['language_code']} is not listed for "
                          f"{dataset} in the licence register")
        if s.get("license") is None:
            s["license"] = reg_license  # verified value from the register, not invented
        elif s["license"] != reg_license:
            errors.append(f"{s['sample_id']}: row licence '{s['license']}' differs from the "
                          f"register licence '{reg_license}'")
    if errors:
        raise DatasetImportError(f"{len(errors)} sample(s) conflict with the licence register", errors)

    with engine.begin() as conn:  # commit on success, rollback on any exception
        # Serialise concurrent imports of the same dataset version.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                     {"k": f"redutax-import:{dataset}@{version}"})
        dataset_id = _upsert_dataset(conn, entry, dataset, version)
        result = LoadResult(dataset, version, dataset_id, rows_received=report.rows_read,
                            warnings=list(report.warnings))
        to_insert = _plan_inserts(conn, dataset_id, samples, result)
        if to_insert:
            conn.execute(text("""
                INSERT INTO dataset_samples
                  (sample_id, dataset_id, language_code, script, text, text_normalized,
                   aligned_group_id, domain, variant_type, split, human_verified, quality_notes,
                   source_name, source_url, license, normalization, content_sha256)
                VALUES
                  (:sample_id, :dataset_id, :language_code, :script, :text, :text_normalized,
                   :aligned_group_id, :domain, :variant_type, :split, :human_verified, :quality_notes,
                   :source_name, :source_url, :license, :normalization, :content_sha256)
            """), to_insert)
        result.rows_inserted = len(to_insert)
        conn.execute(text("""
            INSERT INTO dataset_imports (dataset_id, input_sha256, rows_received, rows_inserted,
                rows_unchanged, rows_skipped, normalization, code_version)
            VALUES (:d, :sha, :rr, :ri, :ru, :rs, :norm, :cv)
        """), {"d": dataset_id, "sha": input_sha256, "rr": result.rows_received,
               "ri": result.rows_inserted, "ru": result.rows_unchanged, "rs": result.rows_skipped,
               "norm": T.NORMALIZATION_ID, "cv": code_version})
    return result


def _upsert_dataset(conn: Connection, entry: dict, name: str, version: str) -> int:
    existing = conn.execute(text("""
        SELECT id, license, source_url, citation, accessed_at FROM datasets
        WHERE name = :n AND version = :v
    """), {"n": name, "v": version}).mappings().first()
    values = {
        "license": str(entry["license"]),
        "source_url": str(entry["source_url"]),
        "citation": str(entry["citation"]),
        "accessed_at": _as_date(entry["accessed_at"]),
    }
    params = {
        "n": name, "v": version, **values,
        "license_url": entry.get("license_url"),
        "coverage": list(entry.get("languages") or []),
        "approved": list(entry.get("approved_for") or []),
        "notes": (entry.get("notes") or "").strip() or None,
    }
    if existing is None:
        return conn.execute(text("""
            INSERT INTO datasets (name, version, license, license_url, source_url, citation,
                                  language_coverage, accessed_at, approved_for, notes)
            VALUES (:n, :v, :license, :license_url, :source_url, :citation,
                    :coverage, :accessed_at, :approved, :notes)
            RETURNING id
        """), params).scalar_one()

    changed = [k for k in FROZEN_REGISTER_FIELDS if existing[k] != values[k]]
    if changed:
        raise DatasetImportError(
            f"licence register entry for {name}@{version} changed since it was first imported "
            f"({', '.join(changed)}). Record the change as a new dataset version instead.")
    # Approved uses, coverage and notes may be extended by the team after review.
    conn.execute(text("""
        UPDATE datasets SET license_url = :license_url, language_coverage = :coverage,
                            approved_for = :approved, notes = :notes
        WHERE id = :id
    """), {**params, "id": existing["id"]})
    return int(existing["id"])


def _plan_inserts(conn: Connection, dataset_id: int, samples: list[dict],
                  result: LoadResult) -> list[dict]:
    """Compare incoming samples with rows already stored for this dataset version."""
    stored = conn.execute(text("""
        SELECT sample_id, content_sha256, split, aligned_group_id, language_code, text_normalized
        FROM dataset_samples WHERE dataset_id = :d
    """), {"d": dataset_id}).mappings().all()
    by_id = {r["sample_id"]: r for r in stored}
    group_split = {r["aligned_group_id"]: r["split"] for r in stored if r["aligned_group_id"]}
    text_split: dict[tuple[str, str], tuple[str, str]] = {
        (r["language_code"], r["text_normalized"]): (r["split"], r["sample_id"]) for r in stored
    }

    errors: list[str] = []
    to_insert: list[dict] = []
    for s in samples:
        h = content_hash(s)
        old = by_id.get(s["sample_id"])
        if old is not None:
            if old["content_sha256"] == h:
                result.rows_unchanged += 1
            else:
                errors.append(f"{s['sample_id']}: already imported with different content; "
                              "imported samples are immutable, record a new dataset version")
            continue
        g = s.get("aligned_group_id")
        if g and g in group_split and group_split[g] != s["split"]:
            errors.append(f"split leakage: aligned group {g} is stored in '{group_split[g]}', "
                          f"{s['sample_id']} is '{s['split']}'")
            continue
        key = (s["language_code"], s["text_normalized"])
        if key in text_split:
            other_split, other_id = text_split[key]
            if other_split != s["split"]:
                errors.append(f"split leakage: {s['sample_id']} ({s['split']}) has the same text "
                              f"as stored {other_id} ({other_split})")
            else:
                result.rows_skipped += 1
                result.warnings.append(f"duplicate text: {s['sample_id']} skipped, same as stored "
                                       f"{other_id}")
            continue
        to_insert.append({
            **{k: s.get(k) for k in CONTENT_FIELDS},
            "dataset_id": dataset_id,
            "text_normalized": s["text_normalized"],
            "normalization": s.get("normalization") or T.NORMALIZATION_ID,
            "content_sha256": h,
        })
    if errors:
        raise DatasetImportError(f"{len(errors)} conflict(s) with stored samples", errors)
    return to_insert


# ---------- read path ----------
class NotFound(LookupError):
    pass


def find_dataset_ids(conn: Connection, name: str, version: str | None) -> list[int]:
    q = "SELECT id FROM datasets WHERE name = :n" + (" AND version = :v" if version else "")
    ids = [r[0] for r in conn.execute(text(q), {"n": name, "v": version})]
    if not ids:
        raise NotFound(f"dataset '{name}'" + (f" version '{version}'" if version else "")
                       + " has not been imported")
    return ids


def list_groups(
    engine: Engine,
    *,
    dataset: str | None = None,
    dataset_version: str | None = None,
    languages: list[str] | None = None,
    split: str | None = None,
    aligned_group_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Aligned groups (one per dataset + aligned_group_id), paginated by group.

    `languages`: keep groups that contain every listed language. Each returned group
    includes all its members, ordered by language code.
    """
    with engine.connect() as conn:
        where = ["s.aligned_group_id IS NOT NULL"]
        params: dict[str, Any] = {}
        if dataset:
            params["dids"] = find_dataset_ids(conn, dataset, dataset_version)
            where.append("s.dataset_id = ANY(:dids)")
        elif dataset_version:
            where.append("d.version = :dv")
            params["dv"] = dataset_version
        if split:
            where.append("s.split = :split")
            params["split"] = split
        if aligned_group_id:
            where.append("s.aligned_group_id = :gid")
            params["gid"] = aligned_group_id
        having = ""
        if languages:
            langs = sorted(set(languages))
            having = ("HAVING COUNT(DISTINCT s.language_code) "
                      "FILTER (WHERE s.language_code = ANY(:langs)) = :nlangs")
            params.update(langs=langs, nlangs=len(langs))

        groups_sql = f"""
            SELECT s.dataset_id, s.aligned_group_id, d.name AS dataset, d.version AS dataset_version,
                   d.license AS dataset_license, MIN(s.split) AS split
            FROM dataset_samples s JOIN datasets d ON d.id = s.dataset_id
            WHERE {' AND '.join(where)}
            GROUP BY s.dataset_id, s.aligned_group_id, d.name, d.version, d.license
            {having}
        """
        total = conn.execute(text(f"SELECT COUNT(*) FROM ({groups_sql}) g"), params).scalar_one()
        groups = conn.execute(text(
            groups_sql + " ORDER BY d.name, d.version, s.aligned_group_id LIMIT :lim OFFSET :off"),
            {**params, "lim": page_size, "off": (page - 1) * page_size}).mappings().all()
        if not groups:
            return [], int(total)

        member_rows = conn.execute(text("""
            SELECT dataset_id, aligned_group_id, sample_id, language_code, script, variant_type,
                   domain, text, source_name, source_url, license, split, human_verified
            FROM dataset_samples
            WHERE dataset_id = ANY(:dids) AND aligned_group_id = ANY(:gids)
            ORDER BY language_code, script, variant_type, sample_id
        """).bindparams(bindparam("dids"), bindparam("gids")),
            {"dids": sorted({g["dataset_id"] for g in groups}),
             "gids": sorted({g["aligned_group_id"] for g in groups})}).mappings().all()

    members: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for m in member_rows:
        members[(m["dataset_id"], m["aligned_group_id"])].append(dict(m))
    out = []
    for g in groups:
        ms = members.get((g["dataset_id"], g["aligned_group_id"]), [])
        out.append({**dict(g), "samples": ms})
    return out, int(total)
