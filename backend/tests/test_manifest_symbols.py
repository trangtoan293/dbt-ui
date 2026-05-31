from utils.manifest_symbols import extract_symbols

MANIFEST = {
    "nodes": {
        "model.demo.stg_orders": {"resource_type": "model", "name": "stg_orders"},
        "model.demo.dim_users": {"resource_type": "model", "name": "dim_users"},
        "test.demo.t1": {"resource_type": "test", "name": "t1"},
    },
    "sources": {
        "source.demo.raw.orders": {"source_name": "raw", "name": "orders"},
    },
    "macros": {
        "macro.demo.cents_to_dollars": {"name": "cents_to_dollars"},
    },
}


def test_extracts_model_names():
    syms = extract_symbols(MANIFEST)
    assert sorted(syms["models"]) == ["dim_users", "stg_orders"]


def test_excludes_non_models_from_models():
    assert "t1" not in extract_symbols(MANIFEST)["models"]


def test_extracts_sources():
    assert {"source": "raw", "table": "orders"} in extract_symbols(MANIFEST)["sources"]


def test_extracts_macros():
    assert "cents_to_dollars" in extract_symbols(MANIFEST)["macros"]


def test_empty_manifest():
    syms = extract_symbols({})
    assert syms == {"models": [], "sources": [], "macros": []}
