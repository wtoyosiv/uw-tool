"""Build year-by-year cash flow projections."""
import math
from typing import List
from uw.underwriting.models import (
    IncomeModel, ExpenseModel, DebtModel, UWAssumptions,
    CashFlowModel, AnnualCashFlow
)


def build_cash_flow_model(
    income: IncomeModel,
    expenses: ExpenseModel,
    debt: DebtModel,
    assumptions: UWAssumptions,
) -> CashFlowModel:
    purchase_price = assumptions.purchase_price
    equity = purchase_price * (1 - assumptions.loan_to_value) if purchase_price > 0 else 0.0
    equity += purchase_price * assumptions.closing_costs_pct if purchase_price > 0 else 0.0

    rent_growth = assumptions.rent_growth_annual
    expense_growth = assumptions.expense_growth_annual
    hold_years = assumptions.hold_years
    loan = debt.loan_amount
    rate = debt.interest_rate
    amort = debt.amortization_years
    io_years = debt.io_period_years

    # Pre-compute amortizing debt service so IO→amortizing switch is correct.
    monthly_rate = rate / 12
    n_payments = amort * 12
    if monthly_rate > 0 and n_payments > 0:
        monthly_amort_pmt = loan * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
                            ((1 + monthly_rate) ** n_payments - 1)
    else:
        monthly_amort_pmt = loan / n_payments if n_payments > 0 else 0.0
    annual_amort_ds = monthly_amort_pmt * 12
    annual_io_ds = loan * rate

    annual_flows: List[AnnualCashFlow] = []
    cumulative = 0.0
    remaining_balance = loan

    for yr in range(1, hold_years + 1):
        growth_factor_income = (1 + rent_growth) ** (yr - 1)
        growth_factor_expense = (1 + expense_growth) ** (yr - 1)

        gpr = income.gross_potential_rent * growth_factor_income
        egi = income.effective_gross_income * growth_factor_income
        noi = (egi - expenses.total_operating_expenses * growth_factor_expense)

        # IO in IO period, then switch to full amortizing payment
        if yr <= io_years:
            ds = annual_io_ds
        else:
            ds = annual_amort_ds

        ncf = noi - ds
        coc = ncf / equity if equity > 0 else 0.0
        cumulative += ncf

        annual_flows.append(AnnualCashFlow(
            year=yr,
            gpr=gpr,
            egi=egi,
            noi=noi,
            debt_service=ds,
            net_cash_flow=ncf,
            cash_on_cash=coc,
            cumulative_cash=cumulative,
        ))

        # Update loan balance (only amortizing payments reduce principal)
        if yr > io_years:
            for _ in range(12):
                interest = remaining_balance * monthly_rate
                principal = monthly_amort_pmt - interest
                remaining_balance = max(0, remaining_balance - principal)

    # Exit: use forward (next-year) NOI, not trailing — standard CRE convention.
    last_noi = annual_flows[-1].noi if annual_flows else income.effective_gross_income - expenses.total_operating_expenses
    exit_noi = last_noi * (1 + rent_growth)
    exit_value = exit_noi / assumptions.exit_cap_rate if assumptions.exit_cap_rate > 0 else 0.0
    sale_costs = exit_value * assumptions.disposition_costs_pct
    sale_proceeds_net = exit_value - remaining_balance - sale_costs

    total_cash = sum(f.net_cash_flow for f in annual_flows)

    return CashFlowModel(
        equity_invested=equity,
        noi_year1=annual_flows[0].noi if annual_flows else 0.0,
        annual_flows=annual_flows,
        total_cash_distributed=total_cash,
        exit_value=exit_value,
        loan_payoff=remaining_balance,
        sale_proceeds_net=sale_proceeds_net,
    )
