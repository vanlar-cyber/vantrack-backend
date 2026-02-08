from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User preferences
    preferred_currency = Column(String(10), default="USD")
    preferred_language = Column(String(10), default="en")
    
    # Business profile fields
    business_name = Column(String(255), nullable=True)
    business_type = Column(String(100), nullable=True)  # Sole Proprietorship, Partnership, Corporation, etc.
    industry = Column(String(100), nullable=True)  # Retail, Food & Beverage, Services, etc.
    business_size = Column(String(50), nullable=True)  # 1 (Solo), 2-5 employees, etc.
    location = Column(String(255), nullable=True)  # City, Province
    phone = Column(String(50), nullable=True)
    years_in_business = Column(Integer, nullable=True)
    monthly_revenue_range = Column(String(100), nullable=True)  # Below ₱50,000/month, etc.
    
    # Cached AI insights
    cached_action_nuggets = Column(Text, nullable=True)  # JSON array of nuggets
    action_nuggets_generated_at = Column(DateTime, nullable=True)  # When nuggets were last generated
    action_nuggets_tx_hash = Column(String(64), nullable=True)  # Hash of transaction state to detect changes

    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
