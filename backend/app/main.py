from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.network import router as network_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.quotations import router as quotations_router
from app.api.routes.deal_files import router as deal_files_router
from app.api.routes.recruitment import router as recruitment_router
from app.api.routes.staff import router as staff_router
from app.api.routes.finance import router as finance_router
from app.api.routes.pos import router as pos_router
from app.api.routes.invoices import router as invoices_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply pending schema migrations before accepting requests. Fail startup if
    # the database cannot be migrated so the API never serves against a partial schema.
    # Tests use an isolated SQLite database supplied by the test fixtures.
    # Never run production Alembic migrations against the developer/CI database.
    if settings.app_env.lower() != "test":
        backend_dir = Path(__file__).resolve().parents[1]
        alembic_config = Config(str(backend_dir / "alembic.ini"))
        command.upgrade(alembic_config, "head")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="The secure business operating system API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(network_router, prefix=settings.api_v1_prefix)
app.include_router(conversations_router, prefix=settings.api_v1_prefix)
app.include_router(quotations_router, prefix=settings.api_v1_prefix)
app.include_router(deal_files_router, prefix=settings.api_v1_prefix)
app.include_router(recruitment_router, prefix=settings.api_v1_prefix)
app.include_router(staff_router, prefix=settings.api_v1_prefix)
app.include_router(finance_router, prefix=settings.api_v1_prefix)
app.include_router(pos_router, prefix=settings.api_v1_prefix)
app.include_router(invoices_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "VEXION API", "docs": "/docs"}
