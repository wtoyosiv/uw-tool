"""Calculate debt assumptions and debt service."""
import math
from uw.underwriting.models import UWAssumptions, DebtModel


def build_debt_model(assumptions: UWAssumptions, noi: float) -> DebtModel:
    notes = []
    purchase_price = assumptions.purchase_price

    if purchase_price <= 0:
        notes.append("ASSUMPTION: No purchase price — debt model uses $0")
        return DebtModel(notes=notes)

    loan_amount = purchase_price * assumptions.loan_to_value
    rate = assumptions.interest_rate
    amort = assumptions.amortization_years
    io_years = assumptions.io_period_years

    # Monthly payment (amortizing)
    monthly_rate = rate / 12
    n_payments = amort * 12
    if monthly_rate > 0:
        monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
                          ((1 + monthly_rate) ** n_payments - 1)
    else:
        monthly_payment = loan_amount / n_payments

    # IO payment
    monthly_io = loan_amount * monthly_rate

    # Year 1 debt service: IO if in IO period, else amortizing
    if io_years > 0:
        annual_ds = monthly_io * 12
        notes.append(f"ASSUMPTION: Interest-only for first {io_years} year(s)")
    else:
        annual_ds = monthly_payment * 12

    dscr = noi / annual_ds if annual_ds > 0 else 0.0
    debt_yield = noi / loan_amount if loan_amount > 0 else 0.0

    if dscr < 1.20:
        notes.append(f"RISK: DSCR of {dscr:.2f}x is below typical lender minimum of 1.20x")
    if debt_yield < 0.07:
        notes.append(f"RISK: Debt yield of {debt_yield:.1%} is below typical lender minimum of 7%")

    return DebtModel(
        loan_amount=loan_amount,
        loan_to_value=assumptions.loan_to_value,
        interest_rate=rate,
        amortization_years=amort,
        io_period_years=io_years,
        annual_debt_service=annual_ds,
        monthly_payment=monthly_payment,
        dscr=dscr,
        debt_yield=debt_yield,
        notes=notes,
    )
