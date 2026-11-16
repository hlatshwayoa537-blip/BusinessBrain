from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Business, User
from app.schemas import PublicBusinessResponse

router = APIRouter(prefix="/network", tags=["business network"])

@router.get("/businesses", response_model=list[PublicBusinessResponse])
def list_businesses(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    industry: str | None = Query(default=None, max_length=120),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PublicBusinessResponse]:
    statement = select(Business).where(Business.directory_listed.is_(True))
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(or_(Business.name.ilike(term), Business.description.ilike(term), Business.industry.ilike(term), Business.city.ilike(term)))
    if industry:
        statement = statement.where(Business.industry.ilike(f"%{industry.strip()}%"))
    if country:
        statement = statement.where(Business.country == country.upper())
    businesses = db.scalars(statement.order_by(Business.name.asc()).limit(limit)).all()
    return [
        PublicBusinessResponse(
            id=business.id,
            name=business.name,
            industry=business.industry,
            country=business.country,
            profile_image_data_url=business.profile_image_data_url,
            website=business.website if business.public_website else None,
            contact_email=business.contact_email if business.public_email else None,
            phone=business.phone if business.public_phone else None,
            city=business.city if business.public_location else None,
            province=business.province if business.public_location else None,
            description=business.description,
        )
        for business in businesses
    ]
