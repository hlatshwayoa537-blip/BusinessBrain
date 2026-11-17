# VEXION

**See More. Know More. Grow More.**

An AI-powered business operating system built for Africa and the world.

## Product direction

VEXION brings core business operations, business intelligence, AI assistance and business-to-business collaboration into one secure workspace. AI recommendations must be grounded in authorised business records; consequential actions remain under human control.

## Repository structure

- `backend/` — Python + FastAPI API, SQLAlchemy models, Alembic migrations and tests
- `frontend/` — React + TypeScript web application
- `.env.example` — local configuration template (contains no production secrets)

## Local development

Use Python 3.11 or newer and Node.js 22 or newer.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload
```

API: `http://localhost:8000`  
Interactive API documentation: `http://localhost:8000/docs`  
Health check: `http://localhost:8000/api/v1/health`

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Web application: `http://localhost:5173`.

## Authentication API

- `POST /api/v1/auth/register` — create a user, business workspace and owner membership in one transaction.
- `POST /api/v1/auth/login` — verify credentials and issue a signed bearer access token.
- `GET /api/v1/auth/me` — return the authenticated user; requires `Authorization: Bearer <token>`.

Registration requires a full name, valid email, password of at least 12 characters, business name and industry. The country defaults to `ZA`. Passwords are hashed with Argon2 through pwdlib. Duplicate email addresses are rejected.

## Database

PostgreSQL is the target database. Schema changes are managed with Alembic:

```bash
cd backend
alembic upgrade head
```

For automated tests, the test suite overrides the database dependency with an isolated in-memory SQLite database.

## Engineering principles

- Keep tenant data isolated by business workspace; enforce access on the server.
- Never store plaintext passwords or commit production secrets.
- Treat financial figures as actuals, estimates or assumptions; never invent business records.
- Require explicit approval for consequential AI-assisted actions.
- Test permissions, validation, error handling and data isolation before release.

## Current build status

Implemented: initial React dashboard shell, FastAPI health endpoint, registration, login, signed bearer tokens, authenticated user profile, user/business/owner-membership persistence and initial Alembic schema migration.

Not yet implemented: email verification, password reset, refresh-token rotation, team invitations, subscription assessment, business onboarding UI and production deployment. These must not be represented as live until implemented and tested.


## Business Network: private conversations and Deal Rooms

The Business Network supports authenticated, invitation-only business conversations. A host selects a listed business, sets a conversation password, and sends an invitation. The password is stored as a one-way password hash and must be shared separately with the recipient; it is never included in the invitation response or notification.

Recipients can view incoming invitations, accept only after entering the password, or reject them. Invitations expire after seven days. Acceptance creates a private conversation between the two business workspaces.

Conversation and Deal Room endpoints require an authenticated member of one of the two participating businesses. Messages are scoped to that conversation or Deal Room. Either participant can create the single Deal Room associated with a conversation and update its status: discussion, negotiation, proposal submitted, agreement reached, deal completed, or deal cancelled.

Key API routes (under `/api/v1`):

- `POST /network/invitations`, `GET /network/invitations?direction=incoming|outgoing|all`
- `POST /network/invitations/{id}/accept`, `POST /network/invitations/{id}/reject`
- `GET /network/conversations`, `GET|POST /network/conversations/{id}/messages`
- `POST /network/conversations/{id}/deal-room`
- `GET|POST /network/deal-rooms/{id}/messages`, `PATCH /network/deal-rooms/{id}`

Migration `0005_business_conversations_deal_rooms` creates the invitation, conversation, message and Deal Room tables. Apply migrations with `alembic upgrade head` before using these routes in a deployed environment.

This initial release provides authenticated request/response messaging, not real-time push notifications, file attachments, video calls, contract e-signatures or legal deal execution. Any binding commercial agreement still requires authorised human review and approval.


## Deal Room quotations

Deal Room participants can create and share structured quotations with up to 50 line items, currency, per-line tax rates, notes and an optional validity date. The API calculates subtotal, tax and total server-side using decimal arithmetic. Both participating businesses can view quotations; only the receiving business can accept or decline, and only the issuing business can withdraw an unanswered quotation. Quotation responses are workflow records and do not constitute a signed contract or legal acceptance of binding terms.

Routes (under `/api/v1`): `POST /network/deal-rooms/{room_id}/quotations`, `GET /network/deal-rooms/{room_id}/quotations`, `POST /network/quotations/{quotation_id}/decision`, and `POST /network/quotations/{quotation_id}/withdraw`.

Migration `0006_deal_room_quotations` follows migration 0005. Run `alembic upgrade head` before using quotations in a deployed environment.

Binary document uploads are not enabled yet. They require private object storage, short-lived signed upload/download URLs, file validation and malware scanning; no public file URLs or local ephemeral Render disk are used as a shortcut.


## Private Deal Room document sharing

Participants can upload PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG and JPG/JPEG files up to 25 MB. The API issues short-lived presigned PUT URLs to a **private S3-compatible bucket**. Uploads first land under a quarantine key and are not listed or downloadable. The completion endpoint verifies the stored byte count and content type, streams the object to a configured ClamAV daemon, and only promotes a clean file to its private final key. Malware detections are rejected and the quarantined object is deleted. Scanner outages fail closed: the upload remains pending in quarantine and no download URL is issued.

Only authenticated members of either business in the active Deal Room can list or download clean files. Download links are short-lived (60 seconds by default). Only the business that uploaded a file can delete it. File bytes are stored outside the application database; the database stores access-controlled metadata only.

### Required deployment configuration

Set these backend environment variables before enabling uploads:

- `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`; set `S3_ENDPOINT_URL` for providers such as Cloudflare R2 or another S3-compatible service.
- `CLAMAV_HOST`, `CLAMAV_PORT` and optionally `CLAMAV_TIMEOUT_SECONDS` for a reachable ClamAV daemon.
- Optionally tune `S3_UPLOAD_URL_EXPIRE_SECONDS` and `S3_DOWNLOAD_URL_EXPIRE_SECONDS`.

The bucket must remain private, have public access blocked, and have lifecycle cleanup configured for abandoned `quarantine/` objects. Configure bucket CORS to allow the exact frontend origins and browser `POST` requests with the `Content-Type` form field. Do not expose bucket credentials to the frontend. Deploy and monitor ClamAV separately; if it is unavailable, VEXION deliberately refuses to release files.

Migration `0007_deal_room_files` follows migration 0006. Apply `alembic upgrade head` before use. Storage and ClamAV credentials are not configured by this code change; document upload remains unavailable until the deployment environment and private bucket CORS are configured.


## VEXION POS ingestion foundation

VEXION supports a provider-neutral transaction model. POS providers can connect through a tested direct API adapter, webhook or authorised local connector. The shared ingestion endpoint accepts normalized sale, refund and void events. A POS provider is not considered integrated until its adapter has been implemented and tested against that provider.

- `POST /api/v1/pos/connections` — owner/admin registers a connection and receives a one-time connector secret.
- `GET /api/v1/pos/connections` — list connections for the authenticated business.
- `POST /api/v1/pos/ingest/{connection_id}` — connector sends a normalized transaction using the `X-Vexion-Secret` header.
- `GET /api/v1/pos/transactions` — list recent business transactions.
- `GET /api/v1/pos/summary` — aggregate sales, refunds, voids and net sales.

Connector secrets are stored only as SHA-256 digests and are shown only when created or rotated. Ingestion is idempotent per connection and external transaction ID. POS actuals are kept separate from manually entered finance records to avoid double-counting. The current foundation does not itself provide vendor-specific adapters, CSV upload parsing, item-level stock feeds or a local agent installer.
