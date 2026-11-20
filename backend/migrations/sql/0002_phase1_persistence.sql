-- REDUTAX 0002: Phase 1 persistence (dataset samples + benchmark results).
-- Adds provenance columns to dataset_samples, an import log, benchmark run metadata,
-- per-run summaries, and DB-level guards against split leakage.

-- ---------- dataset_samples: provenance + reproducibility ----------
ALTER TABLE dataset_samples
    ADD COLUMN source_name    TEXT,
    ADD COLUMN source_url     TEXT,
    ADD COLUMN license        TEXT,
    ADD COLUMN normalization  TEXT,          -- e.g. 'nfc_ws_v1' (policy used for text_normalized)
    ADD COLUMN content_sha256 TEXT;          -- hash of the sample's fields; detects changed re-imports

-- sample_id was unique across ALL datasets, which blocked importing a second version of a
-- dataset that reuses its IDs (e.g. FLORES ids). Scope it to the dataset row instead.
ALTER TABLE dataset_samples DROP CONSTRAINT dataset_samples_sample_id_key;
ALTER TABLE dataset_samples
    ADD CONSTRAINT dataset_samples_dataset_sample_key UNIQUE (dataset_id, sample_id);

ALTER TABLE dataset_samples
    ADD CONSTRAINT dataset_samples_script_check
    CHECK (script IN ('Knda','Deva','Taml','Telu','Latn','mixed'));

CREATE INDEX dataset_samples_dataset_group_idx ON dataset_samples (dataset_id, aligned_group_id);

-- An aligned group must stay inside one split within a dataset (BRD §9.3: no train/test leakage).
-- The importer checks this first; the trigger is a second line of defence.
CREATE FUNCTION dataset_samples_group_split_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.aligned_group_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM dataset_samples
        WHERE dataset_id = NEW.dataset_id
          AND aligned_group_id = NEW.aligned_group_id
          AND split <> NEW.split
          AND id <> COALESCE(NEW.id, -1)
    ) THEN
        -- No '%' placeholder: the file runs through SQLAlchemy/psycopg, which treat '%' specially.
        RAISE EXCEPTION USING
            MESSAGE = 'split leakage: aligned group ' || NEW.aligned_group_id
                      || ' already exists in another split',
            ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dataset_samples_group_split_guard
    BEFORE INSERT OR UPDATE ON dataset_samples
    FOR EACH ROW EXECUTE FUNCTION dataset_samples_group_split_guard();

-- ---------- import log ----------
CREATE TABLE dataset_imports (
    id              BIGSERIAL PRIMARY KEY,
    dataset_id      BIGINT NOT NULL REFERENCES datasets(id),
    input_sha256    TEXT,
    rows_received   INTEGER NOT NULL CHECK (rows_received >= 0),
    rows_inserted   INTEGER NOT NULL CHECK (rows_inserted >= 0),
    rows_unchanged  INTEGER NOT NULL CHECK (rows_unchanged >= 0),
    rows_skipped    INTEGER NOT NULL CHECK (rows_skipped >= 0),
    normalization   TEXT NOT NULL,
    code_version    TEXT,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- benchmark runs ----------
CREATE TABLE benchmark_runs (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             TEXT NOT NULL UNIQUE,
    run_at             TIMESTAMPTZ NOT NULL,
    dataset_id         BIGINT NOT NULL REFERENCES datasets(id),
    split              TEXT CHECK (split IN ('train','validation','test')),
    reference_language TEXT NOT NULL REFERENCES languages(code),
    normalization      TEXT NOT NULL,
    word_count_method  TEXT NOT NULL,
    code_version       TEXT,                  -- git commit, if available
    input_sha256       TEXT,
    n_samples          INTEGER NOT NULL CHECK (n_samples >= 0),
    config             JSONB NOT NULL DEFAULT '{}',   -- full run.json metadata
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every stored count carries its status (CLAUDE.md: exact | estimate | ... | research).
ALTER TABLE token_benchmarks
    ADD COLUMN count_status TEXT NOT NULL DEFAULT 'exact'
    CHECK (count_status IN ('exact','estimate','provider_reported','research','mock','unsupported'));
ALTER TABLE token_benchmarks
    ADD CONSTRAINT token_benchmarks_run_fk
    FOREIGN KEY (run_id) REFERENCES benchmark_runs(run_id) ON DELETE CASCADE;
CREATE INDEX token_benchmarks_run_tokenizer_idx ON token_benchmarks (run_id, tokenizer_id);

-- Per tokenizer x language x script summary, exactly as written to summary.csv.
CREATE TABLE benchmark_summaries (
    id                           BIGSERIAL PRIMARY KEY,
    run_id                       TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
    tokenizer_id                 BIGINT NOT NULL REFERENCES tokenizers(id),
    count_status                 TEXT NOT NULL,
    language_code                TEXT NOT NULL REFERENCES languages(code),
    script                       TEXT NOT NULL,
    n_samples                    INTEGER NOT NULL CHECK (n_samples >= 0),
    total_tokens                 BIGINT NOT NULL CHECK (total_tokens >= 0),
    total_words                  BIGINT NOT NULL CHECK (total_words >= 0),
    fertility_mean               DOUBLE PRECISION,
    fertility_median             DOUBLE PRECISION,
    fertility_stdev              DOUBLE PRECISION,
    fertility_ci95_low           DOUBLE PRECISION,
    fertility_ci95_high          DOUBLE PRECISION,
    paired_groups_with_reference INTEGER NOT NULL CHECK (paired_groups_with_reference >= 0),
    ratio_vs_reference           DOUBLE PRECISION,   -- tokenization ratio, NOT a cost multiplier
    UNIQUE (run_id, tokenizer_id, language_code, script)
);
