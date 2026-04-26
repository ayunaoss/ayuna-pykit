"""
Tests for ayuna_core.utils.jwtagent module.

Tests the JWTAgent class and related models:
- JWTPayload, JWTReference, JWTFailure models
- Token generation and verification
"""

import math
from http import HTTPStatus

import pytest

from ayuna_core.utils.chrono import Chrono
from ayuna_core.utils.jwtagent import (
    JWTAgent,
    JWTFailure,
    JWTPayload,
    JWTReference,
)


class TestJWTPayloadModel:
    """Tests for JWTPayload model."""

    def test_create_payload_basic(self):
        """Test creating a basic JWT payload."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now,
            exp=now + 3600,
        )

        assert payload.iss == "test-issuer"
        assert payload.aud == "test-audience"
        assert payload.sub == "test-subject"
        assert payload.iat == now
        assert payload.exp == now + 3600
        assert payload.nbf is None
        assert payload.custom == {}

    def test_create_payload_with_nbf(self):
        """Test creating payload with not-before claim."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="issuer",
            aud="audience",
            sub="subject",
            iat=now,
            exp=now + 3600,
            nbf=now + 60,
        )

        assert payload.nbf == now + 60

    def test_create_payload_with_custom_claims(self):
        """Test creating payload with custom claims."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="issuer",
            aud="audience",
            sub="subject",
            iat=now,
            exp=now + 3600,
            custom={"role": "admin", "tenant_id": "123"},
        )

        assert payload.custom["role"] == "admin"
        assert payload.custom["tenant_id"] == "123"


class TestJWTReferenceModel:
    """Tests for JWTReference model."""

    def test_create_reference(self):
        """Test creating a JWT reference."""
        reference = JWTReference(
            issuers=["issuer1", "issuer2"],
            audience=["aud1", "aud2"],
            subject="expected-subject",
        )

        assert reference.issuers == ["issuer1", "issuer2"]
        assert reference.audience == ["aud1", "aud2"]
        assert reference.subject == "expected-subject"
        assert math.isclose(reference.leeway, 0.0)

    def test_create_reference_with_leeway(self):
        """Test creating reference with leeway."""
        reference = JWTReference(
            issuers=["issuer"],
            audience=["audience"],
            subject="subject",
            leeway=30.0,
        )

        assert math.isclose(reference.leeway, 30.0)


class TestJWTFailureModel:
    """Tests for JWTFailure model."""

    def test_create_failure(self):
        """Test creating a JWT failure."""
        failure = JWTFailure(
            status=HTTPStatus.UNAUTHORIZED,
            reason="Token expired",
        )

        assert failure.status == HTTPStatus.UNAUTHORIZED
        assert failure.reason == "Token expired"

    def test_failure_status_codes(self):
        """Test various HTTP status codes."""
        failure_401 = JWTFailure(status=HTTPStatus.UNAUTHORIZED, reason="Unauthorized")
        failure_403 = JWTFailure(status=HTTPStatus.FORBIDDEN, reason="Forbidden")

        assert failure_401.status == HTTPStatus.UNAUTHORIZED
        assert failure_403.status == HTTPStatus.FORBIDDEN


class TestJWTAgentTokenGeneration:
    """Tests for JWTAgent token generation."""

    @pytest.fixture
    def signing_key(self):
        """Fixture that provides a signing key."""
        return "test-secret-key-for-jwt-signing"

    def test_generate_token(self, signing_key):
        """Test generating a JWT token."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now,
            exp=now + 3600,
        )

        token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT format: header.payload.signature
        parts = token.split(".")
        assert len(parts) == 3

    def test_generate_token_with_custom_claims(self, signing_key):
        """Test generating token with custom claims."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="issuer",
            aud="audience",
            sub="subject",
            iat=now,
            exp=now + 3600,
            custom={"role": "admin"},
        )

        token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        assert isinstance(token, str)


class TestJWTAgentVerification:
    """Tests for JWTAgent token verification."""

    @pytest.fixture
    def signing_key(self):
        """Fixture that provides a signing key."""
        return "test-secret-key-for-jwt-signing"

    @pytest.fixture
    def valid_reference(self):
        """Fixture that provides a valid JWT reference."""
        return JWTReference(
            issuers=["test-issuer"],
            audience=["test-audience"],
            subject="test-subject",
        )

    @pytest.fixture
    def valid_token(self, signing_key):
        """Fixture that provides a valid JWT token."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now,
            exp=now + 3600,
        )
        return JWTAgent.generate_token(signing_key=signing_key, payload=payload)

    def test_verify_valid_token(self, signing_key, valid_token, valid_reference):
        """Test verifying a valid token."""
        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=valid_token,
            jwt_reference=valid_reference,
        )

        assert isinstance(result, JWTPayload)
        assert result.iss == "test-issuer"
        assert result.aud == "test-audience"
        assert result.sub == "test-subject"

    def test_verify_invalid_issuer(self, signing_key, valid_token):
        """Test verification fails with invalid issuer."""
        reference = JWTReference(
            issuers=["different-issuer"],
            audience=["test-audience"],
            subject="test-subject",
        )

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=valid_token,
            jwt_reference=reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED
        assert "Issuer" in result.reason

    def test_verify_invalid_audience(self, signing_key, valid_token):
        """Test verification fails with invalid audience."""
        reference = JWTReference(
            issuers=["test-issuer"],
            audience=["different-audience"],
            subject="test-subject",
        )

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=valid_token,
            jwt_reference=reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED
        assert "Audience" in result.reason

    def test_verify_invalid_subject(self, signing_key, valid_token):
        """Test verification fails with invalid subject."""
        reference = JWTReference(
            issuers=["test-issuer"],
            audience=["test-audience"],
            subject="different-subject",
        )

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=valid_token,
            jwt_reference=reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED
        assert "Subject" in result.reason

    def test_verify_expired_token(self, signing_key, valid_reference):
        """Test verification fails with expired token."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now - 7200,  # 2 hours ago
            exp=now - 3600,  # Expired 1 hour ago
        )
        expired_token = JWTAgent.generate_token(
            signing_key=signing_key, payload=payload
        )

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=expired_token,
            jwt_reference=valid_reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED
        assert "expired" in result.reason

    def test_verify_future_token(self, signing_key, valid_reference):
        """Test verification fails with future-dated token (iat in future)."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now + 7200,  # 2 hours in future
            exp=now + 10800,  # 3 hours in future
        )
        future_token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=future_token,
            jwt_reference=valid_reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED
        assert "not yet valid" in result.reason

    def test_verify_with_leeway(self, signing_key):
        """Test verification with leeway allows slightly expired tokens."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now - 60,
            exp=now - 10,  # Expired 10 seconds ago
        )
        slightly_expired_token = JWTAgent.generate_token(
            signing_key=signing_key, payload=payload
        )

        reference_with_leeway = JWTReference(
            issuers=["test-issuer"],
            audience=["test-audience"],
            subject="test-subject",
            leeway=30.0,  # 30 second leeway
        )

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=slightly_expired_token,
            jwt_reference=reference_with_leeway,
        )

        # With 30s leeway, a token expired 10s ago should still be valid
        assert isinstance(result, JWTPayload)

    def test_verify_invalid_signature(self, valid_token, valid_reference):
        """Test verification fails with wrong signing key."""
        wrong_key = "wrong-signing-key"

        result = JWTAgent.verify_reference(
            signing_key=wrong_key,
            jwt_token=valid_token,
            jwt_reference=valid_reference,
        )

        # Invalid signature returns JWTFailure
        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED

    def test_verify_with_custom_validator(
        self, signing_key, valid_token, valid_reference
    ):
        """Test verification with custom validator."""

        def custom_validator(payload: JWTPayload):
            if "admin" not in payload.custom.get("role", ""):
                return JWTFailure(
                    status=HTTPStatus.FORBIDDEN,
                    reason="Admin role required",
                )
            return None

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=valid_token,
            jwt_reference=valid_reference,
            jwt_validator=custom_validator,
        )

        # Should fail because no admin role in payload
        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.FORBIDDEN
        assert "Admin role required" in result.reason

    def test_verify_with_passing_custom_validator(self, signing_key, valid_reference):
        """Test verification with custom validator that passes."""
        now = Chrono.get_current_utc_time().timestamp()
        payload = JWTPayload(
            iss="test-issuer",
            aud="test-audience",
            sub="test-subject",
            iat=now,
            exp=now + 3600,
            custom={"role": "admin"},
        )
        token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        def custom_validator(payload: JWTPayload):
            if "admin" not in payload.custom.get("role", ""):
                return JWTFailure(
                    status=HTTPStatus.FORBIDDEN,
                    reason="Admin role required",
                )
            return None

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=token,
            jwt_reference=valid_reference,
            jwt_validator=custom_validator,
        )

        # Should pass because admin role is present
        assert isinstance(result, JWTPayload)

    def test_verify_malformed_token(self, signing_key, valid_reference):
        """Test verification fails with malformed token."""
        malformed_token = "not.a.valid.jwt.token"

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=malformed_token,
            jwt_reference=valid_reference,
        )

        assert isinstance(result, JWTFailure)
        assert result.status == HTTPStatus.UNAUTHORIZED


class TestJWTAgentMultipleIssuersAudiences:
    """Tests for verification with multiple valid issuers/audiences."""

    @pytest.fixture
    def signing_key(self):
        return "test-secret-key"

    def test_verify_with_multiple_issuers(self, signing_key):
        """Test that any valid issuer from the list is accepted."""
        now = Chrono.get_current_utc_time().timestamp()

        reference = JWTReference(
            issuers=["issuer-1", "issuer-2", "issuer-3"],
            audience=["audience"],
            subject="subject",
        )

        # Token with issuer-2
        payload = JWTPayload(
            iss="issuer-2",
            aud="audience",
            sub="subject",
            iat=now,
            exp=now + 3600,
        )
        token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=token,
            jwt_reference=reference,
        )

        assert isinstance(result, JWTPayload)
        assert result.iss == "issuer-2"

    def test_verify_with_multiple_audiences(self, signing_key):
        """Test that any valid audience from the list is accepted."""
        now = Chrono.get_current_utc_time().timestamp()

        reference = JWTReference(
            issuers=["issuer"],
            audience=["aud-1", "aud-2", "aud-3"],
            subject="subject",
        )

        # Token with aud-3
        payload = JWTPayload(
            iss="issuer",
            aud="aud-3",
            sub="subject",
            iat=now,
            exp=now + 3600,
        )
        token = JWTAgent.generate_token(signing_key=signing_key, payload=payload)

        result = JWTAgent.verify_reference(
            signing_key=signing_key,
            jwt_token=token,
            jwt_reference=reference,
        )

        assert isinstance(result, JWTPayload)
        assert result.aud == "aud-3"


class TestJWTAgentJwksToPem:
    """Tests for JWTAgent.jwks_to_pem()."""

    @pytest.fixture
    def rsa_jwks_entry(self):
        """Generate an RSA JWKS entry from a fresh RSA key."""
        import base64

        from cryptography.hazmat.primitives.asymmetric import rsa

        from ayuna_core.utils.jwtagent import JWKSEntry

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_numbers = private_key.public_key().public_numbers()

        def to_b64url(n: int) -> str:
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
            return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode()

        return JWKSEntry(
            kty="RSA",
            alg="RS256",
            use="sig",
            kid="test-rsa-key",
            n=to_b64url(pub_numbers.n),
            e=to_b64url(pub_numbers.e),
            x="",
            y="",
            crv="",
            x5t="",
            x5c=[],
        )

    @pytest.fixture
    def ec_jwks_entry(self):
        """Generate an EC JWKS entry from a fresh P-256 key."""
        import base64

        from cryptography.hazmat.primitives.asymmetric import ec

        from ayuna_core.utils.jwtagent import JWKSEntry

        private_key = ec.generate_private_key(ec.SECP256R1())
        pub_numbers = private_key.public_key().public_numbers()

        def to_b64url(n: int) -> str:
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
            return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode()

        return JWKSEntry(
            kty="EC",
            alg="ES256",
            use="sig",
            kid="test-ec-key",
            n="",
            e="",
            x=to_b64url(pub_numbers.x),
            y=to_b64url(pub_numbers.y),
            crv="P-256",
            x5t="",
            x5c=[],
        )

    def test_rsa_key_to_pem(self, rsa_jwks_entry):
        """Should convert RSA JWKS entry to PEM public key."""
        pem = JWTAgent.jwks_to_pem(rsa_jwks_entry)

        assert isinstance(pem, str)
        assert "-----BEGIN PUBLIC KEY-----" in pem
        assert "-----END PUBLIC KEY-----" in pem

    def test_ec_key_to_pem(self, ec_jwks_entry):
        """Should convert EC JWKS entry to PEM public key."""
        pem = JWTAgent.jwks_to_pem(ec_jwks_entry)

        assert isinstance(pem, str)
        assert "-----BEGIN PUBLIC KEY-----" in pem
        assert "-----END PUBLIC KEY-----" in pem

    def test_unsupported_key_type_raises(self):
        """Should raise ValueError for unsupported key type."""
        from ayuna_core.utils.jwtagent import JWKSEntry

        jwks = JWKSEntry(
            kty="OCT",
            alg="HS256",
            use="sig",
            kid="test-key",
            n="",
            e="",
            x="",
            y="",
            crv="",
            x5t="",
            x5c=[],
        )

        with pytest.raises(ValueError, match="Unsupported key type"):
            JWTAgent.jwks_to_pem(jwks)

    def test_rsa_pem_roundtrip(self, rsa_jwks_entry):
        """Converted PEM should be parseable by cryptography library."""
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        pem = JWTAgent.jwks_to_pem(rsa_jwks_entry)
        key = load_pem_public_key(pem.encode("utf-8"))

        assert key
