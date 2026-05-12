"""Generate a professional multi-tab Excel underwriting workbook."""
from pathlib import Path
from typing import Dict, Any, List, Optional
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_NUMBER_COMMA_SEPARATED1


# ── Color Palette ────────────────────────────────────────────────────────────
DARK_NAVY = "1B2A3B"
MID_NAVY = "2E4057"
LIGHT_BLUE = "D6E4F0"
ACCENT_GOLD = "D4A843"
GREEN_POSITIVE = "1E7145"
RED_NEGATIVE = "C00000"
WHITE = "FFFFFF"
LIGHT_GRAY = "F5F5F5"
MID_GRAY = "CCCCCC"
ASSUMPTION_YELLOW = "FFF2CC"
INPUT_BLUE = "DCE6F1"

FMT_CURRENCY = '"$"#,##0'
FMT_CURRENCY_2 = '"$"#,##0.00'
FMT_PCT = '0.00%'
FMT_PCT_1 = '0.0%'
FMT_MULTIPLE = '0.00"x"'
FMT_INT = '#,##0'
FMT_DATE = 'MM/DD/YYYY'


def _font(bold=False, size=10, color=None, italic=False):
    return Font(bold=bold, size=size, color=color or "000000", italic=italic)


def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)


def _border(style="thin"):
    side = Side(style=style)
    return Border(left=side, right=side, top=side, bottom=side)


def _bottom_border():
    return Border(bottom=Side(style="thin"))


def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def _header_row(ws, row: int, cols: List[str], start_col: int = 1):
    for i, label in enumerate(cols):
        cell = ws.cell(row=row, column=start_col + i, value=label)
        cell.font = _font(bold=True, color=WHITE)
        cell.fill = _fill(DARK_NAVY)
        cell.alignment = _align("center")
        cell.border = _border()


def _section_header(ws, row: int, col: int, label: str, span: int = 2):
    cell = ws.cell(row=row, column=col, value=label)
    cell.font = _font(bold=True, color=WHITE, size=11)
    cell.fill = _fill(MID_NAVY)
    cell.alignment = _align()
    if span > 1:
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + span - 1)


def _label_value(ws, row: int, label: str, value, fmt: str = None,
                 is_assumption: bool = False, note: str = ""):
    lc = ws.cell(row=row, column=1, value=label)
    lc.font = _font()
    lc.alignment = _align()

    vc = ws.cell(row=row, column=2, value=value)
    vc.font = _font(bold=True)
    vc.alignment = _align("right")
    if fmt:
        vc.number_format = fmt
    if is_assumption:
        vc.fill = _fill(ASSUMPTION_YELLOW)
    if note:
        nc = ws.cell(row=row, column=3, value=f"{'[ASSUMPTION] ' if is_assumption else ''}{note}")
        nc.font = _font(italic=True, color="666666", size=9)


def write_excel(model_data: Dict[str, Any], output_dir: Path):
    wb = Workbook()

    prop = model_data.get("property_info")
    assumptions = model_data.get("assumptions")
    income = model_data.get("income")
    expenses = model_data.get("expenses")
    debt = model_data.get("debt")
    cash_flows = model_data.get("cash_flows")
    returns = model_data.get("returns")
    sensitivities = model_data.get("sensitivities", [])
    classified = model_data.get("classified_files", [])
    financials = model_data.get("financials")
    rent_roll_data = model_data.get("rent_roll")

    _build_summary(wb, prop, assumptions, income, expenses, debt, returns, cash_flows)
    _build_sources(wb, classified)
    _build_assumptions(wb, assumptions)
    _build_rent_roll(wb, rent_roll_data)
    _build_income(wb, income, assumptions)
    _build_expenses(wb, expenses, assumptions)
    _build_debt(wb, debt, assumptions)
    _build_cash_flow(wb, cash_flows, assumptions)
    _build_returns(wb, returns, assumptions)
    _build_sensitivities(wb, sensitivities)
    _build_risks(wb, income, expenses, debt, returns, assumptions)

    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    path = output_dir / "underwriting_model.xlsx"
    wb.save(str(path))


def _set_col_widths(ws, widths: Dict[int, int]):
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w


