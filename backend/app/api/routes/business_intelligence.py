from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Membership, POSTransaction, User

router = APIRouter(prefix="/business-intelligence", tags=["business intelligence"])
TZ = ZoneInfo("Africa/Johannesburg")
ZERO = Decimal("0.00")
MIN_OBSERVED_DAYS = 28
MIN_WEEKDAY_SAMPLES = 4


def business_membership(user: User, db: Session) -> Membership:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view business intelligence.")
    return membership


def amount(value) -> Decimal:
    return Decimal(str(value or 0))


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


@router.get("/sales-forecast")
def sales_forecast(
    history_days: int = Query(default=56, ge=56, le=180),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return observed POS history and a weekday-average 7-day sales projection.

    Only full South African calendar days before today are used. Days without
    transactions are not silently treated as zero because feed completeness and
    store opening hours are not independently verified.
    """
    membership = business_membership(user, db)
    today = datetime.now(TZ).date()
    end_date = today
    start_date = end_date - timedelta(days=history_days)
    start_utc = datetime.combine(start_date, time.min, tzinfo=TZ).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, time.min, tzinfo=TZ).astimezone(timezone.utc)

    rows = list(db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.currency == "ZAR",
        POSTransaction.occurred_at >= start_utc,
        POSTransaction.occurred_at < end_utc,
    )).all())

    daily = defaultdict(lambda: {
        "sales": ZERO, "refunds": ZERO, "transactions": 0,
        "sales_count": 0, "refund_count": 0,
    })
    for row in rows:
        local_day = row.occurred_at.astimezone(TZ).date() if row.occurred_at.tzinfo else row.occurred_at.replace(tzinfo=timezone.utc).astimezone(TZ).date()
        if row.transaction_type == "sale":
            daily[local_day]["sales"] += amount(row.net_amount)
            daily[local_day]["sales_count"] += 1
            daily[local_day]["transactions"] += 1
        elif row.transaction_type == "refund":
            daily[local_day]["refunds"] += abs(amount(row.net_amount))
            daily[local_day]["refund_count"] += 1
            daily[local_day]["transactions"] += 1
        # Voids and other event types are deliberately excluded from sales.

    history = []
    weekday_samples = {day: [] for day in range(7)}
    weekday_sales = {day: [] for day in range(7)}
    weekday_refunds = {day: [] for day in range(7)}
    for day in sorted(daily):
        item = daily[day]
        net = item["sales"] - item["refunds"]
        history.append({
            "date": day.isoformat(),
            "sales": money(item["sales"]),
            "refunds": money(item["refunds"]),
            "net_sales": money(net),
            "transaction_count": item["transactions"],
        })
        weekday_samples[day.weekday()].append(day)
        weekday_sales[day.weekday()].append(item["sales"])
        weekday_refunds[day.weekday()].append(item["refunds"])

    observed_days = len(history)
    weekday_sample_counts = {
        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day]: len(weekday_samples[day])
        for day in range(7)
    }
    ready = observed_days >= MIN_OBSERVED_DAYS and all(
        len(weekday_samples[day]) >= MIN_WEEKDAY_SAMPLES for day in range(7)
    )

    forecast = []
    projected_total = ZERO
    if ready:
        next_day = today
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for offset in range(7):
            forecast_day = next_day + timedelta(days=offset)
            weekday = forecast_day.weekday()
            samples = len(weekday_samples[weekday])
            avg_sales = sum(weekday_sales[weekday], ZERO) / Decimal(samples)
            avg_refunds = sum(weekday_refunds[weekday], ZERO) / Decimal(samples)
            projected_net = avg_sales - avg_refunds
            projected_total += projected_net
            forecast.append({
                "date": forecast_day.isoformat(),
                "weekday": weekday_names[weekday],
                "observed_weekday_samples": samples,
                "projected_sales": money(avg_sales),
                "projected_refunds": money(avg_refunds),
                "projected_net_sales": money(projected_net),
            })

    status = "ready" if ready else "insufficient_history"
    return {
        "status": status,
        "currency": "ZAR",
        "history_period": {
            "start": start_date.isoformat(),
            "end_exclusive": end_date.isoformat(),
            "days": history_days,
            "timezone": "Africa/Johannesburg",
        },
        "observed_days": observed_days,
        "transaction_count": sum(item["transactions"] for item in daily.values()),
        "historical_totals": {
            "sales": money(sum((item["sales"] for item in daily.values()), ZERO)),
            "refunds": money(sum((item["refunds"] for item in daily.values()), ZERO)),
            "net_sales": money(sum((item["sales"] - item["refunds"] for item in daily.values()), ZERO)),
        },
        "weekday_sample_counts": weekday_sample_counts,
        "history": history,
        "forecast": forecast,
        "projected_7_day_net_sales": money(projected_total) if ready else None,
        "method": "For each forecast date, average recorded sales and refunds separately across observed historical dates with the same weekday in the selected lookback window.",
        "limitations": [
            "This is a POS net-sales projection, not a profit, cash balance, bank settlement or expense forecast.",
            "Only received ZAR POS sale and refund transactions are included; voids and other transaction types are excluded.",
            "Days with no received transactions are omitted, not assumed to be zero. VEXION cannot yet verify POS feed completeness, store opening hours or missing-feed days.",
            "The projection is indicative and assumes historical weekday patterns remain broadly relevant. It is not a guarantee.",
        ],
        "readiness": {
            "minimum_observed_days": MIN_OBSERVED_DAYS,
            "minimum_samples_per_weekday": MIN_WEEKDAY_SAMPLES,
            "ready": ready,
            "message": "Forecast available." if ready else "More verified POS history is required. VEXION needs at least 28 transaction-bearing days and four observed samples for every weekday; no forecast is generated before that threshold.",
        },
    }
