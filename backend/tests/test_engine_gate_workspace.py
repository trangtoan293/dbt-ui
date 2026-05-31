import pytest
from unittest.mock import patch, MagicMock
from routes.dbt_routes import _engine_gate


def test_engine_gate_workspace_with_connections():
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]

    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"

    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace_mod.get_workspace") as ws_mock:

        catalog_mock.return_value = None

        ws_mock.return_value = {
            "id": "ws-1",
            "connections": {
                "dev": {
                    "engine": "duckdb",
                }
            }
        }

        result = _engine_gate(
            user, request, "ws-1", "/path/to/ws",
            "dev", {}
        )

        assert result == {}


def test_engine_gate_workspace_no_connections():
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]

    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"

    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace_mod.get_workspace") as ws_mock:

        catalog_mock.return_value = None
        ws_mock.return_value = {"id": "ws-1", "connections": {}}

        result = _engine_gate(
            user, request, "ws-1", "/path/to/ws",
            "dev", {}
        )

        assert result == {}


def test_engine_gate_workspace_not_found_fallback():
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]

    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"

    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace_mod.get_workspace") as ws_mock:

        catalog_mock.return_value = None
        ws_mock.return_value = None

        result = _engine_gate(
            user, request, "nonexistent", "/path/to/ws",
            "", {}
        )

        assert result == {}


def test_engine_gate_strips_workspaces_prefix():
    """project_id arrives as the relative path 'workspaces/<id>';
    the workspace store must be queried with the bare id."""
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]

    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"

    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace_mod.get_workspace") as ws_mock:

        catalog_mock.return_value = None
        ws_mock.return_value = {"id": "ws-1", "connections": {}}

        _engine_gate(user, request, "workspaces/ws-1", "/path/to/ws", "dev", {})

        ws_mock.assert_called_once_with("user-123", "ws-1")