def _freeze(ws, row: int = 2, col: int = 1):
    from openpyxl.utils.cell import get_column_letter
    ws.freeze_panes = f"{get_column_letter(col)}{row}"


# ── TAB: Summary ─────────────────────────────────────────────────────────────
def _build_summary(wb, prop, assumptions, income, expenses, debt, returns, cash_flows):
    ws = wb.create_sheet("Summary")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 32, 2: 22, 3: 42})

    row = 1
    # Title banner
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1, value="COMMERCIAL REAL ESTATE UNDERWRITING MODEL")
    c.font = _font(bold=True, size=16, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 1

    prop_name = prop.name if prop else "Property"
    prop_type = (assumptions.property_type.title().replace("_", " ")) if assumptions else "—"
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1, value=f"{prop_name}  |  {prop_type}")
    c.font = _font(bold=True, size=12, color=WHITE)
    c.fill = _fill(MID_NAVY)
    c.alignment = _align("center")
    row += 2

    def add_section(title, rows_data):
        nonlocal row
        _section_header(ws, row, 1, title, span=3)
        row += 1
        for label, value, fmt, is_assump, note in rows_data:
            _label_value(ws, row, label, value, fmt=fmt, is_assumption=is_assump, note=note)
            row += 1
        row += 1

    pp = assumptions.purchase_price if assumptions else 0
    noi_y1 = (income.effective_gross_income - expenses.total_operating_expenses) if income and expenses else 0
    equity = cash_flows.equity_invested if cash_flows else 0

    property_rows = [
        ("Purchase Price", pp, FMT_CURRENCY, not bool(prop and prop.purchase_price), ""),
        ("Property Type", prop_type, None, False, ""),
    ]
    if assumptions and assumptions.total_units:
        property_rows.append(("Total Units", assumptions.total_units, FMT_INT, False, ""))
    if assumptions and assumptions.total_sqft:
        property_rows.append(("Total Rentable SF", assumptions.total_sqft, FMT_INT, False, ""))
    if prop and prop.year_built:
        property_rows.append(("Year Built", prop.year_built, "#,##0", False, ""))

    add_section("PROPERTY OVERVIEW", property_rows)

    income_rows = []
    if income:
        income_rows = [
            ("Gross Potential Rent", income.gross_potential_rent, FMT_CURRENCY, False, "In-place rents annualized"),
            ("Loss to Lease", -income.loss_to_lease if income.loss_to_lease else 0, FMT_CURRENCY, False, ""),
            ("Vacancy Loss", -income.vacancy_loss, FMT_CURRENCY, True, f"{assumptions.vacancy_rate:.1%}" if assumptions else ""),
            ("Credit Loss", -income.credit_loss, FMT_CURRENCY, True, f"{assumptions.credit_loss_rate:.1%}" if assumptions else ""),
            ("Other Income", income.other_income, FMT_CURRENCY, True, ""),
            ("Effective Gross Income", income.effective_gross_income, FMT_CURRENCY, False, ""),
        ]
    add_section("INCOME", income_rows)

    exp_rows = []
    if expenses:
        exp_rows = [
            ("Property Taxes", expenses.property_taxes, FMT_CURRENCY, False, ""),
            ("Insurance", expenses.insurance, FMT_CURRENCY, False, ""),
            ("Management Fee", expenses.management_fee, FMT_CURRENCY, True, f"{assumptions.management_fee_pct:.1%} of EGI" if assumptions else ""),
            ("Payroll", expenses.payroll, FMT_CURRENCY, True, ""),
            ("Repairs & Maintenance", expenses.repairs_maintenance, FMT_CURRENCY, True, ""),
            ("Utilities", expenses.utilities, FMT_CURRENCY, False, ""),
            ("Replacement Reserves", expenses.replacement_reserves, FMT_CURRENCY, True, ""),
            ("CapEx", expenses.capex, FMT_CURRENCY, True, ""),
            ("Other Expenses", expenses.other_expenses, FMT_CURRENCY, False, ""),
            ("Total Operating Expenses", expenses.total_operating_expenses, FMT_CURRENCY, False, f"Expense ratio: {expenses.expense_ratio:.1%}"),
        ]
    add_section("OPERATING EXPENSES", exp_rows)

    add_section("NET OPERATING INCOME", [
        ("NOI (Year 1)", noi_y1, FMT_CURRENCY, False, ""),
    ])

    debt_rows = []
    if debt:
        debt_rows = [
            ("Loan Amount", debt.loan_amount, FMT_CURRENCY, True, f"{debt.loan_to_value:.1%} LTV"),
            ("Interest Rate", debt.interest_rate, FMT_PCT, True, ""),
            ("Amortization", debt.amortization_years, '0" years"', True, ""),
            ("Annual Debt Service", debt.annual_debt_service, FMT_CURRENCY, False, ""),
            ("DSCR", debt.dscr, FMT_MULTIPLE, False, "Min 1.20x"),
            ("Debt Yield", debt.debt_yield, FMT_PCT, False, "Min 7.0%"),
        ]
    add_section("DEBT", debt_rows)

    returns_rows = []
    if returns:
        returns_rows = [
            ("Going-in Cap Rate", returns.going_in_cap_rate, FMT_PCT, False, ""),
            ("Stabilized Cap Rate", returns.stabilized_cap_rate, FMT_PCT, False, ""),
            ("Cash-on-Cash (Yr 1)", returns.cash_on_cash_year1, FMT_PCT, False, ""),
            ("Levered IRR", returns.levered_irr, FMT_PCT, False, f"{assumptions.hold_years if assumptions else 5}-yr hold"),
            ("Unlevered IRR", returns.unlevered_irr, FMT_PCT, False, ""),
            ("Equity Multiple", returns.equity_multiple, FMT_MULTIPLE, False, ""),
            ("Equity Invested", equity, FMT_CURRENCY, False, ""),
        ]
        if assumptions and assumptions.total_units:
            returns_rows.append(("Price per Unit", returns.price_per_unit, FMT_CURRENCY, False, ""))
        if assumptions and assumptions.total_sqft:
            returns_rows.append(("Price per SF", returns.price_per_sqft, FMT_CURRENCY_2, False, ""))
    add_section("INVESTMENT RETURNS", returns_rows)

    _freeze(ws, row=3)


