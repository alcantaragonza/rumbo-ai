from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.openapi import OPENAPI_TAGS, install_openapi
from app.api.routes import (
    agents,
    ai,
    auth,
    catalog,
    chat,
    health,
    history,
    reports,
    services,
    usage,
    users,
)
from app.core.config import get_settings

settings = get_settings()

DESCRIPTION = """
API de Rumbo AI: asistencia y planificación turística con IA.

**Autenticación**: la interfaz web usa la cookie de sesión que crea
`POST /api/v1/auth/login`. Los consumidores externos usan
`Authorization: Bearer rumbo_...`, creado en `POST /api/v1/auth/tokens`.

**Errores**: todas las respuestas de error tienen la forma
`{"code": "...", "message": "...", "details": ...}`.

**Fechas** en UTC y **costos** en USD.
"""

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=DESCRIPTION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=OPENAPI_TAGS,
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(catalog.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(history.router, prefix=settings.api_v1_prefix)
app.include_router(usage.router, prefix=settings.api_v1_prefix)
app.include_router(services.router, prefix=settings.api_v1_prefix)
app.include_router(ai.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
app.include_router(agents.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)

register_exception_handlers(app)
install_openapi(
    app,
    title=settings.app_name,
    version="0.1.0",
    description=DESCRIPTION,
)

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=WEB_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "health")):
            raise HTTPException(status_code=404, detail="Ruta no encontrada")
        candidate = WEB_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
