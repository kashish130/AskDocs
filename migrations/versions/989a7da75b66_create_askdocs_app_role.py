"""create askdocs_app role

Revision ID: 989a7da75b66
Revises: c0e85e760554
Create Date: 2026-10-29 17:20:39.286205

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "989a7da75b66"
down_revision: str | Sequence[str] | None = "c0e85e760554"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'askdocs_app') THEN
                CREATE ROLE askdocs_app LOGIN PASSWORD 'askdocs_app_dev';
            END IF;
        END$$;"""
    )
    op.execute("GRANT USAGE ON SCHEMA public TO askdocs_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO askdocs_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO askdocs_app")
    # Future tables created later should also grant automatically
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO askdocs_app"
    )


def downgrade() -> None:
    op.execxute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        " REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM askdocs_app"
    )
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM askdocs_app")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM askdocs_app")
    op.execute("REVOKE ALL ON SCHEMA public FROM askdocs_app")
    op.execute("DROP ROLE IF EXISTS askdocs_app")
