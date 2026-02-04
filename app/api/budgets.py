from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID

from app.core.database import get_db
from app.models.user import User
from app.models.budget import Budget, BudgetType, BudgetPeriod
from app.models.transaction import Transaction, TransactionType
from app.api.deps import get_current_user

router = APIRouter(prefix="/budgets", tags=["Budgets"])


class BudgetCreate(BaseModel):
    name: str
    type: str  # spending_limit, income_goal, savings_goal, profit_goal
    category: Optional[str] = None
    amount: float
    period: str = "monthly"  # weekly, monthly, yearly
    alert_at_percent: float = 80


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    period: Optional[str] = None
    alert_at_percent: Optional[float] = None
    is_active: Optional[bool] = None


class BudgetResponse(BaseModel):
    id: str
    name: str
    type: str
    category: Optional[str]
    amount: float
    period: str
    current_amount: float
    progress_percent: float
    alert_at_percent: float
    is_active: bool
    is_over_budget: bool
    status: str  # on_track, warning, over_budget, achieved
    period_start: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


def get_period_start(period: str) -> datetime:
    """Get the start of the current period."""
    now = datetime.utcnow()
    if period == "weekly":
        # Start of current week (Monday)
        return now - timedelta(days=now.weekday())
    elif period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "yearly":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def calculate_budget_progress(
    db: AsyncSession,
    budget: Budget,
    user_id: UUID
) -> tuple[float, str]:
    """Calculate current progress for a budget based on transactions."""
    period_start = get_period_start(budget.period)
    
    # Build query based on budget type
    if budget.type == BudgetType.spending_limit:
        # Sum expenses in this category
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= period_start
            )
        )
        if budget.category:
            query = query.where(
                Transaction.category.ilike(f"%{budget.category}%")
            )
        
        result = await db.execute(query)
        transactions = result.scalars().all()
        current = sum(t.amount for t in transactions)
        
        progress = (current / budget.amount * 100) if budget.amount > 0 else 0
        if progress >= 100:
            status = "over_budget"
        elif progress >= budget.alert_at_percent:
            status = "warning"
        else:
            status = "on_track"
            
    elif budget.type == BudgetType.income_goal:
        # Sum income
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.income,
                Transaction.date >= period_start
            )
        )
        result = await db.execute(query)
        transactions = result.scalars().all()
        current = sum(t.amount for t in transactions)
        
        progress = (current / budget.amount * 100) if budget.amount > 0 else 0
        status = "achieved" if progress >= 100 else "on_track"
        
    elif budget.type == BudgetType.savings_goal:
        # Savings = Income - Expenses
        income_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.income,
                Transaction.date >= period_start
            )
        )
        expense_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= period_start
            )
        )
        
        income_result = await db.execute(income_query)
        expense_result = await db.execute(expense_query)
        
        total_income = sum(t.amount for t in income_result.scalars().all())
        total_expense = sum(t.amount for t in expense_result.scalars().all())
        current = max(0, total_income - total_expense)
        
        progress = (current / budget.amount * 100) if budget.amount > 0 else 0
        status = "achieved" if progress >= 100 else "on_track"
        
    elif budget.type == BudgetType.profit_goal:
        # Profit = Income - Expenses (can be negative)
        income_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.income,
                Transaction.date >= period_start
            )
        )
        expense_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= period_start
            )
        )
        
        income_result = await db.execute(income_query)
        expense_result = await db.execute(expense_query)
        
        total_income = sum(t.amount for t in income_result.scalars().all())
        total_expense = sum(t.amount for t in expense_result.scalars().all())
        current = total_income - total_expense
        
        progress = (current / budget.amount * 100) if budget.amount > 0 else 0
        status = "achieved" if progress >= 100 else "on_track"
    else:
        current = 0
        status = "on_track"
    
    return current, status


