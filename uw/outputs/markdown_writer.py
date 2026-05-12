"""Write Markdown reports: summary, assumptions, missing info, risk flags."""
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def write_markdown_reports(model_data: Dict[str, Any], output_dir: Path):
    output_dir.mkdir(exist_ok=True)

    prop = model_data.get("property_info")
    assumptions = model_data.get("assumptions")
    income = model_data.get("income")
    expenses = model_data.get("expenses")
    debt = model_data.get("debt")
    returns = model_data.get("returns")
    cash_flows = model_data.get("cash_flows")

    _write_summary(output_dir, prop, assumptions, income, expenses, debt, returns, cash_flows)
    _write_assumptions(output_dir, assumptions)
    _write_missing_info(output_dir, income, expenses, debt, assumptions, model_data.get("classified_files", []))
    _write_risk_flags(output_dir, income, expenses, debt, returns, assumptions)


def _fmt(v, is_currency=False, is_pct=False):
    if v is None or v == 0:
        return "—"
    if is_currency:
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        return f"${v:,.0f}"
    if is_pct:
        return f"{v:.2%}"
    return str(v)


def _write_summary(output_dir, prop, assumptions, income, expenses, debt, returns, cash_flows):
    pp = assumptions.purchase_price if assumptions else 0
    noi = (income.effective_gross_income - expenses.total_operating_expenses) if income and expenses else 0
    lines = [
        f"# Underwriting Summary",
        f"**Property:** {prop.name if prop else 'Unknown'}",
        f"**Type:** {assumptions.property_type.title() if assumptions else '—'}",
        f"**Run Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Purchase Price | {_fmt(pp, is_currency=True)} |",
    ]

    if assumptions and assumptions.total_units:
        lines.append(f"| Units | {assumptions.total_units:,} |")
    if assumptions and assumptions.total_sqft:
        lines.append(f"| Total SF | {assumptions.total_sqft:,.0f} |")

    if income:
        lines += [
            f"| Gross Potential Rent | {_fmt(income.gross_potential_rent, is_currency=True)} |",
            f"| Vacancy ({_fmt(assumptions.vacancy_rate if assumptions else 0, is_pct=True)}) | ({_fmt(income.vacancy_loss, is_currency=True)}) |",
            f"| Effective Gross Income | {_fmt(income.effective_gross_income, is_currency=True)} |",
        ]
    if expenses:
        lines.append(f"| Total Operating Expenses | ({_fmt(expenses.total_operating_expenses, is_currency=True)}) |")

    lines.append(f"| **NOI (Year 1)** | **{_fmt(noi, is_currency=True)}** |")

    if debt and debt.loan_amount > 0:
        lines += [
            f"| Loan Amount | {_fmt(debt.loan_amount, is_currency=True)} |",
            f"| Annual Debt Service | ({_fmt(debt.annual_debt_service, is_currency=True)}) |",
            f"| DSCR | {debt.dscr:.2f}x |",
            f"| Debt Yield | {_fmt(debt.debt_yield, is_pct=True)} |",
        ]

    if returns:
        lines += [
            "",
            "---",
            "",
            "## Investment Returns",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Going-in Cap Rate | {_fmt(returns.going_in_cap_rate, is_pct=True)} |",
            f"| Stabilized Cap Rate | {_fmt(returns.stabilized_cap_rate, is_pct=True)} |",
            f"| Cash-on-Cash (Yr 1) | {_fmt(returns.cash_on_cash_year1, is_pct=True)} |",
            f"| Avg Cash-on-Cash | {_fmt(returns.average_cash_on_cash, is_pct=True)} |",
            f"| Levered IRR | {_fmt(returns.levered_irr, is_pct=True)} |",
            f"| Unlevered IRR | {_fmt(returns.unlevered_irr, is_pct=True)} |",
            f"| Equity Multiple | {returns.equity_multiple:.2f}x |",
        ]
        if assumptions and assumptions.total_units:
            lines.append(f"| Price per Unit | {_fmt(returns.price_per_unit, is_currency=True)} |")
        if assumptions and assumptions.total_sqft:
            lines.append(f"| Price per SF | ${returns.price_per_sqft:.2f} |")

    if cash_flows:
        lines += [
            "",
            "---",
            "",
            "## Annual Cash Flows",
            "",
            "| Year | GPR | EGI | NOI | Debt Service | Net CF | CoC |",
            "|------|-----|-----|-----|-------------|--------|-----|",
        ]
        for f in cash_flows.annual_flows:
            lines.append(
                f"| {f.year} | {_fmt(f.gpr, is_currency=True)} | {_fmt(f.egi, is_currency=True)} | "
                f"{_fmt(f.noi, is_currency=True)} | ({_fmt(f.debt_service, is_currency=True)}) | "
                f"{_fmt(f.net_cash_flow, is_currency=True)} | {_fmt(f.cash_on_cash, is_pct=True)} |"
            )
        lines += [
            "",
            f"**Exit Value:** {_fmt(cash_flows.exit_value, is_currency=True)}  ",
            f"**Loan Payoff:** ({_fmt(cash_flows.loan_payoff, is_currency=True)})  ",
            f"**Net Sale Proceeds:** {_fmt(cash_flows.sale_proceeds_net, is_currency=True)}  ",
        ]

    _save(output_dir / "underwriting_summary.md", lines)


