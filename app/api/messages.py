from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.database import get_db
from app.models.user import User
from app.models.message import Message, MessageRole
from app.schemas.message import MessageCreate, MessageResponse, MessageListResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("", response_model=MessageListResponse)
async def list_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Message).where(Message.user_id == current_user.id)
    query = query.order_by(Message.timestamp.asc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Get total count
    count_query = select(func.count(Message.id)).where(Message.user_id == current_user.id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return MessageListResponse(messages=messages, total=total)


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    attachments_json = None
    if message_data.attachments:
        attachments_json = [att.model_dump() for att in message_data.attachments]
    
    new_message = Message(
        user_id=current_user.id,
        role=message_data.role,
        content=message_data.content,
        drafts_json=message_data.drafts_json,
        attachments_json=attachments_json
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    return new_message


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Message).where(Message.user_id == current_user.id)
    )
    messages = result.scalars().all()
    
    for msg in messages:
        await db.delete(msg)
    
    await db.commit()


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    await db.delete(message)
    await db.commit()
