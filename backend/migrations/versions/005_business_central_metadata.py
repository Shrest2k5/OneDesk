"""Add Business Central tenant, environment, and company metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_business_central_metadata"
down_revision: Union[str, None] = "004_odoo_database_selector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("integrations", sa.Column("business_central_tenant_id", sa.String(100), nullable=True))
    op.add_column("integrations", sa.Column("business_central_environment_name", sa.String(100), nullable=True))
    op.add_column("integrations", sa.Column("business_central_company_id", sa.String(100), nullable=True))
    op.add_column("integrations", sa.Column("business_central_company_name", sa.String(255), nullable=True))
    op.create_index(
        "ix_integrations_business_central_tenant_id",
        "integrations",
        ["business_central_tenant_id"],
    )
    op.create_index(
        "uq_business_central_user_tenant_environment_company",
        "integrations",
        [
            "user_id", "business_central_tenant_id", "business_central_environment_name",
            "business_central_company_id",
        ],
        unique=True,
        postgresql_where=sa.text("provider = 'business_central'"),
    )


def downgrade() -> None:
    op.drop_index("uq_business_central_user_tenant_environment_company", table_name="integrations")
    op.drop_index("ix_integrations_business_central_tenant_id", table_name="integrations")
    op.drop_column("integrations", "business_central_company_name")
    op.drop_column("integrations", "business_central_company_id")
    op.drop_column("integrations", "business_central_environment_name")
    op.drop_column("integrations", "business_central_tenant_id")