# ── TAB: Sources ─────────────────────────────────────────────────────────────
def _build_sources(wb, classified):
    ws = wb.create_sheet("Sources")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 16, 3: 22, 4: 14, 5: 40})

    row = 1
    ws.merge_cells(f"A{row}:E{row}")
    c = ws.cell(row=row, column=1, value="SOURCE DOCUMENTS REVIEWED")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    _header_row(ws, row, ["File Name", "Extension", "Category", "Confidence", "Notes"])
    row += 1

    for i, cf in enumerate(classified):
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        data = [
            cf.filename,
            cf.extension,
            cf.category.value.replace("_", " ").title(),
            cf.confidence,
            cf.notes,
        ]
        for j, val in enumerate(data):
            cell = ws.cell(row=row, column=j + 1, value=val)
            cell.fill = _fill(bg)
            cell.font = _font()
            cell.alignment = _align()
            if j == 3:
                cell.number_format = FMT_PCT_1
        row += 1

    _freeze(ws, row=3)


# ── TAB: Assumptions ─────────────────────────────────────────────────────────
def _build_assumptions(wb, assumptions):
    ws = wb.create_sheet("Assumptions")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 20, 3: 14, 4: 40})

    row = 1
    ws.merge_cells(f"A{row}:D{row}")
    c = ws.cell(row=row, column=1, value="ASSUMPTIONS")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    note_row = ws.cell(row=row, column=1,
        value="Yellow = assumption (not from documents).  Blue = extracted from documents.")
    note_row.font = _font(italic=True, size=9, color="666666")
    row += 2

    def add_group(title, items):
        nonlocal row
        _section_header(ws, row, 1, title, span=4)
        row += 1
        for label, value, fmt, is_assump in items:
            lc = ws.cell(row=row, column=1, value=label)
            lc.font = _font()
            vc = ws.cell(row=row, column=2, value=value)
            vc.font = _font(bold=True)
            vc.alignment = _align("right")
            vc.fill = _fill(ASSUMPTION_YELLOW if is_assump else INPUT_BLUE)
            if fmt:
                vc.number_format = fmt
            row += 1
        row += 1

    if not assumptions:
        return

    add_group("PROPERTY", [
        ("Purchase Price", assumptions.purchase_price, FMT_CURRENCY, assumptions.purchase_price == 0),
        ("Property Type", assumptions.property_type.title(), None, False),
        ("Total Units", assumptions.total_units, FMT_INT, assumptions.total_units == 0),
        ("Total Rentable SF", assumptions.total_sqft, FMT_INT, assumptions.total_sqft == 0),
        ("Hold Period", assumptions.hold_years, '0" years"', False),
    ])

    add_group("INCOME", [
        ("Vacancy Rate", assumptions.vacancy_rate, FMT_PCT, True),
        ("Credit Loss Rate", assumptions.credit_loss_rate, FMT_PCT, True),
        ("Other Income (per unit)", assumptions.other_income_per_unit, FMT_CURRENCY, True),
        ("Rent Growth (annual)", assumptions.rent_growth_annual, FMT_PCT, True),
    ])

    add_group("EXPENSES", [
        ("Management Fee", assumptions.management_fee_pct, FMT_PCT, True),
        ("Repairs & Maintenance (per unit)", assumptions.repairs_maintenance_per_unit, FMT_CURRENCY, True),
        ("Payroll (per unit)", assumptions.payroll_per_unit, FMT_CURRENCY, True),
        ("Insurance (per unit)", assumptions.insurance_per_unit, FMT_CURRENCY, True),
        ("Replacement Reserves (per unit)", assumptions.replacement_reserves_per_unit, FMT_CURRENCY, True),
        ("Tax Reassessment Factor", assumptions.tax_reassessment_factor, '0.00"x"', True),
        ("Expense Growth (annual)", assumptions.expense_growth_annual, FMT_PCT, True),
        ("CapEx (per unit)", assumptions.capex_per_unit, FMT_CURRENCY, True),
    ])

    add_group("DEBT", [
        ("Loan-to-Value", assumptions.loan_to_value, FMT_PCT, True),
        ("Interest Rate", assumptions.interest_rate, FMT_PCT, True),
        ("Amortization (years)", assumptions.amortization_years, '#,##0', True),
        ("I/O Period (years)", assumptions.io_period_years, '#,##0', True),
    ])

    add_group("EXIT", [
        ("Exit Cap Rate", assumptions.exit_cap_rate, FMT_PCT, True),
        ("Disposition Costs", assumptions.disposition_costs_pct, FMT_PCT, True),
        ("Closing Costs", assumptions.closing_costs_pct, FMT_PCT, True),
    ])


