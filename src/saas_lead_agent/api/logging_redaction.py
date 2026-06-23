"""Logging filters that keep provider secrets out of operational logs."""

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_REDACTED = "REDACTED"
_URL_PATTERN = re.compile(r"https?://[^\s\"']+")
_SENSITIVE_QUERY_KEYS = {
    "api_key",
    "access_token",
    "auth_token",
    "client_secret",
    "key",
    "password",
    "secret",
    "token",
}


class SecretRedactionFilter(logging.Filter):
    """Redact query-string secrets from log records before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_urls(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _redact_arg(value) for key, value in record.args.items()}
        return True


def configure_http_logging_redaction() -> None:
    """Attach redaction to HTTP client loggers once per process."""

    for logger_name in ("httpx", "httpcore"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(filter_, SecretRedactionFilter) for filter_ in logger.filters):
            logger.addFilter(SecretRedactionFilter())


def redact_sensitive_urls(value: str) -> str:
    """Redact sensitive query parameters from any URL-like text."""

    return _URL_PATTERN.sub(lambda match: _redact_url(match.group(0)), value)


def _redact_arg(value: object) -> object:
    text = str(value)
    redacted = redact_sensitive_urls(text)
    return redacted if redacted != text else value


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    changed = False
    redacted_items: list[tuple[str, str]] = []
    for key, value in query_items:
        if _is_sensitive_query_key(key):
            redacted_items.append((key, _REDACTED))
            changed = True
        else:
            redacted_items.append((key, value))
    if not changed:
        return url
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(redacted_items),
            parts.fragment,
        )
    )


def _is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in _SENSITIVE_QUERY_KEYS or normalized.endswith("_key")
