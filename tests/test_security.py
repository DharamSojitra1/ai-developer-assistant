from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_password_hashing():
    password = "StrongPassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_access_token():
    token = create_access_token("user_123")
    payload = decode_token(token)

    assert payload["sub"] == "user_123"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_refresh_token():
    token = create_refresh_token("user_123")
    payload = decode_token(token)

    assert payload["sub"] == "user_123"
    assert payload["type"] == "refresh"
    assert "jti" in payload
    assert "exp" in payload