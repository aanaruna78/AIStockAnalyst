"""Tests for services/api_gateway/auth_utils.py — JWT & password utilities."""
import pytest
import sys
from datetime import timedelta
from services.api_gateway.auth_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)

# passlib+bcrypt has a known bug on Python 3.13+ with newer bcrypt versions
_bcrypt_broken = sys.version_info >= (3, 13)


class TestPasswordHashing:
    @pytest.mark.skipif(_bcrypt_broken, reason="passlib bcrypt incompatible with Python 3.13+")
    def test_hash_and_verify(self):
        raw = "MySecureP@ss123"
        hashed = get_password_hash(raw)
        assert hashed != raw
        assert verify_password(raw, hashed) is True

    @pytest.mark.skipif(_bcrypt_broken, reason="passlib bcrypt incompatible with Python 3.13+")
    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    @pytest.mark.skipif(_bcrypt_broken, reason="passlib bcrypt incompatible with Python 3.13+")
    def test_hash_is_unique(self):
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        # bcrypt salts differ each call
        assert h1 != h2


class TestJWT:
    def test_create_and_decode_token(self):
        data = {"sub": "user@example.com", "role": "user"}
        token = create_access_token(data)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"
        assert payload["role"] == "user"
        assert "exp" in payload

    def test_token_with_custom_expiry(self):
        data = {"sub": "admin@example.com"}
        token = create_access_token(data, expires_delta=timedelta(minutes=5))
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "admin@example.com"

    def test_invalid_token_returns_none(self):
        result = decode_access_token("this.is.not.a.valid.jwt")
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "user@test.com"})
        # Tamper by replacing the entire signature portion with garbage
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".TAMPERED_SIGNATURE_INVALID"
        result = decode_access_token(tampered)
        assert result is None

    def test_token_contains_exp_claim(self):
        token = create_access_token({"sub": "test"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_empty_payload(self):
        token = create_access_token({})
        payload = decode_access_token(token)
        assert payload is not None
        assert "exp" in payload
