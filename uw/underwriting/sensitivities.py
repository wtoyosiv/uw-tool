"""Build sensitivity tables (cap rate vs NOI, exit cap vs returns, etc.)."""
from typing import List
from uw.underwriting.models import (
    IncomeModel, ExpenseModel, DebtModel, UWAssumptions, SensitivityTable
)


def build_sensitivities(
    income: IncomeModel,
    expenses: ExpenseModel,
    debt: DebtModel,
    assumptions: UWAssumptions,
) -> List[SensitivityTable]:
    tables = []

    purchase_price = assumptions.purchase_price
    if purchase_price <= 0:
        return tables

    base_noi = income.effective_gross_income - expenses.total_operating_expenses
    base_vacancy = assumptions.vacancy_rate
    base_exit_cap = assumptions.exit_cap_rate
    base_rate = assumptions.interest_rate
    hold = assumptions.hold_years

    # Table 1: Going-in Cap Rate vs Purchase Price
    noi_deltas = [-0.10, -0.05, 0.0, 0.05, 0.10]
    cap_rates = [0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07]
    noi_values = [round(base_noi * (1 + d)) for d in noi_deltas]
    matrix = []
    for cap in cap_rates:
        row = []
        for noi in noi_values:
            val = noi / cap if cap > 0 else 0
            row.append(round(val))
        matrix.append(row)

    tables.append(SensitivityTable(
        name="Value by Cap Rate and NOI",
        row_label="Exit Cap Rate",
        col_label="NOI Scenario",
        row_values=cap_rates,
        col_values=[round(n) for n in noi_values],
        matrix=matrix,
    ))

    # Table 2: Vacancy vs Rent Growth → NOI Year 1
    vacancy_vals = [0.03, 0.05, 0.07, 0.10, 0.15]
    rent_growth_vals = [0.01, 0.02, 0.03, 0.04, 0.05]
    gpr = income.gross_potential_rent
    credit_loss_rate = assumptions.credit_loss_rate
    total_exp = expenses.total_operating_expenses
    matrix2 = []
    for vac in vacancy_vals:
        row = []
        for rg in rent_growth_vals:
            adj_gpr = gpr * (1 + rg)
            adj_egi = adj_gpr * (1 - vac - credit_loss_rate) + income.other_income
            adj_noi = adj_egi - total_exp
            row.append(round(adj_noi))
        matrix2.append(row)

    tables.append(SensitivityTable(
        name="NOI by Vacancy and Rent Growth",
        row_label="Vacancy Rate",
        col_label="Rent Growth",
        row_values=vacancy_vals,
        col_values=rent_growth_vals,
        matrix=matrix2,
    ))

    # Table 3: Exit Cap Rate vs Hold Period → Implied Value
    hold_periods = [3, 4, 5, 7, 10]
    exit_caps = [0.045, 0.05, 0.055, 0.06, 0.065, 0.07]
    rent_growth = assumptions.rent_growth_annual
    matrix3 = []
    for exit_cap in exit_caps:
        row = []
        for yrs in hold_periods:
            exit_noi = base_noi * (1 + rent_growth) ** yrs
            exit_val = exit_noi / exit_cap if exit_cap > 0 else 0
            row.append(round(exit_val))
        matrix3.append(row)

    tables.append(SensitivityTable(
        name="Exit Value by Cap Rate and Hold Period",
        row_label="Exit Cap Rate",
        col_label="Hold Period (Years)",
        row_values=exit_caps,
        col_values=[float(h) for h in hold_periods],
        matrix=matrix3,
    ))

    return tables
