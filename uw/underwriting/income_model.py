"""Build the income model from rent roll + financials + assumptions."""
from uw.underwriting.models import (
    RentRollData, HistoricalFinancials, UWAssumptions, IncomeModel
)


def build_income_model(
    rent_roll: RentRollData,
    financials: HistoricalFinancials,
    assumptions: UWAssumptions,
) -> IncomeModel:
    notes = []

    # --- Gross Potential Rent ---
    if rent_roll.total_units > 0 and rent_roll.gross_potential_rent_monthly > 0:
        gpr = rent_roll.gross_potential_rent_monthly * 12
        notes.append(f"GPR sourced from rent roll ({rent_roll.total_units} units × monthly rents)")
    elif financials.gross_revenue > 0:
        gpr = financials.gross_revenue
        notes.append("GPR sourced from historical financials (no rent roll found)")
    elif assumptions.total_units > 0:
        # Placeholder — no data
        gpr = 0.0
        notes.append("ASSUMPTION: GPR is $0 — rent roll and financials missing. Provide documents.")
    else:
        gpr = 0.0
        notes.append("ASSUMPTION: GPR is $0 — no income data found.")

    # --- In-place vs Market ---
    in_place = rent_roll.in_place_rent_monthly * 12 if rent_roll.in_place_rent_monthly else gpr
    market = rent_roll.market_rent_monthly * 12 if rent_roll.market_rent_monthly else gpr
    loss_to_lease = max(0.0, market - in_place)

    # --- Use in-place for underwriting (conservative) ---
    uw_gpr = in_place if in_place > 0 else gpr

    # --- Vacancy ---
    vacancy_loss = uw_gpr * assumptions.vacancy_rate
    notes.append(f"ASSUMPTION: Vacancy = {assumptions.vacancy_rate:.1%}")

    # --- Credit Loss ---
    credit_loss = uw_gpr * assumptions.credit_loss_rate
    notes.append(f"ASSUMPTION: Credit loss = {assumptions.credit_loss_rate:.1%}")

    # --- Other Income ---
    # Prefer actual other-income line items from T12 over defaults.
    OTHER_INCOME_KEYWORDS = ["other income", "laundry", "parking", "late fee",
                             "pet fee", "storage", "vending", "misc income",
                             "miscellaneous income", "ancillary", "security deposit"]
    extracted_other = sum(
        item.amount for item in financials.income_items
        if any(kw in item.label.lower() for kw in OTHER_INCOME_KEYWORDS)
    )
    if extracted_other > 0:
        other_income = extracted_other
        notes.append(f"Other income sourced from T12 (${extracted_other:,.0f})")
    elif assumptions.total_units > 0:
        other_income = assumptions.other_income_per_unit * assumptions.total_units
        notes.append(f"ASSUMPTION: Other income = ${assumptions.other_income_per_unit:,.0f}/unit/yr")
    else:
        other_income = uw_gpr * assumptions.other_income_pct_gpr
        notes.append(f"ASSUMPTION: Other income = {assumptions.other_income_pct_gpr:.1%} of GPR")

    # --- EGI ---
    egi = uw_gpr - vacancy_loss - credit_loss + other_income

    return IncomeModel(
        gross_potential_rent=gpr,
        in_place_rent=in_place,
        market_rent=market,
        loss_to_lease=loss_to_lease,
        vacancy_loss=vacancy_loss,
        credit_loss=credit_loss,
        other_income=other_income,
        effective_gross_income=egi,
        notes=notes,
    )
