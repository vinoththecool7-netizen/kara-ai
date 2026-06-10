from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from kara_tax_engine import (
    CapitalGainsCalculator,
    DeductionOptimizer,
    RegimeComparator,
    TaxComputer,
)
from kara_tax_engine.models import (
    CapitalGainsResult,
    CapitalGainTransaction,
    OptimizationResult,
    RegimeComparison,
    TaxBreakdown,
    TaxProfile,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tax", tags=["tax"])

# Module-level singletons — stateless, thread-safe
_computer = TaxComputer(fy="2025-26")
_comparator = RegimeComparator(fy="2025-26")
_optimizer = DeductionOptimizer(fy="2025-26")
_cg_calc = CapitalGainsCalculator(fy="2025-26")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CapitalGainsRequest(BaseModel):
    transactions: list[CapitalGainTransaction] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_engine_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a tax-engine function and translate exceptions to HTTP errors."""
    try:
        return func(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in tax engine")
        raise HTTPException(status_code=500, detail="Internal computation error") from exc


# ---------------------------------------------------------------------------
# Endpoints (sync — CPU-bound; FastAPI runs them in a threadpool)
# ---------------------------------------------------------------------------

@router.post("/compute", response_model=TaxBreakdown)
def compute_tax(profile: TaxProfile) -> TaxBreakdown:
    return _handle_engine_call(_computer.compute_from_profile, profile)


@router.post("/compare", response_model=RegimeComparison)
def compare_regimes(profile: TaxProfile) -> RegimeComparison:
    return _handle_engine_call(_comparator.compare, profile)


@router.post("/optimize", response_model=OptimizationResult)
def optimize_deductions(profile: TaxProfile) -> OptimizationResult:
    return _handle_engine_call(_optimizer.optimize, profile)


@router.post("/capital-gains", response_model=list[CapitalGainsResult])
def compute_capital_gains(request: CapitalGainsRequest) -> list[CapitalGainsResult]:
    txn_dicts = [t.model_dump() for t in request.transactions]
    return _handle_engine_call(_cg_calc.compute_multiple, txn_dicts)
