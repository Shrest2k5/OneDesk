# OneDesk — Unified ERP Integration Platform

**OneDesk** is a modular, multi-tenant Unified ERP Integration Platform built with **FastAPI**, **SQLAlchemy 2.0 (async)**, **PostgreSQL 16**, **Redis 7**, **Celery**, and **React 19 + TypeScript + Vite + Tailwind CSS**.

The platform provides a centralized, secure integration layer between business applications and external ERP/CRM/accounting ecosystems. It abstracts provider-specific authentication, token lifecycles, encryption at rest, data center routing, pagination, rate limits, schema normalization, and delta synchronization.

**Supported Integrations:**
- **Zoho Books:** Organization discovery, organization selection, and paginated extraction of contacts (customers & vendors), invoices, and financial transactions (customer payments, vendor payments, sales receipts, credit note refunds, customer payment refunds, vendor payment refunds, bank transactions/deposits).
- **Zoho CRM (v8 REST API):** Multi-datacenter OAuth 2.0 connection lifecycle, health diagnostics, and paginated read retrieval for Contacts, Leads, Deals, and Accounts.
- **Future Connectors:** Pluggable connector registry prepared for Odoo, SAP, and custom ERP connectors.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph FrontendApp ["Frontend Application (React 19 + Vite)"]
        UI["Web UI (Dashboard, Integrations, CRM, Books, Sync, Activity)"]
        Router["React Router v7 Protected Routes"]
        TanStack["TanStack Query Cache & Axios Client"]
        UI --> Router --> TanStack
    end

    subgraph BackendAPI ["OneDesk Backend (FastAPI REST API)"]
        AuthRouter["/api/v1/auth (Register, Login, Me)"]
        IntRouter["/api/v1/integrations (List, Status, Disconnect)"]
        SyncRouter["/api/v1/integrations/{id}/sync (On-Demand & History)"]
        ZohoCRMRouter["/api/v1/integrations/zoho & /api/v1/zoho (CRM)"]
        ZohoBooksRouter["/api/v1/integrations/zoho/books (Books)"]
    end

    TanStack -->|"JWT Bearer"| BackendAPI

    subgraph CoreServices ["Core Services Layer"]
        AuthSvc["AuthService"]
        IntSvc["IntegrationService"]
        SyncSvc["SyncService"]
        BooksTxSvc["BooksTransactionsService"]
        TokenMgr["Zoho Token Manager (Concurrency Lock & Refresh)"]
    end

    BackendAPI --> CoreServices

    subgraph StorageQueue ["Persistence & Queue"]
        PG[("PostgreSQL 16 (Encrypted Tokens, Users, Integrations, Records, History)")]
        Redis[("Redis 7 (Celery Broker & Cache)")]
        CeleryWorker["Celery Background Worker (async sync tasks)"]
    end

    CoreServices --> PG
    SyncSvc --> Redis
    BooksTxSvc --> Redis
    Redis --> CeleryWorker
    CeleryWorker --> CoreServices

    subgraph ExternalEcosystem ["External Cloud Providers"]
        ZohoAccounts["Zoho Accounts OAuth 2.0 (Multi-DC: .com, .in, .eu, etc.)"]
        ZohoCRMAPI["Zoho CRM v8 APIs"]
        ZohoBooksAPI["Zoho Books APIs"]
    end

    TokenMgr -->|"OAuth 2.0"| ZohoAccounts
    CoreServices -->|"REST / HTTPS"| ZohoCRMAPI
    CoreServices -->|"REST / HTTPS"| ZohoBooksAPI
