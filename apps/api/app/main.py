from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import engine, get_db
from app.services.job_ingestion.greenhouse import fetch_greenhouse_jobs
from app.services.job_ingestion.persist import save_jobs
from app.services.job_matching import match_job_to_profile

load_dotenv()

app = FastAPI(title="CareerOS API")


@app.get("/health")
def health_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/ingest/greenhouse/{company_slug}")
def ingest_greenhouse(company_slug: str, db: Session = Depends(get_db)):
    jobs = fetch_greenhouse_jobs(company_slug)
    result = save_jobs(db, jobs)
    return {"company": company_slug, **result}


@app.get("/jobs")
def list_jobs(
    company: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(models.Job)
    if company:
        query = query.filter(models.Job.company == company)
    if source:
        query = query.filter(models.Job.source == source)

    total = query.count()
    jobs = query.order_by(models.Job.retrieved_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "count": len(jobs),
        "jobs": [
            {
                "id": str(j.id),
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "source": j.source,
                "application_url": j.application_url,
                "date_posted": j.date_posted,
            }
            for j in jobs
        ],
    }


@app.post("/users/{user_id}/match/{job_id}")
def match_job(user_id: str, job_id: str, db: Session = Depends(get_db)):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = match_job_to_profile(profile.data, job.title, job.description_text or "")

    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "company": job.company,
        "match": result,
    }


# --- Users ---


@app.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(email=user.email, full_name=user.full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# --- Candidate Profile ---


@app.put("/users/{user_id}/profile", response_model=schemas.CandidateProfileOut)
def upsert_profile(
    user_id: str, payload: schemas.CandidateProfileUpdate, db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )

    if profile:
        profile.data = payload.data
    else:
        profile = models.CandidateProfile(user_id=user_id, data=payload.data)
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@app.get("/users/{user_id}/profile", response_model=schemas.CandidateProfileOut)
def get_profile(user_id: str, db: Session = Depends(get_db)):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
