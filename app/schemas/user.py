from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    preferred_currency: Optional[str] = None
    preferred_language: Optional[str] = None
    # Business profile fields
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    industry: Optional[str] = None
    business_size: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    years_in_business: Optional[int] = None
    monthly_revenue_range: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    preferred_currency: str
    preferred_language: str
    created_at: datetime
    # Business profile fields
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    industry: Optional[str] = None
    business_size: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    years_in_business: Optional[int] = None
    monthly_revenue_range: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
