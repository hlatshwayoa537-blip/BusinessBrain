from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

InvoiceStatus = Literal["draft", "sent", "paid", "overdue", "cancelled"]

class InvoiceLineCreate(BaseModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)]
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("15.00"), ge=0, le=100, max_digits=5, decimal_places=2)

class InvoiceCreate(BaseModel):
    customer_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)]
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=40)
    customer_address: str | None = Field(default=None, max_length=2000)
    issue_date: date
    due_date: date
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")] = "ZAR"
    lines: list[InvoiceLineCreate] = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_due_date(self):
        if self.due_date < self.issue_date:
            raise ValueError("Due date cannot be earlier than the invoice date.")
        return self

class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    line_tax: Decimal
    line_total: Decimal

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    invoice_number: str
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    issue_date: date
    due_date: date
    currency: str
    status: InvoiceStatus
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    notes: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    lines: list[InvoiceLineResponse]

class InvoiceStatusUpdate(BaseModel):
    status: Literal["sent", "paid", "overdue", "cancelled"]
