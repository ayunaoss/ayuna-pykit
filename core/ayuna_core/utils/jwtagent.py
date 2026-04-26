"""
jwtagent.py - JWT token handling utilities for the Ayuna framework.

This module provides the JWTAgent class for working with JSON Web Tokens:

- Generating JWT tokens with HS256 signing
- Verifying JWT tokens against reference claims
- Converting JWKS entries to PEM format

The module supports custom payload validation through callback functions.
"""

import base64
from http import HTTPStatus
from typing import Any, Callable, Dict, List

import jwt
import orjson as json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.types import Options as JWTOptions
from pydantic import BaseModel, ValidationError

from .chrono import Chrono

# =============================================================================
# JWT Models
# =============================================================================


class JWTReference(BaseModel):
    """
    Reference data for JWT verification.

    Contains the expected values for standard JWT claims used
    during token verification.

    Attributes
    ----------
    issuers : List[str]
        List of valid issuer values (iss claim).
    audience : List[str]
        List of valid audience values (aud claim).
    subject : str
        Expected subject value (sub claim).
    leeway : float
        Time tolerance in seconds for expiry/issued-at checks (default: 0.0).
    """

    issuers: List[str]
    audience: List[str]
    subject: str
    leeway: float = 0.0


class JWTPayload(BaseModel):
    """
    Standard JWT payload structure.

    Contains the standard JWT claims plus support for custom claims.

    Attributes
    ----------
    iss : str
        Issuer claim - identifies the principal that issued the JWT.
    aud : str
        Audience claim - identifies the recipients of the JWT.
    sub : str
        Subject claim - identifies the principal subject of the JWT.
    iat : float
        Issued-at claim - Unix timestamp when token was issued.
    exp : float
        Expiration claim - Unix timestamp when token expires.
    nbf : float | None
        Not-before claim - Unix timestamp before which token is invalid.
    custom : Dict[str, Any]
        Dictionary for any custom claims.
    """

    iss: str
    aud: str
    sub: str
    iat: float  # IssuedAt Datetime in unix timestamp
    exp: float  # Expiry Datetime in unix timestamp
    nbf: float | None = None  # NotBefore Datetime in unix timestamp
    custom: Dict[str, Any] = {}


class JWKSEntry(BaseModel):
    """
    JSON Web Key Set (JWKS) entry structure.

    Represents a single key from a JWKS document, containing
    both RSA and EC key parameters (only relevant fields are populated).

    Attributes
    ----------
    kty : str
        Key type ("RSA" or "EC").
    alg : str
        Algorithm intended for use with the key.
    use : str
        Intended use ("sig" for signing, "enc" for encryption).
    kid : str
        Key ID for key identification.
    n, e : str
        RSA public key parameters (modulus and exponent).
    x, y, crv : str
        EC public key parameters (coordinates and curve).
    x5t : str
        X.509 certificate thumbprint.
    x5c : List[str]
        X.509 certificate chain.
    """

    kty: str
    alg: str
    use: str
    kid: str
    n: str
    e: str
    x: str
    y: str
    crv: str
    x5t: str
    x5c: List[str]


class JWTFailure(BaseModel):
    """
    Model representing a JWT verification failure.

    Attributes
    ----------
    status : HTTPStatus
        HTTP status code appropriate for the failure.
    reason : str
        Human-readable description of the failure.
    """

    status: HTTPStatus
    reason: str


# Type alias for custom JWT payload validators
JWTPayloadValidator = Callable[[JWTPayload], JWTFailure | None]

# =============================================================================
# JWT Agent
# =============================================================================


