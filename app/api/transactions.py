from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TransactionType, DebtStatus
from app.models.contact import Contact
from app.schemas.transaction import (
    TransactionCreate, TransactionUpdate, TransactionResponse,
    TransactionListResponse, BalanceSummary
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    type_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    
    if type_filter:
        query = query.where(Transaction.type == type_filter)
    
    query = query.order_by(Transaction.date.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    # Get total count
    count_query = select(func.count(Transaction.id)).where(Transaction.user_id == current_user.id)
    if type_filter:
        count_query = count_query.where(Transaction.type == type_filter)
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return TransactionListResponse(transactions=transactions, total=total)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    tx_data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Handle contact linking
    contact_id = tx_data.contact_id
    if tx_data.contact_name and not contact_id:
        # Try to find existing contact by name
        result = await db.execute(
            select(Contact).where(
                Contact.user_id == current_user.id,
                func.lower(Contact.name) == tx_data.contact_name.lower()
            )
        )
        existing_contact = result.scalar_one_or_none()
        
        if existing_contact:
            contact_id = existing_contact.id
        else:
            # Create new contact
            new_contact = Contact(
                user_id=current_user.id,
                name=tx_data.contact_name
            )
            db.add(new_contact)
            await db.flush()
            contact_id = new_contact.id
    
    # Normalize due_date to remove timezone info if present
    due_date = tx_data.due_date
    if due_date and due_date.tzinfo is not None:
        due_date = due_date.replace(tzinfo=None)
    
    # Create transaction
    new_tx = Transaction(
        user_id=current_user.id,
        amount=tx_data.amount,
        description=tx_data.description,
        category=tx_data.category,
        type=tx_data.type,
        account=tx_data.account,
        contact_name=tx_data.contact_name,
        contact_id=contact_id,
        due_date=due_date,
        linked_transaction_id=tx_data.linked_transaction_id,
        metadata_json=tx_data.metadata_json
    )
    
    # Handle debt status for credit/loan transactions
    if tx_data.type in [TransactionType.credit_receivable, TransactionType.credit_payable,
                        TransactionType.loan_receivable, TransactionType.loan_payable]:
        new_tx.status = DebtStatus.open
        new_tx.remaining_amount = tx_data.amount
    
    # Handle payment linking with FIFO logic - create separate tx for each debt
    if tx_data.type in [TransactionType.payment_received, TransactionType.payment_made]:
        remaining_payment = tx_data.amount
        created_transactions = []
        debts_to_apply = []
        
        if tx_data.linked_transaction_id:
            # User selected a specific debt - apply to it first
            result = await db.execute(
                select(Transaction).where(
                    Transaction.id == tx_data.linked_transaction_id,
                    Transaction.user_id == current_user.id
                )
            )
            linked_tx = result.scalar_one_or_none()
            if linked_tx:
                debts_to_apply.append(linked_tx)
        
        # If there's remaining payment amount and we have a contact, get FIFO debts
        if remaining_payment > 0 and (tx_data.contact_name or contact_id):
            # Determine which debt types to look for based on payment type
            if tx_data.type == TransactionType.payment_received:
                debt_types = [TransactionType.credit_receivable, TransactionType.loan_receivable]
            else:
                debt_types = [TransactionType.credit_payable, TransactionType.loan_payable]
            
            # Get open debts for this contact, ordered by date (FIFO - oldest first)
            debt_query = select(Transaction).where(
                Transaction.user_id == current_user.id,
                Transaction.type.in_(debt_types),
                Transaction.status != DebtStatus.settled
            )
            
            if contact_id:
                debt_query = debt_query.where(Transaction.contact_id == contact_id)
            elif tx_data.contact_name:
                debt_query = debt_query.where(
                    func.lower(Transaction.contact_name) == tx_data.contact_name.lower()
                )
            
            # Exclude already linked transaction
            if tx_data.linked_transaction_id:
                debt_query = debt_query.where(Transaction.id != tx_data.linked_transaction_id)
            
            debt_query = debt_query.order_by(Transaction.date.asc())  # FIFO - oldest first
            
            result = await db.execute(debt_query)
            additional_debts = result.scalars().all()
            debts_to_apply.extend(additional_debts)
        
        # Create separate payment transaction for each debt
        for debt in debts_to_apply:
            if remaining_payment <= 0:
                break
            
            current_remaining = debt.remaining_amount if debt.remaining_amount is not None else debt.amount
            apply_amount = min(remaining_payment, current_remaining)
            
            # Update the debt
            new_remaining = current_remaining - apply_amount
            debt.remaining_amount = new_remaining
            debt.status = DebtStatus.settled if new_remaining == 0 else DebtStatus.partial
            remaining_payment -= apply_amount
            
            # Create a payment transaction linked to this specific debt
            payment_tx = Transaction(
                user_id=current_user.id,
                amount=apply_amount,
                description=tx_data.description,
                category=tx_data.category,
                type=tx_data.type,
                account=tx_data.account,
                contact_name=tx_data.contact_name,
                contact_id=contact_id,
                due_date=due_date,
                linked_transaction_id=debt.id,
                metadata_json=tx_data.metadata_json
            )
            db.add(payment_tx)
            created_transactions.append(payment_tx)
        
        # Commit all transactions
        await db.commit()
        
        # Refresh and return the first transaction (or all if needed)
        if created_transactions:
            await db.refresh(created_transactions[0])
            return created_transactions[0]
        else:
            # No debts to apply to, create a standalone payment
            db.add(new_tx)
            await db.commit()
            await db.refresh(new_tx)
            return new_tx
    
    db.add(new_tx)
    await db.commit()
    await db.refresh(new_tx)
    
    return new_tx


@router.get("/balances", response_model=BalanceSummary)
async def get_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Transaction).where(Transaction.user_id == current_user.id)
    )
    transactions = result.scalars().all()
    
    balances = {"cash": 0.0, "bank": 0.0, "credit": 0.0, "loan": 0.0}
    
    for tx in transactions:
        amt = tx.amount
        acct = tx.account.value if tx.account else "cash"
        tx_type = tx.type.value if tx.type else ""
        
        if tx_type == "income":
            balances[acct] += amt
        elif tx_type == "expense":
            balances[acct] -= amt
        elif tx_type == "credit_receivable":
            balances["credit"] += amt
        elif tx_type == "credit_payable":
            balances["loan"] += amt
        elif tx_type == "loan_receivable":
            balances[acct] -= amt
            balances["credit"] += amt
        elif tx_type == "loan_payable":
            balances[acct] += amt
            balances["loan"] += amt
        elif tx_type == "payment_received":
            balances[acct] += amt
            balances["credit"] -= amt
        elif tx_type == "payment_made":
            balances[acct] -= amt
            balances["loan"] -= amt
        elif tx_type == "transfer":
            balances[acct] -= amt
    
    return BalanceSummary(**balances)


