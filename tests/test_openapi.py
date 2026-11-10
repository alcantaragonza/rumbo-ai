def test_openapi_has_security_and_paths(client) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    schemes = schema["components"]["securitySchemes"]
    assert "sessionCookie" in schemes
    assert "bearerAuth" in schemes

    paths = schema["paths"]
    for path in (
        "/api/v1/auth/login",
        "/api/v1/chat",
        "/api/v1/agents/itinerary",
        "/api/v1/history/conversations",
        "/api/v1/usage",
        "/api/v1/users",
    ):
        assert path in paths

    assert "security" not in paths["/api/v1/auth/login"]["post"]
    assert {"sessionCookie": []} in paths["/api/v1/chat"]["post"]["security"]


def test_swagger_and_redoc_are_served(client) -> None:
    docs = client.get("/api/docs")
    redoc = client.get("/api/redoc")

    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
    assert redoc.status_code == 200