def _write_assumptions(output_dir, assumptions):
    if not assumptions:
        _save(output_dir / "assumptions_used.md", ["# Assumptions Used", "No assumptions available."])
        return

    lines = [
        "# Assumptions Used",
        "",
        "Items marked **[ASSUMPTION]** were not found in the source documents and were estimated.",
        "",
        "## Income Assumptions",
        f"- Vacancy Rate: {assumptions.vacancy_rate:.1%}",
        f"- Credit Loss: {assumptions.credit_loss_rate:.1%}",
        f"- Other Income (per unit): ${assumptions.other_income_per_unit:,.0f}",
        f"- Rent Growth (annual): {assumptions.rent_growth_annual:.1%}",
        "",
        "## Expense Assumptions",
        f"- Management Fee: {assumptions.management_fee_pct:.1%} of EGI",
        f"- R&M (per unit): ${assumptions.repairs_maintenance_per_unit:,.0f}",
        f"- Payroll (per unit): ${assumptions.payroll_per_unit:,.0f}",
        f"- Insurance (per unit): ${assumptions.insurance_per_unit:,.0f}",
        f"- Replacement Reserves (per unit): ${assumptions.replacement_reserves_per_unit:,.0f}",
        f"- Expense Growth (annual): {assumptions.expense_growth_annual:.1%}",
        f"- Tax Reassessment Factor: {assumptions.tax_reassessment_factor:.2f}x",
        "",
        "## Debt Assumptions",
        f"- Loan-to-Value: {assumptions.loan_to_value:.1%}",
        f"- Interest Rate: {assumptions.interest_rate:.2%}",
        f"- Amortization: {assumptions.amortization_years} years",
        f"- I/O Period: {assumptions.io_period_years} years",
        "",
        "## Exit Assumptions",
        f"- Hold Period: {assumptions.hold_years} years",
        f"- Exit Cap Rate: {assumptions.exit_cap_rate:.2%}",
        f"- Disposition Costs: {assumptions.disposition_costs_pct:.1%}",
        "",
    ]

    if assumptions.assumption_flags:
        lines += ["## Flagged Assumptions", ""]
        for flag in assumptions.assumption_flags:
            lines.append(f"- ⚠️ {flag}")

    _save(output_dir / "assumptions_used.md", lines)