@router.get("/open-debts", response_model=List[TransactionResponse])
async def get_open_debts(
    contact_name: Optional[str] = None,
    contact_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.type.in_([
            TransactionType.credit_receivable,
            TransactionType.credit_payable,
            TransactionType.loan_receivable,
            TransactionType.loan_payable
        ]),
        Transaction.status != DebtStatus.settled
    )
    
    # Filter by contact if provided
    if contact_id:
        query = query.where(Transaction.contact_id == contact_id)
    elif contact_name:
        query = query.where(
            func.lower(Transaction.contact_name) == contact_name.lower()
        )
    
    # Order by date ascending (FIFO - oldest first)
    query = query.order_by(Transaction.date.asc())
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
    )
    tx = result.scalar_one_or_none()
    
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    return tx


@router.get("/{transaction_id}/payments", response_model=List[TransactionResponse])
async def get_debt_payments(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all payments made towards a specific debt transaction using linked_transaction_id."""
    # First verify the debt transaction exists
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
    )
    debt = result.scalar_one_or_none()
    
    if not debt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    # Find all payment transactions that link to this debt via linked_transaction_id
    result = await db.execute(
        select(Transaction).where(
            Transaction.linked_transaction_id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.type.in_([TransactionType.payment_received, TransactionType.payment_made])
        ).order_by(Transaction.date.asc())
    )
    return result.scalars().all()


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    tx_update: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
    )
    tx = result.scalar_one_or_none()
    
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    update_data = tx_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tx, field, value)
    
    await db.commit()
    await db.refresh(tx)
    
    return tx


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
    )
    tx = result.scalar_one_or_none()
    
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    await db.delete(tx)
    await db.commit()
