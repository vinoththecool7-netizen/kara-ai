"""PII helpers: Kara never stores or returns an unmasked PAN."""

from __future__ import annotations


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
