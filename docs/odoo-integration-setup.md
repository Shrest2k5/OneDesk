# OneDesk Odoo 20 integration architecture

Status: **Milestone 3 master-data synchronization implemented; other business resources excluded**

Odoo is an external ERP provider connected through the existing OneDesk application. OneDesk does not host Odoo, an Odoo PostgreSQL database, an Odoo filestore, or Odoo-specific Docker infrastructure.

## Milestone 2 implementation

The connection flow is available at `POST /api/v1/integrations/odoo/connect`. It accepts an external HTTPS instance URL, JSON-2 API key, connection name, and an optional database name. The API key is sent as `Authorization: bearer <API_KEY>` and the database header is sent only when supplied.

Before persistence, OneDesk performs the read-only `res.users/context_get` JSON-2 call. A successful response confirms reachability, JSON-2 availability, API-key authentication, and the authenticated Odoo user's context. Only then is the tenant-owned connection saved with status `active`. The API key is stored through the existing encrypted `Integration.access_token` field and is never returned to the frontend.

Connection status uses the same generic `/api/v1/integrations/{id}/status` endpoint. Disconnect uses the existing tenant-scoped DELETE endpoint. Reconnect validates the replacement key before updating the existing Odoo connection.

## Milestone 3 master data

Odoo partner synchronization uses the standard `res.partner` model through JSON-2:

- `POST /json/2/res.partner/search_read`
- `domain`: empty for the canonical Contacts sync; customer/vendor views filter the persisted classification locally.
- `fields`: identifiers, names, active/company flags, `type`, `parent_id`, `commercial_partner_id`, contact/address fields, `customer_rank`, `supplier_rank`, `create_date`, and `write_date`.
- `context`: `active_test=False`, so archived partners are retrieved and retained with `active=false`.
- Pagination uses JSON-2 `offset` and `limit`, configurable up to 500 per page.

One canonical `IntegrationRecord` is stored per Odoo partner under resource type `contacts`, preventing a dual-role partner from being duplicated across Contacts, Customers, and Vendors. Customer classification is `customer_rank > 0`; vendor classification is `supplier_rank > 0`. `parent_id` and `commercial_partner_id` are normalized to preserve company/contact relationships. Missing optional fields are represented as nulls.

The Odoo UI is available at `/odoo/contacts`, with customer/vendor filters, archived filtering, pagination, stats, loading/error/empty states, and manual refresh. Refresh uses the existing shared `SyncService` and Celery task, with `SyncHistory` and provider-neutral `IntegrationRecord` persistence.

## Existing OneDesk architecture to reuse

The existing Zoho CRM and Zoho Books implementations establish these conventions:

- `backend/app/models/integration.py` is the tenant-owned provider connection model. It already supports provider/product identity, connection metadata, status, API domain, and encrypted credentials.
- `Integration.user_id` and `IntegrationRepository` enforce ownership. `IntegrationService` resolves and deletes only the authenticated user's connections.
- `EncryptedString` and the Fernet helpers in `backend/app/models/base.py` and `backend/app/core/security.py` encrypt provider secrets at rest. Integration response schemas expose metadata only; credentials are not returned.
- `backend/app/integrations/base.py` defines the provider interface, and `backend/app/integrations/registry.py` resolves implementations by provider/product.
- Zoho-specific OAuth, token refresh, retry/error handling, and HTTP behavior are isolated under `backend/app/integrations/zoho/`.
- `backend/app/services/sync_service.py`, `backend/app/workers/sync_worker.py`, and Celery provide shared sync lifecycle, retries, error capture, and `SyncHistory` records.
- `IntegrationRecord` is the provider-neutral durable record shape used for canonical Odoo partner records.
- `backend/app/api/routes.py` and the integration routers provide authenticated, tenant-scoped connection/status/disconnect flows. The existing frontend `IntegrationContext`, integrations API, and `IntegrationsPage` provide the connection list, status, details, and disconnect patterns.

No new database tables, Docker services, or provider infrastructure are required for the initial Odoo connection architecture.

Milestone 2 adds one nullable shared-model field, `integrations.external_database`, via migration `004_odoo_database_selector`. This is necessary to persist an optional Odoo `X-Odoo-Database` selector without overloading Zoho's organization fields; it is nullable for all providers and does not alter existing Zoho records.

## Odoo connection contract

Odoo 20 External JSON-2 uses an HTTP endpoint of the form:

```text
POST {instance_url}/json/2/{model}/{method}
Authorization: bearer {api_key}
```

The official [Odoo 20 External API documentation](https://www.odoo.com/documentation/20.0/developer/reference/external_api.html) states that API keys are created for a user under Preferences -> Account Security and that JSON-2 enforces that user's access rights, record rules, and field permissions.

The provider-specific connection will therefore need:

- `instance_url`: the externally hosted Odoo base URL, normalized and restricted to HTTPS outside local development. This maps to the existing `Integration.api_domain` field.
- `api_key`: the Odoo JSON-2 bearer key, stored in the existing encrypted `Integration.access_token` column. It must never appear in response payloads or logs.
- `connection_name`: the existing user-facing connection label.
- Optional database selector: only when the external deployment requires `X-Odoo-Database` because multiple Odoo databases are served by the same host and host-based selection/dbfilter is insufficient. This is persisted in the nullable shared `external_database` field; it is not required universally or treated as an OAuth field.

Odoo JSON-2 does not require an OAuth redirect flow for this connection. A login/email is not an authentication credential for JSON-2 requests; the API key identifies the Odoo user. The OneDesk user who owns the connection remains represented by `Integration.user_id`.

The provider client uses read-only `res.partner/search_read` for synchronization. It does not use XML-RPC or JSON-RPC as a fallback.

## Removed standalone infrastructure

The Milestone 1 standalone artifacts were removed after reference checks:

- `odoo/docker-compose.yml` -- deleted
- `odoo/.env.example` -- deleted
- Odoo-specific `.gitignore` entries for local env/runtime data -- deleted

The root `docker-compose.yml`, its PostgreSQL/Redis/API/Celery services, existing OneDesk database, and all Zoho files remain unchanged. Any pre-existing local `odoo/.env` file was preserved and remains ignored by the repository's generic `.env` rule; it is no longer consumed by any project configuration.

## Verification

Completed during architecture alignment:

- Searched the repository for references to the standalone Compose file, Odoo env template, project name, container names, and Odoo volumes before deletion. No existing application or Zoho code referenced those resources; only the Milestone 1 documentation and files themselves did.
- Reviewed the provider-neutral model, repository, service, registry, Celery, sync-history, API, and frontend integration patterns.
- Confirmed migration `004_odoo_database_selector` is the only schema change required for the optional database selector; it is nullable and does not alter existing Zoho records.
- Confirmed the official API requirement is bearer API-key authentication over JSON-2; no OAuth support was assumed.
- SSRF review: HTTPS, credentials/query/fragment rejection, local/private IP rejection, internal hostname rejection, DNS resolution checks, and redirect refusal are implemented. The hostname is re-resolved by the HTTP stack during connection, so a malicious DNS rebinding race remains a deployment-level residual risk; outbound network policy should also restrict backend egress where available.

Not implemented by design:

- Live Odoo API validation in this development environment; automated coverage uses mocked HTTP responses only.
- Odoo leads, opportunities, pipelines, activities, invoices, bills, sales orders, and payments.

This document stops after Milestone 3 master-data synchronization. No other business-resource synchronization has started.
