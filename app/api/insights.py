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
from app.services.insights_service import generate_weekly_summary, answer_financial_question, calculate_health_score, generate_health_tips, calculate_spending_comparisons, calculate_smart_predictions, generate_proactive_nudges, generate_action_nuggets_ai, generate_contact_tips
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


class ActionNugget(BaseModel):
    icon: str
    label: str
    value: str
    color: str
    prompt: str
    whyItMatters: str
    ifYouDoThis: str
    actionView: Optional[str] = None
    actionLabel: Optional[str] = None


class ActionNuggetsResponse(BaseModel):
    nuggets: list[ActionNugget]


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


@router.get("/action-nuggets", response_model=ActionNuggetsResponse)
async def get_action_nuggets(
    currency_symbol: str = "$",
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get data-driven action nuggets for the Daily Decision Feed.
    These are prioritized, actionable insights based on the user's financial data.
    
    Nuggets are cached and regenerated when:
    - Cache is older than 4 hours
    - Transaction data has changed significantly
    - force_refresh=true is passed
    """
    import json
    import hashlib
    from datetime import datetime, timedelta
    
    CACHE_TTL_HOURS = 4
    
    # Fetch all user transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Create a hash of transaction state to detect meaningful changes
    # Includes: count, total income/expense, receivables/payables, recent tx IDs+amounts, upcoming due dates
    total_income = sum(tx.amount for tx in transactions if tx.type and tx.type.value == 'income')
    total_expense = sum(tx.amount for tx in transactions if tx.type and tx.type.value == 'expense')
    total_receivable = sum(tx.remaining_amount or 0 for tx in transactions if tx.type and tx.type.value == 'receivable')
    total_payable = sum(tx.remaining_amount or 0 for tx in transactions if tx.type and tx.type.value == 'payable')
    
    # Include recent transaction IDs and amounts (catches edits to existing transactions)
    recent_tx_data = [(str(tx.id), tx.amount, tx.remaining_amount or 0) for tx in transactions[:20]]
    
    # Include upcoming due dates (next 7 days) - invalidates when bills become due
    from datetime import date
    today = date.today()
    week_later = today + timedelta(days=7)
    upcoming_due = sorted([
        tx.due_date.isoformat() for tx in transactions 
        if tx.due_date and today <= tx.due_date.date() <= week_later
    ])
    
    # Include user profile fields (so cache invalidates when profile is updated)
    profile_data = f"{current_user.business_name}|{current_user.business_type}|{current_user.industry}|{current_user.business_size}|{current_user.location}"
    
    tx_summary = f"{len(transactions)}|{total_income:.2f}|{total_expense:.2f}|{total_receivable:.2f}|{total_payable:.2f}|{recent_tx_data}|{upcoming_due}|{profile_data}"
    tx_hash = hashlib.md5(tx_summary.encode()).hexdigest()
    
    # Check if we can use cached nuggets
    now = datetime.utcnow()
    cache_valid = (
        not force_refresh
        and current_user.cached_action_nuggets
        and current_user.action_nuggets_generated_at
        and current_user.action_nuggets_tx_hash == tx_hash
        and (now - current_user.action_nuggets_generated_at) < timedelta(hours=CACHE_TTL_HOURS)
    )
    
    if cache_valid:
        # Return cached nuggets
        try:
            cached = json.loads(current_user.cached_action_nuggets)
            return ActionNuggetsResponse(nuggets=cached)
        except json.JSONDecodeError:
            pass  # Cache corrupted, regenerate
    
    # Convert to dict format for AI processing
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
    
    # Build user profile dict for AI context
    user_profile = {
        "full_name": current_user.full_name,
        "business_name": current_user.business_name,
        "business_type": current_user.business_type,
        "industry": current_user.industry,
        "business_size": current_user.business_size,
        "location": current_user.location,
        "years_in_business": current_user.years_in_business,
        "monthly_revenue_range": current_user.monthly_revenue_range,
    }
    
    # Generate AI-powered action nuggets
    nuggets = await generate_action_nuggets_ai(tx_data, currency_symbol, user_profile)
    
    # Cache the results
    current_user.cached_action_nuggets = json.dumps(nuggets)
    current_user.action_nuggets_generated_at = now
    current_user.action_nuggets_tx_hash = tx_hash
    await db.commit()
    
    return ActionNuggetsResponse(nuggets=nuggets)


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


class ContactTipResponse(BaseModel):
    tip: str
    sentiment: str
    recommendation: str


class ContactTipWithId(BaseModel):
    contact_id: str
    contact_name: str
    tip: str
    sentiment: str
    recommendation: str


class AllContactTipsResponse(BaseModel):
    tips: list[ContactTipWithId]


@router.get("/contact-tips", response_model=AllContactTipsResponse)
async def get_all_contact_tips(
    currency_symbol: str = "$",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get AI-generated tips for all contacts with transactions (prioritizes warnings/negatives)."""
    
    # Get all contacts
    contacts_result = await db.execute(
        select(Contact).where(Contact.user_id == current_user.id)
    )
    contacts = contacts_result.scalars().all()
    
    if not contacts:
        return AllContactTipsResponse(tips=[])
    
    # Get all transactions
    tx_result = await db.execute(
        select(Transaction).where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
    )
    all_transactions = tx_result.scalars().all()
    
    # Group transactions by contact
    contact_txs: dict[str, list] = {str(c.id): [] for c in contacts}
    contact_names: dict[str, str] = {str(c.id): c.name for c in contacts}
    
    for tx in all_transactions:
        contact_id = str(tx.contact_id) if tx.contact_id else None
        if not contact_id:
            # Try to match by name
            for c in contacts:
                if tx.contact_name and tx.contact_name.lower() == c.name.lower():
                    contact_id = str(c.id)
                    break
        
        if contact_id and contact_id in contact_txs:
            contact_txs[contact_id].append({
                "id": str(tx.id),
                "date": tx.date.isoformat() if tx.date else None,
                "amount": tx.amount,
                "description": tx.description,
                "type": tx.type.value if tx.type else None,
                "status": tx.status.value if tx.status else None,
                "remaining_amount": tx.remaining_amount,
                "due_date": tx.due_date.isoformat() if tx.due_date else None,
                "linked_transaction_id": str(tx.linked_transaction_id) if tx.linked_transaction_id else None,
            })
    
    # Generate tips for contacts with transactions (prioritize those with debt)
    tips = []
    for contact_id, txs in contact_txs.items():
        if not txs:
            continue
        
        tip_data = await generate_contact_tips(contact_names[contact_id], txs, currency_symbol)
        tips.append(ContactTipWithId(
            contact_id=contact_id,
            contact_name=contact_names[contact_id],
            tip=tip_data["tip"],
            sentiment=tip_data["sentiment"],
            recommendation=tip_data["recommendation"]
        ))
    
    # Sort: negative first, then warning, then others
    sentiment_order = {"negative": 0, "warning": 1, "neutral": 2, "positive": 3}
    tips.sort(key=lambda x: sentiment_order.get(x.sentiment, 2))
    
    return AllContactTipsResponse(tips=tips)


@router.get("/contact-tip/{contact_id}", response_model=ContactTipResponse)
async def get_contact_tip(
    contact_id: str,
    currency_symbol: str = "$",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get AI-generated tip about a contact's payment behavior."""
    
    # Get the contact
    contact_result = await db.execute(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    )
    contact = contact_result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Get all transactions related to this contact
    tx_result = await db.execute(
        select(Transaction).where(
            Transaction.user_id == current_user.id,
            (Transaction.contact_id == contact_id) | (Transaction.contact_name == contact.name)
        ).order_by(Transaction.date.desc())
    )
    transactions = tx_result.scalars().all()
    
    # Convert to dict format
    tx_data = [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else None,
            "amount": tx.amount,
            "description": tx.description,
            "type": tx.type.value if tx.type else None,
            "status": tx.status.value if tx.status else None,
            "remaining_amount": tx.remaining_amount,
            "due_date": tx.due_date.isoformat() if tx.due_date else None,
            "linked_transaction_id": str(tx.linked_transaction_id) if tx.linked_transaction_id else None,
        }
        for tx in transactions
    ]
    
    # Generate tip
    tip_data = await generate_contact_tips(contact.name, tx_data, currency_symbol)
    
    return ContactTipResponse(
        tip=tip_data["tip"],
        sentiment=tip_data["sentiment"],
        recommendation=tip_data["recommendation"]
    )
