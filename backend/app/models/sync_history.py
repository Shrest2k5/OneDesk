from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.integration import Integration


class SyncHistory(Base):
    """
    Sync history model tracking background and on-demand synchronization jobs
    for external ERP resources.
    """
    __tablename__ = "sync_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Resource synchronized, e.g. 'contacts', 'leads', 'deals', 'accounts'",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Job status: 'pending', 'in_progress', 'completed', 'failed'",
    )
    records_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Count of records fetched or processed",
    )
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Set only after all pages and record upserts complete successfully",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed error message if the synchronization failed",
    )

    # Relationships
    integration: Mapped["Integration"] = relationship(
        "Integration",
        back_populates="sync_histories",
    )

    def __repr__(self) -> str:
        return f"<SyncHistory id={self.id} resource={self.resource_type} status={self.status}>"