# ── TAB: Rent Roll ────────────────────────────────────────────────────────────
def _build_rent_roll(wb, rent_roll_data):
    ws = wb.create_sheet("Rent Roll")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 12, 2: 22, 3: 16, 4: 8, 8: 14, 5: 10, 6: 14, 7: 14})

    row = 1
    ws.merge_cells(f"A{row}:H{row}")
    c = ws.cell(row=row, column=1, value="RENT ROLL ANALYSIS")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not rent_roll_data or not rent_roll_data.units:
        ws.cell(row=row, column=1, value="No rent roll data extracted. Provide a rent roll spreadsheet.")
        return

    # Summary stats
    stats = [
        ("Total Units", rent_roll_data.total_units),
        ("Vacant Units", rent_roll_data.vacant_units),
        ("Physical Vacancy", f"{rent_roll_data.physical_vacancy_rate:.1%}"),
        ("Monthly GPR", f"${rent_roll_data.gross_potential_rent_monthly:,.0f}"),
        ("Annual GPR", f"${rent_roll_data.gross_potential_rent_monthly * 12:,.0f}"),
    ]
    if rent_roll_data.total_sqft:
        stats.append(("Total SF", f"{rent_roll_data.total_sqft:,.0f}"))

    for label, val in stats:
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = _font(bold=True)
        vc = ws.cell(row=row, column=2, value=val)
        vc.font = _font()
        row += 1
    row += 1

    # Unit table
    headers = ["Unit", "Tenant", "Type", "BR", "SF", "Current Rent", "Market Rent", "Status"]
    _header_row(ws, row, headers)
    row += 1

    for i, unit in enumerate(rent_roll_data.units):
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        status = "Vacant" if unit.vacant else "Occupied"
        data = [
            unit.unit_id, unit.tenant_name, unit.unit_type,
            unit.bedrooms, unit.sqft,
            unit.current_rent, unit.market_rent, status,
        ]
        for j, val in enumerate(data):
            cell = ws.cell(row=row, column=j + 1, value=val)
            cell.fill = _fill(bg)
            cell.font = _font()
            cell.alignment = _align()
            if j in (5, 6) and val:
                cell.number_format = FMT_CURRENCY
            if unit.vacant:
                cell.font = _font(color=RED_NEGATIVE)
        row += 1

    _freeze(ws, row=4)


