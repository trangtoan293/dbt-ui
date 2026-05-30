"""Shared test fixtures: a local RSA keypair that stands in for Keycloak's JWKS."""
import os
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt

TEST_ISSUER = "https://portal-pam.hanas.io/realms/sbv-portal"
TEST_AUDIENCE = "account"
TEST_KID = "test-key-1"

# Set env vars before auth module is imported so the hard-fail check passes.
os.environ.setdefault("KEYCLOAK_ISSUER", TEST_ISSUER)
os.environ.setdefault("KEYCLOAK_JWKS_URI", "https://portal-pam.hanas.io/realms/sbv-portal/protocol/openid-connect/certs")


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def public_pem(rsa_key):
    return rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture
def make_token(rsa_key):
    """Build a signed JWT with the given claims, defaulting to a valid token."""
    def _make(sub="user-abc", email="dev@example.com", roles=None,
              aud=TEST_AUDIENCE, iss=TEST_ISSUER, exp_delta=300):
        now = int(time.time())
        claims = {
            "sub": sub,
            "email": email,
            "aud": aud,
            "iss": iss,
            "iat": now,
            "exp": now + exp_delta,
            "realm_access": {"roles": roles or ["developer"]},
        }
        return jwt.encode(claims, rsa_key, algorithm="RS256",
                          headers={"kid": TEST_KID})
    return _make
