"""Build the expense model."""
from uw.underwriting.models import (
    HistoricalFinancials, UWAssumptions, IncomeModel, ExpenseModel, FinancialLineItem
)


def build_expense_model(
    financials: HistoricalFinancials,
    assumptions: UWAssumptions,
    income: IncomeModel,
) -> ExpenseModel:
    notes = []
    units = assumptions.total_units
    sqft = assumptions.total_sqft
    egi = income.effective_gross_income

    def from_financials(keywords: list) -> float:
        for item in financials.expense_items:
            if any(kw in item.label.lower() for kw in keywords):
                return item.amount
        return 0.0

    # --- Property Taxes ---
    taxes = from_financials(["property tax", "real estate tax", "tax"])
    if taxes == 0 and assumptions.property_tax_annual > 0:
        taxes = assumptions.property_tax_annual * assumptions.tax_reassessment_factor
        notes.append(f"ASSUMPTION: Taxes from config × reassessment factor {assumptions.tax_reassessment_factor}")
    elif taxes > 0 and assumptions.tax_reassessment_factor != 1.0:
        taxes *= assumptions.tax_reassessment_factor
        notes.append(f"Taxes reassessed by factor {assumptions.tax_reassessment_factor}")
    elif taxes == 0:
        # Rough estimate: 1.25% of purchase price
        taxes = assumptions.purchase_price * 0.0125
        notes.append("ASSUMPTION: Taxes estimated at 1.25% of purchase price — verify with actual tax bill")

    # --- Insurance ---
    insurance = from_financials(["insurance"])
    if insurance == 0:
        if units > 0:
            insurance = assumptions.insurance_per_unit * units
        elif sqft > 0:
            insurance = assumptions.insurance_per_sqft * sqft
        else:
            insurance = egi * 0.02
        notes.append("ASSUMPTION: Insurance estimated from per-unit/sqft defaults")

    # --- Management Fee ---
    mgmt = from_financials(["management fee", "management"])
    if mgmt == 0:
        mgmt = egi * assumptions.management_fee_pct
        notes.append(f"ASSUMPTION: Management = {assumptions.management_fee_pct:.1%} of EGI")

    # --- Payroll ---
    payroll = from_financials(["payroll", "wages", "salary", "labor"])
    if payroll == 0 and units > 0:
        payroll = assumptions.payroll_per_unit * units
        notes.append("ASSUMPTION: Payroll from per-unit default")

    # --- Repairs & Maintenance ---
    rm = from_financials(["repairs", "maintenance", "r&m"])
    if rm == 0:
        if units > 0:
            rm = assumptions.repairs_maintenance_per_unit * units
        elif assumptions.repairs_maintenance_pct_egi > 0:
            rm = egi * assumptions.repairs_maintenance_pct_egi
        else:
            rm = egi * 0.03
        notes.append("ASSUMPTION: R&M from per-unit default")

    # --- Utilities ---
    utilities = from_financials(["utilities", "electric", "gas", "water", "sewer"])
    if utilities == 0:
        if units > 0 and assumptions.utilities_per_unit > 0:
            utilities = assumptions.utilities_per_unit * units
        elif sqft > 0 and assumptions.utilities_per_sqft > 0:
            utilities = assumptions.utilities_per_sqft * sqft

    # --- Replacement Reserves ---
    reserves = from_financials(["reserves", "replacement"])
    if reserves == 0:
        if units > 0:
            reserves = assumptions.replacement_reserves_per_unit * units
        elif sqft > 0:
            reserves = assumptions.replacement_reserves_per_sqft * sqft
        notes.append("ASSUMPTION: Reserves from per-unit default")

    # --- CapEx ---
    capex = 0.0
    if units > 0 and assumptions.capex_per_unit > 0:
        capex = assumptions.capex_per_unit * units
    elif sqft > 0 and assumptions.capex_per_sqft > 0:
        capex = assumptions.capex_per_sqft * sqft

    # --- Other Expenses ---
    other = from_financials(["admin", "legal", "marketing", "professional", "misc",
                             "landscaping", "grounds", "trash", "pest", "elevator",
                             "security", "accounting"])

    total = taxes + insurance + mgmt + payroll + rm + utilities + reserves + capex + other

    # Reconcile against extracted T12 total — never silently understate expenses.
    # Any gap between our categorized sum and the extracted total goes into "other".
    if financials.total_expenses > 0 and financials.total_expenses > total:
        gap = financials.total_expenses - total
        other += gap
        total = financials.total_expenses
        notes.append(
            f"NOTE: ${gap:,.0f} of extracted T12 expenses unallocated to a category "
            f"— added to other expenses to match T12 total of ${financials.total_expenses:,.0f}"
        )

    expense_ratio = total / egi if egi > 0 else 0.0

    return ExpenseModel(
        property_taxes=taxes,
        insurance=insurance,
        management_fee=mgmt,
        payroll=payroll,
        repairs_maintenance=rm,
        utilities=utilities,
        replacement_reserves=reserves,
        capex=capex,
        other_expenses=other,
        total_operating_expenses=total,
        expense_ratio=expense_ratio,
        notes=notes,
    )
