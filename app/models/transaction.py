from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class TransactionType(str, enum.Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    credit_receivable = "credit_receivable"
    credit_payable = "credit_payable"
    loan_receivable = "loan_receivable"
    loan_payable = "loan_payable"
    payment_received = "payment_received"
    payment_made = "payment_made"


class AccountType(str, enum.Enum):
    cash = "cash"
    bank = "bank"


class DebtStatus(str, enum.Enum):
    open = "open"
    partial = "partial"
    settled = "settled"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=False)
    description = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    
    type = Column(Enum(TransactionType), nullable=False)
    account = Column(Enum(AccountType), nullable=False)
    
    contact_name = Column(String(255), nullable=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    
    linked_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    remaining_amount = Column(Float, nullable=True)
    status = Column(Enum(DebtStatus), nullable=True)
    
    metadata_json = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")
    contact = relationship("Contact", back_populates="transactions")
    linked_transaction = relationship("Transaction", remote_side=[id], foreign_keys=[linked_transaction_id])
