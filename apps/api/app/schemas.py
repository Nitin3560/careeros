import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[str]
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    id: uuid.UUID
    username: str

    class Config:
        from_attributes = True


class CandidateProfileUpdate(BaseModel):
    data: dict


class ProfileBasicInfo(BaseModel):
    full_name: Optional[str] = None
    country: Optional[str] = None
    remote_preference: Optional[str] = None


class CandidateProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    data: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeVersionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    content: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeVersionUpdate(BaseModel):
    content: dict


class CompanyTargetCreate(BaseModel):
    slug: str
    source: str = "greenhouse"


class CompanyTargetBulkCreate(BaseModel):
    slugs: list[str]
    source: str = "greenhouse"


class CompanyTargetOut(BaseModel):
    id: uuid.UUID
    slug: str
    source: str
    active: bool
    last_ingested_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    resume_version_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class ApplicationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    resume_version_id: Optional[uuid.UUID]
    status: str
    notes: Optional[str]
    applied_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BackgroundJobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    queue_job_id: Optional[str]
    dedupe_key: Optional[str]
    payload: dict
    result: Optional[dict]
    error: Optional[str]
    attempts: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True