@router.get("", response_model=List[BudgetResponse])
async def get_budgets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all budgets for the current user with progress."""
    result = await db.execute(
        select(Budget)
        .where(Budget.user_id == current_user.id)
        .order_by(Budget.created_at.desc())
    )
    budgets = result.scalars().all()
    
    response = []
    for budget in budgets:
        current_amount, status = await calculate_budget_progress(db, budget, current_user.id)
        progress = (current_amount / budget.amount * 100) if budget.amount > 0 else 0
        
        response.append(BudgetResponse(
            id=str(budget.id),
            name=budget.name,
            type=budget.type.value if hasattr(budget.type, 'value') else str(budget.type),
            category=budget.category,
            amount=budget.amount,
            period=budget.period.value if hasattr(budget.period, 'value') else str(budget.period),
            current_amount=round(current_amount, 2),
            progress_percent=round(progress, 1),
            alert_at_percent=budget.alert_at_percent,
            is_active=budget.is_active,
            is_over_budget=progress >= 100 and budget.type == BudgetType.spending_limit,
            status=status,
            period_start=get_period_start(budget.period.value if hasattr(budget.period, 'value') else str(budget.period)).isoformat(),
            created_at=budget.created_at.isoformat()
        ))
    
    return response


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new budget or goal."""
    # Validate type
    try:
        budget_type = BudgetType(budget_data.type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid budget type. Must be one of: {[t.value for t in BudgetType]}"
        )
    
    # Validate period
    try:
        budget_period = BudgetPeriod(budget_data.period)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of: {[p.value for p in BudgetPeriod]}"
        )
    
    budget = Budget(
        user_id=current_user.id,
        name=budget_data.name,
        type=budget_type,
        category=budget_data.category,
        amount=budget_data.amount,
        period=budget_period,
        alert_at_percent=budget_data.alert_at_percent,
        period_start=get_period_start(budget_data.period)
    )
    
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    
    current_amount, budget_status = await calculate_budget_progress(db, budget, current_user.id)
    progress = (current_amount / budget.amount * 100) if budget.amount > 0 else 0
    
    return BudgetResponse(
        id=str(budget.id),
        name=budget.name,
        type=budget.type.value,
        category=budget.category,
        amount=budget.amount,
        period=budget.period.value,
        current_amount=round(current_amount, 2),
        progress_percent=round(progress, 1),
        alert_at_percent=budget.alert_at_percent,
        is_active=budget.is_active,
        is_over_budget=progress >= 100 and budget.type == BudgetType.spending_limit,
        status=budget_status,
        period_start=budget.period_start.isoformat() if budget.period_start else None,
        created_at=budget.created_at.isoformat()
    )


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    budget_data: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a budget."""
    result = await db.execute(
        select(Budget).where(
            and_(
                Budget.id == budget_id,
                Budget.user_id == current_user.id
            )
        )
    )
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    if budget_data.name is not None:
        budget.name = budget_data.name
    if budget_data.amount is not None:
        budget.amount = budget_data.amount
    if budget_data.category is not None:
        budget.category = budget_data.category
    if budget_data.period is not None:
        try:
            budget.period = BudgetPeriod(budget_data.period)
            budget.period_start = get_period_start(budget_data.period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    if budget_data.alert_at_percent is not None:
        budget.alert_at_percent = budget_data.alert_at_percent
    if budget_data.is_active is not None:
        budget.is_active = budget_data.is_active
    
    await db.commit()
    await db.refresh(budget)
    
    current_amount, budget_status = await calculate_budget_progress(db, budget, current_user.id)
    progress = (current_amount / budget.amount * 100) if budget.amount > 0 else 0
    
    return BudgetResponse(
        id=str(budget.id),
        name=budget.name,
        type=budget.type.value if hasattr(budget.type, 'value') else str(budget.type),
        category=budget.category,
        amount=budget.amount,
        period=budget.period.value if hasattr(budget.period, 'value') else str(budget.period),
        current_amount=round(current_amount, 2),
        progress_percent=round(progress, 1),
        alert_at_percent=budget.alert_at_percent,
        is_active=budget.is_active,
        is_over_budget=progress >= 100 and budget.type == BudgetType.spending_limit,
        status=budget_status,
        period_start=budget.period_start.isoformat() if budget.period_start else None,
        created_at=budget.created_at.isoformat()
    )


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a budget."""
    result = await db.execute(
        select(Budget).where(
            and_(
                Budget.id == budget_id,
                Budget.user_id == current_user.id
            )
        )
    )
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    await db.delete(budget)
    await db.commit()
