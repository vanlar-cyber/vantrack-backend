from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.schemas.message import Attachment


class ParsedTransaction(BaseModel):
    amount: float
    description: str
    category: Optional[str] = None
    type: str
    account: str
    contact: Optional[str] = None
    date: Optional[str] = None  # Transaction occurring date (YYYY-MM-DD)
    due_date: Optional[str] = None
    interest_rate: Optional[float] = None
    term_months: Optional[int] = None
    linked_transaction_id: Optional[str] = None


class AIParseRequest(BaseModel):
    input_text: str
    history: Optional[List[Dict[str, Any]]] = None
    pending_drafts: Optional[List[Dict[str, Any]]] = None
    open_debts: Optional[List[Dict[str, Any]]] = None
    currency_code: Optional[str] = "USD"
    currency_symbol: Optional[str] = "$"
    language_code: Optional[str] = "en"
    attachments: Optional[List[Attachment]] = None


class AIParseResponse(BaseModel):
    transactions: List[ParsedTransaction]
    is_question: bool
    question_response: Optional[str] = None
    is_correction: Optional[bool] = None
