"""Initial schema: languages, datasets, dataset_samples, tokenizers, token_benchmarks.

The schema lives in plain SQL (migrations/sql/0001_initial.sql) so it can be
reviewed and tested with psql directly.

Revision ID: 0001
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0001_initial.sql"


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS token_benchmarks, tokenizers, dataset_samples, "
        "datasets, languages CASCADE"
    )
