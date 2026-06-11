"""PII helpers: Kara never stores or returns an unmasked PAN."""

from __future__ import annotations


def sanitize_text(text: str | None, max_length: int = 200) -> str | None:
    """Flatten untrusted document-derived text before it reaches the LLM
    context or stored slots: collapse whitespace/control characters to
    single spaces and cap the length."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    return cleaned[:max_length]


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
