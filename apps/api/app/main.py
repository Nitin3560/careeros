import io
import os
from time import perf_counter
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import engine, get_db
from app.services.auth import hash_password, verify_password
from app.services.background_jobs import get_or_create_background_job, set_queue_job_id
from app.services.job_ingestion.greenhouse import fetch_greenhouse_jobs
from app.services.job_ingestion.persist import save_jobs
from app.services.job_matching import (
    count_matching_jobs,
    get_cached_matches,
    get_or_create_matches,
    match_job_to_profile,
    shortlist_jobs,
)
from app.services.resume_parsing import extract_text, parse_resume_to_profile
from app.services.resume_export import generate_docx, generate_pdf
from app.services.resume_tailoring import tailor_resume_for_job
from app.services.metrics import metrics_snapshot, record_http_request
from app.services.upload_validation import validate_resume_upload
from app.services.queue import get_queue
from app.workers.ingestion import run_bulk_greenhouse_ingestion
from app.workers.matching import run_match_refresh

load_dotenv()

app = FastAPI(title="CareerOS API")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    latency_ms = (perf_counter() - started) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    record_http_request(request.method, path, response.status_code, latency_ms)
    response.headers["X-Process-Time-Ms"] = f"{latency_ms:.2f}"
    return response


VALID_STATUSES = {
    "Applied",
    "OA",
    "Recruiter Screen",
    "Technical",
    "Final",
    "Offer",
    "Rejected",
    "Ghosted",
}


def enqueue_match_refresh(
    db: Session,
    user_id: str,
    offset: int = 0,
    limit: int = 10,
    profile_version: int | None = None,
):
    payload = {"user_id": user_id, "offset": offset, "limit": limit}
    key_parts = ["match_refresh", user_id, str(offset), str(limit)]
    if profile_version is not None:
        payload["profile_version"] = profile_version
        key_parts.append(str(profile_version))

    background_job, created = get_or_create_background_job(
        db,
        job_type="match_refresh",
        payload=payload,
        dedupe_key=":".join(key_parts),
    )
    if not created:
        return background_job

    queue_job = get_queue().enqueue(
        run_match_refresh,
        str(background_job.id),
        job_timeout=900,
    )
    return set_queue_job_id(db, background_job, queue_job.id)


def warm_profile_matches(db: Session, user_id: str, profile: models.CandidateProfile):
    try:
        enqueue_match_refresh(
            db,
            user_id,
            offset=0,
            limit=10,
            profile_version=profile.profile_version,
        )
    except Exception:
        pass


@app.get("/health")
def health_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/metrics")
def get_metrics():
    return metrics_snapshot()