```

---

## 2. Key Features

- **Multi-Tenant User Isolation:** Every ERP connection, token, synchronization log, and extracted integration record is strictly scoped to the authenticated user and tenant. Cross-tenant access attempts return `404 Not Found`.
- **At-Rest Token Encryption (Fernet AES-128-CBC):** OAuth 2.0 access and refresh tokens are encrypted at rest using a custom SQLAlchemy `TypeDecorator` (`EncryptedString`) with a 32-byte URL-safe base64 Fernet key. Plaintext tokens are never stored on disk, returned in API payloads, or printed in logs.
- **CSRF-Protected OAuth State Handshake:** Single-use, cryptographically signed JWT state tokens bind the tenant ID, connection label, data center, product (`crm` or `books`), and optional reauthorization integration ID with strict 15-minute expiration windows.
- **Global Data Center Routing:** Seamlessly connects across all global Zoho data centers (`us`, `in`, `eu`, `au`, `ca`, `jp`, `cn`) via dynamic accounts and API domain mapping.
- **Proactive & Reactive Token Refresh:** Detects impending token expiration with a 5-minute safety buffer; intercepts external HTTP 401 Unauthorized responses to perform automatic token refresh and request replay protected by per-integration asyncio locks.
- **In-Place Reauthorization (Zoho Books):** Existing Books connections can be reauthorized (e.g., when adding the `ZohoBooks.banking.READ` scope) without deleting the integration, losing stored records, or changing the selected organization.
- **Dual-Mode Data Synchronization:** Supports inline synchronous execution (`async_mode: false`) for instant feedback and background Celery queue dispatch (`async_mode: true`) via Redis with retry policies.
- **Structured Error Handling & Form UX:** Distinct machine-readable error codes (`USER_NOT_FOUND`, `INVALID_CREDENTIALS`) allow the login interface to guide unregistered users to account creation with email prefill via React Router navigation state.

---

## 3. Supported Data Extraction

### Zoho Books

Zoho Books data extraction is organization-scoped. An organization must be discovered and selected (`PUT /api/v1/integrations/zoho/books/{id}/organizations/{org_id}/select`) prior to record synchronization.

| Resource Category | Extraction Details | Storage & Scope |
| :--- | :--- | :--- |
| **Organizations** | Discovers all accessible Books organizations, currency codes, edition, and portal status. | `books_organizations` table |
| **Contacts (Customers & Vendors)** | Extracts contacts via `/contacts`, classifies records into customer and vendor types, and normalizes contact status, balances, and currency. | `integration_records` (`resource_type: contacts`) |
| **Invoices** | Extracts invoices via `/invoices`, normalizes totals, balance due, payment status, and computes paid amounts without floating-point inaccuracies. | `integration_records` (`resource_type: invoices`) |
| **Customer Payments** | Extracts customer payments from `/customerpayments` with invoice links, payment modes, and amounts. | `integration_records` (`resource_type: customer_payments`) |
| **Vendor Payments** | Extracts outgoing payments to vendors from `/vendorpayments` with bill associations and payment numbers. | `integration_records` (`resource_type: vendor_payments`) |
| **Sales Receipts** | Extracts direct sales receipts from `/salesreceipts` with tax totals, subtotal, and receipt numbers. | `integration_records` (`resource_type: sales_receipts`) |
| **Credit Note Refunds** | Extracts refunds issued on credit notes from `/creditnotes/refunds` with refund modes and amounts. | `integration_records` (`resource_type: credit_note_refunds`) |
| **Customer Payment Refunds** | Discovers parent customer payments and extracts nested refund records via `/customerpayments/{payment_id}/refunds`. | `integration_records` (`resource_type: customer_payment_refunds`) |
| **Vendor Payment Refunds** | Discovers parent vendor payments and extracts nested refunds via `/vendorpayments/{payment_id}/refunds`. | `integration_records` (`resource_type: vendor_payment_refunds`) |
| **Bank Transactions / Deposits** | Extracts bank transactions and deposits via `/banktransactions` (filtered by date range and transaction type). *Requires `ZohoBooks.banking.READ` OAuth scope.* | `integration_records` (`resource_type: bank_transactions`) |

> [!IMPORTANT]
> **Live Verification Status for Books Resources:**
> Organization listing, organization selection, contact synchronization, and invoice synchronization have been live-verified against the official Zoho Books API sandbox. Financial transactions and refund extraction modules are implemented, normalized, and covered by automated unit/integration test suites, but require the `ZohoBooks.banking.READ` OAuth scope on live accounts. If an integration was connected before this scope was added, trigger the **Reauthorize** action in the UI.

### Zoho CRM (v8 REST API)

All implemented CRM modules provide read-only paginated extraction with optional field selection and ISO-8601 incremental timestamps (`If-Modified-Since`):

| CRM Module | Endpoint | Normalized Schema Fields |
| :--- | :--- | :--- |
| **Contacts** | `GET /api/v1/zoho/contacts` | `id`, `first_name`, `last_name`, `email`, `phone`, `account_name`, `created_time`, `modified_time`, `raw_data` |
| **Leads** | `GET /api/v1/zoho/leads` | `id`, `first_name`, `last_name`, `company`, `email`, `phone`, `lead_status`, `lead_source`, `raw_data` |
| **Deals** | `GET /api/v1/zoho/deals` | `id`, `deal_name`, `amount`, `stage`, `closing_date`, `account_name`, `probability`, `raw_data` |
| **Accounts** | `GET /api/v1/zoho/accounts` | `id`, `account_name`, `phone`, `website`, `industry`, `billing_city`, `billing_country`, `raw_data` |

*Note: CRM record mutation (create, update, delete) is intentionally unsupported; the platform operates strictly as an integration and synchronization extraction engine.*

---

## 4. Technology Stack

### Backend
- **Runtime & Framework:** Python 3.11+, FastAPI (Starlette), Uvicorn
- **Database & ORM:** PostgreSQL 16, SQLAlchemy 2.0 (asyncio with `asyncpg` and `greenlet`), Alembic
- **Asynchronous Task Queue & Broker:** Celery 5.3+, Redis 7
- **HTTP Client:** HTTPX (async HTTP/1.1 & HTTP/2 ready)
- **Data Validation & Settings:** Pydantic v2, Pydantic-Settings
- **Security & Cryptography:** Cryptography (Fernet AES-128-CBC), PyJWT (HS256), Passlib (Bcrypt)
- **Testing:** Pytest, pytest-asyncio, aiosqlite

### Frontend
- **Framework & Language:** React 19, TypeScript 7
- **Build Tool:** Vite 8, `@vitejs/plugin-react`
- **Styling & Design System:** Tailwind CSS v4 (`@tailwindcss/vite`), Lucide React icons
- **State & Server Cache:** TanStack Query v5 (`@tanstack/react-query`)
- **Routing:** React Router v7 (`react-router-dom`)
- **HTTP Client:** Axios with JWT Bearer request interceptors and structured error normalization

---

## 5. Project Directory Structure

```text
OneDesk/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI application factory, CORS, exception handlers
│   │   ├── api/                             # API presentation layer
│   │   │   ├── dependencies.py              # get_current_user, get_db session dependency
│   │   │   ├── routes.py                    # Top-level API v1 router mounting
│   │   │   └── integrations_router.py       # Connection management, status probe, sync endpoints
│   │   ├── auth/                            # Authentication module
│   │   │   ├── router.py                    # /api/v1/auth (register, login, me)
│   │   │   ├── schemas.py                   # Pydantic schemas for user and token
│   │   │   └── service.py                   # Password verification, JWT creation, error codes
│   │   ├── core/                            # Infrastructure and settings
│   │   │   ├── config.py                    # BaseSettings with .env validation
│   │   │   ├── database.py                  # Async SQLAlchemy engine & session factory
│   │   │   ├── security.py                  # Fernet encryption/decryption, password hashing
│   │   │   └── logging.py                   # Centralized logger
│   │   ├── integrations/                    # ERP integrations module
│   │   │   ├── base.py                      # BaseERPIntegration abstract interface
│   │   │   ├── registry.py                  # Singleton IntegrationRegistry
│   │   │   └── zoho/                        # Zoho integration package
│   │   │       ├── oauth.py                 # Multi-datacenter OAuth state & token exchange
│   │   │       ├── token_manager.py         # Async locking token refresh manager
│   │   │       ├── client.py                # Zoho CRM v8 HTTP client
│   │   │       ├── books_client.py          # Zoho Books HTTP client (org headers, pagination)
│   │   │       ├── integration.py           # Zoho CRM adapter
│   │   │       ├── books_integration.py     # Zoho Books adapter
│   │   │       ├── router.py                # Zoho CRM OAuth endpoints (/connect, /callback)
│   │   │       ├── books_router.py          # Zoho Books endpoints (OAuth, orgs, transactions)
│   │   │       ├── crm_router.py            # Zoho CRM data endpoints (/contacts, /leads, etc.)
│   │   │       ├── exceptions.py            # Domain exceptions (tokens, rate limits, API)
│   │   │       ├── schemas/crm.py           # Pydantic normalized CRM schemas
│   │   │       └── services/                # CRM resource retrieval services
│   │   ├── models/                          # SQLAlchemy ORM models
│   │   │   ├── base.py                      # Base, TimestampMixin, EncryptedString TypeDecorator
│   │   │   ├── user.py                      # User model
│   │   │   ├── integration.py               # Integration connection model (encrypted tokens)
│   │   │   ├── books_organization.py        # Cached Zoho Books organizations
│   │   │   ├── integration_record.py        # Generic synced records table (org & product aware)
│   │   │   └── sync_history.py              # Synchronization audit tracking model
│   │   ├── repositories/                    # Database repository data access layer
│   │   ├── services/                        # Business services
│   │   │   ├── integration_service.py       # Integration resolution & ownership checks
│   │   │   ├── sync_service.py              # Unified sync orchestration & record upserts
│   │   │   ├── books_contacts_service.py    # Books contacts retrieval & stats
│   │   │   ├── books_invoices_service.py    # Books invoices retrieval & stats
│   │   │   └── books_transactions_service.py# Books financial transactions retrieval & stats
│   │   └── workers/                         # Asynchronous task workers
│   │       ├── celery_app.py                # Celery configuration
│   │       └── sync_worker.py               # Celery sync tasks (resource, books, financial)
│   ├── migrations/                          # Alembic migration scripts
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_schema.py        # Initial tables, indexes, encryption
│   │       ├── 002_product_aware_records.py # Product column and composite indexes
│   │       └── 003_books_organizations.py   # Zoho Books organization cache table
│   ├── tests/                               # Comprehensive automated test suite (82 tests)
│   ├── Dockerfile                           # Backend production container
│   ├── requirements.txt                     # Pinned Python dependencies
│   ├── pytest.ini                           # Pytest configuration
│   └── .env.example                         # Backend environment variables template
├── frontend/
│   ├── src/
│   │   ├── api/                             # Axios client & typed endpoint clients
│   │   ├── components/                      # UI design system components (Badge, Button, Drawer, etc.)
│   │   ├── context/                         # AuthContext & IntegrationContext providers
│   │   ├── pages/                           # Application route views
│   │   │   ├── auth/                        # LoginPage, RegisterPage
│   │   │   ├── dashboard/                   # DashboardPage
│   │   │   ├── integrations/                # IntegrationsPage, ZohoCallbackPage
│   │   │   ├── crm/                         # ContactsPage, LeadsPage, DealsPage, AccountsPage
│   │   │   ├── books/                       # BooksContactsPage, BooksInvoicesPage, BooksTransactionsPage
│   │   │   ├── sync/                        # SyncCenterPage
│   │   │   ├── activity/                    # ActivityPage (Audit logs)
│   │   │   └── settings/                    # SettingsPage
│   │   ├── types/                           # TypeScript interfaces
│   │   ├── App.tsx                          # App routing layout
│   │   └── main.tsx                         # Entrypoint
│   ├── package.json                         # Frontend dependencies & scripts
│   ├── vite.config.ts                       # Port 3000, path aliases, /api proxy
│   └── .env.example                         # Frontend environment variables template
├── docker-compose.yml                       # Multi-container orchestration (db, redis, backend, celery)
└── README.md                                # Platform documentation
```

---

## 6. Installation & Quickstart

### Prerequisites
- **Docker & Docker Compose** (recommended for production and containerized testing)
- Or for local development:
  - **Python 3.11+**
  - **Node.js 18+** & **npm**
  - Running **PostgreSQL 16** server
  - Running **Redis 7** instance

---

### Option A: Running with Docker Compose (Recommended)

1. **Clone repository:**
   ```bash
   git clone <repo-url>
   cd OneDesk
   ```

2. **Configure environment:**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   # Edit backend/.env with your encryption key and Zoho credentials
   ```

