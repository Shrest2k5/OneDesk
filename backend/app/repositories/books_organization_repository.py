from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.books_organization import BooksOrganization


class BooksOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID, integration_id: uuid.UUID) -> List[BooksOrganization]:
        result = await self.session.execute(
            select(BooksOrganization)
            .where(
                BooksOrganization.user_id == user_id,
                BooksOrganization.integration_id == integration_id,
            )
            .order_by(BooksOrganization.name.asc())
        )
        return list(result.scalars().all())

    async def get_for_user(
        self, user_id: uuid.UUID, integration_id: uuid.UUID, external_organization_id: str
    ) -> Optional[BooksOrganization]:
        result = await self.session.execute(
            select(BooksOrganization).where(
                BooksOrganization.user_id == user_id,
                BooksOrganization.integration_id == integration_id,
                BooksOrganization.external_organization_id == external_organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_many(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
        organizations: List[Dict[str, Any]],
    ) -> List[BooksOrganization]:
        saved: List[BooksOrganization] = []
        for payload in organizations:
            external_id = payload.get("organization_id")
            if external_id is None:
                continue
            organization = await self.get_for_user(user_id, integration_id, str(external_id))
            values = {
                "name": str(payload.get("name") or external_id),
                "email": payload.get("email"),
                "currency_code": payload.get("currency_code"),
                "currency_symbol": payload.get("currency_symbol"),
                "time_zone": payload.get("time_zone"),
                "is_default_org": bool(payload.get("is_default_org", False)),
                "is_org_active": bool(payload.get("is_org_active", True)),
                "raw_data": payload,
                "fetched_at": datetime.now(timezone.utc),
            }
            if organization:
                for key, value in values.items():
                    setattr(organization, key, value)
            else:
                organization = BooksOrganization(
                    user_id=user_id,
                    integration_id=integration_id,
                    external_organization_id=str(external_id),
                    **values,
                )
                self.session.add(organization)
            saved.append(organization)
        await self.session.flush()
        return saved
