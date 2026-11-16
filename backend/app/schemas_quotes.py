from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]

class QuotationLineCreate(BaseModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)]
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)

class QuotationCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)]
    currency: Currency
    line_items: list[QuotationLineCreate] = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=3000)
    valid_until: date | None = None

class QuotationDecision(BaseModel):
    decision: Annotated[str, StringConstraints(pattern=r"^(accepted|declined)$")]
    note: str | None = Field(default=None, max_length=2000)

class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_room_id: str
    issuer_business_id: str
    issuer_business_name: str
    reference: str
    title: str
    currency: str
    line_items: list[dict]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    notes: str | None = None
    valid_until: date | None = None
    status: str
    response_note: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
