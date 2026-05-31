import yaml
from pathlib import Path
from utils.profiles import build_profile, write_profiles


CONN = {
    "dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"},
    "prod": {"engine": "dremio", "host": "h", "port": 9047,
             "database": "dl", "schema": "analytics"},
}


def test_build_profile_shape():
    prof = build_profile("demo", CONN, default_target="dev")
    assert "demo" in prof
    assert prof["demo"]["target"] == "dev"
    assert set(prof["demo"]["outputs"]) == {"dev", "prod"}


def test_duckdb_output_is_complete_and_identity_free():
    out = build_profile("demo", CONN)["demo"]["outputs"]["dev"]
    assert out["type"] == "duckdb"
    assert out["path"] == "dev.duckdb"
    assert "token" not in out  # Dev Engine: no per-user identity


def test_dremio_output_references_runtime_token_env():
    out = build_profile("demo", CONN)["demo"]["outputs"]["prod"]
    assert out["type"] == "dremio"
    assert out["host"] == "h"
    # token is supplied at runtime via env var, never stored in the file
    assert out["token"] == "{{ env_var('DREMIO_TOKEN') }}"


def test_write_profiles_creates_file(tmp_path):
    write_profiles(tmp_path, "demo", CONN, default_target="dev")
    written = yaml.safe_load((tmp_path / "profiles.yml").read_text())
    assert written["demo"]["outputs"]["dev"]["type"] == "duckdb"
