from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import engine, get_db

load_dotenv()

app = FastAPI(title="CareerOS API")


@app.get("/health")
def health_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


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
