"""知识库管理路由 — 上传、列表、删除。"""
from __future__ import annotations

from fastapi import Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.api import APIRouter, success_response, error_response
from pycore.core import get_logger

from backend.src.db.session import get_db
from backend.src.db.models import DocStatus
from backend.src.api.deps import get_current_user
from backend.src.repositories.knowledge import KnowledgeRepository
from backend.src.services.embedding import EmbeddingService
from backend.src.services.knowledge import KnowledgeProcessor

logger = get_logger()

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _get_settings():
    """延迟获取配置（避免循环导入）。"""
    from backend.src.main import settings
    return settings


def _build_processor(s) -> KnowledgeProcessor:
    """根据 settings 构建知识处理器。"""
    emb = s.embedding
    llm = s.llm
    ret = s.retrieval
    embedding_svc = EmbeddingService(
        api_key=emb.api_key,
        base_url=emb.base_url,
        model=emb.model,
        dimension=emb.dimension,
    )
    return KnowledgeProcessor(
        embedding_service=embedding_svc,
        llm_api_key=llm.api_key,
        llm_base_url=llm.base_url,
        llm_model=llm.model,
        chunk_size=ret.chunk_size,
        chunk_overlap=ret.chunk_overlap,
    )


# ── POST /api/knowledge/upload ───────────────────────────

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """上传 Markdown 文件，触发切片 + 向量化 + QA 生成。"""
    # 验证文件类型
    if not file.filename or not file.filename.endswith(".md"):
        resp, _ = error_response(
            error="仅支持 .md 格式文件",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )
        return resp

    # 读取内容
    raw = await file.read()
    content = raw.decode("utf-8", errors="ignore")

    if not content.strip():
        resp, _ = error_response(
            error="文件内容为空",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )
        return resp

    repo = KnowledgeRepository(db)

    # 创建文档记录（processing 状态）
    doc = await repo.create_doc(file.filename)
    await db.commit()

    # 异步处理：切片、向量化、QA 生成
    try:
        s = _get_settings()
        processor = _build_processor(s)

        vector_chunks, qa_pairs = await processor.process_document(doc.id, content)

        # 入库
        if vector_chunks:
            await repo.create_chunks(vector_chunks)
        if qa_pairs:
            await repo.create_qa_pairs(qa_pairs)

        # 更新文档状态
        await repo.update_doc_status(
            doc.id,
            status=DocStatus.READY.value,
            chunk_count=len(vector_chunks),
            qa_count=len(qa_pairs),
            content=content,
        )
        await db.commit()

        logger.info(
            "文档上传处理成功",
            doc_id=doc.id,
            filename=file.filename,
            chunks=len(vector_chunks),
            qa_pairs=len(qa_pairs),
        )

        return success_response(
            data={
                "doc_id": doc.id,
                "filename": file.filename,
                "status": DocStatus.READY.value,
                "chunk_count": len(vector_chunks),
                "qa_count": len(qa_pairs),
            },
            message="文档上传并处理成功",
        )

    except Exception as e:
        logger.error("文档处理失败", doc_id=doc.id, error=str(e))
        # 更新状态为失败
        await repo.update_doc_status(doc.id, status=DocStatus.FAILED.value)
        await db.commit()

        resp, _ = error_response(
            error=f"文档处理失败: {str(e)}",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
        return resp


# ── GET /api/knowledge/docs ──────────────────────────────

@router.get("/docs")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取所有知识文档列表。"""
    repo = KnowledgeRepository(db)
    docs = await repo.list_docs()
    data = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "qa_count": doc.qa_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in docs
    ]
    return success_response(data=data)


# ── DELETE /api/knowledge/docs/{doc_id} ──────────────────

@router.delete("/docs/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """删除知识文档及其关联数据。"""
    repo = KnowledgeRepository(db)
    deleted = await repo.delete_doc(doc_id)
    if not deleted:
        resp, _ = error_response(
            error="文档不存在",
            error_code="NOT_FOUND",
            status_code=404,
        )
        return resp

    await db.commit()
    logger.info("文档已删除", doc_id=doc_id)
    return success_response(message="文档已删除")
