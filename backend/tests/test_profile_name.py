from utils.profiles import resolve_profile_name, read_default_target, write_profiles


def test_reads_profile_key(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: demo_profile\n")
    assert resolve_profile_name(tmp_path) == "demo_profile"


def test_falls_back_to_name(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\n")
    assert resolve_profile_name(tmp_path) == "demo"


def test_read_default_target(tmp_path):
    conn = {"dev": {"engine": "duckdb", "path": "d.duckdb"},
            "prod": {"engine": "dremio", "host": "h"}}
    write_profiles(tmp_path, "demo", conn, default_target="prod")
    assert read_default_target(tmp_path, "demo") == "prod"


def test_read_default_target_missing_file(tmp_path):
    assert read_default_target(tmp_path, "demo") is None