@app.post("/auth/signup", response_model=schemas.AuthResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    user = models.User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.AuthResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return user


@app.post("/company-targets/bulk")
def add_company_targets_bulk(
    payload: schemas.CompanyTargetBulkCreate,
    db: Session = Depends(get_db),
):
    added = 0
    skipped = 0

    for raw_slug in payload.slugs:
        slug = raw_slug.strip().lower()
        if not slug:
            continue

        existing = (
            db.query(models.CompanyTarget)
            .filter(models.CompanyTarget.slug == slug)
            .first()
        )
        if existing:
            skipped += 1
            continue

        db.add(models.CompanyTarget(slug=slug, source=payload.source))
        added += 1

    db.commit()
    return {"added": added, "skipped": skipped}


@app.get("/company-targets")
def list_company_targets(db: Session = Depends(get_db)):
    targets = db.query(models.CompanyTarget).order_by(models.CompanyTarget.slug).all()
    return {
        "count": len(targets),
        "targets": [
            {
                "slug": t.slug,
                "source": t.source,
                "active": t.active,
                "last_ingested_at": t.last_ingested_at,
            }
            for t in targets
        ],
    }


@app.post("/ingest/greenhouse/bulk", response_model=schemas.BackgroundJobOut)
def bulk_ingest_greenhouse(db: Session = Depends(get_db)):
    background_job, created = get_or_create_background_job(
        db,
        job_type="greenhouse_bulk_ingest",
        payload={"source": "greenhouse"},
        dedupe_key="greenhouse_bulk_ingest:greenhouse",
    )
    if not created:
        return background_job

    queue_job = get_queue().enqueue(
        run_bulk_greenhouse_ingestion,
        str(background_job.id),
        job_timeout=900,
    )
    return set_queue_job_id(db, background_job, queue_job.id)


@app.get("/background-jobs/{job_id}", response_model=schemas.BackgroundJobOut)
def get_background_job(job_id: str, db: Session = Depends(get_db)):
    background_job = (
        db.query(models.BackgroundJob)
        .filter(models.BackgroundJob.id == job_id)
        .first()
    )
    if not background_job:
        raise HTTPException(status_code=404, detail="Background job not found")

    return background_job


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


@app.get("/users/{user_id}/shortlist")
def get_shortlist(user_id: str, limit: int = 30, db: Session = Depends(get_db)):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    jobs = shortlist_jobs(db, profile.data, limit=limit)

    return {
        "count": len(jobs),
        "jobs": [
            {
                "id": str(j.id),
                "title": j.title,
                "company": j.company,
                "location": j.location,
            }
            for j in jobs
        ],
    }


@app.get("/users/{user_id}/matches/count")
def get_matches_count(user_id: str, db: Session = Depends(get_db)):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    total = count_matching_jobs(db, profile.data)
    return {"total_matches": total}


@app.get("/users/{user_id}/matches")
def get_matches(
    user_id: str, offset: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    results = get_or_create_matches(
        db, user_id, profile, offset=offset, page_size=limit
    )

    return {
        "offset": offset,
        "limit": limit,
        "count": len(results),
        "has_more": len(results) == limit,
        "results": results,
    }


@app.get("/users/{user_id}/matches/cached")
def get_cached_user_matches(
    user_id: str, offset: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    results = get_cached_matches(
        db, user_id, profile, offset=offset, page_size=limit
    )

    return {
        "offset": offset,
        "limit": limit,
        "count": len(results),
        "has_more": len(results) == limit,
        "results": results,
    }


@app.post("/users/{user_id}/matches/refresh", response_model=schemas.BackgroundJobOut)
def refresh_matches(
    user_id: str,
    offset: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 30:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 30")

    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    return enqueue_match_refresh(
        db,
        user_id,
        offset=offset,
        limit=limit,
    )


@app.post("/users/{user_id}/tailor/{job_id}")
def tailor_resume(user_id: str, job_id: str, db: Session = Depends(get_db)):
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

    try:
        suggestions = tailor_resume_for_job(
            profile.data, job.title, job.description_text or ""
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Resume tailoring is temporarily unavailable. Try again later.",
        )

    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "company": job.company,
        "suggestions": suggestions,
    }


@app.get(
    "/users/{user_id}/resume-version/{job_id}",
    response_model=schemas.ResumeVersionOut,
)
def get_resume_version(user_id: str, job_id: str, db: Session = Depends(get_db)):
    version = (
        db.query(models.ResumeVersion)
        .filter(
            models.ResumeVersion.user_id == user_id,
            models.ResumeVersion.job_id == job_id,
        )
        .first()
    )
    if version:
        return version

    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    seeded_content = {
        "full_name": profile.data.get("full_name", ""),
        "summary": "",
        "skills": profile.data.get("skills", []),
        "experience": profile.data.get("experience", []),
        "education": profile.data.get("education", []),
    }

    version = models.ResumeVersion(
        user_id=user_id,
        job_id=job_id,
        content=seeded_content,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@app.put(
    "/users/{user_id}/resume-version/{job_id}",
    response_model=schemas.ResumeVersionOut,
)
def update_resume_version(
    user_id: str,
    job_id: str,
    payload: schemas.ResumeVersionUpdate,
    db: Session = Depends(get_db),
):
    version = (
        db.query(models.ResumeVersion)
        .filter(
            models.ResumeVersion.user_id == user_id,
            models.ResumeVersion.job_id == job_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=404,
            detail="Resume version not found - GET first to initialize it",
        )

    version.content = payload.content
    db.commit()
    db.refresh(version)
    return version


@app.get("/users/{user_id}/resume-version/{job_id}/export")
def export_resume(
    user_id: str,
    job_id: str,
    format: str = "pdf",
    db: Session = Depends(get_db),
):
    version = (
        db.query(models.ResumeVersion)
        .filter(
            models.ResumeVersion.user_id == user_id,
            models.ResumeVersion.job_id == job_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Resume version not found")

    filename_base = (version.content.get("full_name") or "resume").replace(" ", "_")

    if format == "docx":
        file_bytes = generate_docx(version.content)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        filename = f"{filename_base}.docx"
    elif format == "pdf":
        file_bytes = generate_pdf(version.content)
        media_type = "application/pdf"
        filename = f"{filename_base}.pdf"
    else:
        raise HTTPException(status_code=400, detail="format must be 'pdf' or 'docx'")

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/users/{user_id}/applications", response_model=schemas.ApplicationOut)
def create_application(
    user_id: str,
    payload: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
):
    job = db.query(models.Job).filter(models.Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == user_id,
            models.Application.job_id == payload.job_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Application already tracked for this job",
        )

    if payload.resume_version_id:
        resume_version = (
            db.query(models.ResumeVersion)
            .filter(
                models.ResumeVersion.id == payload.resume_version_id,
                models.ResumeVersion.user_id == user_id,
            )
            .first()
        )
        if not resume_version:
            raise HTTPException(status_code=400, detail="Invalid resume version")

    application = models.Application(
        user_id=user_id,
        job_id=payload.job_id,
        resume_version_id=payload.resume_version_id,
        notes=payload.notes,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.get("/users/{user_id}/applications")
def list_applications(
    user_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Application, models.Job)
        .join(models.Job, models.Application.job_id == models.Job.id)
        .filter(models.Application.user_id == user_id)
    )

    if status:
        query = query.filter(models.Application.status == status)

    results = query.order_by(models.Application.applied_at.desc()).all()

    return {
        "count": len(results),
        "applications": [
            {
                "id": str(application.id),
                "job_id": str(application.job_id),
                "job_title": job.title,
                "company": job.company,
                "status": application.status,
                "notes": application.notes,
                "applied_at": application.applied_at,
                "updated_at": application.updated_at,
                "resume_version_id": (
                    str(application.resume_version_id)
                    if application.resume_version_id
                    else None
                ),
            }
            for application, job in results
        ],
    }


@app.patch(
    "/users/{user_id}/applications/{application_id}",
    response_model=schemas.ApplicationOut,
)
def update_application(
    user_id: str,
    application_id: str,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
):
    application = (
        db.query(models.Application)
        .filter(
            models.Application.id == application_id,
            models.Application.user_id == user_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of {sorted(VALID_STATUSES)}",
            )
        application.status = payload.status

    if payload.notes is not None:
        application.notes = payload.notes

    db.commit()
    db.refresh(application)
    return application


@app.get("/users/{user_id}/applications/by-job/{job_id}")
def get_application_for_job(
    user_id: str,
    job_id: str,
    db: Session = Depends(get_db),
):
    application = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == user_id,
            models.Application.job_id == job_id,
        )
        .first()
    )
    if not application:
        return {"tracked": False}

    return {
        "tracked": True,
        "status": application.status,
        "id": str(application.id),
    }


@app.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(
        username=user.email,
        password_hash=hash_password("temporary-dev-password"),
        email=user.email,
        full_name=user.full_name,
    )
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
        profile.profile_version = (profile.profile_version or 1) + 1
    else:
        profile = models.CandidateProfile(user_id=user_id, data=payload.data)
        db.add(profile)

    db.commit()
    db.refresh(profile)
    warm_profile_matches(db, user_id, profile)
    return profile


@app.patch(
    "/users/{user_id}/profile/basic-info",
    response_model=schemas.CandidateProfileOut,
)
def update_basic_info(
    user_id: str, payload: schemas.ProfileBasicInfo, db: Session = Depends(get_db)
):
    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found - upload a resume first",
        )

    updated_data = dict(profile.data or {})
    if payload.full_name is not None:
        updated_data["full_name"] = payload.full_name
    if payload.country is not None:
        updated_data["country"] = payload.country
    if payload.remote_preference is not None:
        updated_data["remote_preference"] = payload.remote_preference

    profile.data = updated_data
    db.commit()
    db.refresh(profile)
    return profile


@app.post("/users/{user_id}/resume", response_model=schemas.CandidateProfileOut)
async def upload_resume(
    user_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    file_bytes = await file.read()

    try:
        validate_resume_upload(file.filename, file.content_type, file_bytes)
        resume_text = extract_text(file.filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from the uploaded file",
        )

    try:
        parsed_profile = parse_resume_to_profile(resume_text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Resume parsing failed: {exc}")

    profile = (
        db.query(models.CandidateProfile)
        .filter(models.CandidateProfile.user_id == user_id)
        .first()
    )

    if profile:
        for key in ("country", "remote_preference"):
            if key in (profile.data or {}) and key not in parsed_profile:
                parsed_profile[key] = profile.data[key]
        profile.data = parsed_profile
        profile.profile_version = (profile.profile_version or 1) + 1
    else:
        profile = models.CandidateProfile(user_id=user_id, data=parsed_profile)
        db.add(profile)

    db.commit()
    db.refresh(profile)
    warm_profile_matches(db, user_id, profile)
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
