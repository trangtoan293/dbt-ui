"""Redact secrets from dbt output before it is stored, returned, or logged."""
import re

_PATTERNS = [
    # Bearer tokens
    re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"),
    # key=value / key: value (unquoted)
    re.compile(r"(?i)\b(password|token|secret|api[-_]?key|pw)\s*[=:]\s*\S+"),
    # key="value" / key='value' (quoted) — catches pw="...", password='...'
    re.compile(r"""(?i)\b(password|token|secret|api[-_]?key|pw)\s*=\s*(['"])[^\2]*?\2"""),
    # URL credentials (postgres://user:pass@host)
    re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)"),
    # AWS access key patterns: AKIA... / ASIA...
    re.compile(r"(AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}"),
    # AWS secret key: 40-char base64-ish after known label
    re.compile(r"(?i)(aws_secret_access_key\s*[=:]\s*)\S+"),
]
_REPL = [
    "\\1<REDACTED>",
    "\\1=<REDACTED>",
    "\\1=<REDACTED>",
    "\\1<REDACTED>\\2",
    "<REDACTED_AWS_KEY>",
    "\\1<REDACTED>",
]


def scrub(text: str) -> str:
    if not text:
        return text
    for pat, repl in zip(_PATTERNS, _REPL):
        text = pat.sub(repl, text)
    return text
