"""UW CLI — main entry point."""
import logging
from pathlib import Path
from typing import Optional

import typer

from uw.ingestion.folder_scanner import scan_folder
from uw.ingestion.file_classifier import classify_files
from uw.ingestion.file_reader import read_files
from uw.extraction.rent_roll_extractor import extract_rent_roll
from uw.extraction.financials_extractor import extract_financials
from uw.extraction.property_extractor import extract_property_info
from uw.underwriting.assumptions import load_assumptions, merge_assumptions
from uw.underwriting.income_model import build_income_model
from uw.underwriting.expense_model import build_expense_model
from uw.underwriting.debt_model import build_debt_model
from uw.underwriting.cash_flow_model import build_cash_flow_model
from uw.underwriting.returns_model import build_returns_model
from uw.underwriting.sensitivities import build_sensitivities
from uw.outputs.excel_writer import write_excel
from uw.outputs.markdown_writer import write_markdown_reports
from uw.outputs.json_writer import write_json_outputs
from uw.tui.display import (
    display_header, display_file_tree, display_phase,
    display_summary, display_questions, console,
)

logging.basicConfig(level=logging.WARNING)

app = typer.Typer(
    name="uw",
    help="Commercial Real Estate Underwriting Engine",
    add_completion=False,
    no_args_is_help=True,
)


@app.command()
def underwrite(
    folder: Path = typer.Argument(..., help="Path to the property folder"),
    purchase_price: Optional[float] = typer.Option(
        None, "--price", "-p", help="Purchase price (overrides documents)"
    ),
    property_type: Optional[str] = typer.Option(
        None, "--type", "-t",
        help="Property type: multifamily / retail / office / industrial / mixed_use / land / net_lease",
    ),
    hold_years: int = typer.Option(5, "--hold", "-H", help="Hold period in years"),
    exit_cap: Optional[float] = typer.Option(None, "--exit-cap", help="Exit cap rate (e.g. 0.06)"),
    ltv: Optional[float] = typer.Option(None, "--ltv", help="Loan-to-value ratio (e.g. 0.65)"),
    rate: Optional[float] = typer.Option(None, "--rate", help="Interest rate (e.g. 0.065)"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", "-i/-n",
        help="Ask for missing critical inputs",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logging"),
):
    """
    Underwrite a commercial real estate property from a folder of documents.

    Example:
        uw ./deals/Maple-Apartments
        uw ./deals/Maple-Apartments --price 3500000 --type multifamily --hold 5
    """
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    display_header()

    # Validate
    if not folder.exists():
        console.print(f"[red]Error:[/red] Folder '{folder}' does not exist.")
        raise typer.Exit(1)
    if not folder.is_dir():
        console.print(f"[red]Error:[/red] '{folder}' is not a directory.")
        raise typer.Exit(1)

    # ── Phase 1: Scan ────────────────────────────────────────────────────────
    display_phase("1", "Scanning folder")
    raw_files = scan_folder(folder)
    if not raw_files:
        console.print("[yellow]Warning:[/yellow] No files found in folder.")

    # ── Phase 2: Classify ────────────────────────────────────────────────────
    display_phase("2", "Classifying files")
    classified = classify_files(raw_files)
    display_file_tree(folder, classified)

    # ── Phase 3: Read ────────────────────────────────────────────────────────
    display_phase("3", "Reading files")
    file_data = read_files(classified)

    # ── Phase 4: Extract ─────────────────────────────────────────────────────
    display_phase("4", "Extracting underwriting data")
    rent_roll = extract_rent_roll(file_data)
    financials = extract_financials(file_data)
    prop_info = extract_property_info(file_data, folder.name)

    # ── Phase 5: Assumptions ─────────────────────────────────────────────────
    display_phase("5", "Building assumptions")

    # CLI flags override extracted values
    if purchase_price is not None:
        prop_info.purchase_price = purchase_price
    if property_type:
        prop_info.property_type = property_type
    prop_info.hold_years = hold_years

    # Rent roll is authoritative for unit count and sqft — override extracted text values
    if rent_roll.total_units > 0:
        prop_info.total_units = rent_roll.total_units
    if rent_roll.total_sqft > 0:
        prop_info.total_sqft = rent_roll.total_sqft

    if interactive:
        prop_info = _ask_missing_inputs(prop_info, rent_roll, financials)

    base_defaults = load_assumptions()
    # Apply CLI overrides to defaults
    if exit_cap is not None:
        base_defaults["exit_cap_rate"] = exit_cap
    if ltv is not None:
        base_defaults["loan_to_value"] = ltv
    if rate is not None:
        base_defaults["interest_rate"] = rate

    assumptions = merge_assumptions(base_defaults, prop_info)

    # ── Phase 6: Build Model ─────────────────────────────────────────────────
    display_phase("6", "Building underwriting model")
    income = build_income_model(rent_roll, financials, assumptions)
    expenses = build_expense_model(financials, assumptions, income)
    noi_y1 = income.effective_gross_income - expenses.total_operating_expenses
    debt = build_debt_model(assumptions, noi_y1)
    cash_flows = build_cash_flow_model(income, expenses, debt, assumptions)
    returns = build_returns_model(cash_flows, assumptions)
    sensitivities = build_sensitivities(income, expenses, debt, assumptions)

    # ── Phase 7: Outputs ─────────────────────────────────────────────────────
    display_phase("7", "Generating outputs")
    output_dir = folder / "output"
    output_dir.mkdir(exist_ok=True)

    model_data = {
        "property_info": prop_info,
        "rent_roll": rent_roll,
        "financials": financials,
        "assumptions": assumptions,
        "income": income,
        "expenses": expenses,
        "debt": debt,
        "cash_flows": cash_flows,
        "returns": returns,
        "sensitivities": sensitivities,
        "classified_files": classified,
    }

    write_json_outputs(model_data, output_dir)
    write_excel(model_data, output_dir)
    write_markdown_reports(model_data, output_dir)

    display_summary(model_data, output_dir)


def _ask_missing_inputs(prop_info, rent_roll, financials):
    questions = []
    if not prop_info.purchase_price:
        questions.append(("purchase_price", "Purchase price?  (e.g. 3500000 or skip)", float))
    if prop_info.property_type in ("unknown",):
        questions.append(("property_type", "Property type?  (multifamily/retail/office/industrial/mixed_use/land/net_lease or skip)", str))
    if not prop_info.total_units and not prop_info.total_sqft:
        questions.append(("total_units", "Total units? (enter 0 if non-multifamily, or skip)", int))
    if prop_info.total_units and not prop_info.total_sqft:
        questions.append(("total_sqft", "Total rentable SF?  (or skip)", float))

    if questions:
        display_questions(questions)
        for attr, question, dtype in questions:
            try:
                value = typer.prompt(f"  {question}", default="skip")
                if value.lower() != "skip" and value.strip():
                    converted = dtype(value)
                    if attr == "total_units" and converted == 0:
                        pass
                    setattr(prop_info, attr, converted)
            except (ValueError, TypeError):
                pass

    return prop_info


def main():
    app()


if __name__ == "__main__":
    main()
