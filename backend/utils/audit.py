"""Structured audit logging: who did what, when."""
import json
import logging
import time

_logger = logging.getLogger("dbt_ui.audit")


def audit(sub: str, action: str, target: str = "", extra: dict | None = None) -> None:
    record = {"ts": time.time(), "sub": sub, "action": action, "target": target}
    if extra:
        record.update(extra)
    _logger.info(json.dumps(record))
