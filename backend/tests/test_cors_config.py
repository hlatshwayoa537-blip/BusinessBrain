from app.core.config import Settings


def test_base44_preview_origin_is_in_cors_allowlist():
    settings = Settings(
        frontend_origins="https://businessbrain-web.onrender.com,http://localhost:5173",
        base44_preview_origin="https://preview--vexion-next-core.base44.app",
    )

    assert "https://preview--vexion-next-core.base44.app" in settings.cors_origins
    assert "https://businessbrain-web.onrender.com" in settings.cors_origins
    assert "http://localhost:5173" in settings.cors_origins
    assert "*" not in settings.cors_origins


def test_cors_origin_is_not_duplicated():
    settings = Settings(
        frontend_origins="https://preview--vexion-next-core.base44.app",
        base44_preview_origin="https://preview--vexion-next-core.base44.app/",
    )

    assert settings.cors_origins.count("https://preview--vexion-next-core.base44.app") == 1
