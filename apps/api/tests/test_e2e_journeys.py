"""Ten end-to-end user journeys (original roadmap Days 69-70).

Each journey scripts the LLM's tool-calling behaviour with FakeLLMProvider
and runs the full pipeline — HTTP → chat router → AgentLoop → real
ToolRegistry → real tax engine — asserting on exact tool results, SSE
events, and session/profile state.
"""
from __future__ import annotations

import json

from kara_api.llm.providers import FakeLLMProvider
from tests.test_integration import (
    InMemorySessionManager,
    _fake_response,
    _integration_client,
    _tool_call,
    parse_sse_events,
)


def _tool_results(events: list[dict]) -> dict[str, dict | list]:
    """Map tool name -> parsed result from SSE events (last call wins)."""
    out: dict[str, dict | list] = {}
    for e in events:
        if e["type"] == "tool_result" and not e["is_error"]:
            out[e["tool_name"]] = json.loads(e["result"])
    return out


async def _run_turn(client, message: str, session_id: str | None = None) -> list[dict]:
    url = "/api/v1/chat" if session_id is None else f"/api/v1/chat/{session_id}"
    resp = await client.post(url, json={"message": message})
    assert resp.status_code == 200
    return parse_sse_events(resp.text)


# ---------------------------------------------------------------------------
# Journey 1: salaried employee, new regime, standard deduction
# ---------------------------------------------------------------------------


async def test_journey_salaried_new_regime():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[_tool_call("compute_tax", {"gross_salary": 1_500_000, "regime": "new"})]
            ),
            _fake_response(content="Your tax under the new regime is ₹97,500."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Tax on 15 lakh salary, new regime?")

    results = _tool_results(events)
    assert results["compute_tax"]["total_tax_payable"] == 97_500
    assert results["compute_tax"]["standard_deduction"] == 75_000
    # The structured card event must accompany the tool result
    assert any(e["type"] == "tax_breakdown" for e in events)
    # Profile captured the salary from the tool args
    done = events[-1]
    assert done["profile_state"]["slots"]["gross_salary"] == 1_500_000


# ---------------------------------------------------------------------------
# Journey 2: salaried, old regime, stacked deductions
# ---------------------------------------------------------------------------


async def test_journey_old_regime_stacked_deductions():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_tax",
                        {
                            "gross_salary": 1_800_000,
                            "regime": "old",
                            "deductions": {"80C": 150_000, "80D": 25_000, "80CCD1B": 50_000},
                        },
                    )
                ]
            ),
            _fake_response(content="Here's your old regime computation."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Old regime with my deductions?")

    breakdown = _tool_results(events)["compute_tax"]
    assert breakdown["total_deductions"] == 225_000
    # Slots captured per deduction section
    assert events[-1]["profile_state"]["slots"]["section_80c"] == 150_000


# ---------------------------------------------------------------------------
# Journey 3: senior citizen with pension + FD interest (80TTB capped)
# ---------------------------------------------------------------------------


async def test_journey_senior_pension_fd_interest():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_tax",
                        {
                            "gross_salary": 600_000,  # pension
                            "other_income": 80_000,  # FD interest
                            "regime": "old",
                            "age_category": "senior",
                            "deductions": {"80TTB": 80_000},
                        },
                    )
                ]
            ),
            _fake_response(content="As a senior citizen your 80TTB deduction caps at ₹50,000."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "I am 65, pension 6L and FD interest 80K")

    breakdown = _tool_results(events)["compute_tax"]
    ttb = next(d for d in breakdown["deductions_applied"] if d["section"] == "80TTB")
    assert ttb["allowed"] == 50_000  # capped


# ---------------------------------------------------------------------------
# Journey 4: presumptive business (44ADA) — advance tax in one installment
# ---------------------------------------------------------------------------


