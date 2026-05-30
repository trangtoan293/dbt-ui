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


def test_redacts_quoted_password():
    out = scrub('profiles: {password="S3cr3t!"}')
    assert "S3cr3t!" not in out


def test_redacts_aws_access_key():
    out = scrub("key=AKIAIOSFODNN7EXAMPLE rest of line")
    assert "AKIAIOSFODNN7EXAMPLE" not in out


def test_redacts_aws_secret_key():
    out = scrub("aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    assert "wJalrXUtnFEMI" not in out
