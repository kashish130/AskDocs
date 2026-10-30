"""enable RLS on tenant tables

Revision ID: a2a89bdb5a35
Revises: 989a7da75b66
Create Date: 2026-10-29 17:41:11.960030

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2a89bdb5a35"
down_revision: str | Sequence[str] | None = "989a7da75b66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = [
    ("organizations", "id"),
    ("memberships", "organization_id"),
    ("documents", "organization_id"),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, org_column in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # Policy: visible only rows where the organization_id matches the current_organization_id
        # setting
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {table}
            USING ({org_column}::text = current_setting('app.current_org',TRUE))
            WITH CHECK ({org_column}::text = current_setting('app.current_org',TRUE))
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, _ in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