async def test_journey_presumptive_advance_tax():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "calculate_advance_tax",
                        {"total_estimated_tax": 240_000, "is_presumptive": True},
                    )
                ]
            ),
            _fake_response(content="Pay the full amount by 15 March."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Freelancer under 44ADA — advance tax?")

    schedule = _tool_results(events)["calculate_advance_tax"]
    assert schedule["required"] is True
    assert len(schedule["installments"]) == 1
    assert schedule["installments"][0]["due_date"] == "2026-03-15"
    assert schedule["installments"][0]["amount_due"] == 240_000


# ---------------------------------------------------------------------------
# Journey 5: equity mutual fund sale — 112A LTCG with exemption
# ---------------------------------------------------------------------------


async def test_journey_equity_mf_ltcg():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_capital_gains",
                        {
                            "transactions": [
                                {
                                    "asset_class": "equity_mf",
                                    "purchase_price": 800_000,
                                    "sale_price": 1_100_000,
                                    "holding_months": 30,
                                }
                            ]
                        },
                    )
                ]
            ),
            _fake_response(content="Your LTCG after the ₹1.25L exemption is ₹1.75L."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Sold equity MF after 2.5 years")

    gains = _tool_results(events)["compute_capital_gains"]
    assert gains[0]["gain_type"] == "long_term"
    assert gains[0]["total_gain"] == 300_000
    assert gains[0]["exempt_amount"] == 125_000
    assert gains[0]["taxable_gain"] == 175_000
    assert any(e["type"] == "capital_gains" for e in events)


# ---------------------------------------------------------------------------
# Journey 6: property sale with Section 54 reinvestment
# ---------------------------------------------------------------------------


async def test_journey_property_section_54():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_capital_gains",
                        {
                            "transactions": [
                                {
                                    "asset_class": "property",
                                    "purchase_price": 5_000_000,
                                    "sale_price": 9_000_000,
                                    "holding_months": 60,
                                    "section_54_amount": 3_000_000,
                                }
                            ]
                        },
                    )
                ]
            ),
            _fake_response(content="Section 54 shields the reinvested portion."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Sold my flat, bought a new one")

    gains = _tool_results(events)["compute_capital_gains"]
    assert gains[0]["total_gain"] == 4_000_000
    assert gains[0]["exempt_amount"] == 3_000_000
    assert gains[0]["taxable_gain"] == 1_000_000


# ---------------------------------------------------------------------------
# Journey 7: crypto trader — flat 30%, no exemptions
# ---------------------------------------------------------------------------


async def test_journey_crypto_trader():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_capital_gains",
                        {
                            "transactions": [
                                {
                                    "asset_class": "vda_crypto",
                                    "purchase_price": 300_000,
                                    "sale_price": 800_000,
                                    "holding_months": 26,
                                }
                            ]
                        },
                    )
                ]
            ),
            _fake_response(content="Crypto gains are taxed at a flat 30%."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "Sold bitcoin held 2 years")

    gains = _tool_results(events)["compute_capital_gains"]
    assert gains[0]["tax_rate"] == 0.30
    assert gains[0]["exempt_amount"] == 0
    assert gains[0]["tax_amount"] == 150_000


# ---------------------------------------------------------------------------
# Journey 8: NRI — ITR form selection
# ---------------------------------------------------------------------------


async def test_journey_nri_itr_selection():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "select_itr_form",
                        {
                            "total_income": 2_000_000,
                            "has_salary": True,
                            "residential_status": "non_resident",
                        },
                    )
                ]
            ),
            _fake_response(content="As an NRI you must file ITR-2."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "I work in Dubai with rental income in India")

    recommendation = _tool_results(events)["select_itr_form"]
    assert recommendation["form"] == "ITR-2"
    assert any("resident" in e for e in recommendation["exclusions_applied"])


# ---------------------------------------------------------------------------
# Journey 9: multi-source income across TWO turns — profile accumulates
# ---------------------------------------------------------------------------


async def test_journey_multi_turn_profile_accumulation():
    fake = FakeLLMProvider(
        responses=[
            # Turn 1: compute tax on salary + business
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compute_tax",
                        {"gross_salary": 1_200_000, "business_income": 400_000, "regime": "new"},
                    )
                ]
            ),
            _fake_response(content="Computed for salary + business."),
            # Turn 2: regime comparison with deductions
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "compare_regimes",
                        {
                            "gross_salary": 1_200_000,
                            "business_income": 400_000,
                            "deductions": {"80C": 150_000},
                        },
                    )
                ]
            ),
            _fake_response(content="Old regime wins with your deductions."),
        ]
    )
    sm = InMemorySessionManager()
    async with _integration_client(fake, sm) as ac:
        events1 = await _run_turn(ac, "Salary 12L and consulting income 4L")
        session_id = events1[0]["session_id"]
        events2 = await _run_turn(ac, "Which regime is better with 1.5L in 80C?", session_id)

    # Same session, profile accumulated across both turns
    slots = events2[-1]["profile_state"]["slots"]
    assert slots["gross_salary"] == 1_200_000
    assert slots["business_income"] == 400_000
    assert slots["section_80c"] == 150_000
    assert any(e["type"] == "regime_comparison" for e in events2)

    # Four messages persisted (2 user + 2 assistant)
    messages = await sm.get_messages(session_id_to_uuid(session_id))
    assert len(messages) == 4


def session_id_to_uuid(session_id: str):
    import uuid as _uuid

    return _uuid.UUID(session_id)


# ---------------------------------------------------------------------------
# Journey 10: TDS on rent + interest for missed advance tax
# ---------------------------------------------------------------------------


async def test_journey_tds_and_234_interest():
    fake = FakeLLMProvider(
        responses=[
            _fake_response(
                tool_calls=[
                    _tool_call(
                        "get_tds_rate",
                        {"payment_type": "rent_land_building", "amount": 60_000},
                    ),
                    _tool_call(
                        "calculate_interest_234",
                        {
                            "total_tax_liability": 100_000,
                            "advance_tax_paid": 0,
                            "as_of_date": "2026-07-31",
                        },
                    ),
                ]
            ),
            _fake_response(content="Your landlord TDS is 10% and interest is due."),
        ]
    )
    async with _integration_client(fake, InMemorySessionManager()) as ac:
        events = await _run_turn(ac, "TDS on 60K rent? And I paid no advance tax")

    results = _tool_results(events)
    tds = results["get_tds_rate"]
    assert tds["section"] == "194-I"
    assert tds["applicable"] is True
    assert tds["tds_amount"] == 6_000

    interest = results["calculate_interest_234"]
    assert interest["interest_234b"]["interest"] == 4_000
    assert interest["interest_234c"]["interest"] == 5_050
    assert interest["total_interest"] == 9_050