# ── TAB: Income ───────────────────────────────────────────────────────────────
def _build_income(wb, income, assumptions):
    ws = wb.create_sheet("Income")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 18, 3: 18, 4: 36})

    row = 1
    ws.merge_cells(f"A{row}:D{row}")
    c = ws.cell(row=row, column=1, value="INCOME BUILD-UP")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not income:
        return

    rows = [
        ("Gross Potential Rent (Annual)", income.gross_potential_rent, False, "In-place rent × 12"),
        ("Loss to Lease", -income.loss_to_lease if income.loss_to_lease else 0, False, "Market vs in-place"),
        ("Effective Gross Potential Rent", income.gross_potential_rent - (income.loss_to_lease or 0), False, ""),
        (None, None, False, None),  # spacer
        ("Less: Vacancy Loss", -income.vacancy_loss, True, f"{assumptions.vacancy_rate:.1%}" if assumptions else ""),
        ("Less: Credit Loss", -income.credit_loss, True, f"{assumptions.credit_loss_rate:.1%}" if assumptions else ""),
        ("Plus: Other Income", income.other_income, True, "Laundry, parking, fees"),
        (None, None, False, None),
        ("Effective Gross Income (EGI)", income.effective_gross_income, False, ""),
    ]

    for label, value, is_assump, note in rows:
        if label is None:
            row += 1
            continue
        is_total = "Effective Gross Income" in label
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = _font(bold=is_total)
        vc = ws.cell(row=row, column=2, value=value)
        vc.font = _font(bold=is_total, color=RED_NEGATIVE if (value or 0) < 0 else "000000")
        vc.number_format = FMT_CURRENCY
        vc.alignment = _align("right")
        vc.fill = _fill(ASSUMPTION_YELLOW if is_assump else (LIGHT_BLUE if is_total else WHITE))
        if note:
            nc = ws.cell(row=row, column=3, value=note)
            nc.font = _font(italic=True, color="666666", size=9)
        if is_total:
            for col in range(1, 4):
                ws.cell(row=row, column=col).border = _bottom_border()
        row += 1

    # Year-by-year income growth table
    row += 2
    _section_header(ws, row, 1, "INCOME GROWTH PROJECTION", span=7)
    row += 1

    hold = assumptions.hold_years if assumptions else 5
    rent_growth = assumptions.rent_growth_annual if assumptions else 0.03
    headers = [""] + [f"Year {y}" for y in range(1, hold + 1)]
    _header_row(ws, row, headers)
    row += 1

    for label, base in [("GPR", income.gross_potential_rent), ("EGI", income.effective_gross_income)]:
        ws.cell(row=row, column=1, value=label).font = _font(bold=True)
        for y in range(1, hold + 1):
            val = base * (1 + rent_growth) ** (y - 1)
            c = ws.cell(row=row, column=y + 1, value=val)
            c.number_format = FMT_CURRENCY
            c.alignment = _align("right")
        row += 1


