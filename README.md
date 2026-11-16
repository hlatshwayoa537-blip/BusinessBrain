# BusinessBrain

**Your Business. One Intelligent Brain.**

An AI-powered business operating system built for Africa and the world.

## Product direction

BusinessBrain brings core business operations, business intelligence, AI assistance and business-to-business collaboration into one secure workspace. AI recommendations must be grounded in authorised business records; consequential actions remain under human control.

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
