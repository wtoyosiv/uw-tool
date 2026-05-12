"""Pydantic data models for the underwriting engine."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class PropertyType(str, Enum):
    MULTIFAMILY = "multifamily"
    RETAIL = "retail"
    OFFICE = "office"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"
    LAND = "land"
    COVERED_LAND = "covered_land"
    NET_LEASE = "net_lease"
    UNKNOWN = "unknown"


class FileCategory(str, Enum):
    RENT_ROLL = "rent_roll"
    T12 = "t12"
    PRO_FORMA = "pro_forma"
    OFFERING_MEMO = "offering_memo"
    LEASE = "lease"
    TAX = "tax"
    INSURANCE = "insurance"
    DEBT = "debt"
    SALES_COMPS = "sales_comps"
    LEASE_COMPS = "lease_comps"
    APPRAISAL = "appraisal"
    PHOTOS = "photos"
    SURVEY = "survey"
    ZONING = "zoning"
    NOTES = "notes"
    UNKNOWN = "unknown"


class ClassifiedFile(BaseModel):
    path: str
    filename: str
    extension: str
    size_bytes: int
    category: FileCategory
    confidence: float = 0.0
    notes: str = ""


class RentRollUnit(BaseModel):
    unit_id: str = ""
    tenant_name: str = ""
    unit_type: str = ""
    bedrooms: Optional[float] = None
    bathrooms: Optional[float] = None
    sqft: Optional[float] = None
    current_rent: Optional[float] = None
    market_rent: Optional[float] = None
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    vacant: bool = False
    notes: str = ""


class RentRollData(BaseModel):
    units: List[RentRollUnit] = Field(default_factory=list)
    total_units: int = 0
    total_sqft: float = 0.0
    gross_potential_rent_monthly: float = 0.0
    in_place_rent_monthly: float = 0.0
    market_rent_monthly: float = 0.0
    vacant_units: int = 0
    physical_vacancy_rate: float = 0.0
    source_file: str = ""
    extraction_confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)


class FinancialLineItem(BaseModel):
    label: str
    amount: float
    period: str = "annual"
    source: str = "extracted"
    is_assumption: bool = False
    notes: str = ""


class HistoricalFinancials(BaseModel):
    year_label: str = "T12"
    income_items: List[FinancialLineItem] = Field(default_factory=list)
    expense_items: List[FinancialLineItem] = Field(default_factory=list)
    gross_revenue: float = 0.0
    total_expenses: float = 0.0
    noi: float = 0.0
    source_file: str = ""
    extraction_confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)


class PropertyInfo(BaseModel):
    name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    property_type: str = "unknown"
    total_units: Optional[int] = None
    total_sqft: Optional[float] = None
    year_built: Optional[int] = None
    lot_size_acres: Optional[float] = None
    purchase_price: Optional[float] = None
    asking_price: Optional[float] = None
    hold_years: int = 5
    notes: List[str] = Field(default_factory=list)


class UWAssumptions(BaseModel):
    purchase_price: float = 0.0
    property_type: str = "multifamily"
    total_units: int = 0
    total_sqft: float = 0.0
    hold_years: int = 5

    vacancy_rate: float = 0.05
    credit_loss_rate: float = 0.01
    management_fee_pct: float = 0.05
    repairs_maintenance_per_unit: float = 600.0
    repairs_maintenance_pct_egi: float = 0.0
    payroll_per_unit: float = 400.0
    insurance_per_unit: float = 300.0
    insurance_per_sqft: float = 0.25
    replacement_reserves_per_unit: float = 250.0
    replacement_reserves_per_sqft: float = 0.15
    property_tax_annual: float = 0.0
    tax_reassessment_factor: float = 1.0
    utilities_per_unit: float = 0.0
    utilities_per_sqft: float = 0.0
    other_income_per_unit: float = 50.0
    other_income_pct_gpr: float = 0.02
    capex_per_unit: float = 0.0
    capex_per_sqft: float = 0.0

    rent_growth_annual: float = 0.03
    expense_growth_annual: float = 0.025
    exit_cap_rate: float = 0.06

    interest_rate: float = 0.065
    amortization_years: int = 30
    loan_to_value: float = 0.65
    io_period_years: int = 0

    closing_costs_pct: float = 0.01
    disposition_costs_pct: float = 0.02

    assumption_flags: List[str] = Field(default_factory=list)


class IncomeModel(BaseModel):
    gross_potential_rent: float = 0.0
    in_place_rent: float = 0.0
    market_rent: float = 0.0
    loss_to_lease: float = 0.0
    vacancy_loss: float = 0.0
    credit_loss: float = 0.0
    other_income: float = 0.0
    effective_gross_income: float = 0.0
    notes: List[str] = Field(default_factory=list)


class ExpenseModel(BaseModel):
    property_taxes: float = 0.0
    insurance: float = 0.0
    management_fee: float = 0.0
    payroll: float = 0.0
    repairs_maintenance: float = 0.0
    utilities: float = 0.0
    replacement_reserves: float = 0.0
    capex: float = 0.0
    other_expenses: float = 0.0
    total_operating_expenses: float = 0.0
    expense_ratio: float = 0.0
    notes: List[str] = Field(default_factory=list)


class DebtModel(BaseModel):
    loan_amount: float = 0.0
    loan_to_value: float = 0.0
    interest_rate: float = 0.0
    amortization_years: int = 30
    io_period_years: int = 0
    annual_debt_service: float = 0.0
    monthly_payment: float = 0.0
    dscr: float = 0.0
    debt_yield: float = 0.0
    notes: List[str] = Field(default_factory=list)


class AnnualCashFlow(BaseModel):
    year: int
    gpr: float = 0.0
    egi: float = 0.0
    noi: float = 0.0
    debt_service: float = 0.0
    net_cash_flow: float = 0.0
    cash_on_cash: float = 0.0
    cumulative_cash: float = 0.0


class CashFlowModel(BaseModel):
    equity_invested: float = 0.0
    noi_year1: float = 0.0
    annual_flows: List[AnnualCashFlow] = Field(default_factory=list)
    total_cash_distributed: float = 0.0
    exit_value: float = 0.0
    loan_payoff: float = 0.0
    sale_proceeds_net: float = 0.0
    notes: List[str] = Field(default_factory=list)


class ReturnsModel(BaseModel):
    going_in_cap_rate: float = 0.0
    stabilized_cap_rate: float = 0.0
    price_per_unit: float = 0.0
    price_per_sqft: float = 0.0
    gross_rent_multiplier: float = 0.0
    cash_on_cash_year1: float = 0.0
    levered_irr: float = 0.0
    unlevered_irr: float = 0.0
    equity_multiple: float = 0.0
    average_cash_on_cash: float = 0.0
    notes: List[str] = Field(default_factory=list)


class SensitivityTable(BaseModel):
    name: str
    row_label: str
    col_label: str
    row_values: List[float]
    col_values: List[float]
    matrix: List[List[float]]


class RiskFlag(BaseModel):
    category: str
    severity: str
    description: str
    recommendation: str = ""


class MissingInfo(BaseModel):
    field: str
    importance: str
    assumption_used: str = ""
    notes: str = ""
