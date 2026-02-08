"""质检结果数据访问层。"""
from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.models import QCResult, Ticket, TicketStatus


class QCResultRepository:
    """质检结果 CRUD。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        ticket_id: int,
        accuracy_score: int,
        compliance_score: int,
        resolution_score: int,
        comment: Optional[str] = None,
    ) -> QCResult:
        total = round((accuracy_score + compliance_score + resolution_score) / 3, 2)
        qc = QCResult(
            ticket_id=ticket_id,
            accuracy_score=accuracy_score,
            compliance_score=compliance_score,
            resolution_score=resolution_score,
            total_score=total,
            comment=comment,
        )
        self.db.add(qc)
        await self.db.flush()
        await self.db.refresh(qc)
        return qc

    async def get_by_ticket_id(self, ticket_id: int) -> Optional[QCResult]:
        result = await self.db.execute(
            select(QCResult).where(QCResult.ticket_id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def exists_for_ticket(self, ticket_id: int) -> bool:
        qc = await self.get_by_ticket_id(ticket_id)
        return qc is not None

    async def list_qc_tickets(self) -> List[Ticket]:
        """获取可质检的工单（closed + reviewed 状态）。"""
        result = await self.db.execute(
            select(Ticket)
            .where(Ticket.status.in_([TicketStatus.CLOSED.value, TicketStatus.REVIEWED.value]))
            .order_by(Ticket.updated_at.desc())
        )
        return list(result.scalars().all())
