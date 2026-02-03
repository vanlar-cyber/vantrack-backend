from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class AttachmentType(str, Enum):
    image = "image"
    audio = "audio"


class Attachment(BaseModel):
    id: str
    type: AttachmentType
    mime_type: str
    data_url: str
    name: Optional[str] = None
    duration_ms: Optional[int] = None


class MessageBase(BaseModel):
    role: MessageRole
    content: str


class MessageCreate(MessageBase):
    drafts_json: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Attachment]] = None


class MessageResponse(MessageBase):
    id: UUID
    user_id: UUID
    timestamp: datetime
    drafts_json: Optional[List[Dict[str, Any]]] = None
    attachments_json: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
