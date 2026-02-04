from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.contact import Contact
from app.api.deps import get_current_user
from app.services.insights_service import generate_weekly_summary, answer_financial_question, calculate_health_score, generate_health_tips, calculate_spending_comparisons, calculate_smart_predictions, generate_proactive_nudges
from app.models.budget import Budget

router = APIRouter(prefix="/insights", tags=["Insights"])


class WeeklySummaryResponse(BaseModel):
    summary: str


class QuestionRequest(BaseModel):
    question: str
    currency_symbol: Optional[str] = "$"
    language_code: Optional[str] = "en"


class QuestionResponse(BaseModel):
    answer: str


class BreakdownItem(BaseModel):
    score: float
    max: int
    value: str
    label: str


class HealthBreakdown(BaseModel):
    savings_rate: BreakdownItem
    debt_ratio: BreakdownItem
    consistency: BreakdownItem
    emergency_fund: BreakdownItem


class HealthSummary(BaseModel):
    monthly_income: float
    monthly_expense: float
    total_receivable: float
    total_payable: float
    net_position: float


class HealthScoreResponse(BaseModel):
    score: int
    grade: str
    grade_color: str
    breakdown: HealthBreakdown
    summary: HealthSummary
    tips: str


class ComparisonItem(BaseModel):
    category: str
    your_value: str
    your_pct: Optional[str] = None
    benchmark: str
    difference: float
    is_better: bool
    insight: str


class SpendingComparisonsResponse(BaseModel):
    monthly_income: float
    monthly_expenses: float
    comparisons: list[ComparisonItem]
    percentile: int
    summary: str


class CashFlowForecast(BaseModel):
    current_balance: float
    projected_end_of_month: float
    projected_income: float
    projected_expenses: float
    days_remaining: int
    trend: str
    message: str


class BillReminder(BaseModel):
    name: str
    amount: float
    usual_day: int
    days_until_due: int
    is_upcoming: bool
    message: str


class DebtItem(BaseModel):
    id: str
    description: str
    contact: str
    original_amount: float
    remaining: float
    due_date: Optional[str] = None


class DebtPayoff(BaseModel):
    total_debt: float
    debt_count: int
    debts: list[DebtItem]
    avg_monthly_payment: float
    months_to_payoff: Optional[float] = None
    payoff_date: Optional[str] = None
    message: Optional[str] = None


class SmartPredictionsResponse(BaseModel):
    cash_flow_forecast: CashFlowForecast
    bill_reminders: list[BillReminder]
    debt_payoff: DebtPayoff
    generated_at: str


class NudgeDetails(BaseModel):
    weekly_income: Optional[float] = None
    weekly_expenses: Optional[float] = None
    weekly_balance: Optional[float] = None
    days_left: Optional[int] = None


class Nudge(BaseModel):
    type: str  # morning_brief, alert, celebration
    icon: str
    color: str
    title: str
    message: str
    priority: Optional[str] = None
    details: Optional[NudgeDetails] = None


class NudgeSummary(BaseModel):
    weekly_balance: float
    monthly_income: float
    monthly_expenses: float
    days_left_week: int
    days_left_month: int


class ProactiveNudgesResponse(BaseModel):
    nudges: list[Nudge]
    summary: NudgeSummary
    generated_at: str


@router.get("/weekly-summary", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    currency_symbol: str = "$",
    language_code: str = "en",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI-powered weekly financial summary."""
    
    # Fetch user's transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Convert to dict format for the AI service
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
            "account": tx.account.value if tx.account else None,
            "contact_name": tx.contact_name,
            "status": tx.status.value if tx.status else None,
            "remaining_amount": tx.remaining_amount
        }
        for tx in transactions
    ]
    
    summary = await generate_weekly_summary(
        transactions=tx_data,
        currency_symbol=currency_symbol,
        language_code=language_code
    )
    
    return WeeklySummaryResponse(summary=summary)


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ask AI a question about your financial data."""
    
    # Fetch user's transactions
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = tx_result.scalars().all()
    
    # Fetch user's contacts
    contact_result = await db.execute(
        select(Contact)
        .where(Contact.user_id == current_user.id)
    )
    contacts = contact_result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
            "account": tx.account.value if tx.account else None,
            "contact_name": tx.contact_name,
            "status": tx.status.value if tx.status else None,
            "remaining_amount": tx.remaining_amount,
            "due_date": tx.due_date.isoformat() if tx.due_date else None
        }
        for tx in transactions
    ]
    
    contact_data = [
        {
            "id": str(c.id),
            "name": c.name,
            "phone": c.phone,
            "email": c.email
        }
        for c in contacts
    ]
    
    answer = await answer_financial_question(
        question=request.question,
        transactions=tx_data,
        contacts=contact_data,
        currency_symbol=request.currency_symbol,
        language_code=request.language_code
    )
    
    return QuestionResponse(answer=answer)


