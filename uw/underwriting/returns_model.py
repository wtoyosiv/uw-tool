"""Calculate investment return metrics."""
import math
from typing import List, Optional
from uw.underwriting.models import CashFlowModel, UWAssumptions, IncomeModel, ExpenseModel, ReturnsModel


def build_returns_model(
    cash_flows: CashFlowModel,
    assumptions: UWAssumptions,
) -> ReturnsModel:
    notes = []
    purchase_price = assumptions.purchase_price
    noi_y1 = cash_flows.noi_year1
    equity = cash_flows.equity_invested
    flows = cash_flows.annual_flows

    # Cap rates
    going_in_cap = noi_y1 / purchase_price if purchase_price > 0 else 0.0
    stabilized_noi = flows[-1].noi if flows else noi_y1
    stabilized_cap = stabilized_noi / purchase_price if purchase_price > 0 else 0.0

    # Price ratios
    units = assumptions.total_units
    sqft = assumptions.total_sqft
    ppu = purchase_price / units if units > 0 else 0.0
    ppsf = purchase_price / sqft if sqft > 0 else 0.0

    # GRM
    gpr_y1 = flows[0].gpr if flows else 0.0
    grm = purchase_price / gpr_y1 if gpr_y1 > 0 else 0.0

    # Cash-on-cash year 1
    coc_y1 = flows[0].cash_on_cash if flows else 0.0
    avg_coc = sum(f.cash_on_cash for f in flows) / len(flows) if flows else 0.0

    # Levered IRR (equity flows in, sale proceeds out)
    levered_irr = _calculate_irr(equity, flows, cash_flows.sale_proceeds_net)

    # Unlevered IRR (purchase price in, exit value out, using NOI)
    unlevered_irr = _calculate_irr(
        purchase_price,
        flows,
        cash_flows.exit_value,
        use_noi=True
    )

    # Equity multiple
    total_in = equity
    total_out = cash_flows.total_cash_distributed + cash_flows.sale_proceeds_net
    eq_multiple = total_out / total_in if total_in > 0 else 0.0

    if going_in_cap < 0.04:
        notes.append(f"RISK: Going-in cap rate of {going_in_cap:.2%} is very low — verify assumptions")
    if eq_multiple < 1.0:
        notes.append("RISK: Equity multiple < 1.0 — deal may lose money")

    return ReturnsModel(
        going_in_cap_rate=going_in_cap,
        stabilized_cap_rate=stabilized_cap,
        price_per_unit=ppu,
        price_per_sqft=ppsf,
        gross_rent_multiplier=grm,
        cash_on_cash_year1=coc_y1,
        levered_irr=levered_irr,
        unlevered_irr=unlevered_irr,
        equity_multiple=eq_multiple,
        average_cash_on_cash=avg_coc,
        notes=notes,
    )


def _calculate_irr(
    initial_investment: float,
    flows,
    terminal_value: float,
    use_noi: bool = False,
) -> float:
    if initial_investment <= 0:
        return 0.0

    cash_flows = [-initial_investment]
    for i, f in enumerate(flows):
        annual_cf = f.noi if use_noi else f.net_cash_flow
        if i == len(flows) - 1:
            cash_flows.append(annual_cf + terminal_value)
        else:
            cash_flows.append(annual_cf)

    return _newton_irr(cash_flows)


def _npv(cash_flows: List[float], rate: float) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _newton_irr(cash_flows: List[float], guess: float = 0.10, tol: float = 1e-6, max_iter: int = 100) -> float:
    rate = guess
    for _ in range(max_iter):
        if rate <= -0.999999:
            break
        npv = _npv(cash_flows, rate)
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))
        if abs(dnpv) < 1e-12:
            break
        new_rate = rate - npv / dnpv
        if not math.isfinite(new_rate) or new_rate <= -0.999999:
            break
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate

    fallback = _bisection_irr(cash_flows, tol=tol)
    return fallback if fallback is not None else 0.0


def _bisection_irr(cash_flows: List[float], tol: float = 1e-6) -> Optional[float]:
    """Find a stable IRR root, returning None when no bracketed root exists."""
    low = -0.9999
    high = 10.0
    steps = 1000

    prev_rate = low
    prev_npv = _npv(cash_flows, prev_rate)
    if abs(prev_npv) < tol:
        return prev_rate

    for i in range(1, steps + 1):
        rate = low + (high - low) * i / steps
        npv = _npv(cash_flows, rate)
        if abs(npv) < tol:
            return rate
        if prev_npv * npv < 0:
            return _bisect_between(cash_flows, prev_rate, rate, tol)
        prev_rate = rate
        prev_npv = npv

    return None


def _bisect_between(cash_flows: List[float], low: float, high: float, tol: float) -> float:
    low_npv = _npv(cash_flows, low)
    for _ in range(100):
        mid = (low + high) / 2
        mid_npv = _npv(cash_flows, mid)
        if abs(mid_npv) < tol or abs(high - low) < tol:
            return mid
        if low_npv * mid_npv < 0:
            high = mid
        else:
            low = mid
            low_npv = mid_npv
    return (low + high) / 2
