# BusinessBrain

**Your Business. One Intelligent Brain.**

An AI-powered business operating system built for Africa and the world.

## Product direction

BusinessBrain brings core business operations, business intelligence, AI assistance and business-to-business collaboration into one secure workspace. AI recommendations must be grounded in authorised business records; consequential actions remain under human control.

## Repository structure

- `backend/` — Python + FastAPI API and automated tests
- `frontend/` — React + TypeScript web application
- `.env.example` — local configuration template (contains no production secrets)

## Local development

### Backend

Use Python 3.11 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

Web application: `http://localhost:5173`. It checks the backend health endpoint and displays the connection state.

### Configuration

Copy `.env.example` to `.env` and replace development secrets before running outside local development. Never commit real credentials or production secrets.

## Engineering principles

- Keep tenant data isolated by business workspace.
- Enforce authorisation on the server, not only in the interface.
- Hash passwords with a modern password-hashing algorithm; never store plaintext passwords.
- Treat financial figures as actuals, estimates or assumptions, and never invent business records.
- Require explicit approval for consequential AI-assisted actions.
- Test permissions, validation, error handling and data isolation before release.

## Current build status

The initial application shell and API health check are the first foundation milestone. Authentication, business workspaces, database persistence, onboarding and subscription assessment are subsequent implementation milestones; they must not be considered live until implemented and tested.
