-- REDUTAX initial schema (Phase 0).
-- Tables from BRD §14 needed for Phase 1: languages, datasets, dataset_samples,
-- tokenizers, token_benchmarks. Later phases add optimizer, model registry,
-- chat, voice and audit tables in their own migrations.

CREATE TABLE languages (
    code        TEXT PRIMARY KEY,                -- BCP-47, e.g. 'kn'
    name        TEXT NOT NULL,
    scripts     TEXT[] NOT NULL,                 -- ISO 15924, e.g. {Knda,Latn}
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A dataset cannot be registered without licence and provenance (BRD §9.2).
CREATE TABLE datasets (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    version           TEXT NOT NULL,
    license           TEXT NOT NULL,
    license_url       TEXT,
    source_url        TEXT NOT NULL,
    citation          TEXT,
    language_coverage TEXT[] NOT NULL DEFAULT '{}',
    accessed_at       DATE NOT NULL,
    approved_for      TEXT[] NOT NULL DEFAULT '{}',  -- e.g. {evaluation,tokenizer_training}
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

-- Sample schema follows BRD §9.3.
CREATE TABLE dataset_samples (
    id               BIGSERIAL PRIMARY KEY,
    sample_id        TEXT NOT NULL UNIQUE,                    -- stable external ID
    dataset_id       BIGINT NOT NULL REFERENCES datasets(id),
    language_code    TEXT NOT NULL REFERENCES languages(code),
    script           TEXT NOT NULL,                           -- Knda | Latn | mixed ...
    text             TEXT NOT NULL,                           -- original, never modified
    text_normalized  TEXT,                                    -- per documented policy
    aligned_group_id TEXT,                                    -- links equivalent meanings
    domain           TEXT NOT NULL DEFAULT 'general',
    variant_type     TEXT NOT NULL CHECK (variant_type IN
                       ('original','translation','transliteration','code_mixed','paraphrase')),
    split            TEXT NOT NULL CHECK (split IN ('train','validation','test')),
    human_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    quality_notes    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX dataset_samples_group_idx ON dataset_samples (aligned_group_id);
CREATE INDEX dataset_samples_lang_split_idx ON dataset_samples (language_code, split);

CREATE TABLE tokenizers (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT NOT NULL,                 -- e.g. 'cl100k_base'
    library           TEXT NOT NULL,                 -- e.g. 'tiktoken', 'sentencepiece'
    library_version   TEXT NOT NULL,
    vocab_size        INTEGER,
    config            JSONB NOT NULL DEFAULT '{}',
    model_association TEXT,                          -- verified association only, else NULL
    kind              TEXT NOT NULL CHECK (kind IN ('baseline','experimental','model_input')),
    artifact_uri      TEXT,                          -- object storage path for trained files
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, library, library_version)
);

-- Every count is tied to a tokenizer version and a run (BRD §16 reproducibility).
CREATE TABLE token_benchmarks (
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL,
    sample_id         BIGINT NOT NULL REFERENCES dataset_samples(id),
    tokenizer_id      BIGINT NOT NULL REFERENCES tokenizers(id),
    token_count       INTEGER NOT NULL CHECK (token_count >= 0),
    word_count        INTEGER NOT NULL CHECK (word_count >= 0),
    char_count        INTEGER NOT NULL CHECK (char_count >= 0),
    fertility         DOUBLE PRECISION,              -- token_count / word_count
    normalization     TEXT NOT NULL,                 -- e.g. 'NFC'
    word_count_method TEXT NOT NULL,
    code_version      TEXT,                          -- git commit
    run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, sample_id, tokenizer_id)
);
CREATE INDEX token_benchmarks_run_idx ON token_benchmarks (run_id);

-- Reference rows: the five initial languages (BRD §9.1). Factual codes only, no data.
INSERT INTO languages (code, name, scripts) VALUES
    ('kn', 'Kannada', ARRAY['Knda','Latn']),
    ('hi', 'Hindi',   ARRAY['Deva','Latn']),
    ('ta', 'Tamil',   ARRAY['Taml','Latn']),
    ('te', 'Telugu',  ARRAY['Telu','Latn']),
    ('en', 'English', ARRAY['Latn']);
