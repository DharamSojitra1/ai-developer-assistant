"""Keep personal data out of logs.

Tool arguments can carry user text (search queries, text to analyze), so
free-text values are logged as their length only. Every log record also
passes through `RedactionFilter`, which masks email addresses and bearer or
JWT tokens wherever they appear.
"""

import logging
import re
from typing import Any

# Short, non-personal arguments that are useful when debugging.
ALLOWED_TOOL_ARGS = frozenset({"expression", "document_id"})
MAX_ALLOWED_ARG_LENGTH = 200

# Injected by LangGraph, never chosen by the model; `state` holds the whole
# conversation.
INJECTED_TOOL_ARGS = frozenset({"state", "tool_call_id"})

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# Standard LogRecord attributes; everything else is an `extra` field.
_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


def redact_text(text: str) -> str:
    text = JWT.sub("<redacted token>", text)
    text = BEARER.sub("Bearer <redacted token>", text)
    return EMAIL.sub("<redacted email>", text)


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        if key in ALLOWED_TOOL_ARGS and len(value) <= MAX_ALLOWED_ARG_LENGTH:
            return redact_text(value)
        return f"<redacted len={len(value)}>"

    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_redact_value(key, item) for item in value]

    return value


def redact_tool_args(args: Any) -> Any:
    """Tool arguments safe to log: injected values dropped, text as lengths."""
    if isinstance(args, str):
        return f"<redacted len={len(args)}>"

    if not isinstance(args, dict):
        return args

    return {
        key: _redact_value(key, value)
        for key, value in args.items()
        if key not in INJECTED_TOOL_ARGS
    }


def _redact_any(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)

    if isinstance(value, dict):
        return {k: _redact_any(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_redact_any(item) for item in value]

    return value


class RedactionFilter(logging.Filter):
    """Mask emails and tokens in the message, its args, and extra fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)

        if isinstance(record.args, tuple):
            record.args = tuple(_redact_any(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = _redact_any(record.args)

        for key, value in list(record.__dict__.items()):
            if key not in _RECORD_ATTRS:
                setattr(record, key, _redact_any(value))

        return True
