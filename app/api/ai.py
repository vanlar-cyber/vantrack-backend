from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import AIParseRequest, AIParseResponse, ParsedTransaction
from app.services.gemini_service import parse_financial_input
from app.api.deps import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/parse", response_model=AIParseResponse)
async def parse_input(
    request: AIParseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Convert attachments to dict format
        attachments = None
        if request.attachments:
            attachments = [
                {
                    "type": att.type.value,
                    "mime_type": att.mime_type,
                    "data_url": att.data_url,
                    "name": att.name
                }
                for att in request.attachments
            ]
        
        result = await parse_financial_input(
            input_text=request.input_text,
            history=request.history,
            pending_drafts=request.pending_drafts,
            open_debts=request.open_debts,
            currency_code=request.currency_code or current_user.preferred_currency,
            currency_symbol=request.currency_symbol or "$",
            language_code=request.language_code or current_user.preferred_language,
            attachments=attachments
        )
        
        transactions = [
            ParsedTransaction(
                amount=tx.get("amount", 0),
                description=tx.get("description", ""),
                category=tx.get("category"),
                type=tx.get("type", "expense"),
                account=tx.get("account", "cash"),
                contact=tx.get("contact"),
                date=tx.get("date"),  # Transaction occurring date from AI
                due_date=tx.get("dueDate"),
                interest_rate=tx.get("interestRate"),
                term_months=tx.get("termMonths"),
                linked_transaction_id=tx.get("linkedTransactionId")
            )
            for tx in result.get("transactions", [])
        ]
        
        return AIParseResponse(
            transactions=transactions,
            is_question=result.get("is_question", False),
            question_response=result.get("question_response"),
            is_correction=result.get("is_correction")
        )
        
    except ValueError as e:
        if str(e) == "QUOTA_EXHAUSTED":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI quota exhausted. Please try again later."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI processing error: {str(e)}"
        )
