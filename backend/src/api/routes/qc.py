"""质检路由。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.api import APIRouter, success_response, error_response
from pycore.core import get_logger

from backend.src.db.session import get_db
from backend.src.db.models import TicketStatus
from backend.src.api.deps import get_current_user
from backend.src.repositories.qc import QCResultRepository
from backend.src.repositories.ticket import TicketRepository, MessageRepository

logger = get_logger()

router = APIRouter(prefix="/api/qc", tags=["qc"])


# ── 请求/响应模型 ─────────────────────────────────────────

class QCScoreCreate(BaseModel):
    ticket_id: int
    accuracy_score: int = Field(..., ge=1, le=5, description="知识准确性 1-5")
    compliance_score: int = Field(..., ge=1, le=5, description="服务规范性 1-5")
    resolution_score: int = Field(..., ge=1, le=5, description="问题解决度 1-5")
    comment: Optional[str] = None


# ── 辅助函数 ─────────────────────────────────────────────

def _ticket_to_dict(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "user_id": t.user_id,
        "agent_id": t.agent_id,
        "category": t.category,
        "summary": t.summary,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }


def _qc_to_dict(qc) -> dict:
    return {
        "id": qc.id,
        "ticket_id": qc.ticket_id,
        "accuracy_score": qc.accuracy_score,
        "compliance_score": qc.compliance_score,
        "resolution_score": qc.resolution_score,
        "total_score": qc.total_score,
        "comment": qc.comment,
        "created_at": qc.created_at.isoformat() if qc.created_at else None,
    }


# ── GET /api/qc/tickets ──────────────────────────────────

@router.get("/tickets")
async def list_qc_tickets(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取可质检的工单列表（closed + reviewed）。"""
    qc_repo = QCResultRepository(db)
    tickets = await qc_repo.list_qc_tickets()

    # 附加每个工单是否已质检
    result = []
    for t in tickets:
        td = _ticket_to_dict(t)
        td["has_qc"] = t.status == TicketStatus.REVIEWED.value
        result.append(td)

    return success_response(data=result)


# ── POST /api/qc/results ─────────────────────────────────

@router.post("/results")
async def submit_qc_result(
    req: QCScoreCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """提交质检评分。"""
    ticket_repo = TicketRepository(db)
    qc_repo = QCResultRepository(db)

    # 验证工单
    ticket = await ticket_repo.get_by_id(req.ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp

    if ticket.status != TicketStatus.CLOSED.value:
        resp, _ = error_response(
            error="仅已完结(closed)工单可提交质检",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )
        return resp

    # 检查是否已质检
    if await qc_repo.exists_for_ticket(req.ticket_id):
        resp, _ = error_response(
            error="该工单已质检，不可重复提交",
            error_code="CONFLICT",
            status_code=409,
        )
        return resp

    # 创建质检结果
    qc = await qc_repo.create(
        ticket_id=req.ticket_id,
        accuracy_score=req.accuracy_score,
        compliance_score=req.compliance_score,
        resolution_score=req.resolution_score,
        comment=req.comment,
    )

    # 更新工单状态 → reviewed
    await ticket_repo.update_status(req.ticket_id, TicketStatus.REVIEWED.value)
    await db.commit()

    logger.info("质检评分提交成功", ticket_id=req.ticket_id, total=qc.total_score)
    return success_response(data=_qc_to_dict(qc), message="质检评分已提交")


# ── GET /api/qc/results/{ticket_id} ──────────────────────

@router.get("/results/{ticket_id}")
async def get_qc_result(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取某工单的质检结果。"""
    qc_repo = QCResultRepository(db)
    qc = await qc_repo.get_by_ticket_id(ticket_id)
    if qc is None:
        return success_response(data=None, message="暂无质检结果")
    return success_response(data=_qc_to_dict(qc))
