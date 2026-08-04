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