# ── TAB: Expenses ─────────────────────────────────────────────────────────────
def _build_expenses(wb, expenses, assumptions):
    ws = wb.create_sheet("Expenses")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 18, 3: 18, 4: 36})

    row = 1
    ws.merge_cells(f"A{row}:D{row}")
    c = ws.cell(row=row, column=1, value="OPERATING EXPENSE BUILD-UP")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not expenses:
        return

    items = [
        ("Property Taxes", expenses.property_taxes, False),
        ("Insurance", expenses.insurance, True),
        ("Management Fee", expenses.management_fee, True),
        ("Payroll", expenses.payroll, True),
        ("Repairs & Maintenance", expenses.repairs_maintenance, True),
        ("Utilities", expenses.utilities, False),
        ("Replacement Reserves", expenses.replacement_reserves, True),
        ("CapEx", expenses.capex, True),
        ("Other Expenses", expenses.other_expenses, False),
    ]

    for label, value, is_assump in items:
        if value == 0:
            continue
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = _font()
        vc = ws.cell(row=row, column=2, value=value)
        vc.font = _font()
        vc.number_format = FMT_CURRENCY
        vc.alignment = _align("right")
        vc.fill = _fill(ASSUMPTION_YELLOW if is_assump else WHITE)
        row += 1

    row += 1
    for col in range(1, 4):
        ws.cell(row=row, column=col).border = _bottom_border()
    tc = ws.cell(row=row, column=1, value="Total Operating Expenses")
    tc.font = _font(bold=True)
    tv = ws.cell(row=row, column=2, value=expenses.total_operating_expenses)
    tv.font = _font(bold=True)
    tv.number_format = FMT_CURRENCY
    tv.alignment = _align("right")
    tv.fill = _fill(LIGHT_BLUE)
    row += 1

    er = ws.cell(row=row, column=1, value="Expense Ratio")
    er.font = _font(italic=True)
    ev = ws.cell(row=row, column=2, value=expenses.expense_ratio)
    ev.number_format = FMT_PCT_1
    ev.alignment = _align("right")


# ── TAB: Debt ─────────────────────────────────────────────────────────────────
def _build_debt(wb, debt, assumptions):
    ws = wb.create_sheet("Debt")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 22, 3: 36})

    row = 1
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1, value="DEBT ASSUMPTIONS & DEBT SERVICE")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not debt:
        return

    items = [
        ("Purchase Price", assumptions.purchase_price if assumptions else 0, FMT_CURRENCY),
        ("Loan-to-Value", debt.loan_to_value, FMT_PCT),
        ("Loan Amount", debt.loan_amount, FMT_CURRENCY),
        ("Interest Rate", debt.interest_rate, FMT_PCT),
        ("Amortization (years)", debt.amortization_years, '#,##0'),
        ("I/O Period (years)", debt.io_period_years, '#,##0'),
        ("Monthly Payment", debt.monthly_payment, FMT_CURRENCY),
        ("Annual Debt Service", debt.annual_debt_service, FMT_CURRENCY),
        ("DSCR", debt.dscr, FMT_MULTIPLE),
        ("Debt Yield", debt.debt_yield, FMT_PCT),
    ]

    for label, value, fmt in items:
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = _font()
        vc = ws.cell(row=row, column=2, value=value)
        vc.font = _font(bold=True)
        vc.number_format = fmt
        vc.alignment = _align("right")
        vc.fill = _fill(ASSUMPTION_YELLOW)
        row += 1


