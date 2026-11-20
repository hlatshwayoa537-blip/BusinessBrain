from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

IntegrationMethod = Literal["api", "webhook", "local_agent"]
TransactionType = Literal["sale", "refund", "void"]

class POSConnectionCreate(BaseModel):
    provider_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    integration_method: IntegrationMethod

class POSConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider_name: str
    display_name: str
    integration_method: IntegrationMethod
    status: str
    created_at: datetime
    last_received_at: datetime | None = None

class POSConnectionCreated(POSConnectionResponse):
    webhook_secret: str

class POSIngestLine(BaseModel):
    sku: str | None = Field(default=None, max_length=80)
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    external_line_id: str | None = Field(default=None, max_length=180)
    original_line_id: str | None = Field(default=None, max_length=36)
    original_line_external_id: str | None = Field(default=None, max_length=180)
    original_line_number: int | None = Field(default=None, ge=1, le=200)
    restock: bool = False


class POSIngestLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    line_number: int
    external_line_id: str | None = None
    original_line_id: str | None = None
    sku: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: str | None = None


class POSIngestTransaction(BaseModel):
    external_transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
    # Legacy internal VEXION ID; external POS systems should use the external reference below.
    original_transaction_id: str | None = Field(default=None, max_length=36)
    original_external_transaction_id: str | None = Field(default=None, max_length=180)
    branch_name: str | None = Field(default=None, max_length=160)
    till_name: str | None = Field(default=None, max_length=120)
    transaction_type: TransactionType
    occurred_at: datetime
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")] = "ZAR"
    gross_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    net_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    payment_method: str | None = Field(default=None, max_length=60)
    items: list[POSIngestLine] = Field(default_factory=list, max_length=200)

class POSTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    connection_id: str
    external_transaction_id: str
    branch_name: str | None = None
    till_name: str | None = None
    transaction_type: TransactionType
    occurred_at: datetime
    currency: str
    gross_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    payment_method: str | None = None
    items: list[POSIngestLineResponse] = Field(default_factory=list, validation_alias="lines")

class POSSalesSummary(BaseModel):
    currency: str = "ZAR"
    days: int
    transaction_count: int
    sales_total: str
    refunds_total: str
    net_sales: str
    void_count: int
