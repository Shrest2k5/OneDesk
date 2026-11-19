from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration_record import IntegrationRecord
from app.models.integration import Integration


class IntegrationRecordRepository:
    """Tenant-safe persistence operations for provider-neutral external records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _source_time(payload: Dict[str, Any], *keys: str) -> Optional[datetime]:
        for key in keys:
            value = payload.get(key)
            if not value:
                continue
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
        return None

    async def upsert(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
        provider: str,
        product: str,
        external_organization_id: Optional[str],
        resource_type: str,
        payload: Dict[str, Any],
    ) -> str:
        if not external_organization_id:
            raise ValueError("An external organization ID is required to persist a record")
        external_record_id = (
            payload.get("id") or payload.get("contact_id") or payload.get("invoice_id")
            or payload.get("payment_id") or payload.get("payment_refund_id")
            or payload.get("creditnote_refund_id") or payload.get("vendorpayment_refund_id")
            or payload.get("transaction_id") or payload.get("sales_receipt_id")
            or payload.get("receipt_id")
        )
        if external_record_id is None:
            raise ValueError("External record payload is missing id")

        integration = (await self.session.execute(
            select(Integration).where(Integration.id == integration_id, Integration.user_id == user_id)
        )).scalar_one_or_none()
        if not integration:
            raise ValueError("Integration does not belong to this tenant")
        if integration.provider != provider or integration.product != product:
            raise ValueError("Integration provider or product does not match the record")
        if product == "books" and integration.selected_organization_id != str(external_organization_id):
            raise ValueError("Record organization does not match the selected Books organization")

        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == user_id,
            IntegrationRecord.integration_id == integration_id,
            IntegrationRecord.external_organization_id == str(external_organization_id),
            IntegrationRecord.resource_type == resource_type,
            IntegrationRecord.external_record_id == str(external_record_id),
            IntegrationRecord.provider == provider,
            IntegrationRecord.product == product,
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        values = {
            "raw_data": payload,
            "source_created_at": self._source_time(payload, "Created_Time", "created_time", "created_at"),
            "source_modified_at": self._source_time(payload, "Modified_Time", "modified_time", "last_modified_time", "updated_at"),
            "last_synced_at": now,
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            await self.session.flush()
            return "updated"

        self.session.add(IntegrationRecord(
            user_id=user_id,
            integration_id=integration_id,
            provider=provider,
            product=product,
            external_organization_id=str(external_organization_id),
            resource_type=resource_type,
            external_record_id=str(external_record_id),
            **values,
        ))
        await self.session.flush()
        return "inserted"

    async def list_for_user(
        self, user_id: uuid.UUID, integration_id: uuid.UUID, resource_type: Optional[str] = None
    ) -> List[IntegrationRecord]:
        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == user_id,
            IntegrationRecord.integration_id == integration_id,
        )
        if resource_type:
            query = query.where(IntegrationRecord.resource_type == resource_type)
        result = await self.session.execute(query.order_by(IntegrationRecord.last_synced_at.desc()))
        return list(result.scalars().all())