# ── TAB: Cash Flow ────────────────────────────────────────────────────────────
def _build_cash_flow(wb, cash_flows, assumptions):
    ws = wb.create_sheet("Cash Flow")
    ws.sheet_view.showGridLines = False

    row = 1
    ws.merge_cells(f"A{row}:H{row}")
    c = ws.cell(row=row, column=1, value="LEVERED CASH FLOW ANALYSIS")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not cash_flows or not cash_flows.annual_flows:
        return

    hold = len(cash_flows.annual_flows)
    _set_col_widths(ws, {1: 30} | {i + 2: 16 for i in range(hold)})

    headers = [""] + [f"Year {f.year}" for f in cash_flows.annual_flows]
    _header_row(ws, row, headers)
    row += 1

    rows_def = [
        ("Gross Potential Rent", "gpr"),
        ("Effective Gross Income", "egi"),
        ("Net Operating Income", "noi"),
        ("Debt Service", "debt_service"),
        ("Net Cash Flow", "net_cash_flow"),
        ("Cash-on-Cash Return", "cash_on_cash"),
        ("Cumulative Cash Flow", "cumulative_cash"),
    ]

    for label, attr in rows_def:
        ws.cell(row=row, column=1, value=label).font = _font(bold="Net" in label or "NOI" in label)
        is_pct = "Return" in label
        is_total = "Net Cash Flow" in label

        for i, f in enumerate(cash_flows.annual_flows):
            val = getattr(f, attr, 0)
            if attr == "debt_service":
                val = -abs(val)
            cell = ws.cell(row=row, column=i + 2, value=val)
            cell.number_format = FMT_PCT if is_pct else FMT_CURRENCY
            cell.alignment = _align("right")
            if val < 0:
                cell.font = _font(color=RED_NEGATIVE, bold=is_total)
            else:
                cell.font = _font(color=GREEN_POSITIVE if is_total else "000000", bold=is_total)
            if is_total:
                cell.fill = _fill(LIGHT_BLUE)
        row += 1

    row += 2
    _section_header(ws, row, 1, "EXIT / REVERSION", span=hold + 1)
    row += 1

    exit_items = [
        ("Exit Value (NOI ÷ Exit Cap)", cash_flows.exit_value),
        ("Loan Payoff", -cash_flows.loan_payoff),
        ("Disposition Costs", -(cash_flows.exit_value * (assumptions.disposition_costs_pct if assumptions else 0.02))),
        ("Net Sale Proceeds", cash_flows.sale_proceeds_net),
        ("Total Cash Distributed", cash_flows.total_cash_distributed),
        ("Equity Invested", -cash_flows.equity_invested),
        ("Net Profit", cash_flows.total_cash_distributed + cash_flows.sale_proceeds_net - cash_flows.equity_invested),
    ]

    for label, val in exit_items:
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = _font(bold="Net" in label or "Total" in label)
        vc = ws.cell(row=row, column=2, value=val)
        vc.number_format = FMT_CURRENCY
        vc.alignment = _align("right")
        vc.font = _font(bold="Net" in label, color=RED_NEGATIVE if val < 0 else "000000")
        row += 1

    _freeze(ws, row=3, col=2)


# ── TAB: Returns ─────────────────────────────────────────────────────────────
def _build_returns(wb, returns, assumptions):
    ws = wb.create_sheet("Returns")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 36, 2: 20, 3: 36})

    row = 1
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1, value="INVESTMENT RETURN SUMMARY")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    if not returns:
        return

    groups = [
        ("VALUATION METRICS", [
            ("Going-in Cap Rate", returns.going_in_cap_rate, FMT_PCT),
            ("Stabilized Cap Rate", returns.stabilized_cap_rate, FMT_PCT),
            ("Gross Rent Multiplier", returns.gross_rent_multiplier, FMT_MULTIPLE),
            ("Price per Unit", returns.price_per_unit, FMT_CURRENCY),
            ("Price per SF", returns.price_per_sqft, FMT_CURRENCY_2),
        ]),
        ("CASH RETURN METRICS", [
            ("Cash-on-Cash (Year 1)", returns.cash_on_cash_year1, FMT_PCT),
            ("Average Cash-on-Cash", returns.average_cash_on_cash, FMT_PCT),
        ]),
        ("TOTAL RETURN METRICS", [
            ("Levered IRR", returns.levered_irr, FMT_PCT),
            ("Unlevered IRR", returns.unlevered_irr, FMT_PCT),
            ("Equity Multiple", returns.equity_multiple, FMT_MULTIPLE),
        ]),
    ]

    for group_title, items in groups:
        _section_header(ws, row, 1, group_title, span=3)
        row += 1
        for label, value, fmt in items:
            if not value:
                continue
            lc = ws.cell(row=row, column=1, value=label)
            lc.font = _font()
            vc = ws.cell(row=row, column=2, value=value)
            vc.font = _font(bold=True, color=GREEN_POSITIVE if value > 0 else RED_NEGATIVE)
            vc.number_format = fmt
            vc.alignment = _align("right")
            row += 1
        row += 1


