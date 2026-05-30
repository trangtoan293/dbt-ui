from utils.secret_scrub import scrub


def test_redacts_bearer_token():
    assert "REDACTED" in scrub("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in scrub("Authorization: Bearer abc.def.ghi")


def test_redacts_password_kv():
    out = scrub("password=SuperSecret123 host=dremio")
    assert "SuperSecret123" not in out
    assert "host=dremio" in out


def test_redacts_url_credentials():
    out = scrub("postgres://user:p4ss@db:5432/x")
    assert "p4ss" not in out


def test_plain_text_unchanged():
    assert scrub("Completed 5 models in 3.2s") == "Completed 5 models in 3.2s"
