"""Tests for authentication utilities."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from fourdpocket.api.auth_utils import (
    _JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestHashPassword:
    def test_hash_password_returns_string(self):
        result = hash_password("TestPass123!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_different_each_time(self):
        h1 = hash_password("SamePass")
        h2 = hash_password("SamePass")
        assert h1 != h2  # bcrypt uses random salt

    def test_hash_password_unicode(self):
        result = hash_password("Password with unicode: \u00e9\u00e0\u00fc")
        assert isinstance(result, str)


class TestVerifyPassword:
    def test_verify_password_correct(self):
        pw = "TestPass123!"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("CorrectPass")
        assert verify_password("WrongPass", hashed) is False

    def test_verify_password_empty(self):
        hashed = hash_password("NonEmpty")
        assert verify_password("", hashed) is False

    def test_verify_password_wrong_type(self):
        hashed = hash_password("Password123")
        # Passing None should raise TypeError or similar
        with pytest.raises(Exception):
            verify_password(None, hashed)  # type: ignore


class TestCreateAccessToken:
    def test_create_access_token_returns_jwt_string(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        assert isinstance(token, str)
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_create_access_token_default_expiry(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = jwt.decode(token, settings.auth.secret_key, algorithms=[_JWT_ALGORITHM])
        # Should expire in the future (default is 30 min)
        assert payload["exp"] > datetime.now(timezone.utc).timestamp() + 60

    def test_create_access_token_custom_expiry(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        token = create_access_token(user_id, expires_delta=timedelta(hours=1))
        payload = jwt.decode(token, settings.auth.secret_key, algorithms=[_JWT_ALGORITHM])
        assert payload["exp"] > datetime.now(timezone.utc).timestamp() + 3000

    def test_create_access_token_includes_claims(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = jwt.decode(token, settings.auth.secret_key, algorithms=[_JWT_ALGORITHM])
        assert payload["sub"] == str(user_id)
        assert payload["iss"] == "4dpocket"
        assert "iat" in payload
        assert "exp" in payload


class TestDecodeAccessToken:
    def test_decode_valid_token(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)

    def test_decode_expired_token_raises(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        # Create a token that's already expired
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "iss": "4dpocket",
        }
        token = jwt.encode(payload, settings.auth.secret_key, algorithm=_JWT_ALGORITHM)
        with pytest.raises(ValueError, match="expired"):
            decode_access_token(token)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        # Tamper with the signature
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".tampered_signature"
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(tampered)

    def test_decode_wrong_issuer_not_validated(self):
        """decode_access_token does not validate the 'iss' claim, so wrong issuer is accepted."""
        from fourdpocket.config import get_settings
        settings = get_settings()
        user_id = uuid.uuid4()
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": "wrong-issuer",
        }
        token = jwt.encode(payload, settings.auth.secret_key, algorithm=_JWT_ALGORITHM)
        # The implementation does not validate issuer, so it should decode successfully
        result = decode_access_token(token)
        assert result["sub"] == str(user_id)


class TestJWTAlgorithmFixed:
    def test_jwt_algorithm_is_hs256(self):
        # The algorithm should always be HS256 to prevent algorithm confusion attacks
        assert _JWT_ALGORITHM == "HS256"
