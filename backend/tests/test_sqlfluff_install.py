import routes.venv_routes as vr


def test_format_tools_lists_sqlfluff():
    assert "sqlfluff" in vr.FORMAT_TOOLS


def test_install_format_tools_issues_pip_command(monkeypatch, tmp_path):
    calls = []

    class _Res:
        success = True
        stdout = "ok"
        stderr = ""
        error = ""

    monkeypatch.setattr(vr, "run_command", lambda cmd, cwd, timeout=None, env=None: calls.append(cmd) or _Res())
    vr.install_format_tools(tmp_path / ".dbt-ui-venv" / "bin" / "python", tmp_path, [])

    flat = [c for call in calls for c in call]
    assert "sqlfluff" in flat
