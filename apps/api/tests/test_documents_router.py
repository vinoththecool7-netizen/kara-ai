"""Tests for kara_api.routers.documents — document upload endpoint."""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BASE = "/api/v1/documents"


# ---------------------------------------------------------------------------
# Minimal fake PDF bytes (valid PDF magic bytes but unprocessable by pdfplumber)
# ---------------------------------------------------------------------------

_PDF_MAGIC = b"%PDF-1.4 fake content for testing"
_JSON_AIS = json.dumps(
    {
        "PAN": "ABCDE1234F",
        "Assessment_Year": "2025-26",
        "Name": "Test User",
        "AIS_Data": [
            {
                "Information_Category": "194A",
                "Transaction_Data": [
                    {
                        "Payer_Name": "SBI Bank",
                        "Account_Type": "savings",
                        "Interest_Amount": "10000",
                        "TDS_Amount": "0",
                    }
                ],
            }
        ],
    }
).encode()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _FakeDbSession:
    def __init__(self, session_id: uuid.UUID | None = None, profile_json: dict | None = None):
        self.id = session_id or uuid.uuid4()
        self.created_at = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        self.updated_at = self.created_at
        self.profile_json = profile_json or {}


def _mock_session_manager(session_found: bool = True, profile_json: dict | None = None):
    """Return a patched SessionManager that either returns a fake session or None."""
    fake_session = _FakeDbSession(profile_json=profile_json) if session_found else None
    sm = MagicMock()
    sm.get_session = AsyncMock(return_value=fake_session)
    sm.update_profile = AsyncMock(return_value=True)
    return sm


def _mock_parse_form16(gross_salary: int = 1_200_000, tds: int = 60_000):
    """Return a mock Form16Document."""
    from kara_api.parsers.form16 import (
        ChapterVIADeductions,
        Form16Document,
        Form16PartA,
        Form16PartB,
    )

    part_a = Form16PartA(
        employer_name="Acme Corp",
        employer_tan="AABC12345D",
        employee_name="Test Employee",
        employee_pan="ABCDE1234F",
        assessment_year="2025-26",
        total_tds_deposited=tds,
    )
    chapter_via = ChapterVIADeductions(sec_80c=150_000, sec_80d=25_000)
    part_b = Form16PartB(
        gross_salary=gross_salary,
        standard_deduction=50_000,
        chapter_via=chapter_via,
    )
    return Form16Document(part_a=part_a, part_b=part_b)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadDocumentRejectsInvalidFiles:
    async def test_rejects_file_too_large(self, client):
        big_content = b"X" * (10 * 1024 * 1024 + 1)
        session_id = str(uuid.uuid4())
        resp = await client.post(
            f"{BASE}/upload",
            data={"session_id": session_id, "document_type": "form16"},
            files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    async def test_rejects_empty_file(self, client):
        session_id = str(uuid.uuid4())
        resp = await client.post(
            f"{BASE}/upload",
            data={"session_id": session_id, "document_type": "form16"},
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert resp.status_code == 422

    async def test_rejects_wrong_mimetype_when_auto(self, client):
        """Plain text content with no PDF/JSON magic should get a 415."""
        session_id = str(uuid.uuid4())
        resp = await client.post(
            f"{BASE}/upload",
            data={"session_id": session_id, "document_type": "auto"},
            files={"file": ("test.txt", io.BytesIO(b"Hello world plain text"), "text/plain")},
        )
        assert resp.status_code == 415

    async def test_rejects_invalid_session_uuid_format(self, client):
        """A malformed session_id UUID should still return parsed result with warning."""
        with patch(
            "kara_api.routers.documents.parse_form16", return_value=_mock_parse_form16()
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": "not-a-valid-uuid", "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )
        # Should return 200 with a warning about session not found / UUID invalid
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "form16"


class TestUploadDocumentHappyPath:
    async def test_upload_form16_happy_path(self, client):
        fake_doc = _mock_parse_form16(gross_salary=1_200_000, tds=60_000)
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        assert resp.status_code == 200
        data = resp.json()

        assert data["document_type"] == "form16"
        assert "document_id" in data
        assert "parsed_summary" in data
        assert "profile_diff" in data

        summary = data["parsed_summary"]
        assert summary["document_type"] == "form16"
        assert summary["pan"] == "ABCDE1234F"
        assert summary["employer_name"] == "Acme Corp"
        assert summary["key_amounts"]["gross_salary"] == 1_200_000
        assert summary["key_amounts"]["total_tds"] == 60_000

        diff = data["profile_diff"]
        assert "gross_salary" in diff["slots_added"]
        assert diff["slots_added"]["gross_salary"] == 1_200_000

    async def test_upload_ais_json_happy_path(self, client):
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        with patch("kara_api.routers.documents._create_session_manager", return_value=sm):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "ais"},
                files={"file": ("ais.json", io.BytesIO(_JSON_AIS), "application/json")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "ais"
        assert "document_id" in data

    async def test_upload_returns_valid_document_id(self, client):
        fake_doc = _mock_parse_form16()
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        data = resp.json()
        doc_id = data["document_id"]
        # Should be a valid UUID4
        parsed = uuid.UUID(doc_id)
        assert str(parsed) == doc_id


class TestUploadDocumentSessionNotFound:
    async def test_session_not_found_still_returns_result(self, client):
        """When the session is not found, parse succeeds but autofill is skipped."""
        fake_doc = _mock_parse_form16(gross_salary=1_200_000)
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=False)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "form16"

        # Profile diff should be empty (no autofill)
        diff = data["profile_diff"]
        assert diff["slots_added"] == {}
        assert diff["slots_overridden"] == {}

        # Warning about session not found
        assert any("not found" in w.lower() for w in data["warnings"])

    async def test_session_not_found_update_profile_not_called(self, client):
        fake_doc = _mock_parse_form16()
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=False)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        sm.update_profile.assert_not_called()


