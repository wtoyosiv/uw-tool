"""Rich-based terminal UI: header, file tree sidebar, phase markers, and summary."""
from pathlib import Path
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
from rich import box

from uw.underwriting.models import ClassifiedFile, FileCategory
from uw.ingestion.file_classifier import get_category_color
from uw.ingestion.folder_scanner import get_file_size_str

console = Console()

CATEGORY_LABELS = {
    FileCategory.RENT_ROLL: "Rent Roll",
    FileCategory.T12: "T12 / Historicals",
    FileCategory.PRO_FORMA: "Pro Forma",
    FileCategory.OFFERING_MEMO: "Offering Memo",
    FileCategory.LEASE: "Lease",
    FileCategory.TAX: "Tax",
    FileCategory.INSURANCE: "Insurance",
    FileCategory.DEBT: "Debt / Loan",
    FileCategory.SALES_COMPS: "Sales Comps",
    FileCategory.LEASE_COMPS: "Lease Comps",
    FileCategory.APPRAISAL: "Appraisal",
    FileCategory.PHOTOS: "Photos",
    FileCategory.SURVEY: "Survey",
    FileCategory.ZONING: "Zoning",
    FileCategory.NOTES: "Notes",
    FileCategory.UNKNOWN: "Unknown",
}


def display_header():
    console.print()
    console.print(Panel.fit(
        "[bold white]UW — Commercial Real Estate Underwriting Engine[/bold white]\n"
        "[dim]Reads your documents. Builds the model. Flags the risks.[/dim]",
        border_style="bright_blue",
    ))
    console.print()


def display_phase(number: str, label: str):
    console.print(Rule(f"[bold cyan]Phase {number}[/bold cyan]  [white]{label}[/white]", style="dim"))


def display_file_tree(folder: Path, classified: List[ClassifiedFile]):
    tree = Tree(
        f"[bold yellow]{folder.name}/[/bold yellow]",
        guide_style="dim",
    )

    categories: Dict[FileCategory, List[ClassifiedFile]] = {}
    for cf in classified:
        categories.setdefault(cf.category, []).append(cf)

    for category, files in sorted(categories.items(), key=lambda x: x[0].value):
        color = get_category_color(category)
        label = CATEGORY_LABELS.get(category, category.value)
        branch = tree.add(f"[{color}]{label}[/{color}] [dim]({len(files)} file{'s' if len(files) != 1 else ''})[/dim]")
        for cf in files:
            size = get_file_size_str(Path(cf.path))
            conf = f"{cf.confidence:.0%}" if cf.confidence else ""
            branch.add(
                f"[white]{cf.filename}[/white]  [dim]{size}  {conf}[/dim]"
            )

    console.print(tree)
    console.print()


def display_questions(questions: List[Tuple[str, str, type]]):
    console.print(Panel(
        "[bold yellow]Missing Critical Inputs[/bold yellow]\n"
        "[dim]Please answer the following to complete the model.[/dim]",
        border_style="yellow",
    ))


def display_summary(model_data: Dict[str, Any], output_dir: Path):
    console.print()
    console.print(Rule("[bold green]Underwriting Complete[/bold green]", style="green"))
    console.print()

    returns = model_data.get("returns")
    income = model_data.get("income")
    expenses = model_data.get("expenses")
    debt = model_data.get("debt")
    assumptions = model_data.get("assumptions")
    prop = model_data.get("property_info")

    # Key metrics table
    table = Table(
        title=f"[bold]{prop.name if prop else 'Property'} — Key Metrics[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    table.add_column("Metric", style="white", no_wrap=True)
    table.add_column("Value", style="bold green", justify="right")
    table.add_column("Notes", style="dim")

    def fmt_currency(v):
        if v is None or v == 0:
            return "[dim]—[/dim]"
        if v >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        return f"${v:,.0f}"

    def fmt_pct(v):
        if v is None or v == 0:
            return "[dim]—[/dim]"
        return f"{v:.2%}"

    if assumptions:
        table.add_row("Purchase Price", fmt_currency(assumptions.purchase_price), "")
        table.add_row("Property Type", assumptions.property_type.title(), "")
        if assumptions.total_units:
            table.add_row("Units", str(assumptions.total_units), "")
        if assumptions.total_sqft:
            table.add_row("Total SF", f"{assumptions.total_sqft:,.0f}", "")

    if income:
        table.add_row("GPR (Annual)", fmt_currency(income.gross_potential_rent), "In-place rents × 12")
        table.add_row("Vacancy", fmt_currency(income.vacancy_loss), fmt_pct(assumptions.vacancy_rate if assumptions else 0))
        table.add_row("EGI", fmt_currency(income.effective_gross_income), "")

    if expenses:
        table.add_row("Total Expenses", fmt_currency(expenses.total_operating_expenses), fmt_pct(expenses.expense_ratio) + " of EGI")

    noi_y1 = (income.effective_gross_income - expenses.total_operating_expenses) if income and expenses else 0
    table.add_row("NOI (Year 1)", fmt_currency(noi_y1), "")

    if debt and debt.loan_amount > 0:
        table.add_row("Loan Amount", fmt_currency(debt.loan_amount), fmt_pct(debt.loan_to_value) + " LTV")
        table.add_row("Annual Debt Service", fmt_currency(debt.annual_debt_service), f"{debt.interest_rate:.2%} / {debt.amortization_years}yr")
        table.add_row("DSCR", f"{debt.dscr:.2f}x", "Min 1.20x preferred")
        table.add_row("Debt Yield", fmt_pct(debt.debt_yield), "Min 7% preferred")

    if returns:
        table.add_row("Going-in Cap Rate", fmt_pct(returns.going_in_cap_rate), "")
        if assumptions and assumptions.total_units:
            table.add_row("Price per Unit", fmt_currency(returns.price_per_unit), "")
        if assumptions and assumptions.total_sqft:
            table.add_row("Price per SF", f"${returns.price_per_sqft:.2f}", "")
        table.add_row("Cash-on-Cash (Yr 1)", fmt_pct(returns.cash_on_cash_year1), "")
        table.add_row("Levered IRR", fmt_pct(returns.levered_irr), f"{assumptions.hold_years if assumptions else 5}-year hold")
        table.add_row("Equity Multiple", f"{returns.equity_multiple:.2f}x", "")

    console.print(table)
    console.print()

    # Output files
    output_table = Table(box=box.SIMPLE, title="[bold]Output Files Generated[/bold]", title_style="white")
    output_table.add_column("File", style="cyan")
    output_table.add_column("Description", style="dim")

    output_files = [
        ("underwriting_model.xlsx", "Full Excel model with all tabs"),
        ("underwriting_summary.md", "Executive summary in Markdown"),
        ("extracted_data.json", "All extracted data in structured JSON"),
        ("assumptions_used.md", "All assumptions with flags"),
        ("missing_info.md", "Missing inputs and recommended next steps"),
        ("risk_flags.md", "Risk flags and warnings"),
        ("source_summary.json", "Document classification and confidence scores"),
    ]

    for fname, desc in output_files:
        fpath = output_dir / fname
        status = "[green]OK[/green]" if fpath.exists() else "[dim]--[/dim]"
        output_table.add_row(f"{status} {fname}", desc)

    console.print(output_table)
    console.print(f"\n[bold green]Output folder:[/bold green] {output_dir}\n")
