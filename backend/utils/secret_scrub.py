"""Redact secrets from dbt output before it is stored, returned, or logged."""
import re

_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"),
    re.compile(r"(?i)\b(password|token|secret|api[-_]?key)\s*[=:]\s*\S+"),
    re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)"),  # url credentials
]
_REPL = ["\\1<REDACTED>", "\\1=<REDACTED>", "\\1<REDACTED>\\2"]


def scrub(text: str) -> str:
    if not text:
        return text
    for pat, repl in zip(_PATTERNS, _REPL):
        text = pat.sub(repl, text)
    return text
