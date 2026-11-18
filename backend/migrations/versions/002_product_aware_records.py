"""Add product-aware integrations and durable external records."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_product_aware_records"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("integrations", sa.Column("product", sa.String(50), nullable=True, server_default="crm"))
    op.execute("UPDATE integrations SET product = 'crm' WHERE product IS NULL")
    op.alter_column("integrations", "product", nullable=False, server_default="crm")
    op.drop_constraint("uq_user_provider_account", "integrations", type_="unique")
    op.create_unique_constraint(
        "uq_user_provider_product_account",
        "integrations",
        ["user_id", "provider", "product", "external_account_id"],
    )
    op.create_index("ix_integrations_product", "integrations", ["product"])

    op.add_column("sync_history", sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_history", sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_history", sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_history", sa.Column("successful_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "integration_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("product", sa.String(50), nullable=False),
        sa.Column("external_organization_id", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("external_record_id", sa.String(255), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id", "external_organization_id", "resource_type", "external_record_id",
            name="uq_integration_record_external_identity",
        ),
    )
    op.create_index("ix_integration_records_user_id", "integration_records", ["user_id"])
    op.create_index("ix_integration_records_integration_id", "integration_records", ["integration_id"])
    op.create_index("ix_integration_records_scope", "integration_records", ["user_id", "provider", "product", "resource_type"])
    op.create_index("ix_integration_records_modified", "integration_records", ["integration_id", "resource_type", "source_modified_at"])


def downgrade() -> None:
    op.drop_index("ix_integration_records_modified", table_name="integration_records")
    op.drop_index("ix_integration_records_scope", table_name="integration_records")
    op.drop_index("ix_integration_records_integration_id", table_name="integration_records")
    op.drop_index("ix_integration_records_user_id", table_name="integration_records")
    op.drop_table("integration_records")
    op.drop_column("sync_history", "successful_at")
    op.drop_column("sync_history", "records_failed")
    op.drop_column("sync_history", "records_updated")
    op.drop_column("sync_history", "records_inserted")
    op.drop_index("ix_integrations_product", table_name="integrations")
    op.drop_constraint("uq_user_provider_product_account", "integrations", type_="unique")
    op.create_unique_constraint("uq_user_provider_account", "integrations", ["user_id", "provider", "external_account_id"])
    op.drop_column("integrations", "product")
