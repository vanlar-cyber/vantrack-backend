from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class ContactBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class ContactResponse(ContactBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total: int
