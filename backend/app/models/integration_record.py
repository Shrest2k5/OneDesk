from datetime import datetime, timezone
from typing import Any, Dict, TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.integration import Integration
    from app.models.user import User


class IntegrationRecord(Base):
    """Provider-neutral durable representation of a synchronized external record."""

    __tablename__ = "integration_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    product: Mapped[str] = mapped_column(String(50), nullable=False)
    external_organization_id: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    external_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    integration: Mapped["Integration"] = relationship("Integration")

    __table_args__ = (
        UniqueConstraint(
            "integration_id", "external_organization_id", "resource_type", "external_record_id",
            name="uq_integration_record_external_identity",
        ),
        Index("ix_integration_records_scope", "user_id", "provider", "product", "resource_type"),
        Index("ix_integration_records_modified", "integration_id", "resource_type", "source_modified_at"),
    )
