"""Persist Zoho Books organizations and selected organization metadata."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_books_organizations"
down_revision: Union[str, None] = "002_product_aware_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("integrations", sa.Column("selected_organization_id", sa.String(100), nullable=True))
    op.create_index("ix_integrations_selected_organization_id", "integrations", ["selected_organization_id"])

    op.create_table(
        "books_organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("external_organization_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("currency_code", sa.String(20), nullable=True),
        sa.Column("currency_symbol", sa.String(20), nullable=True),
        sa.Column("time_zone", sa.String(100), nullable=True),
        sa.Column("is_default_org", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_org_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_organization_id", name="uq_books_org_integration_external_id"),
    )
    op.create_index("ix_books_organizations_user_id", "books_organizations", ["user_id"])
    op.create_index("ix_books_organizations_integration_id", "books_organizations", ["integration_id"])
    op.create_index("ix_books_org_scope", "books_organizations", ["user_id", "integration_id", "is_org_active"])


def downgrade() -> None:
    op.drop_index("ix_books_org_scope", table_name="books_organizations")
    op.drop_index("ix_books_organizations_integration_id", table_name="books_organizations")
    op.drop_index("ix_books_organizations_user_id", table_name="books_organizations")
    op.drop_table("books_organizations")
    op.drop_index("ix_integrations_selected_organization_id", table_name="integrations")
    op.drop_column("integrations", "selected_organization_id")
