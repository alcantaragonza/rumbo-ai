from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["salud"])


@router.get("/health")
def health() -> dict[str, str]:
    """Comprueba que el proceso está vivo sin tocar la base de datos."""
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.env,
        "version": "0.1.0",
    }
