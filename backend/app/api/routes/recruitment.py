from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Business, JobApplication, JobPosting, Membership, User
from app.schemas import ApplicationStatusUpdate, JobApplicationCreate, JobCreate, JobStatusUpdate

router = APIRouter(prefix="/recruitment", tags=["people and recruitment"])

def workspace(user: User, db: Session) -> tuple[Business, Membership]:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    return business, membership

def job_response(job: JobPosting, business_name: str, application_count: int = 0) -> dict:
    return {"id": job.id, "business_id": job.business_id, "business_name": business_name, "title": job.title,
        "department": job.department, "location": job.location, "employment_type": job.employment_type,
        "description": job.description, "requirements": job.requirements, "status": job.status,
        "created_at": job.created_at, "application_count": application_count}

@router.get("/jobs")
def list_jobs(q: str | None = Query(default=None, max_length=120), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business, _ = workspace(current_user, db)
    jobs = db.scalars(select(JobPosting).where(JobPosting.business_id == business.id).order_by(JobPosting.created_at.desc())).all()
    return [job_response(job, business.name, len(db.scalars(select(JobApplication).where(JobApplication.job_id == job.id)).all())) for job in jobs if not q or q.lower() in job.title.lower()]

@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business, membership = workspace(current_user, db)
    if membership.role not in {"owner", "admin", "hr"}:
        raise HTTPException(status_code=403, detail="Only owners, administrators or HR members can manage vacancies.")
    job = JobPosting(business_id=business.id, **payload.model_dump())
    db.add(job); db.commit(); db.refresh(job)
    return job_response(job, business.name)

@router.patch("/jobs/{job_id}")
def update_job(job_id: str, payload: JobStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business, membership = workspace(current_user, db)
    if membership.role not in {"owner", "admin", "hr"}: raise HTTPException(status_code=403, detail="You cannot manage vacancies.")
    job = db.scalar(select(JobPosting).where(JobPosting.id == job_id, JobPosting.business_id == business.id))
    if not job: raise HTTPException(status_code=404, detail="Vacancy not found.")
    job.status = payload.status; db.commit(); db.refresh(job)
    return job_response(job, business.name)

@router.get("/applications")
def list_applications(job_id: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business, _ = workspace(current_user, db)
    statement = select(JobApplication, JobPosting).join(JobPosting, JobApplication.job_id == JobPosting.id).where(JobPosting.business_id == business.id)
    if job_id: statement = statement.where(JobPosting.id == job_id)
    rows = db.execute(statement.order_by(JobApplication.created_at.desc())).all()
    return [{"id": app.id, "job_id": job.id, "job_title": job.title, "applicant_name": app.applicant_name, "email": app.email,
        "phone": app.phone, "location": app.location, "experience": app.experience, "resume_url": app.resume_url,
        "cover_letter": app.cover_letter, "status": app.status, "created_at": app.created_at} for app, job in rows]

@router.post("/jobs/{job_id}/applications", status_code=status.HTTP_201_CREATED)
def apply(job_id: str, payload: JobApplicationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(JobPosting).where(JobPosting.id == job_id, JobPosting.status == "published"))
    if not job: raise HTTPException(status_code=404, detail="This vacancy is not accepting applications.")
    app = JobApplication(job_id=job.id, **payload.model_dump())
    db.add(app); db.commit(); db.refresh(app)
    return {"id": app.id, "status": app.status, "created_at": app.created_at}

@router.patch("/applications/{application_id}")
def update_application(application_id: str, payload: ApplicationStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business, membership = workspace(current_user, db)
    if membership.role not in {"owner", "admin", "hr"}: raise HTTPException(status_code=403, detail="You cannot update applicant records.")
    app = db.scalar(select(JobApplication).join(JobPosting).where(JobApplication.id == application_id, JobPosting.business_id == business.id))
    if not app: raise HTTPException(status_code=404, detail="Applicant not found.")
    app.status = payload.status; db.commit(); db.refresh(app)
    return {"id": app.id, "status": app.status}
