from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db

router = APIRouter(tags=["system"])


@router.get("/health", summary="API liveness check")
async def health_check() -> dict[str, str]:
    """Confirm that the API process is running; this does not imply dependencies are ready."""
    return {"status": "ok", "service": "vexion-api"}


@router.get("/health/ready", summary="Production dependency readiness check")
def readiness_check(db: Session = Depends(get_db)):
    """Check the database and schema without exposing connection details or secrets."""
    try:
        db.execute(text("SELECT 1"))
        schema_revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {"database": "unavailable", "schema": "unavailable"},
            },
        )

    if not schema_revision:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {"database": "ok", "schema": "not_initialized"},
            },
        )

    document_storage_ready = all(
        (
            settings.s3_bucket,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
            settings.clamav_host,
        )
    )
    payfast_configured = all(
        (
            settings.payfast_merchant_id,
            settings.payfast_merchant_key,
            settings.payfast_passphrase,
        )
    )
    email_configured = all(
        (settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)
    )

    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "schema_revision": schema_revision,
        },
        "optional_integrations": {
            "document_storage_and_scanning": (
                "configured" if document_storage_ready else "not_configured"
            ),
            "payfast": "configured" if payfast_configured else "not_configured",
            "email": "configured" if email_configured else "not_configured",
        },
    }