@router.get("/health-score", response_model=HealthScoreResponse)
async def get_health_score(
    currency_symbol: str = "$",
    language_code: str = "en",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate financial health score with AI-powered improvement tips."""
    
    # Fetch user's transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
            "account": tx.account.value if tx.account else None,
            "contact_name": tx.contact_name,
            "status": tx.status.value if tx.status else None,
            "remaining_amount": tx.remaining_amount
        }
        for tx in transactions
    ]
    
    # Calculate health score
    health_data = calculate_health_score(tx_data, currency_symbol)
    
    # Generate AI tips
    tips = await generate_health_tips(health_data, currency_symbol, language_code)
    
    return HealthScoreResponse(
        score=health_data["score"],
        grade=health_data["grade"],
        grade_color=health_data["grade_color"],
        breakdown=health_data["breakdown"],
        summary=health_data["summary"],
        tips=tips
    )


@router.get("/spending-comparisons", response_model=SpendingComparisonsResponse)
async def get_spending_comparisons(
    currency_symbol: str = "$",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare user's spending to anonymous benchmarks."""
    
    # Fetch user's transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
        }
        for tx in transactions
    ]
    
    # Calculate comparisons
    comparisons_data = calculate_spending_comparisons(tx_data, currency_symbol)
    
    return SpendingComparisonsResponse(
        monthly_income=comparisons_data["monthly_income"],
        monthly_expenses=comparisons_data["monthly_expenses"],
        comparisons=comparisons_data["comparisons"],
        percentile=comparisons_data["percentile"],
        summary=comparisons_data["summary"]
    )


@router.get("/smart-predictions", response_model=SmartPredictionsResponse)
async def get_smart_predictions(
    currency_symbol: str = "$",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get smart predictions including:
    - Cash flow forecast for end of month
    - Bill reminders based on recurring patterns
    - Debt payoff timeline
    """
    
    # Fetch all user transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
            "contact_name": tx.contact_name,
            "remaining_amount": tx.remaining_amount,
            "status": tx.status.value if tx.status else None,
            "due_date": tx.due_date.isoformat() if tx.due_date else None,
        }
        for tx in transactions
    ]
    
    # Calculate predictions
    predictions = calculate_smart_predictions(tx_data, currency_symbol)
    
    return SmartPredictionsResponse(
        cash_flow_forecast=predictions["cash_flow_forecast"],
        bill_reminders=predictions["bill_reminders"],
        debt_payoff=predictions["debt_payoff"],
        generated_at=predictions["generated_at"]
    )


@router.get("/nudges", response_model=ProactiveNudgesResponse)
async def get_proactive_nudges(
    currency_symbol: str = "$",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get proactive AI nudges including:
    - Morning brief with daily financial snapshot
    - Smart alerts for budget warnings and unusual spending
    - Celebrations for achievements and milestones
    """
    from app.api.budgets import calculate_budget_progress, get_period_start
    from app.models.budget import BudgetType
    
    # Fetch all user transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "category": tx.category,
            "type": tx.type.value if tx.type else None,
            "contact_name": tx.contact_name,
        }
        for tx in transactions
    ]
    
    # Fetch user budgets with progress
    budget_result = await db.execute(
        select(Budget)
        .where(Budget.user_id == current_user.id)
    )
    budgets = budget_result.scalars().all()
    
    budget_data = []
    for budget in budgets:
        current_amount, status = await calculate_budget_progress(db, budget, current_user.id)
        progress = (current_amount / budget.amount * 100) if budget.amount > 0 else 0
        
        budget_data.append({
            "id": str(budget.id),
            "name": budget.name,
            "type": budget.type.value if hasattr(budget.type, 'value') else str(budget.type),
            "category": budget.category,
            "amount": budget.amount,
            "current_amount": current_amount,
            "progress_percent": progress,
            "alert_at_percent": budget.alert_at_percent,
            "is_active": budget.is_active,
        })
    
    # Generate nudges
    nudges_data = generate_proactive_nudges(tx_data, budget_data, currency_symbol)
    
    return ProactiveNudgesResponse(
        nudges=nudges_data["nudges"],
        summary=nudges_data["summary"],
        generated_at=nudges_data["generated_at"]
    )