class JWTAgent:
    """
    Static utility class for JWT token operations.

    Provides methods for generating, verifying, and working with
    JWT tokens. All methods are static.
    """

    @staticmethod
    def jwks_to_pem(jwks: JWKSEntry):
        if jwks.kty == "RSA":
            public_numbers = rsa.RSAPublicNumbers(
                e=int.from_bytes(base64.urlsafe_b64decode(jwks.e + "=="), "big"),
                n=int.from_bytes(base64.urlsafe_b64decode(jwks.n + "=="), "big"),
            )
            public_key = public_numbers.public_key()
        elif jwks.kty == "EC":
            curve = {
                "P-256": ec.SECP256R1(),
                "P-384": ec.SECP384R1(),
                "P-521": ec.SECP521R1(),
            }[jwks.crv]
            public_key = ec.EllipticCurvePublicNumbers(
                x=int.from_bytes(base64.urlsafe_b64decode(jwks.x + "=="), "big"),
                y=int.from_bytes(base64.urlsafe_b64decode(jwks.y + "=="), "big"),
                curve=curve,
            ).public_key()
        else:
            raise ValueError(f"Unsupported key type: {jwks.kty}")

        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return pem.decode("utf-8")

    @staticmethod
    def generate_token(*, signing_key: str, payload: JWTPayload) -> str:
        """
        Generate a JWT token from the provided JWTPayload. This uses HS256 algorithm
        and PEM formatted signing key.

        Parameters
        ----------
        payload: JWTPayload
            JWTPayload to be used for generating JWT token

        Returns
        -------
        str
            JWT token
        """

        ws_jwt = jwt.encode(
            json.loads(payload.model_dump_json(by_alias=True)),
            signing_key,
            algorithm="HS256",
        )

        return ws_jwt

    @staticmethod
    def verify_reference(
        *,
        signing_key: str,
        jwt_token: str,
        jwt_reference: JWTReference,
        jwt_validator: JWTPayloadValidator | None = None,
    ):
        """
        Verify expected claims in the JWT token using the JWT Reference, provided.
        An optional, custom validator can be provided to further validate the JWT payload.
        This facilitates extending the JWT payload with custom claims.

        Parameters
        ----------
        jwt_token: str
            JWT token to be verified
        jwt_reference: JWTReference
            JWT Reference to be used for verification
        jwt_validator: JWTPayloadValidator | None
            Optional, custom validator to be applied to the JWT payload

        Returns
        -------
        JWTPayload | JWTFailure
            JWTPayload if the JWT token is valid, JWTFailure otherwise
        """

        verify_opts: JWTOptions = {
            "verify_signature": True,
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
            "verify_aud": False,
            "verify_iss": False,
            "verify_sub": False,
            "verify_jti": False,
            "require": [],
        }

        try:
            payload_dict = jwt.decode(
                jwt=jwt_token,
                key=signing_key,
                algorithms=["HS256"],
                options=verify_opts,
            )
            jwt_payload = JWTPayload(**payload_dict)

            if jwt_payload.iss not in jwt_reference.issuers:
                return JWTFailure(
                    status=HTTPStatus.UNAUTHORIZED,
                    reason="Invalid JWT Issuer received\n",
                )

            if jwt_payload.aud not in jwt_reference.audience:
                return JWTFailure(
                    status=HTTPStatus.UNAUTHORIZED,
                    reason="Invalid JWT Audience received\n",
                )

            if jwt_payload.sub != jwt_reference.subject:
                return JWTFailure(
                    status=HTTPStatus.UNAUTHORIZED,
                    reason="Invalid JWT Subject received\n",
                )

            now = Chrono.get_current_utc_time().timestamp()

            if int(jwt_payload.exp) <= (now - jwt_reference.leeway):
                return JWTFailure(
                    status=HTTPStatus.UNAUTHORIZED,
                    reason="JWT payload is expired\n",
                )

            if int(jwt_payload.iat) > (now + jwt_reference.leeway):
                return JWTFailure(
                    status=HTTPStatus.UNAUTHORIZED,
                    reason="JWT payload is not yet valid\n",
                )

            if jwt_validator:
                failure = jwt_validator(jwt_payload)

                if failure:
                    return failure

            return jwt_payload
        except (ValidationError, json.JSONDecodeError, jwt.exceptions.DecodeError):
            return JWTFailure(
                status=HTTPStatus.UNAUTHORIZED,
                reason="Invalid JWT Payload received\n",
            )
