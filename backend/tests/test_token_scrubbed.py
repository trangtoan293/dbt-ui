from utils.secret_scrub import scrub


def test_dremio_token_value_is_scrubbed():
    out = scrub("connecting with token=eyJabc.def.ghi to dremio")
    assert "eyJabc.def.ghi" not in out
