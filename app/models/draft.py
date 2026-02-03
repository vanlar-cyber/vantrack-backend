from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class DraftStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    discarded = "discarded"


class Draft(Base):
    __tablename__ = "drafts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    
    date = Column(DateTime, nullable=False, server_default=func.now())  # Transaction occurring date
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    type = Column(String, nullable=False)  # income, expense, credit_receivable, etc.
    account = Column(String, nullable=False)  # cash, bank
    
    contact_name = Column(String, nullable=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    linked_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(SQLEnum(DraftStatus, name="draftstatus", create_constraint=False), default=DraftStatus.pending)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