def _write_missing_info(output_dir, income, expenses, debt, assumptions, classified_files):
    missing = []

    if assumptions and assumptions.purchase_price == 0:
        missing.append(("CRITICAL", "Purchase Price", "Not found in documents", "Provide OM, term sheet, or enter via --price flag"))
    if not any(cf.category.value == "rent_roll" for cf in classified_files if hasattr(cf, "category")):
        missing.append(("HIGH", "Rent Roll", "No rent roll found", "Provide Excel rent roll with unit, rent, and sqft columns"))
    if not any(cf.category.value == "t12" for cf in classified_files if hasattr(cf, "category")):
        missing.append(("HIGH", "T12 / Historical Financials", "No T12 found", "Provide trailing 12-month P&L"))
    if debt and debt.loan_amount == 0:
        missing.append(("MEDIUM", "Debt Terms", "No loan quote found", "Provide debt quote or use --rate and --ltv flags"))
    if assumptions and assumptions.property_tax_annual == 0:
        missing.append(("MEDIUM", "Property Tax", "Estimated from purchase price", "Provide actual tax bill for accuracy"))

    lines = ["# Missing Information", ""]
    if not missing:
        lines.append("No critical information missing. All key inputs found or estimated.")
    else:
        lines += [
            "The following inputs were not found in the provided documents.",
            "Items marked CRITICAL may significantly affect model accuracy.",
            "",
            "| Priority | Item | Status | Recommendation |",
            "|----------|------|--------|----------------|",
        ]
        for priority, item, status, rec in missing:
            lines.append(f"| {priority} | {item} | {status} | {rec} |")

    lines += [
        "",
        "## Recommended Next Steps",
        "",
        "1. Provide a rent roll if not already included",
        "2. Confirm purchase price",
        "3. Obtain a current tax bill (taxes often reassess after sale)",
        "4. Get a debt quote to replace default assumptions",
        "5. Compare seller pro forma expenses vs T12 actuals",
        "6. Verify insurance is correctly estimated",
        "7. Confirm unit count and square footage",
    ]

    _save(output_dir / "missing_info.md", lines)


def _write_risk_flags(output_dir, income, expenses, debt, returns, assumptions):
    flags = []

    if income and income.loss_to_lease > income.gross_potential_rent * 0.05:
        flags.append(("HIGH", "Loss to Lease", f"In-place rent is ${income.loss_to_lease:,.0f} below market — upside exists but underwrite conservatively"))

    if debt and debt.dscr > 0 and debt.dscr < 1.20:
        flags.append(("HIGH", "Low DSCR", f"DSCR of {debt.dscr:.2f}x is below typical lender minimum of 1.20x"))

    if debt and debt.debt_yield > 0 and debt.debt_yield < 0.07:
        flags.append(("MEDIUM", "Low Debt Yield", f"Debt yield of {debt.debt_yield:.1%} is below many lender minimums"))

    if assumptions and assumptions.tax_reassessment_factor == 1.0:
        flags.append(("MEDIUM", "Tax Reassessment", "Taxes may increase after sale — verify with local assessor methodology"))

    if expenses and income and income.effective_gross_income > 0:
        er = expenses.expense_ratio
        if er > 0.55:
            flags.append(("MEDIUM", "High Expense Ratio", f"Expense ratio of {er:.1%} is above typical range — review line items"))
        elif er < 0.25 and assumptions and assumptions.property_type not in ("net_lease", "industrial"):
            flags.append(("MEDIUM", "Low Expense Ratio", f"Expense ratio of {er:.1%} may be understated — verify all expenses"))

    if returns and returns.going_in_cap_rate > 0 and returns.going_in_cap_rate < 0.04:
        flags.append(("MEDIUM", "Aggressive Cap Rate", f"Going-in cap of {returns.going_in_cap_rate:.2%} implies significant rent growth assumptions"))

    if returns and returns.levered_irr < 0:
        flags.append(("CRITICAL", "Negative IRR", "Model shows negative levered IRR — deal likely does not work at this price"))

    lines = ["# Risk Flags", ""]
    if not flags:
        lines.append("No significant risk flags identified based on current model inputs.")
    else:
        lines += [
            "| Severity | Flag | Detail |",
            "|----------|------|--------|",
        ]
        for severity, flag, detail in flags:
            lines.append(f"| {severity} | {flag} | {detail} |")

    _save(output_dir / "risk_flags.md", lines)


def _save(path: Path, lines):
    path.write_text("\n".join(lines), encoding="utf-8")
