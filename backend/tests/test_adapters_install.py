import routes.venv_routes as vr


def test_dbt_adapters_constant_lists_three_engines():
    assert set(vr.DBT_ADAPTERS) == {"dbt-duckdb", "dbt-spark", "dbt-dremio"}


def test_install_adapters_issues_pip_command(monkeypatch, tmp_path):
    calls = []

    class _Res:
        success = True
        stdout = "ok"
        stderr = ""
        error = ""

    def fake_run(cmd, cwd, timeout=None, env=None):
        calls.append(cmd)
        return _Res()

    monkeypatch.setattr(vr, "run_command", fake_run)
    vr.install_adapters(tmp_path / ".dbt-ui-venv" / "bin" / "python", tmp_path, [])

    flat = [c for call in calls for c in call]
    assert "dbt-duckdb" in flat and "dbt-spark" in flat and "dbt-dremio" in flat
