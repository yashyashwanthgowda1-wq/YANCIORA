"""Phase 1 persistence: sample provenance, import log, benchmark runs and summaries.

Schema in migrations/sql/0002_phase1_persistence.sql.

Revision ID: 0002
Revises: 0001
"""
from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0002_phase1_persistence.sql"


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS benchmark_summaries;
        DROP INDEX IF EXISTS token_benchmarks_run_tokenizer_idx;
        ALTER TABLE token_benchmarks DROP CONSTRAINT IF EXISTS token_benchmarks_run_fk;
        ALTER TABLE token_benchmarks DROP COLUMN IF EXISTS count_status;
        DROP TABLE IF EXISTS benchmark_runs;
        DROP TABLE IF EXISTS dataset_imports;
        DROP TRIGGER IF EXISTS dataset_samples_group_split_guard ON dataset_samples;
        DROP FUNCTION IF EXISTS dataset_samples_group_split_guard();
        DROP INDEX IF EXISTS dataset_samples_dataset_group_idx;
        ALTER TABLE dataset_samples DROP CONSTRAINT IF EXISTS dataset_samples_script_check;
        ALTER TABLE dataset_samples DROP CONSTRAINT IF EXISTS dataset_samples_dataset_sample_key;
        ALTER TABLE dataset_samples ADD CONSTRAINT dataset_samples_sample_id_key UNIQUE (sample_id);
        ALTER TABLE dataset_samples
            DROP COLUMN IF EXISTS source_name, DROP COLUMN IF EXISTS source_url,
            DROP COLUMN IF EXISTS license, DROP COLUMN IF EXISTS normalization,
            DROP COLUMN IF EXISTS content_sha256;
    """)
