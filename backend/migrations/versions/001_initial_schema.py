"""Initial schema for users, integrations, and sync_history

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-12 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. Create integrations table
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, comment="ERP provider identifier, e.g. 'zoho'"),
        sa.Column("external_account_id", sa.String(length=100), nullable=True, comment="External account ID"),
        sa.Column("connection_name", sa.String(length=100), nullable=False),
        sa.Column("access_token", sa.String(length=2048), nullable=True, comment="AES-encrypted access token"),
        sa.Column("refresh_token", sa.String(length=2048), nullable=True, comment="AES-encrypted refresh token"),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, comment="active, expired, revoked, error"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", "external_account_id", name="uq_user_provider_account"),
    )
    op.create_index(op.f("ix_integrations_user_id"), "integrations", ["user_id"], unique=False)
    op.create_index(op.f("ix_integrations_provider"), "integrations", ["provider"], unique=False)
    op.create_index(op.f("ix_integrations_external_account_id"), "integrations", ["external_account_id"], unique=False)
    op.create_index(op.f("ix_integrations_status"), "integrations", ["status"], unique=False)

    # 3. Create sync_history table
    op.create_table(
        "sync_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_history_integration_id"), "sync_history", ["integration_id"], unique=False)
    op.create_index(op.f("ix_sync_history_resource_type"), "sync_history", ["resource_type"], unique=False)
    op.create_index(op.f("ix_sync_history_status"), "sync_history", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_history_status"), table_name="sync_history")
    op.drop_index(op.f("ix_sync_history_resource_type"), table_name="sync_history")
    op.drop_index(op.f("ix_sync_history_integration_id"), table_name="sync_history")
    op.drop_table("sync_history")

    op.drop_index(op.f("ix_integrations_status"), table_name="integrations")
    op.drop_index(op.f("ix_integrations_external_account_id"), table_name="integrations")
    op.drop_index(op.f("ix_integrations_provider"), table_name="integrations")
    op.drop_index(op.f("ix_integrations_user_id"), table_name="integrations")
    op.drop_table("integrations")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