3. **Start all backend services:**
   ```bash
   docker compose up --build -d
   ```
   This launches:
   - `onedesk_postgres`: PostgreSQL 16 on port `5432`
   - `onedesk_redis`: Redis 7 on port `6379`
   - `onedesk_api`: FastAPI on `http://localhost:8000` (auto-runs migrations on startup)
   - `onedesk_celery_worker`: Background Celery queue processor

4. **Start the frontend application:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

### Option B: Local Development Setup (Without Docker)

#### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Generate and set a valid Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy output into ENCRYPTION_KEY in backend/.env

# Run Alembic migrations against local PostgreSQL
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

In a separate terminal, start the Celery worker:
```bash
cd backend
.venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info
```

#### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Open `http://localhost:3000`. Requests to `/api/v1/*` are automatically reverse-proxied to `http://localhost:8000`.

---

## 7. Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `PROJECT_NAME` | Name of the platform | `OneDesk` |
| `ENVIRONMENT` | Runtime environment (`development`, `production`) | `development` |
| `DEBUG` | Enable debug mode | `true` |
| `API_V1_STR` | Prefix for version 1 API endpoints | `/api/v1` |
| `SECRET_KEY` | Cryptographic secret for signing JWTs and OAuth states | *(Must be at least 32 characters)* |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Application session JWT expiration in minutes | `60` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ENCRYPTION_KEY` | 32-byte URL-safe base64 Fernet key for encrypting tokens at rest | *(Generate with `Fernet.generate_key()`)* |
| `POSTGRES_SERVER` | PostgreSQL hostname | `localhost` (or `db` in Docker) |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_USER` | PostgreSQL user | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `password` |
| `POSTGRES_DB` | PostgreSQL database name | `onedesk_db` |
| `DATABASE_URL` | SQLAlchemy async database connection URI | `postgresql+asyncpg://postgres:password@localhost:5432/onedesk_db` |
| `DATABASE_URL_SYNC` | Synchronous URI used by Celery tasks if needed | `postgresql+psycopg2://postgres:password@localhost:5432/onedesk_db` |
| `REDIS_URL` | Redis connection URI | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery message broker URI | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery results storage URI | `redis://localhost:6379/1` |
| `ZOHO_CLIENT_ID` | Zoho CRM OAuth Client ID | `your_zoho_crm_client_id` |
| `ZOHO_CLIENT_SECRET` | Zoho CRM OAuth Client Secret | `your_zoho_crm_client_secret` |
| `ZOHO_REDIRECT_URI` | Zoho CRM OAuth redirect callback URL | `http://localhost:8000/api/v1/integrations/zoho/callback` |
| `ZOHO_SCOPES` | Scopes requested for Zoho CRM | `ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ` |
| `ZOHO_DEFAULT_ACCOUNTS_URL` | Default accounts endpoint for US data center | `https://accounts.zoho.com` |
| `ZOHO_BOOKS_CLIENT_ID` | Zoho Books OAuth Client ID | `your_zoho_books_client_id` |
| `ZOHO_BOOKS_CLIENT_SECRET`| Zoho Books OAuth Client Secret | `your_zoho_books_client_secret` |
| `ZOHO_BOOKS_REDIRECT_URI` | Zoho Books OAuth redirect callback URL | `http://localhost:8000/api/v1/integrations/zoho/books/callback` |
| `ZOHO_BOOKS_SCOPES` | Scopes requested for Zoho Books (read-only) | *See Scopes section below* |
| `FRONTEND_BASE_URL` | Frontend URL for OAuth browser callback redirects | `http://localhost:3000` |
| `BACKEND_CORS_ORIGINS` | Permitted browser origins (JSON list or comma-separated) | `["http://localhost:3000","http://localhost:8000"]` |

