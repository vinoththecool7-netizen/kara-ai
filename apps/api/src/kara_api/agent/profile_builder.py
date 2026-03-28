"""Profile builder: accumulates taxpayer slots and converts to TaxProfile.

Manages slot state across conversation turns, checks intent readiness
(which required slots are present), and converts accumulated data into
a ``kara_tax_engine.models.TaxProfile`` for computation.

Does **not** extract slots from text — that is the LLM's job.
"""
from __future__ import annotations

from typing import Any

from kara_api.agent.prompts import INTENT_SPECS, Intent


class ProfileBuilder:
    """Accumulates taxpayer information across conversation turns.

    Does NOT extract slots from text — that's the LLM's job.
    Only manages slot state, checks readiness, and converts to TaxProfile.
    """

    def __init__(self, initial_slots: dict[str, Any] | None = None) -> None:
        self._slots: dict[str, Any] = dict(initial_slots) if initial_slots else {}

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------

    def add_slot(self, name: str, value: Any) -> None:
        """Store a single slot value, overwriting if it already exists."""
        self._slots[name] = value

    def add_slots(self, slot_dict: dict[str, Any]) -> None:
        """Merge multiple slot values into the current state."""
        self._slots.update(slot_dict)

    def get_slot(self, name: str) -> Any | None:
        """Return the value of *name*, or ``None`` if not yet collected."""
        return self._slots.get(name)

    def get_filled_slots(self) -> dict[str, Any]:
        """Return a **copy** of all filled slots (safe to mutate)."""
        return dict(self._slots)

    def remove_slot(self, name: str) -> None:
        """Remove a single slot if present (no-op if absent)."""
        self._slots.pop(name, None)

    def clear(self) -> None:
        """Remove all accumulated slots."""
        self._slots.clear()

    @property
    def slot_count(self) -> int:
        """Number of currently filled slots."""
        return len(self._slots)

    # ------------------------------------------------------------------
    # Intent readiness
    # ------------------------------------------------------------------

    def get_missing_slots(self, intent: Intent) -> list[str]:
        """Return the list of required-but-unfilled slot names for *intent*."""
        spec = INTENT_SPECS[intent]
        return [s for s in spec.required_slots if s not in self._slots]

    def is_intent_ready(self, intent: Intent) -> bool:
        """``True`` when every required slot for *intent* is filled."""
        return len(self.get_missing_slots(intent)) == 0

    def get_ready_intents(self) -> list[Intent]:
        """Return every intent whose required slots are currently satisfied."""
        return [i for i in Intent if self.is_intent_ready(i)]

    # ------------------------------------------------------------------
    # Profile conversion
    # ------------------------------------------------------------------

    def to_tax_profile(self):
        """Convert accumulated slots to a ``TaxProfile``.

        Raises ``ValueError`` if no income source is present at all.
        """
        from kara_tax_engine.models import TaxProfile

        gross_salary = self._slots.get("gross_salary", 0)
        business_income = self._slots.get("business_income", 0)
        house_property_income = self._slots.get("house_property_income", 0)
        other_income = self._slots.get("other_income", 0)

        if not any([gross_salary, business_income, house_property_income, other_income]):
            raise ValueError("No income source provided")

        regime = self._slots.get("regime", "new")
        age_category = self._slots.get("age_category", "below_60")

        deductions = self._build_deductions()

        return TaxProfile(
            gross_salary=gross_salary,
            regime=regime,
            age_category=age_category,
            business_income=business_income,
            house_property_income=house_property_income,
            other_income=other_income,
            deductions=deductions,
        )

    def _build_deductions(self):
        """Extract deduction slots into a ``Deductions`` object."""
        from kara_tax_engine.models import Deductions

        mapping = {
            "section_80c": "section_80c",
            "section_80d": "section_80d",
            "section_80d_parents": "section_80d_parents",
            "section_80ccd_1b": "section_80ccd_1b",
            "section_80ccd_2": "section_80ccd_2",
            "section_80e": "section_80e",
            "section_80g": "section_80g",
            "section_80tta": "section_80tta",
            "section_24b": "section_24b",
            "hra_exemption": "hra_exemption",
        }

        ded = Deductions()
        for slot_name, field_name in mapping.items():
            value = self._slots.get(slot_name)
            if value is not None and hasattr(ded, field_name):
                setattr(ded, field_name, value)
        return ded

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize builder state to a plain dict."""
        return {"slots": dict(self._slots)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileBuilder:
        """Restore a builder from a dict produced by :meth:`to_dict`."""
        return cls(initial_slots=data.get("slots", {}))
