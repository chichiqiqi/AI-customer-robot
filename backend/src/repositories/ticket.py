"""工单与消息数据访问层。"""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.db.models import Ticket, Message, TicketStatus, MessageRole


class TicketRepository:
    """工单 CRUD。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, title: str = "新对话") -> Ticket:
        ticket = Ticket(user_id=user_id, title=title)
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        result = await self.db.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> List[Ticket]:
        """获取某用户的所有工单（按更新时间倒序）。"""
        result = await self.db.execute(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_status(self, *statuses: str) -> List[Ticket]:
        """按状态筛选工单。"""
        result = await self.db.execute(
            select(Ticket)
            .where(Ticket.status.in_(statuses))
            .order_by(Ticket.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self, ticket_id: int, status: str,
        agent_id: Optional[int] = None,
    ) -> Optional[Ticket]:
        ticket = await self.get_by_id(ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        if agent_id is not None:
            ticket.agent_id = agent_id
        if status in (TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value):
            ticket.closed_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def update_category(self, ticket_id: int, category: str) -> Optional[Ticket]:
        ticket = await self.get_by_id(ticket_id)
        if ticket is None:
            return None
        ticket.category = category
        ticket.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def update_title(self, ticket_id: int, title: str) -> Optional[Ticket]:
        ticket = await self.get_by_id(ticket_id)
        if ticket is None:
            return None
        ticket.title = title
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket


class MessageRepository:
    """消息 CRUD。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, ticket_id: int, role: str, content: str) -> Message:
        msg = Message(ticket_id=ticket_id, role=role, content=content)
        self.db.add(msg)
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def list_by_ticket(self, ticket_id: int) -> List[Message]:
        """获取某工单的全部消息（按时间正序）。"""
        result = await self.db.execute(
            select(Message)
            .where(Message.ticket_id == ticket_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_recent_context(self, ticket_id: int, limit: int = 10) -> List[Message]:
        """获取最近 N 条消息，用于构建上下文。"""
        result = await self.db.execute(
            select(Message)
            .where(Message.ticket_id == ticket_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # 恢复正序
        return messages
