"""Comprehensive API tests for /api/v1/tax/ endpoints (Days 25-26)."""

from __future__ import annotations


BASE = "/api/v1/tax"


# ---------------------------------------------------------------------------
# POST /api/v1/tax/compute
# ---------------------------------------------------------------------------


class TestComputeTax:
    """Tests for the tax computation endpoint."""

    async def test_compute_basic_new_regime(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={"gross_salary": 1_500_000, "regime": "new"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regime"] == "new"
        assert data["gross_salary"] == 1_500_000
        assert data["total_tax_payable"] >= 0
        assert "slab_breakdown" in data

    async def test_compute_old_regime_with_deductions(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={
                "gross_salary": 1_500_000,
                "regime": "old",
                "deductions": {
                    "section_80c": 150_000,
                    "section_80d": 25_000,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regime"] == "old"
        assert data["total_deductions"] > 0

    async def test_compute_zero_salary(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={"gross_salary": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tax_payable"] == 0

    async def test_compute_senior_citizen(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={
                "gross_salary": 800_000,
                "regime": "old",
                "age_category": "senior",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["age_category"] == "senior"

    async def test_compute_invalid_regime_returns_422(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={"regime": "invalid"},
        )
        assert resp.status_code == 422

    async def test_compute_empty_body_uses_defaults(self, client):
        resp = await client.post(f"{BASE}/compute", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["regime"] == "new"
        assert data["total_tax_payable"] == 0

    async def test_compute_with_multiple_income_sources(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={
                "gross_salary": 1_000_000,
                "business_income": 500_000,
                "other_income": 200_000,
                "regime": "new",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["business_income"] == 500_000
        assert data["other_income"] == 200_000

    async def test_compute_response_has_computation_steps(self, client):
        resp = await client.post(
            f"{BASE}/compute",
            json={"gross_salary": 1_500_000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "computation_steps" in data
        assert len(data["computation_steps"]) > 0


# ---------------------------------------------------------------------------
# POST /api/v1/tax/compare
# ---------------------------------------------------------------------------


class TestCompareRegimes:
    """Tests for the regime comparison endpoint."""

    async def test_compare_basic(self, client):
        resp = await client.post(
            f"{BASE}/compare",
            json={"gross_salary": 1_500_000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "old_regime" in data
        assert "new_regime" in data
        assert "recommended_regime" in data
        assert "savings" in data
        assert data["recommended_regime"] in ("old", "new")
        assert data["savings"] >= 0

    async def test_compare_with_heavy_deductions(self, client):
        resp = await client.post(
            f"{BASE}/compare",
            json={
                "gross_salary": 2_000_000,
                "deductions": {
                    "section_80c": 150_000,
                    "section_80d": 50_000,
                    "section_80ccd_1b": 50_000,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["old_regime"]["total_deductions"] > 0
        assert isinstance(data["breakeven_deductions"], int)

    async def test_compare_empty_body(self, client):
        resp = await client.post(f"{BASE}/compare", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["old_regime"]["total_tax_payable"] == 0
        assert data["new_regime"]["total_tax_payable"] == 0


# ---------------------------------------------------------------------------
# POST /api/v1/tax/optimize
# ---------------------------------------------------------------------------


class TestOptimizeDeductions:
    """Tests for the deduction optimization endpoint."""

    async def test_optimize_basic(self, client):
        resp = await client.post(
            f"{BASE}/optimize",
            json={"gross_salary": 1_500_000, "regime": "old"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_tax"] >= 0
        assert data["section_80c_remaining"] > 0
        assert len(data["suggestions"]) > 0

    async def test_optimize_maxed_deductions(self, client):
        resp = await client.post(
            f"{BASE}/optimize",
            json={
                "gross_salary": 1_500_000,
                "regime": "old",
                "deductions": {
                    "section_80c": 150_000,
                    "section_80ccd_1b": 50_000,
                    "section_80d": 25_000,
                    "section_80d_parents": 50_000,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_80c_remaining"] == 0

    async def test_optimize_empty_body(self, client):
        resp = await client.post(f"{BASE}/optimize", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_tax"] == 0


# ---------------------------------------------------------------------------
# POST /api/v1/tax/capital-gains
# ---------------------------------------------------------------------------


class TestCapitalGains:
    """Tests for the capital gains computation endpoint."""

    async def test_capital_gains_single_equity(self, client):
        resp = await client.post(
            f"{BASE}/capital-gains",
            json={
                "transactions": [
                    {
                        "asset_class": "listed_equity",
                        "purchase_price": 100_000,
                        "sale_price": 250_000,
                        "holding_months": 18,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "listed_equity"
        assert data[0]["gain_type"] == "long_term"
        assert data[0]["tax_amount"] >= 0

    async def test_capital_gains_multiple_transactions(self, client):
        resp = await client.post(
            f"{BASE}/capital-gains",
            json={
                "transactions": [
                    {
                        "asset_class": "listed_equity",
                        "purchase_price": 100_000,
                        "sale_price": 250_000,
                        "holding_months": 18,
                    },
                    {
                        "asset_class": "property",
                        "purchase_price": 5_000_000,
                        "sale_price": 7_500_000,
                        "holding_months": 30,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_capital_gains_empty_transactions_returns_422(self, client):
        resp = await client.post(
            f"{BASE}/capital-gains",
            json={"transactions": []},
        )
        assert resp.status_code == 422

    async def test_capital_gains_missing_transactions_returns_422(self, client):
        resp = await client.post(f"{BASE}/capital-gains", json={})
        assert resp.status_code == 422

    async def test_capital_gains_invalid_asset_class_returns_422(self, client):
        resp = await client.post(
            f"{BASE}/capital-gains",
            json={
                "transactions": [
                    {
                        "asset_class": "invalid_class",
                        "purchase_price": 100_000,
                        "sale_price": 200_000,
                        "holding_months": 12,
                    },
                ],
            },
        )
        assert resp.status_code == 422

    async def test_capital_gains_loss_scenario(self, client):
        resp = await client.post(
            f"{BASE}/capital-gains",
            json={
                "transactions": [
                    {
                        "asset_class": "listed_equity",
                        "purchase_price": 200_000,
                        "sale_price": 100_000,
                        "holding_months": 6,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["total_gain"] < 0
        assert data[0]["tax_amount"] == 0
