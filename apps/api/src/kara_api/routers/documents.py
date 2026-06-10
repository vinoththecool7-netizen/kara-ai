"""Document upload and auto-fill endpoint.

Accepts Form 16, AIS, and Form 26AS documents (PDF or JSON), parses them,
and applies extracted fields to the session's ProfileBuilder.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from kara_api.agent.document_autofill import AutofillDiff, apply_26as, apply_ais, apply_form16
from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.agent.session import SessionManager
from kara_api.db.connection import get_session_factory
from kara_api.parsers import (
    AISDocument,
    Form16Document,
    Form16ParseError,
    Form26ASDocument,
    parse_ais_json,
    parse_ais_pdf,
    parse_form16,
    parse_form_26as,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ParsedDocumentSummary(BaseModel):
    document_id: str
    document_type: str
    pan: str | None = None
    employer_name: str | None = None
    period: str | None = None
    key_amounts: dict[str, int] = {}
    fields_filled: int = 0


class DocumentUploadResponse(BaseModel):
    document_id: str
    document_type: str
    parsed_summary: ParsedDocumentSummary
    profile_diff: AutofillDiff
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _create_session_manager() -> SessionManager:
    return SessionManager(get_session_factory())


# ---------------------------------------------------------------------------
# Internal: type sniffing
# ---------------------------------------------------------------------------


def _sniff_document_type(
    content: bytes,
    filename: str,
    declared: Literal["form16", "ais", "26as", "auto"],
) -> Literal["form16", "ais", "26as"]:
    """Determine the actual document type from content magic bytes and filename hints."""
    if declared != "auto":
        return declared  # type: ignore[return-value]

    name_lower = filename.lower() if filename else ""

    # JSON → AIS
    if content[:1] in (b"{", b"["):
        return "ais"

    # PDF: check magic bytes
    if content[:4] == b"%PDF":
        # Disambiguate by filename
        if "ais" in name_lower:
            return "ais"
        if "26as" in name_lower or "26_as" in name_lower or "form26" in name_lower:
            return "26as"
        # Default PDF → form16
        return "form16"

    # Unknown
    raise HTTPException(
        status_code=415,
        detail="Only PDF or JSON files are supported.",
    )


# ---------------------------------------------------------------------------
# Internal: parse dispatch
# ---------------------------------------------------------------------------


def _parse_document(
    content: bytes,
    doc_type: Literal["form16", "ais", "26as"],
    filename: str,
) -> Form16Document | AISDocument | Form26ASDocument:
    """Parse *content* as the given document type."""
    try:
        if doc_type == "form16":
            return parse_form16(content)

        if doc_type == "26as":
            return parse_form_26as(content)

        # AIS: JSON or PDF
        if content[:1] in (b"{", b"["):
            blob = json.loads(content.decode("utf-8"))
            return parse_ais_json(blob)
        else:
            return parse_ais_pdf(content)

    except Form16ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON content: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Internal: build ParsedDocumentSummary
# ---------------------------------------------------------------------------


def _build_summary(
    document_id: str,
    doc_type: str,
    doc: Form16Document | AISDocument | Form26ASDocument,
) -> ParsedDocumentSummary:
    """Extract a human-readable summary from the parsed document."""
    pan: str | None = None
    employer_name: str | None = None
    period: str | None = None
    key_amounts: dict[str, int] = {}
    fields_filled = 0

    if isinstance(doc, Form16Document):
        pan = doc.part_a.employee_pan
        if pan == "UNKNOWN0000X":
            pan = None
        employer_name = doc.part_a.employer_name
        if employer_name == "Unknown Employer":
            employer_name = None

        # Period
        if doc.part_a.period_from and doc.part_a.period_to:
            period = f"{doc.part_a.period_from} to {doc.part_a.period_to}"
        elif doc.part_a.assessment_year:
            period = f"AY {doc.part_a.assessment_year}"

        # Key amounts (rupees)
        if doc.part_b:
            if doc.part_b.gross_salary:
                key_amounts["gross_salary"] = doc.part_b.gross_salary
                fields_filled += 1
            if doc.part_a.total_tds_deposited:
                key_amounts["total_tds"] = doc.part_a.total_tds_deposited
                fields_filled += 1
            if doc.part_b.chapter_via.sec_80c:
                key_amounts["section_80c"] = doc.part_b.chapter_via.sec_80c
                fields_filled += 1
            if doc.part_b.chapter_via.sec_80d:
                key_amounts["section_80d"] = doc.part_b.chapter_via.sec_80d
                fields_filled += 1
            if doc.part_b.chapter_via.sec_80ccd_1b:
                key_amounts["section_80ccd_1b"] = doc.part_b.chapter_via.sec_80ccd_1b
                fields_filled += 1
            if doc.part_b.chapter_via.sec_80ccd_2:
                key_amounts["section_80ccd_2"] = doc.part_b.chapter_via.sec_80ccd_2
                fields_filled += 1

    elif isinstance(doc, AISDocument):
        pan = doc.pan
        period = doc.assessment_year

        total_interest_paise = sum(e.amount for e in doc.interest_savings) + sum(
            e.amount for e in doc.interest_fd
        )
        total_div_paise = sum(e.amount for e in doc.dividends)

        if total_interest_paise:
            key_amounts["total_interest"] = total_interest_paise // 100
            fields_filled += 1
        if total_div_paise:
            key_amounts["total_dividends"] = total_div_paise // 100
            fields_filled += 1
        if doc.security_sales:
            key_amounts["security_sales_count"] = len(doc.security_sales)
            fields_filled += 1

    elif isinstance(doc, Form26ASDocument):
        pan = doc.pan
        period = doc.assessment_year

        tds_salary_paise = doc.totals.total_tds_salary
        if tds_salary_paise:
            key_amounts["tds_salary"] = tds_salary_paise // 100
            fields_filled += 1

        advance_tax_paise = sum(e.amount for e in doc.advance_tax_paid)
        if advance_tax_paise:
            key_amounts["advance_tax"] = advance_tax_paise // 100
            fields_filled += 1

        self_assessment_paise = sum(e.amount for e in doc.self_assessment_tax)
        if self_assessment_paise:
            key_amounts["self_assessment_tax"] = self_assessment_paise // 100
            fields_filled += 1

    return ParsedDocumentSummary(
        document_id=document_id,
        document_type=doc_type,
        pan=pan,
        employer_name=employer_name,
        period=period,
        key_amounts=key_amounts,
        fields_filled=fields_filled,
    )


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session_id: str = Form(...),
    document_type: Literal["form16", "ais", "26as", "auto"] = Form("auto"),
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """Upload a tax document (Form 16, AIS, or 26AS) and auto-fill the session profile.

    - Validates file size (max 10 MB).
    - Sniffs document type if ``document_type="auto"``.
    - Parses the document and maps fields onto the session's ProfileBuilder.
    - Returns a diff of what slots were added/overridden, plus a parsed summary.

    If the session is not found, the document is still parsed and the diff is
    returned (autofill is skipped).
    """
    # --- Read and validate file size ---
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum is 10 MB.",
        )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is empty.",
        )

    filename = file.filename or ""

    # --- Sniff / validate document type ---
    actual_type = _sniff_document_type(content, filename, document_type)

    # --- Parse ---
    doc = _parse_document(content, actual_type, filename)

    # --- Generate document ID ---
    document_id = str(uuid.uuid4())

    # --- Build parsed summary (before autofill, so fields_filled is always present) ---
    parsed_summary = _build_summary(document_id, actual_type, doc)

    # --- Load session and apply autofill ---
    diff = AutofillDiff()
    session_found = False

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        logger.warning("Invalid session_id format: %s — skipping autofill", session_id)
        all_warnings = list(diff.warnings)
        return DocumentUploadResponse(
            document_id=document_id,
            document_type=actual_type,
            parsed_summary=parsed_summary,
            profile_diff=diff,
            warnings=all_warnings,
        )

    sm = _create_session_manager()
    db_session = await sm.get_session(session_uuid)

    if db_session is None:
        logger.warning("Session %s not found — parsing succeeded but autofill skipped", session_id)
    else:
        session_found = True
        # Rebuild ProfileBuilder from persisted state
        profile_data = db_session.profile_json or {}
        builder = ProfileBuilder.from_dict(profile_data) if profile_data else ProfileBuilder()

        # Apply autofill
        if isinstance(doc, Form16Document):
            diff = apply_form16(builder, doc)
        elif isinstance(doc, AISDocument):
            diff = apply_ais(builder, doc)
        elif isinstance(doc, Form26ASDocument):
            diff = apply_26as(builder, doc)

        # Persist updated builder
        await sm.update_profile(session_uuid, builder.to_dict())

    # --- Collect all warnings ---
    all_warnings: list[str] = list(diff.warnings)
    if not session_found:
        all_warnings.insert(0, f"Session '{session_id}' not found; profile was not updated.")

    # Also surface parser warnings
    if hasattr(doc, "warnings"):
        for w in doc.warnings:
            if hasattr(w, "message"):
                all_warnings.append(f"Parser: {w.message}")
            else:
                all_warnings.append(f"Parser: {w}")

    return DocumentUploadResponse(
        document_id=document_id,
        document_type=actual_type,
        parsed_summary=parsed_summary,
        profile_diff=diff,
        warnings=all_warnings,
    )
