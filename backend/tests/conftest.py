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


import json
import subprocess


@pytest.fixture
def catalog_with_conn(tmp_path, git_project, monkeypatch):
    """A Catalog with one project that has dev (duckdb) + prod (dremio) connections."""
    catalog_path = tmp_path / "catalog.json"
    entry = {
        "id": "p1",
        "name": "Demo",
        "repo_path": str(git_project),
        "main_branch": "main",
        "connections": {
            "dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"},
            "prod": {"engine": "dremio", "host": "dremio.local", "port": 9047,
                     "database": "dl", "schema": "analytics"},
        },
    }
    catalog_path.write_text(json.dumps([entry]))
    monkeypatch.setenv("CATALOG_PATH", str(catalog_path))
    return entry


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


@pytest.fixture
def git_project(tmp_path):
    """A canonical local repo with one commit on 'main'. Returns its path."""
    repo = tmp_path / "canonical" / "demo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "seed@example.com")
    _git(repo, "config", "user.name", "Seed")
    (repo / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    (repo / "models").mkdir()
    (repo / "models" / "stg_x.sql").write_text("select 1 as id\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo
