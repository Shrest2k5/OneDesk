"""Add optional external database selector for provider connections."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_odoo_database_selector"
down_revision: Union[str, None] = "003_books_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integrations",
        sa.Column(
            "external_database",
            sa.String(length=100),
            nullable=True,
            comment="Optional provider database selector, e.g. Odoo X-Odoo-Database",
        ),
    )


def downgrade() -> None:
    op.drop_column("integrations", "external_database")
