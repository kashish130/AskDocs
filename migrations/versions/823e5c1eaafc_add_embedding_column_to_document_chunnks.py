"""add embedding column to document chunnks

Revision ID: 823e5c1eaafc
Revises: b5165ba1c8b7
Create Date: 2026-11-05 23:53:12.855494

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "823e5c1eaafc"
down_revision: str | Sequence[str] | None = "b5165ba1c8b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding", Vector(384), nullable=True))
    op.execute("""CREATE INDEX document_chunks_embedding_hnsw_idx
     ON document_chunks 
     USING hnsw (embedding vector_cosine_ops)
      """)


def downgrade() -> None:
    op.execute("""DROP INDEX if exists document_chunks_embedding_hnsw_idx""")
    op.drop_column("document_chunks", "embedding")
