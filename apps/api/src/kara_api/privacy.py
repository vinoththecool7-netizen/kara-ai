"""PII helpers: Kara never stores or returns an unmasked PAN."""

from __future__ import annotations

import re


def sanitize_text(text: str | None, max_length: int = 200) -> str | None:
    """Flatten untrusted document-derived text before it reaches the LLM
    context or stored slots: collapse whitespace/control characters to
    single spaces and cap the length."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    return cleaned[:max_length]


_PAN_KEYS = frozenset({"pan", "payer_pan_or_tan"})

# PAN format: 5 letters, 4 digits, 1 letter. Free-text fields (e.g. a
# parser's raw_text_excerpt) can embed the full PAN, so PAN-shaped tokens
# are redacted from every string, not just PAN-named fields.
_PAN_TOKEN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")


def _is_pan_key(key: str) -> bool:
    return key in _PAN_KEYS or key.endswith("_pan")


def _is_name_key(key: str) -> bool:
    return key == "name" or key.endswith("_name")


def _redact_pan_tokens(text: str) -> str:
    return _PAN_TOKEN_RE.sub(lambda m: mask_pan(m.group(0)), text)


def mask_document_pii(data):
    """Recursively mask PII in a parsed-document dump before it leaves the
    process: PAN-bearing fields are masked to their last four characters,
    free-text name fields are flattened via :func:`sanitize_text`, and
    PAN-shaped tokens are redacted from all remaining strings.

    Used by the LLM parse_* tools, whose results are streamed to clients,
    persisted in ``tool_calls_json``, and fed back into LLM context.
    """
    if isinstance(data, list):
        return [mask_document_pii(item) for item in data]
    if isinstance(data, str):
        return _redact_pan_tokens(data)
    if not isinstance(data, dict):
        return data
    masked = {}
    for key, value in data.items():
        if isinstance(value, str) and _is_pan_key(key):
            masked[key] = mask_pan(value)
        elif isinstance(value, str) and _is_name_key(key):
            masked[key] = _redact_pan_tokens(sanitize_text(value))
        else:
            masked[key] = mask_document_pii(value)
    return masked


def mask_pan(pan: str | None) -> str | None:
    """Mask a PAN to its last four characters (e.g. ``XXXXXX234F``).

    Parsers may extract the full PAN for in-process reconciliation, but
    anything persisted or sent to a client must pass through here first.
    """
    if pan is None:
        return None
    if len(pan) <= 4:
        return "X" * len(pan)
    return "X" * (len(pan) - 4) + pan[-4:]
