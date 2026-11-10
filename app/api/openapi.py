from fastapi.openapi.utils import get_openapi

OPENAPI_TAGS = [
    {"name": "salud", "description": "Estado del servicio."},
    {"name": "autenticación", "description": "Sesiones web y tokens para consumidores externos."},
    {"name": "catálogo", "description": "Destinos y actividades turísticas."},
    {"name": "usuarios", "description": "Administración de usuarios y límites de tokens."},
    {"name": "historial", "description": "Conversaciones y mensajes."},
    {"name": "consumo", "description": "Consultas y tokens acumulados por servicio."},
    {"name": "servicios", "description": "Servicios de IA disponibles."},
    {"name": "IA", "description": "Verificación de cuota antes de ejecutar una llamada."},
    {"name": "chat", "description": "Chatbot con RAG y memoria conversacional."},
    {"name": "agentes", "description": "Itinerarios y ajustes multi-paso."},
    {"name": "reportes", "description": "Agregados diarios para la web y Power BI."},
]

PUBLIC_PATHS = {
    "/health",
    "/api/v1/auth/login",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}


def install_openapi(app, *, title: str, version: str, description: str) -> None:
    """Añade esquemas de seguridad y metadatos al OpenAPI generado."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=title,
            version=version,
            description=description,
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )
        components = schema.setdefault("components", {})
        components["securitySchemes"] = {
            "sessionCookie": {
                "type": "apiKey",
                "in": "cookie",
                "name": "rumbo_session",
                "description": "Cookie de sesión creada por /api/v1/auth/login.",
            },
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "rumbo_...",
                "description": "Token creado en /api/v1/auth/tokens.",
            },
        }
        for path, operations in schema.get("paths", {}).items():
            if path in PUBLIC_PATHS:
                continue
            for operation in operations.values():
                if isinstance(operation, dict):
                    operation.setdefault(
                        "security",
                        [{"sessionCookie": []}, {"bearerAuth": []}],
                    )
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
