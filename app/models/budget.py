from sqlalchemy import Column, String, DateTime, Float, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class BudgetType(str, enum.Enum):
    spending_limit = "spending_limit"  # Limit spending in a category
    income_goal = "income_goal"        # Target income amount
    savings_goal = "savings_goal"      # Target savings amount
    profit_goal = "profit_goal"        # Target profit (income - expenses)


class BudgetPeriod(str, enum.Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)  # e.g., "Food Budget", "Monthly Savings"
    type = Column(Enum(BudgetType), nullable=False)
    category = Column(String(100), nullable=True)  # For spending limits, e.g., "food", "entertainment"
    
    amount = Column(Float, nullable=False)  # Target/limit amount
    period = Column(Enum(BudgetPeriod), default=BudgetPeriod.monthly)
    
    # Track progress
    current_amount = Column(Float, default=0)  # Current spent/earned this period
    
    # Notification settings
    alert_at_percent = Column(Float, default=80)  # Alert when reaching this % of budget
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Period tracking
    period_start = Column(DateTime, nullable=True)  # When current period started
    
    # Relationships
    user = relationship("User", back_populates="budgets")
