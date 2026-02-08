"""工单与消息路由 — 员工端 + 坐席端共用。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.api import APIRouter, success_response, error_response
from pycore.core import get_logger

from backend.src.db.session import get_db
from backend.src.db.models import TicketStatus, MessageRole
from backend.src.api.deps import get_current_user
from backend.src.repositories.ticket import TicketRepository, MessageRepository

logger = get_logger()

router = APIRouter(prefix="/api", tags=["tickets"])


# ── 请求模型 ─────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: str = "新对话"

class SendMessageRequest(BaseModel):
    ticket_id: int
    content: str
    sender_type: str = "user"  # user / agent

class UpdateCategoryRequest(BaseModel):
    category: str


# ── 辅助函数 ─────────────────────────────────────────────

def _get_settings():
    from backend.src.main import settings
    return settings


def _build_agent_assist():
    """延迟构建坐席智能助手。"""
    from backend.src.services.embedding import EmbeddingService
    from backend.src.services.rag import RAGSearchService
    from backend.src.services.agent_assist import AgentAssistService

    s = _get_settings()
    emb_svc = EmbeddingService(
        api_key=s.embedding.api_key,
        base_url=s.embedding.base_url,
        model=s.embedding.model,
        dimension=s.embedding.dimension,
    )
    rag_svc = RAGSearchService(
        embedding_service=emb_svc,
        qa_threshold=s.retrieval.qa_threshold,
        vector_top_k=s.retrieval.vector_top_k,
    )
    return AgentAssistService(
        llm_api_key=s.llm.api_key,
        llm_base_url=s.llm.base_url,
        llm_model=s.llm.model,
        rag_service=rag_svc,
        temperature=s.llm.temperature,
        max_tokens=s.llm.max_tokens,
    )


def _build_ai_engine():
    """延迟构建 AI 引擎，避免循环导入。"""
    from backend.src.services.embedding import EmbeddingService
    from backend.src.services.rag import RAGSearchService
    from backend.src.services.ai_engine import AIEngine

    s = _get_settings()
    emb_svc = EmbeddingService(
        api_key=s.embedding.api_key,
        base_url=s.embedding.base_url,
        model=s.embedding.model,
        dimension=s.embedding.dimension,
    )
    rag_svc = RAGSearchService(
        embedding_service=emb_svc,
        qa_threshold=s.retrieval.qa_threshold,
        vector_top_k=s.retrieval.vector_top_k,
    )
    return AIEngine(
        llm_api_key=s.llm.api_key,
        llm_base_url=s.llm.base_url,
        llm_model=s.llm.model,
        embedding_service=emb_svc,
        rag_service=rag_svc,
        temperature=s.llm.temperature,
        max_tokens=s.llm.max_tokens,
    )


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


def _message_to_dict(m) -> dict:
    return {
        "id": m.id,
        "ticket_id": m.ticket_id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ── GET /api/tickets ─────────────────────────────────────

@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取工单列表。status 可逗号分隔传多个值。"""
    repo = TicketRepository(db)
    if status:
        statuses = [s.strip() for s in status.split(",")]
        tickets = await repo.list_by_status(*statuses)
    else:
        tickets = await repo.list_by_user(user.id)
    return success_response(data=[_ticket_to_dict(t) for t in tickets])


# ── POST /api/tickets ────────────────────────────────────

