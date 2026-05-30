import pytest
from pathlib import Path
from fastapi import HTTPException
from utils.user_paths import user_root, resolve_under_root


def test_user_root_embeds_sub(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    root = user_root("user-xyz")
    assert root == (tmp_path / "user-xyz").resolve()


def test_resolve_inside_root_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    (tmp_path / "user-xyz" / "proj").mkdir(parents=True)
    p = resolve_under_root("user-xyz", "proj")
    assert p == (tmp_path / "user-xyz" / "proj").resolve()


def test_resolve_escapes_root_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    (tmp_path / "user-a").mkdir()
    (tmp_path / "user-b").mkdir()
    with pytest.raises(HTTPException) as e:
        resolve_under_root("user-a", "../user-b")
    assert e.value.status_code == 403


def test_absolute_path_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    with pytest.raises(HTTPException) as e:
        resolve_under_root("user-a", "/etc/passwd")
    assert e.value.status_code == 403


def test_sub_with_special_chars_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    with pytest.raises(HTTPException) as e:
        user_root("../../etc")
    assert e.value.status_code == 400


def test_valid_uuid_sub_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    root = user_root("550e8400-e29b-41d4-a716-446655440000")
    assert "550e8400-e29b-41d4-a716-446655440000" in str(root)
