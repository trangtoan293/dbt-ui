"""Tests for run_command stdin input support."""
from utils.subprocess_utils import run_command


def test_run_command_stdin_passes_input_to_process():
    result = run_command(["cat"], cwd=".", input="hello\n")
    assert result.success
    assert result.stdout == "hello\n"


def test_run_command_stdin_default_none_unchanged():
    result = run_command(["echo", "ok"], cwd=".")
    assert result.success
    assert "ok" in result.stdout
