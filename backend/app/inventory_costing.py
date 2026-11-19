from decimal import Decimal
from sqlalchemy import select
from app.models import InventoryMovement, POSTransaction, POSTransactionLine

ZERO = Decimal("0")


def inventory_costing_summary(db, business_id: str, start_utc, end_utc, currency: str = "ZAR"):
    """Calculate POS COGS only from item-level sales with a recorded receipt cost."""
    transactions = list(db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == business_id,
        POSTransaction.transaction_type == "sale",
        POSTransaction.currency == currency,
        POSTransaction.occurred_at >= start_utc,
        POSTransaction.occurred_at < end_utc,
    )).all())
    transaction_ids = [row.id for row in transactions]
    lines = list(db.scalars(select(POSTransactionLine).where(
        POSTransactionLine.business_id == business_id,
        POSTransactionLine.transaction_id.in_(transaction_ids),
    )).all()) if transaction_ids else []
    line_ids = [line.id for line in lines]
    movements = list(db.scalars(select(InventoryMovement).where(
        InventoryMovement.business_id == business_id,
        InventoryMovement.source_type == "pos_transaction",
        InventoryMovement.movement_type == "pos_sale",
        InventoryMovement.source_line_id.in_(line_ids),
    )).all()) if line_ids else []
    movement_by_line = {row.source_line_id: row for row in movements}
    lines_by_transaction = {}
    for line in lines:
        lines_by_transaction.setdefault(line.transaction_id, []).append(line)

    total_cogs = ZERO
    uncosted_lines = 0
    uncosted_quantity = ZERO
    product_rows = {}
    for transaction in transactions:
        transaction_lines = lines_by_transaction.get(transaction.id, [])
        if not transaction_lines:
            uncosted_lines += 1
            continue
        for line in transaction_lines:
            product = product_rows.setdefault(line.inventory_item_id or f"unmapped:{line.sku or line.description}", {
                "inventory_item_id": line.inventory_item_id, "sku": line.sku,
                "description": line.description, "quantity_sold": ZERO,
                "line_revenue": ZERO, "costed_quantity": ZERO,
                "uncosted_quantity": ZERO, "cogs": ZERO,
            })
            quantity = Decimal(line.quantity)
            product["quantity_sold"] += quantity
            product["line_revenue"] += Decimal(line.line_total)
            movement = movement_by_line.get(line.id)
            if not line.inventory_item_id or not movement or movement.unit_cost is None:
                product["uncosted_quantity"] += quantity
                uncosted_quantity += quantity
                uncosted_lines += 1
                continue
            cost = Decimal(movement.unit_cost)
            product["costed_quantity"] += quantity
            product["cogs"] += quantity * cost
            total_cogs += quantity * cost

    return {
        "sales_transaction_count": len(transactions), "sales_line_count": len(lines),
        "uncosted_line_count": uncosted_lines, "uncosted_quantity": uncosted_quantity,
        "cogs": total_cogs, "complete": bool(transactions) and uncosted_lines == 0,
        "products": list(product_rows.values()),
    }


def current_weighted_average_cost(db, business_id: str, inventory_item_id: str, required_quantity: Decimal):
    """Return a moving-average cost only while all on-hand stock has known cost."""
    movements = list(db.scalars(select(InventoryMovement).where(
        InventoryMovement.business_id == business_id,
        InventoryMovement.inventory_item_id == inventory_item_id,
    ).order_by(InventoryMovement.created_at.asc(), InventoryMovement.id.asc())).all())
    on_hand = ZERO
    average_cost = None
    unknown_stock = False
    for movement in movements:
        delta = Decimal(movement.quantity_delta)
        if movement.movement_type == "purchase_receipt":
            if movement.unit_cost is None:
                on_hand += delta
                if delta > ZERO:
                    unknown_stock = True
            elif delta > ZERO:
                if on_hand <= ZERO:
                    on_hand = delta
                    average_cost = Decimal(movement.unit_cost)
                    unknown_stock = False
                elif unknown_stock or average_cost is None:
                    on_hand += delta
                    unknown_stock = True
                else:
                    new_quantity = on_hand + delta
                    average_cost = ((on_hand * average_cost) + (delta * Decimal(movement.unit_cost))) / new_quantity
                    on_hand = new_quantity
        elif movement.movement_type == "pos_sale":
            on_hand += delta
            if movement.unit_cost is None:
                unknown_stock = True
        elif movement.movement_type in {"adjustment_in", "adjustment_out"}:
            on_hand += delta
            if delta > ZERO:
                unknown_stock = True
        else:
            on_hand += delta
            if delta > ZERO:
                unknown_stock = True
        if on_hand <= ZERO:
            on_hand = ZERO
            average_cost = None
            unknown_stock = False
    if on_hand < required_quantity or on_hand <= ZERO or unknown_stock or average_cost is None:
        return None
    return average_cost
