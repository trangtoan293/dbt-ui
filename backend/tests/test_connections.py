import pytest
from fastapi import HTTPException
from utils.connections import (
    validate_connections, engine_for_target, is_production_engine,
    SECRET_KEYS, DEV_ENGINES, PROD_ENGINES,
)


def test_valid_block_passes():
    block = {
        "dev": {"engine": "duckdb", "path": "dev.duckdb"},
        "prod": {"engine": "dremio", "host": "h", "port": 9047},
    }
    validate_connections(block)  # no raise


def test_rejects_unknown_engine():
    with pytest.raises(HTTPException) as e:
        validate_connections({"dev": {"engine": "oracle"}})
    assert e.value.status_code == 400


def test_rejects_secret_keys():
    for secret in SECRET_KEYS:
        with pytest.raises(HTTPException) as e:
            validate_connections({"prod": {"engine": "dremio", secret: "x"}})
        assert e.value.status_code == 400


def test_engine_for_target():
    block = {"dev": {"engine": "duckdb"}, "prod": {"engine": "dremio"}}
    assert engine_for_target(block, "prod") == "dremio"
    assert engine_for_target(block, "dev") == "duckdb"


def test_production_classification():
    assert is_production_engine("dremio") is True
    assert is_production_engine("duckdb") is False
    assert is_production_engine("spark") is False
