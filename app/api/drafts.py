from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.models.draft import Draft, DraftStatus
from app.models.transaction import Transaction, TransactionType, DebtStatus
from app.models.contact import Contact
from app.schemas.draft import DraftCreate, DraftUpdate, DraftResponse, DraftListResponse
from app.schemas.transaction import TransactionResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/drafts", tags=["Drafts"])


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    status_filter: DraftStatus = Query(DraftStatus.pending, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all drafts for the current user, filtered by status (default: pending)."""
    query = select(Draft).where(
        Draft.user_id == current_user.id,
        Draft.status == status_filter
    )
    query = query.order_by(Draft.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    drafts = result.scalars().all()
    
    count_query = select(func.count(Draft.id)).where(
        Draft.user_id == current_user.id,
        Draft.status == status_filter
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return DraftListResponse(drafts=drafts, total=total)


@router.post("", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    draft_data: DraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new draft transaction."""
    from datetime import datetime
    # Handle timezone-aware dates by converting to naive UTC
    draft_date = draft_data.date
    if draft_date and hasattr(draft_date, 'tzinfo') and draft_date.tzinfo is not None:
        draft_date = draft_date.replace(tzinfo=None)
    
    new_draft = Draft(
        user_id=current_user.id,
        message_id=draft_data.message_id,
        date=draft_date or datetime.utcnow(),
        amount=draft_data.amount,
        description=draft_data.description,
        category=draft_data.category,
        type=draft_data.type,
        account=draft_data.account,
        contact_name=draft_data.contact_name,
        contact_id=draft_data.contact_id,
        due_date=draft_data.due_date,
        linked_transaction_id=draft_data.linked_transaction_id,
        status=DraftStatus.pending
    )
    
    db.add(new_draft)
    await db.commit()
    await db.refresh(new_draft)
    
    return new_draft


@router.post("/batch", response_model=List[DraftResponse], status_code=status.HTTP_201_CREATED)
async def create_drafts_batch(
    drafts_data: List[DraftCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create multiple drafts at once (used when AI generates multiple transactions)."""
    from datetime import datetime
    new_drafts = []
    for draft_data in drafts_data:
        # Handle timezone-aware dates by converting to naive UTC
        draft_date = draft_data.date
        if draft_date and hasattr(draft_date, 'tzinfo') and draft_date.tzinfo is not None:
            draft_date = draft_date.replace(tzinfo=None)
        
        new_draft = Draft(
            user_id=current_user.id,
            message_id=draft_data.message_id,
            date=draft_date or datetime.utcnow(),
            amount=draft_data.amount,
            description=draft_data.description,
            category=draft_data.category,
            type=draft_data.type,
            account=draft_data.account,
            contact_name=draft_data.contact_name,
            contact_id=draft_data.contact_id,
            due_date=draft_data.due_date,
            linked_transaction_id=draft_data.linked_transaction_id,
            status=DraftStatus.pending
        )
        db.add(new_draft)
        new_drafts.append(new_draft)
    
    await db.commit()
    for draft in new_drafts:
        await db.refresh(draft)
    
    return new_drafts


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific draft by ID."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    
    return draft


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: UUID,
    draft_update: DraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a draft (only pending drafts can be updated)."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    
    if draft.status != DraftStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending drafts can be updated")
    
    update_data = draft_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)
    
    await db.commit()
    await db.refresh(draft)
    
    return draft


@router.post("/{draft_id}/confirm", response_model=TransactionResponse)
async def confirm_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm a draft and create the actual transaction."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    
    if draft.status != DraftStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending drafts can be confirmed")
    
    # Handle contact linking
    contact_id = draft.contact_id
    if draft.contact_name and not contact_id:
        result = await db.execute(
            select(Contact).where(
                Contact.user_id == current_user.id,
                func.lower(Contact.name) == draft.contact_name.lower()
            )
        )
        existing_contact = result.scalar_one_or_none()
        if existing_contact:
            contact_id = existing_contact.id
        else:
            new_contact = Contact(user_id=current_user.id, name=draft.contact_name)
            db.add(new_contact)
            await db.flush()
            contact_id = new_contact.id
    
    # Create the transaction
    new_tx = Transaction(
        user_id=current_user.id,
        amount=draft.amount,
        description=draft.description,
        category=draft.category,
        type=draft.type,
        account=draft.account,
        contact_name=draft.contact_name,
        contact_id=contact_id,
        due_date=draft.due_date,
        linked_transaction_id=draft.linked_transaction_id
    )
    
    # Handle debt status
    if draft.type in [TransactionType.credit_receivable.value, TransactionType.credit_payable.value,
                      TransactionType.loan_receivable.value, TransactionType.loan_payable.value]:
        new_tx.status = DebtStatus.open
        new_tx.remaining_amount = draft.amount
    
    # Handle payment linking
    if draft.type in [TransactionType.payment_received.value, TransactionType.payment_made.value]:
        if draft.linked_transaction_id:
            linked_result = await db.execute(
                select(Transaction).where(
                    Transaction.id == draft.linked_transaction_id,
                    Transaction.user_id == current_user.id
                )
            )
            linked_tx = linked_result.scalar_one_or_none()
            
            if linked_tx:
                current_remaining = linked_tx.remaining_amount if linked_tx.remaining_amount is not None else linked_tx.amount
                apply_amount = min(draft.amount, current_remaining)
                new_remaining = current_remaining - apply_amount
                linked_tx.remaining_amount = new_remaining
                linked_tx.status = DebtStatus.settled if new_remaining == 0 else DebtStatus.partial
    
    db.add(new_tx)
    
    # Mark draft as confirmed
    draft.status = DraftStatus.confirmed
    
    await db.commit()
    await db.refresh(new_tx)
    
    return new_tx


@router.post("/{draft_id}/discard", response_model=DraftResponse)
async def discard_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Discard a draft (mark as discarded, not deleted for history)."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    
    if draft.status != DraftStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending drafts can be discarded")
    
    draft.status = DraftStatus.discarded
    
    await db.commit()
    await db.refresh(draft)
    
    return draft


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Permanently delete a draft."""
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    
    await db.delete(draft)
    await db.commit()
