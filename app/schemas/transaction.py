from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    credit_receivable = "credit_receivable"
    credit_payable = "credit_payable"
    loan_receivable = "loan_receivable"
    loan_payable = "loan_payable"
    payment_received = "payment_received"
    payment_made = "payment_made"


class AccountType(str, Enum):
    cash = "cash"
    bank = "bank"


class DebtStatus(str, Enum):
    open = "open"
    partial = "partial"
    settled = "settled"


class TransactionBase(BaseModel):
    amount: float
    description: str
    category: Optional[str] = None
    type: TransactionType
    account: AccountType
    contact_name: Optional[str] = None
    due_date: Optional[datetime] = None
    linked_transaction_id: Optional[UUID] = None
    metadata_json: Optional[Dict[str, Any]] = None


class TransactionCreate(TransactionBase):
    contact_id: Optional[UUID] = None


class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    type: Optional[TransactionType] = None
    account: Optional[AccountType] = None
    contact_name: Optional[str] = None
    contact_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    linked_transaction_id: Optional[UUID] = None
    remaining_amount: Optional[float] = None
    status: Optional[DebtStatus] = None


class TransactionResponse(TransactionBase):
    id: UUID
    user_id: UUID
    date: datetime
    contact_id: Optional[UUID] = None
    remaining_amount: Optional[float] = None
    status: Optional[DebtStatus] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BalanceSummary(BaseModel):
    cash: float
    bank: float
    credit: float
    loan: float


class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