class TestUploadDocumentAutoDetect:
    async def test_auto_detect_json_as_ais(self, client):
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        with patch("kara_api.routers.documents._create_session_manager", return_value=sm):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "auto"},
                files={"file": ("ais_data.json", io.BytesIO(_JSON_AIS), "application/json")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "ais"

    async def test_auto_detect_pdf_with_26as_filename(self, client):
        """PDF file with '26as' in filename should be detected as 26as type."""
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        from kara_api.parsers.twenty_six_as import Form26ASDocument, Form26ASTotals

        fake_26as = Form26ASDocument(source="pdf")
        fake_26as.totals = Form26ASTotals()

        with (
            patch("kara_api.routers.documents.parse_form_26as", return_value=fake_26as),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "auto"},
                files={
                    "file": (
                        "form26as_2025.pdf",
                        io.BytesIO(_PDF_MAGIC),
                        "application/pdf",
                    )
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "26as"

    async def test_auto_detect_pdf_defaults_to_form16(self, client):
        """PDF with no special filename should default to form16."""
        fake_doc = _mock_parse_form16()
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(session_found=True)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "auto"},
                files={
                    "file": ("tax_certificate.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "form16"


class TestUploadDocumentParseErrors:
    async def test_parse_error_returns_422(self, client):
        from kara_api.parsers.form16 import Form16ParseError

        session_id = str(uuid.uuid4())

        with patch(
            "kara_api.routers.documents.parse_form16",
            side_effect=Form16ParseError("Not a Form 16: test error"),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("bad.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        assert resp.status_code == 422

    async def test_invalid_json_returns_422(self, client):
        session_id = str(uuid.uuid4())
        bad_json = b"{not valid json at all"

        resp = await client.post(
            f"{BASE}/upload",
            data={"session_id": session_id, "document_type": "ais"},
            files={"file": ("ais.json", io.BytesIO(bad_json), "application/json")},
        )
        assert resp.status_code == 422


class TestUploadDocumentProfileUpdate:
    async def test_profile_updated_after_successful_form16_upload(self, client):
        fake_doc = _mock_parse_form16(gross_salary=1_500_000)
        session_id = str(uuid.uuid4())
        session_uuid = uuid.UUID(session_id)
        sm = _mock_session_manager(session_found=True)

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        assert resp.status_code == 200
        sm.update_profile.assert_called_once()
        call_args = sm.update_profile.call_args
        updated_profile: dict = call_args[0][1]  # second positional arg
        assert "slots" in updated_profile
        assert updated_profile["slots"]["gross_salary"] == 1_500_000

    async def test_existing_profile_slots_preserved_and_updated(self, client):
        """Slots already in the profile are preserved; new ones from the doc are added."""
        fake_doc = _mock_parse_form16(gross_salary=1_200_000, tds=60_000)
        session_id = str(uuid.uuid4())
        sm = _mock_session_manager(
            session_found=True,
            profile_json={"slots": {"regime": "old", "age_category": "below_60"}},
        )

        with (
            patch("kara_api.routers.documents.parse_form16", return_value=fake_doc),
            patch("kara_api.routers.documents._create_session_manager", return_value=sm),
        ):
            resp = await client.post(
                f"{BASE}/upload",
                data={"session_id": session_id, "document_type": "form16"},
                files={"file": ("form16.pdf", io.BytesIO(_PDF_MAGIC), "application/pdf")},
            )

        assert resp.status_code == 200
        sm.update_profile.assert_called_once()
        call_args = sm.update_profile.call_args
        updated_slots = call_args[0][1]["slots"]

        # Original slots should be preserved
        assert updated_slots["regime"] == "old"
        assert updated_slots["age_category"] == "below_60"
        # New slots from Form 16 should be added
        assert updated_slots["gross_salary"] == 1_200_000
