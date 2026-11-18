from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

FinanceKind = Literal["income", "expense"]
FinanceStatus = Literal["paid", "unpaid"]

class FinanceTransactionCreate(BaseModel):
    kind: FinanceKind
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    status: FinanceStatus = "paid"
    occurred_on: date
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)

class FinanceTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: FinanceKind
    category: str
    description: str
    amount: Decimal
    currency: str
    status: FinanceStatus
    occurred_on: date
    reference: str | None = None
    notes: str | None = None
    created_at: datetime

class FinanceMonthSummary(BaseModel):
    month: int
    income: str
    expenses: str

class FinanceSummaryResponse(BaseModel):
    year: int
    currency: str = "ZAR"
    income_total: str
    manual_income_total: str
    pos_sales_total: str
    pos_refunds_total: str
    pos_net_income_total: str
    pos_transaction_count: int
    expense_total: str
    net_total: str
    outstanding_income: str
    unpaid_expenses: str
    transaction_count: int
    months: list[FinanceMonthSummary]
