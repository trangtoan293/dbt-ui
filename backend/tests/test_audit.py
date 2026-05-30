import json
import logging
from utils.audit import audit


def test_audit_emits_structured_record(caplog):
    with caplog.at_level(logging.INFO, logger="dbt_ui.audit"):
        audit(sub="user-a", action="dbt_run", target="proj", extra={"selector": "stg_x"})
    rec = [r for r in caplog.records if r.name == "dbt_ui.audit"][-1]
    payload = json.loads(rec.getMessage())
    assert payload["sub"] == "user-a"
    assert payload["action"] == "dbt_run"
    assert payload["target"] == "proj"
    assert payload["selector"] == "stg_x"
    assert "ts" in payload
