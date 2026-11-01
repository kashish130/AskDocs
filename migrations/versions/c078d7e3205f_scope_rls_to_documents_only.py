"""scope rls to documents only

Revision ID: c078d7e3205f
Revises: a2a89bdb5a35
Create Date: 2026-10-30 22:49:08.825673

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c078d7e3205f"
down_revision: str | Sequence[str] | None = "a2a89bdb5a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON organizations")
    op.execute("ALTER TABLE organizations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON memberships")
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON organizations
        USING (id::text = current_setting('app.current_org',TRUE))
        WITH CHECK (id::text = current_setting('app.current_org',TRUE))
        """
    )
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON memberships
        USING (organization_id::text = current_setting('app.current_org',TRUE))
        WITH CHECK (organization_id::text = current_setting('app.current_org',TRUE))
        """
    )
