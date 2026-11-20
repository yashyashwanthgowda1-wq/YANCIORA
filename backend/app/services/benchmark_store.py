"""Persist benchmark runs (metadata, per-sample counts, summaries) and read them back.

`store_run` is called by research/scripts/run_benchmark.py --store-db after the CSV,
summary and chart files are written, so file outputs never depend on the database.
The samples must already be loaded (import_pilot.py --load-db) and unchanged: every
benchmark row references a stored sample, and content hashes are compared.

Framework-free: takes a SQLAlchemy Engine, never imports FastAPI.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.services.benchmark import Row
from app.services.dataset_store import NotFound, content_hash, find_dataset_ids
from app.tokenizers import TokenizerAdapter

RATIO_NOTE = "Ratios are tokenization ratios under each tokenizer, not cost multipliers."


class BenchmarkStoreError(ValueError):
    pass


def _dataset_of(samples: list[dict]) -> tuple[str, str]:
    keys = {(s.get("dataset"), s.get("dataset_version")) for s in samples}
    if len(keys) != 1 or None in next(iter(keys)):
        raise BenchmarkStoreError(
            "a stored run must cover exactly one dataset version with 'dataset' and "
            f"'dataset_version' on every sample (found: {sorted(map(str, keys))}). "
            "Use the processed samples.jsonl written by import_pilot.py.")
    name, version = next(iter(keys))
    return str(name), str(version)


def _upsert_tokenizer(conn: Connection, tok: TokenizerAdapter) -> int:
    i = tok.info
    return conn.execute(text("""
        INSERT INTO tokenizers (name, library, library_version, kind)
        VALUES (:n, :l, :v, :k)
        ON CONFLICT (name, library, library_version) DO UPDATE SET kind = EXCLUDED.kind
        RETURNING id
    """), {"n": i.name, "l": i.library, "v": i.version, "k": i.kind}).scalar_one()


def store_run(engine: Engine, *, meta: dict, samples: list[dict], rows: list[Row],
              summary: list[dict], tokenizers: list[TokenizerAdapter]) -> dict:
    """Write one run atomically. Returns counts. Raises BenchmarkStoreError on any conflict."""
    name, version = _dataset_of(samples)
    with engine.begin() as conn:
        ds = conn.execute(text("SELECT id, license FROM datasets WHERE name = :n AND version = :v"),
                          {"n": name, "v": version}).first()
        if ds is None:
            raise BenchmarkStoreError(
                f"dataset {name}@{version} is not in the database; load it first with "
                "import_pilot.py --load-db")
        did, ds_license = ds
        if conn.execute(text("SELECT 1 FROM benchmark_runs WHERE run_id = :r"),
                        {"r": meta["run_id"]}).scalar():
            raise BenchmarkStoreError(f"benchmark run {meta['run_id']} is already stored")

        stored = {r["sample_id"]: r for r in conn.execute(text("""
            SELECT id, sample_id, content_sha256 FROM dataset_samples
            WHERE dataset_id = :d AND sample_id = ANY(:ids)
        """), {"d": did, "ids": [s["sample_id"] for s in samples]}).mappings()}
        missing = [s["sample_id"] for s in samples if s["sample_id"] not in stored]
        if missing:
            raise BenchmarkStoreError(
                f"{len(missing)} sample(s) are not stored for {name}@{version} "
                f"(e.g. {', '.join(missing[:5])}); load the dataset first")
        # The loader fills a missing row licence from the register; mirror that here.
        changed = [s["sample_id"] for s in samples
                   if stored[s["sample_id"]]["content_sha256"]
                   != content_hash({**s, "license": s.get("license") or ds_license})]
        if changed:
            raise BenchmarkStoreError(
                f"{len(changed)} sample(s) differ from the stored copy "
                f"(e.g. {', '.join(changed[:5])}); benchmark the imported version")

        tok_ids: dict[str, int] = {}
        status: dict[str, str] = {}
        for t in tokenizers:
            tok_ids[t.info.name] = _upsert_tokenizer(conn, t)
            status[t.info.name] = t.count_status

        conn.execute(text("""
            INSERT INTO benchmark_runs (run_id, run_at, dataset_id, split, reference_language,
                normalization, word_count_method, code_version, input_sha256, n_samples, config)
            VALUES (:run_id, :run_at, :d, :split, :ref, :norm, :wcm, :cv, :sha, :n,
                    CAST(:config AS JSONB))
        """), {"run_id": meta["run_id"], "run_at": datetime.fromisoformat(meta["run_at"]),
               "d": did, "split": meta.get("split"), "ref": meta["reference_language"],
               "norm": meta["normalization"], "wcm": meta["word_count_method"],
               "cv": meta.get("code_version"), "sha": meta.get("input_sha256"),
               "n": meta["n_samples"], "config": json.dumps(meta, ensure_ascii=False)})

        conn.execute(text("""
            INSERT INTO token_benchmarks (run_id, sample_id, tokenizer_id, token_count, word_count,
                char_count, fertility, normalization, word_count_method, code_version, run_at,
                count_status)
            VALUES (:run_id, :sid, :tid, :tc, :wc, :cc, :f, :norm, :wcm, :cv, :run_at, :st)
        """), [{"run_id": meta["run_id"], "sid": stored[r.sample_id]["id"],
                "tid": tok_ids[r.tokenizer], "tc": r.token_count, "wc": r.word_count,
                "cc": r.char_count, "f": r.fertility, "norm": meta["normalization"],
                "wcm": meta["word_count_method"], "cv": meta.get("code_version"),
                "run_at": datetime.fromisoformat(meta["run_at"]), "st": status[r.tokenizer]}
               for r in rows])

        if summary:
            conn.execute(text("""
                INSERT INTO benchmark_summaries (run_id, tokenizer_id, count_status, language_code,
                    script, n_samples, total_tokens, total_words, fertility_mean, fertility_median,
                    fertility_stdev, fertility_ci95_low, fertility_ci95_high,
                    paired_groups_with_reference, ratio_vs_reference)
                VALUES (:run_id, :tid, :st, :language_code, :script, :n_samples, :total_tokens,
                    :total_words, :fertility_mean, :fertility_median, :fertility_stdev,
                    :fertility_ci95_low, :fertility_ci95_high, :paired_groups_with_reference,
                    :ratio_vs_reference)
            """), [{**s, "run_id": meta["run_id"], "tid": tok_ids[s["tokenizer"]],
                    "st": status[s["tokenizer"]]} for s in summary])
    return {"run_id": meta["run_id"], "dataset": name, "dataset_version": version,
            "rows": len(rows), "summaries": len(summary)}


# ---------- read path ----------
_TOK_COLS = "t.name AS tok_name, t.library AS tok_library, t.library_version AS tok_version, t.kind AS tok_kind"


def _tok(r: Any) -> dict:
    return {"name": r["tok_name"], "library": r["tok_library"], "version": r["tok_version"],
            "kind": r["tok_kind"]}


def list_runs(engine: Engine, *, run_id: str | None = None, dataset: str | None = None,
              dataset_version: str | None = None, tokenizer: str | None = None,
              language: str | None = None, page: int = 1, page_size: int = 20
              ) -> tuple[list[dict], int]:
    """Stored runs with their summaries (summaries filtered by tokenizer/language if given)."""
    with engine.connect() as conn:
        where, params = ["TRUE"], {}
        if run_id:
            where.append("r.run_id = :run_id")
            params["run_id"] = run_id
        if dataset:
            params["dids"] = find_dataset_ids(conn, dataset, dataset_version)
            where.append("r.dataset_id = ANY(:dids)")
        elif dataset_version:
            where.append("d.version = :dv")
            params["dv"] = dataset_version
        if tokenizer:
            where.append("""EXISTS (SELECT 1 FROM benchmark_summaries bs
                            JOIN tokenizers bt ON bt.id = bs.tokenizer_id
                            WHERE bs.run_id = r.run_id AND bt.name = :tok)""")
            params["tok"] = tokenizer
        base = f"FROM benchmark_runs r JOIN datasets d ON d.id = r.dataset_id WHERE {' AND '.join(where)}"
        total = conn.execute(text(f"SELECT COUNT(*) {base}"), params).scalar_one()
        if run_id and total == 0:
            raise NotFound(f"benchmark run '{run_id}' not found")
        runs = conn.execute(text(f"""
            SELECT r.run_id, r.run_at, d.name AS dataset, d.version AS dataset_version, r.split,
                   r.reference_language, r.normalization, r.word_count_method, r.code_version,
                   r.input_sha256, r.n_samples
            {base} ORDER BY r.run_at DESC, r.run_id DESC LIMIT :lim OFFSET :off
        """), {**params, "lim": page_size, "off": (page - 1) * page_size}).mappings().all()
        if not runs:
            return [], int(total)

        sw, sp = ["s.run_id = ANY(:rids)"], {"rids": [r["run_id"] for r in runs]}
        if tokenizer:
            sw.append("t.name = :tok")
            sp["tok"] = tokenizer
        if language:
            sw.append("s.language_code = :lang")
            sp["lang"] = language
        srows = conn.execute(text(f"""
            SELECT s.*, {_TOK_COLS} FROM benchmark_summaries s
            JOIN tokenizers t ON t.id = s.tokenizer_id
            WHERE {' AND '.join(sw)}
            ORDER BY t.name, s.language_code, s.script
        """), sp).mappings().all()
        trows = conn.execute(text(f"""
            SELECT DISTINCT s.run_id, {_TOK_COLS} FROM benchmark_summaries s
            JOIN tokenizers t ON t.id = s.tokenizer_id WHERE s.run_id = ANY(:rids)
            ORDER BY t.name
        """), {"rids": sp["rids"]}).mappings().all()

    summaries: dict[str, list[dict]] = defaultdict(list)
    for s in srows:
        summaries[s["run_id"]].append({
            "tokenizer": _tok(s), "status": s["count_status"], "language": s["language_code"],
            "script": s["script"], "n_samples": s["n_samples"],
            "total_tokens": s["total_tokens"], "total_words": s["total_words"],
            "fertility_mean": s["fertility_mean"], "fertility_median": s["fertility_median"],
            "fertility_stdev": s["fertility_stdev"], "fertility_ci95_low": s["fertility_ci95_low"],
            "fertility_ci95_high": s["fertility_ci95_high"],
            "paired_groups_with_reference": s["paired_groups_with_reference"],
            "ratio_vs_reference": s["ratio_vs_reference"],
        })
    toks: dict[str, list[dict]] = defaultdict(list)
    for t in trows:
        toks[t["run_id"]].append(_tok(t))
    out = [{**dict(r), "tokenizers": toks[r["run_id"]], "summaries": summaries[r["run_id"]],
            "note": RATIO_NOTE} for r in runs]
    return out, int(total)


def list_results(engine: Engine, run_id: str, *, tokenizer: str | None = None,
                 language: str | None = None, script: str | None = None,
                 aligned_group_id: str | None = None, page: int = 1, page_size: int = 50
                 ) -> tuple[list[dict], int]:
    """Per-sample counts for one run."""
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM benchmark_runs WHERE run_id = :r"),
                            {"r": run_id}).scalar():
            raise NotFound(f"benchmark run '{run_id}' not found")
        where, params = ["b.run_id = :r"], {"r": run_id}
        for col, key, val in (("t.name", "tok", tokenizer), ("s.language_code", "lang", language),
                              ("s.script", "script", script),
                              ("s.aligned_group_id", "gid", aligned_group_id)):
            if val:
                where.append(f"{col} = :{key}")
                params[key] = val
        base = f"""FROM token_benchmarks b
            JOIN dataset_samples s ON s.id = b.sample_id
            JOIN tokenizers t ON t.id = b.tokenizer_id
            WHERE {' AND '.join(where)}"""
        total = conn.execute(text(f"SELECT COUNT(*) {base}"), params).scalar_one()
        rows = conn.execute(text(f"""
            SELECT s.sample_id, s.aligned_group_id, s.language_code, s.script, s.variant_type,
                   b.token_count, b.word_count, b.char_count, b.fertility, b.count_status,
                   {_TOK_COLS}
            {base} ORDER BY t.name, s.aligned_group_id NULLS LAST, s.language_code, s.sample_id
            LIMIT :lim OFFSET :off
        """), {**params, "lim": page_size, "off": (page - 1) * page_size}).mappings().all()
    return [{
        "sample_id": r["sample_id"], "aligned_group_id": r["aligned_group_id"],
        "language": r["language_code"], "script": r["script"], "variant_type": r["variant_type"],
        "tokenizer": _tok(r), "status": r["count_status"], "token_count": r["token_count"],
        "word_count": r["word_count"], "char_count": r["char_count"],
        "tokens_per_word": r["fertility"],
    } for r in rows], int(total)
