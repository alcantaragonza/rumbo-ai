from app.core.security import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    hashed = hash_password("Secret123!")

    assert hashed != "Secret123!"
    assert verify_password("Secret123!", hashed)
    assert not verify_password("incorrecta", hashed)
