from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum
from dateutil import parser as date_parser


class DraftStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    discarded = "discarded"


class DraftBase(BaseModel):
    date: Optional[datetime] = None  # Transaction occurring date (defaults to today)
    amount: float
    description: str
    category: Optional[str] = None
    type: str
    account: str
    contact_name: Optional[str] = None
    contact_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    linked_transaction_id: Optional[UUID] = None
    
    @field_validator('date', 'due_date', mode='before')
    @classmethod
    def parse_date_naive(cls, v):
        """Parse date and strip timezone info to get naive datetime."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = date_parser.parse(v)
                return parsed.replace(tzinfo=None)
            except:
                return None
        if isinstance(v, datetime):
            return v.replace(tzinfo=None) if v.tzinfo else v
        return v


class DraftCreate(DraftBase):
    message_id: Optional[UUID] = None


class DraftUpdate(BaseModel):
    date: Optional[datetime] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    account: Optional[str] = None
    contact_name: Optional[str] = None
    contact_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    linked_transaction_id: Optional[UUID] = None


class DraftResponse(DraftBase):
    id: UUID
    user_id: UUID
    message_id: Optional[UUID] = None
    date: datetime  # Override to make non-optional in response
    status: DraftStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DraftListResponse(BaseModel):
    drafts: List[DraftResponse]
    total: int