# ── TAB: Sensitivities ───────────────────────────────────────────────────────
def _build_sensitivities(wb, sensitivities):
    ws = wb.create_sheet("Sensitivities")
    ws.sheet_view.showGridLines = False

    row = 1
    ws.merge_cells(f"A{row}:J{row}")
    c = ws.cell(row=row, column=1, value="SENSITIVITY ANALYSIS")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    for table in sensitivities:
        # Table title
        ws.cell(row=row, column=1, value=table.name).font = _font(bold=True, size=11)
        row += 1

        # Header: row label + col values
        ws.cell(row=row, column=1, value=table.row_label).font = _font(bold=True)
        ws.cell(row=row, column=1).fill = _fill(MID_NAVY)
        ws.cell(row=row, column=1).font = _font(bold=True, color=WHITE)

        for j, col_val in enumerate(table.col_values):
            cell = ws.cell(row=row, column=j + 2, value=col_val)
            cell.font = _font(bold=True, color=WHITE)
            cell.fill = _fill(MID_NAVY)
            cell.alignment = _align("center")
            if "rate" in table.col_label.lower() or "growth" in table.col_label.lower():
                cell.number_format = FMT_PCT
        row += 1

        # Data rows
        for i, (row_val, data_row) in enumerate(zip(table.row_values, table.matrix)):
            rc = ws.cell(row=row, column=1, value=row_val)
            rc.font = _font(bold=True, color=WHITE)
            rc.fill = _fill(MID_NAVY)
            if "cap" in table.row_label.lower() or "rate" in table.row_label.lower():
                rc.number_format = FMT_PCT
            rc.alignment = _align("right")

            for j, val in enumerate(data_row):
                cell = ws.cell(row=row, column=j + 2, value=val)
                cell.number_format = FMT_CURRENCY
                cell.alignment = _align("right")
                bg = LIGHT_BLUE if j == len(data_row) // 2 and i == len(table.matrix) // 2 else WHITE
                cell.fill = _fill(bg)
            row += 1

        _set_col_widths(ws, {1: 24} | {j + 2: 16 for j in range(len(table.col_values))})
        row += 3


# ── TAB: Risks / Missing Info ─────────────────────────────────────────────────
def _build_risks(wb, income, expenses, debt, returns, assumptions):
    ws = wb.create_sheet("Risks & Missing Info")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {1: 16, 2: 28, 3: 56})

    row = 1
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1, value="RISK FLAGS & MISSING INFORMATION")
    c.font = _font(bold=True, size=13, color=WHITE)
    c.fill = _fill(DARK_NAVY)
    c.alignment = _align("center")
    row += 2

    _header_row(ws, row, ["Severity", "Flag", "Detail"])
    row += 1

    flags = []

    if assumptions and assumptions.purchase_price == 0:
        flags.append(("CRITICAL", "No Purchase Price", "Purchase price not found — returns cannot be calculated"))
    if debt and debt.dscr > 0 and debt.dscr < 1.20:
        flags.append(("HIGH", "Low DSCR", f"DSCR of {debt.dscr:.2f}x below lender minimum"))
    if debt and debt.debt_yield > 0 and debt.debt_yield < 0.07:
        flags.append(("MEDIUM", "Low Debt Yield", f"Debt yield of {debt.debt_yield:.1%} may limit financing options"))
    if assumptions and assumptions.tax_reassessment_factor == 1.0:
        flags.append(("MEDIUM", "Tax Reassessment", "Verify taxes won't reassess after sale"))
    if income and income.loss_to_lease > (income.gross_potential_rent or 1) * 0.05:
        flags.append(("INFO", "Loss to Lease", f"${income.loss_to_lease:,.0f} gap between in-place and market rent"))
    if returns and returns.levered_irr < 0:
        flags.append(("CRITICAL", "Negative IRR", "Model shows negative levered IRR"))

    severity_colors = {
        "CRITICAL": "FF0000",
        "HIGH": "C00000",
        "MEDIUM": "D4A843",
        "INFO": "2E75B6",
    }

    for i, (severity, flag, detail) in enumerate(flags):
        color = severity_colors.get(severity, "000000")
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE

        sc = ws.cell(row=row, column=1, value=severity)
        sc.font = _font(bold=True, color=color)
        sc.fill = _fill(bg)

        fc = ws.cell(row=row, column=2, value=flag)
        fc.font = _font(bold=True)
        fc.fill = _fill(bg)

        dc = ws.cell(row=row, column=3, value=detail)
        dc.font = _font()
        dc.fill = _fill(bg)
        dc.alignment = _align(wrap=True)
        row += 1

    if not flags:
        ws.cell(row=row, column=1, value="No critical risk flags identified.").font = _font(italic=True)
