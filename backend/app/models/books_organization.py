from datetime import datetime, timezone
from typing import Any, Dict, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.integration import Integration
    from app.models.user import User


class BooksOrganization(Base, TimestampMixin):
    """Zoho Books organization metadata belonging to one Books OAuth integration."""

    __tablename__ = "books_organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_organization_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default_org: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_org_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    integration: Mapped["Integration"] = relationship("Integration")

    __table_args__ = (
        UniqueConstraint(
            "integration_id", "external_organization_id",
            name="uq_books_org_integration_external_id",
        ),
        Index("ix_books_org_scope", "user_id", "integration_id", "is_org_active"),
    )
