"""Parsers sub-package for Kara API.

Provides:
- Form 16 PDF parser (Day 56)
- AIS JSON + PDF parser (Day 57)
- Form 26AS PDF parser (Day 57)
"""
from kara_api.parsers.ais import AISDocument, parse_ais_json, parse_ais_pdf
from kara_api.parsers.form16 import Form16Document, Form16ParseError, parse_form16
from kara_api.parsers.twenty_six_as import Form26ASDocument, parse_form_26as

__all__ = [
    # Form 16
    "Form16Document",
    "Form16ParseError",
    "parse_form16",
    # AIS
    "AISDocument",
    "parse_ais_json",
    "parse_ais_pdf",
    # Form 26AS
    "Form26ASDocument",
    "parse_form_26as",
]