@router.post("/tickets")
async def create_ticket(
    req: CreateTicketRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """创建新工单（对话）。"""
    repo = TicketRepository(db)
    ticket = await repo.create(user.id, req.title)
    await db.commit()
    return success_response(data=_ticket_to_dict(ticket), message="工单创建成功")


# ── GET /api/tickets/{id}/messages ───────────────────────

@router.get("/tickets/{ticket_id}/messages")
async def get_messages(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取工单消息列表。"""
    msg_repo = MessageRepository(db)
    messages = await msg_repo.list_by_ticket(ticket_id)
    return success_response(data=[_message_to_dict(m) for m in messages])


# ── POST /api/messages ───────────────────────────────────

@router.post("/messages")
async def send_message(
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    发送消息。
    - sender_type=user → 员工发送，自动触发 AI 回复（返回 user_msg + ai_msg）
    - sender_type=agent → 坐席发送，不触发 AI（返回 message）
    """
    ticket_repo = TicketRepository(db)
    msg_repo = MessageRepository(db)

    # 验证工单
    ticket = await ticket_repo.get_by_id(req.ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp

    # ---------- 坐席发送 ----------
    if req.sender_type == "agent":
        if ticket.status not in (TicketStatus.HANDLING.value,):
            resp, _ = error_response(
                error="仅处理中的工单允许坐席回复",
                error_code="VALIDATION_ERROR",
                status_code=400,
            )
            return resp
        agent_msg = await msg_repo.create(req.ticket_id, MessageRole.AGENT.value, req.content)
        await db.commit()
        return success_response(data=_message_to_dict(agent_msg), message="坐席消息已发送")

    # ---------- 员工在人工处理中发送（不触发 AI） ----------
    if req.sender_type == "employee":
        if ticket.status not in (TicketStatus.HANDLING.value,):
            resp, _ = error_response(
                error="仅坐席处理中的工单允许此方式发送",
                error_code="VALIDATION_ERROR",
                status_code=400,
            )
            return resp
        user_msg = await msg_repo.create(req.ticket_id, MessageRole.USER.value, req.content)
        await db.commit()
        return success_response(data=_message_to_dict(user_msg), message="消息已发送")

    # ---------- 员工发送（AI对话中，触发AI回复） ----------
    if ticket.status not in (TicketStatus.CHATTING.value,):
        resp, _ = error_response(
            error="当前工单状态不允许发送消息",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )
        return resp

    # 保存用户消息
    user_msg = await msg_repo.create(req.ticket_id, MessageRole.USER.value, req.content)

    # 自动更新工单标题（首条消息）
    existing = await msg_repo.list_by_ticket(req.ticket_id)
    if len(existing) <= 1:
        title = req.content[:50] + ("..." if len(req.content) > 50 else "")
        await ticket_repo.update_title(req.ticket_id, title)

    # 构建对话历史
    recent = await msg_repo.get_recent_context(req.ticket_id, limit=10)
    history = [{"role": m.role, "content": m.content} for m in recent]

    # 调用 AI 引擎
    try:
        engine = _build_ai_engine()
        ai_reply = await engine.process_query(req.content, db, history)
    except Exception as e:
        logger.error("AI 引擎调用失败", error=str(e))
        ai_reply = "抱歉，AI 服务暂时不可用，请稍后重试或转接人工客服。"

    # 保存 AI 消息
    ai_msg = await msg_repo.create(req.ticket_id, MessageRole.AI.value, ai_reply)
    await db.commit()

    return success_response(data={
        "user_msg": _message_to_dict(user_msg),
        "ai_msg": _message_to_dict(ai_msg),
    })


# ── POST /api/tickets/{id}/transfer ─────────────────────

@router.post("/tickets/{ticket_id}/transfer")
async def transfer_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """转接人工：status → pending。"""
    repo = TicketRepository(db)
    msg_repo = MessageRepository(db)

    ticket = await repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp
    if ticket.status not in (TicketStatus.CHATTING.value,):
        resp, _ = error_response(error="当前状态无法转人工", error_code="VALIDATION_ERROR", status_code=400)
        return resp

    ticket = await repo.update_status(ticket_id, TicketStatus.PENDING.value)

    # 插入系统提示消息
    await msg_repo.create(ticket_id, MessageRole.AI.value, "已转接人工客服，请等待坐席接入...")
    await db.commit()

    return success_response(data=_ticket_to_dict(ticket), message="已转接人工")


# ── POST /api/tickets/{id}/resolve ───────────────────────

@router.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """标记 AI 已解决：status → resolved。"""
    repo = TicketRepository(db)

    ticket = await repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp
    if ticket.status not in (TicketStatus.CHATTING.value,):
        resp, _ = error_response(error="当前状态无法标记已解决", error_code="VALIDATION_ERROR", status_code=400)
        return resp

    ticket = await repo.update_status(ticket_id, TicketStatus.RESOLVED.value)
    await db.commit()

    return success_response(data=_ticket_to_dict(ticket), message="已标记为 AI 解决")


# ═══════════════════════════════════════════════════════════
#  以下为 Phase 4 — 坐席端新增路由
# ═══════════════════════════════════════════════════════════


# ── POST /api/tickets/{id}/accept ─────────────────────────

@router.post("/tickets/{ticket_id}/accept")
async def accept_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """坐席接单：pending → handling，绑定 agent_id。"""
    repo = TicketRepository(db)

    ticket = await repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp
    if ticket.status != TicketStatus.PENDING.value:
        resp, _ = error_response(error="仅待处理工单可接单", error_code="VALIDATION_ERROR", status_code=400)
        return resp

    ticket = await repo.update_status(ticket_id, TicketStatus.HANDLING.value, agent_id=user.id)
    await db.commit()

    return success_response(data=_ticket_to_dict(ticket), message="接单成功")


# ── POST /api/tickets/{id}/close ──────────────────────────

@router.post("/tickets/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """坐席结束工单：handling → closed。"""
    repo = TicketRepository(db)
    msg_repo = MessageRepository(db)

    ticket = await repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp
    if ticket.status != TicketStatus.HANDLING.value:
        resp, _ = error_response(error="仅处理中工单可结束", error_code="VALIDATION_ERROR", status_code=400)
        return resp

    ticket = await repo.update_status(ticket_id, TicketStatus.CLOSED.value)

    # 插入系统提示
    await msg_repo.create(ticket_id, MessageRole.AI.value, "工单已由坐席关闭。")
    await db.commit()

    return success_response(data=_ticket_to_dict(ticket), message="工单已结束")


# ── POST /api/tickets/{id}/assist ─────────────────────────

@router.post("/tickets/{ticket_id}/assist")
async def ticket_assist(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    坐席智能助手：分析对话意图 + RAG 检索 + 推荐回复。
    返回: { intent, confidence, keywords, suggestion, sources }
    """
    ticket_repo = TicketRepository(db)
    msg_repo = MessageRepository(db)

    ticket = await ticket_repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp

    messages = await msg_repo.list_by_ticket(ticket_id)
    if not messages:
        resp, _ = error_response(error="工单暂无消息", error_code="VALIDATION_ERROR", status_code=400)
        return resp

    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

    try:
        assist_svc = _build_agent_assist()
        result = await assist_svc.assist(msg_dicts, db)
    except Exception as e:
        logger.error("智能助手调用失败", error=str(e))
        result = {
            "intent": "分析失败",
            "confidence": 0.0,
            "keywords": [],
            "suggestion": "智能助手暂时不可用，请手动回复。",
            "sources": [],
        }

    return success_response(data=result)


# ── PATCH /api/tickets/{id}/category ──────────────────────

@router.patch("/tickets/{ticket_id}/category")
async def update_ticket_category(
    ticket_id: int,
    req: UpdateCategoryRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """更新工单分类。"""
    repo = TicketRepository(db)

    ticket = await repo.get_by_id(ticket_id)
    if ticket is None:
        resp, _ = error_response(error="工单不存在", error_code="NOT_FOUND", status_code=404)
        return resp

    ticket = await repo.update_category(ticket_id, req.category)
    await db.commit()

    return success_response(data=_ticket_to_dict(ticket), message="分类已更新")
