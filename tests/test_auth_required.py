def test_protected_endpoints_require_authentication(client) -> None:
    assert client.get("/api/v1/destinations").status_code == 401
    assert client.get("/api/v1/activities").status_code == 401
    assert client.get("/api/v1/users").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