### Frontend (`frontend/.env`)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `VITE_API_URL` | Base API prefix for Axios requests (proxied by Vite) | `/api/v1` |

---

## 8. Zoho OAuth 2.0 Setup Guide

Zoho CRM and Zoho Books use separate OAuth client applications in the [Zoho API Console](https://api-console.zoho.com/) to isolate scopes and credentials.

### 1. Register Client Applications in Zoho API Console

For each integration (CRM and Books):
1. Navigate to [Zoho API Console](https://api-console.zoho.com/).
2. Click **Add Client** and select **Server-based Applications**.
3. Configure redirect URIs:
   - **Zoho CRM Application:**
     - Authorized Redirect URI: `http://localhost:8000/api/v1/integrations/zoho/callback`
   - **Zoho Books Application:**
     - Authorized Redirect URI: `http://localhost:8000/api/v1/integrations/zoho/books/callback`
4. Copy the Client ID and Client Secret into `backend/.env`.

### 2. OAuth Scopes

#### Zoho CRM Scopes (`ZOHO_SCOPES`)
```text
ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ
```

#### Zoho Books Scopes (`ZOHO_BOOKS_SCOPES`)
```text
ZohoBooks.settings.READ,ZohoBooks.contacts.READ,ZohoBooks.invoices.READ,ZohoBooks.bills.READ,ZohoBooks.expenses.READ,ZohoBooks.customerpayments.READ,ZohoBooks.vendorpayments.READ,ZohoBooks.estimates.READ,ZohoBooks.creditnotes.READ,ZohoBooks.banking.READ
```

> [!IMPORTANT]
> **Banking Scope Requirement:**
> Extracting bank transactions and deposits via `/banktransactions` requires `ZohoBooks.banking.READ`. If an integration was connected prior to including this scope, click **Reauthorize** on the Books integration card in the UI.

### 3. In-Place Reauthorization Workflow

When a token expires, is revoked, or requires updated scopes (such as banking):
1. In the frontend **Integrations** tab, click **Reauthorize** on the affected Zoho Books card.
2. The platform generates an authorization URL carrying the existing `integration_id` in the signed OAuth state JWT.
3. Upon completing consent on Zoho Accounts, the callback handler updates the access token, refresh token, and expiration in place.
4. **Existing synchronized records, audit history, and the selected organization ID are completely preserved.**

---

## 9. API Reference

Interactive OpenAPI documentation is accessible at `http://localhost:8000/docs`.

### Authentication (`/api/v1/auth`)

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user account with duplicate email validation | No |
| `POST` | `/api/v1/auth/login` | Authenticate user credentials and receive JWT access token | No |
| `GET` | `/api/v1/auth/me` | Retrieve profile of the currently authenticated user | Yes (Bearer) |

### Generic Integration Management (`/api/v1/integrations`)

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/integrations` | List all connected ERP integrations for current tenant | Yes (Bearer) |
| `GET` | `/api/v1/integrations/{id}` | Retrieve connection details and metadata | Yes (Bearer) |
| `GET` | `/api/v1/integrations/{id}/status` | Probe live connection against the remote ERP provider | Yes (Bearer) |
| `DELETE` | `/api/v1/integrations/{id}` | Disconnect and delete integration connection and tokens | Yes (Bearer) |
| `POST` | `/api/v1/integrations/{id}/sync` | Trigger on-demand sync (inline or Celery background task) | Yes (Bearer) |
| `GET` | `/api/v1/integrations/{id}/sync-history` | View synchronization audit logs and job execution details | Yes (Bearer) |

### Zoho CRM Integration (`/api/v1/integrations/zoho` & `/api/v1/zoho`)

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/integrations/zoho/connect` | Generate Zoho CRM OAuth authorization URL and CSRF state | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/callback` | OAuth redirect callback handler (exchanges code for tokens) | No |
| `GET` | `/api/v1/zoho/contacts` | Paginated CRM contacts list with search, fields, and delta filters | Yes (Bearer) |
| `GET` | `/api/v1/zoho/contacts/{id}` | Retrieve single CRM contact record by ID | Yes (Bearer) |
| `GET` | `/api/v1/zoho/leads` | Paginated CRM leads list | Yes (Bearer) |
| `GET` | `/api/v1/zoho/leads/{id}` | Retrieve single CRM lead record by ID | Yes (Bearer) |
| `GET` | `/api/v1/zoho/deals` | Paginated CRM deals list | Yes (Bearer) |
| `GET` | `/api/v1/zoho/deals/{id}` | Retrieve single CRM deal record by ID | Yes (Bearer) |
| `GET` | `/api/v1/zoho/accounts` | Paginated CRM accounts list | Yes (Bearer) |
| `GET` | `/api/v1/zoho/accounts/{id}` | Retrieve single CRM account record by ID | Yes (Bearer) |

### Zoho Books Integration (`/api/v1/integrations/zoho/books`)

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/integrations/zoho/books/connect` | Generate Zoho Books OAuth URL (supports `integration_id` for reauth) | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/callback` | OAuth redirect callback handler for Zoho Books | No |
| `GET` | `/api/v1/integrations/zoho/books/{id}/organizations` | List cached organizations for the connection | Yes (Bearer) |
| `POST` | `/api/v1/integrations/zoho/books/{id}/organizations/refresh` | Discover and refresh organizations live from Zoho Books | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/organizations/selected` | View currently selected active organization | Yes (Bearer) |
| `PUT` | `/api/v1/integrations/zoho/books/{id}/organizations/{org_id}/select` | Select active organization for subsequent extractions | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/contacts` | List synced Books contacts (supports `contact_type: customer\|vendor`) | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/contacts/stats` | Aggregate contact counts (total, customer, vendor) | Yes (Bearer) |
| `POST` | `/api/v1/integrations/zoho/books/{id}/contacts/refresh` | Trigger sync for Books contacts | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/invoices` | List synced Books invoices (with status, balance, totals) | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/invoices/stats` | Aggregate invoice counts, balances, and totals by currency | Yes (Bearer) |
| `POST` | `/api/v1/integrations/zoho/books/{id}/invoices/refresh` | Trigger sync for Books invoices | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/transactions` | List synced financial transactions (filter by date, type, search) | Yes (Bearer) |
| `GET` | `/api/v1/integrations/zoho/books/{id}/transactions/stats` | Aggregate financial transactions counts and currency totals | Yes (Bearer) |
| `POST` | `/api/v1/integrations/zoho/books/{id}/transactions/refresh` | Trigger sync for Books financial transactions (inline or Celery) | Yes (Bearer) |

---

## 10. Synchronization Workflow & Status Tracking

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Frontend
    participant API as OneDesk API
    participant DB as PostgreSQL
    participant Worker as Celery Worker
    participant Zoho as Zoho Books / CRM API

    User->>API: POST /integrations/{id}/sync (async_mode: true)
    API->>DB: Create SyncHistory (status: "in_progress")
    API->>Worker: Dispatch sync task via Redis
    API-->>User: 200 OK (status: "queued" / "in_progress")

    Worker->>DB: Fetch Integration & Decrypt OAuth Tokens
    Worker->>Zoho: GET /resource (with pagination & delta headers)
    Zoho-->>Worker: JSON Records Page
    Worker->>DB: Upsert normalized records into integration_records
    
    alt Synchronization Succeeded
        Worker->>DB: Update SyncHistory (status: "completed", records_processed, successful_at)
    else Synchronization Encountered Error
        Worker->>DB: Update SyncHistory (status: "failed", error_message)
    end

    User->>API: GET /integrations/{id}/sync-history
    API->>DB: Query SyncHistory
    DB-->>API: List of sync runs
    API-->>User: Display status, records processed, duration, and error diagnostics
```

---

## 11. Testing & Verification

### Running Backend Tests

All 82 automated backend tests execute against an isolated in-memory SQLite database (`aiosqlite`) with mocked HTTPX clients:

```bash
cd backend
.venv\Scripts\activate
pytest -v
```

**Test Suite Coverage:**
- `test_auth.py`: Registration, login error codes (`USER_NOT_FOUND`, `INVALID_CREDENTIALS`), and `/me`.
- `test_crm_and_integrations.py`: Connection lifecycle, multi-tenant isolation, CRM record extraction.
- `test_milestone2_persistence.py`: Product-aware records, tenant scoping, deduplication upserts.
- `test_oauth_security_and_lifecycle.py`: Fernet encryption roundtrip, CSRF token replay protection, sanitization.
- `test_phase1.py`: Core health check and security hashing.
- `test_sync.py`: On-demand and delta synchronization workflows.
- `test_zoho_books_contacts.py`: Customer and vendor classification, pagination parsing.
- `test_zoho_books_invoices.py`: Invoice normalization, decimal precision, pagination.
- `test_zoho_books_oauth.py`: Books OAuth URL generation, state validation, reauthorization in-place.
- `test_zoho_books_organizations.py`: Organization discovery, caching, selection.
- `test_zoho_books_transactions.py`: Financial transaction normalization, date ranges, refunds, Celery task registration.
- `test_zoho_client_and_tokens.py`: Token expiration checks, 401 token refresh retry, rate limiting backoff.
- `test_zoho_oauth.py`: CRM OAuth state generation and callback handling.

### Running Frontend Checks & Build

```bash
cd frontend

# Verify TypeScript compilation and Vite production bundle
npm run build
```

---

## 12. Troubleshooting & Security Considerations

### Troubleshooting Common Issues

1. **`ValueError: Fernet key must be 32 url-safe base64-encoded bytes`:**
   - The `ENCRYPTION_KEY` in `backend/.env` is missing or invalid.
   - Generate a valid key using:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
2. **Zoho OAuth Redirect URI Mismatch (`redirect_uri_mismatch`):**
   - Verify that the redirect URI registered in the Zoho API Console matches `ZOHO_REDIRECT_URI` or `ZOHO_BOOKS_REDIRECT_URI` in `backend/.env`.
3. **Missing Financial Transactions / Banking API Errors:**
   - Zoho Books banking endpoints require `ZohoBooks.banking.READ`.
   - Ensure this scope is in `ZOHO_BOOKS_SCOPES` and click **Reauthorize** on the Books connection card in the UI.
4. **Celery Worker Connection Refused:**
   - Verify Redis is running and reachable on `REDIS_URL`. If running with Docker Compose, ensure `REDIS_URL="redis://redis:6379/0"`.

### Security Architecture

- **Zero Token Leakage:** OAuth access tokens, refresh tokens, and encryption keys are strictly omitted from API serializer schemas, frontend state, and log outputs.
- **Single-Use Signed States:** OAuth state parameters are HMAC-signed JWTs with 15-minute expirations to prevent CSRF and replay attacks.
- **Tenant Isolation:** All database queries enforce `user_id` scoping to prevent cross-tenant data leakage.
- **Encryption at Rest:** Sensitive credentials stored in PostgreSQL use AES-128-CBC encryption via Fernet.
