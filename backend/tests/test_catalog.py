import pytest
from fastapi import HTTPException
from utils.catalog import add_entry, remove_entry, list_entries, get_entry


@pytest.fixture(autouse=True)
def catalog_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))


def test_add_and_list(git_project):
    add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    entries = list_entries()
    assert len(entries) == 1
    assert entries[0]["name"] == "Demo"
    assert entries[0]["id"]


def test_add_rejects_non_git_path(tmp_path):
    with pytest.raises(HTTPException) as e:
        add_entry(name="Bad", repo_path=str(tmp_path / "nope"), main_branch="main")
    assert e.value.status_code == 400


def test_get_entry_by_id(git_project):
    e = add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    assert get_entry(e["id"])["repo_path"] == str(git_project)


def test_remove_entry(git_project):
    e = add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    remove_entry(e["id"])
    assert list_entries() == []


def test_get_missing_entry_404():
    with pytest.raises(HTTPException) as e:
        get_entry("does-not-exist")
    assert e.value.status_code == 404
