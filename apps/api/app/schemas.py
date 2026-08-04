import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateProfileUpdate(BaseModel):
    data: dict


class CandidateProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    data: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
