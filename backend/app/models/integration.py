from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, EncryptedString, TimestampMixin

if TYPE_CHECKING:
    from app.models.sync_history import SyncHistory
    from app.models.user import User


class Integration(Base, TimestampMixin):
    """
    Integration model representing a connected ERP instance (e.g. Zoho CRM, Odoo, SAP).
    Stores encrypted OAuth access/refresh tokens and connection metadata.
    """
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="ERP provider identifier, e.g. 'zoho', 'odoo', 'sap'",
    )
    external_account_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="External account or organization identifier from the provider",
    )
    connection_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User-defined connection name, e.g. 'Production Zoho CRM'",
    )
    # Encrypted fields
    access_token: Mapped[Optional[str]] = mapped_column(
        EncryptedString(2048),
        nullable=True,
        comment="AES-encrypted OAuth access token",
    )
    refresh_token: Mapped[Optional[str]] = mapped_column(
        EncryptedString(2048),
        nullable=True,
        comment="AES-encrypted OAuth refresh token",
    )
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when current access token expires",
    )
    api_domain: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Base API domain URL returned during authorization (varies by DC)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
        index=True,
        comment="Connection status: 'active', 'expired', 'revoked', 'error'",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="integrations",
    )
    sync_histories: Mapped[List["SyncHistory"]] = relationship(
        "SyncHistory",
        back_populates="integration",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_account_id", name="uq_user_provider_account"),
    )

    def __repr__(self) -> str:
        return f"<Integration id={self.id} provider={self.provider} name={self.connection_name} status={self.status}>"

