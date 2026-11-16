from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health", summary="API health check")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "businessbrain-api"}
