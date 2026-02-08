"""知识库数据访问层。"""
from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.db.models import KnowledgeDoc, VectorChunk, QAPair, DocStatus


class KnowledgeRepository:
    """知识库相关 CRUD 操作。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── KnowledgeDoc ─────────────────────────────────────

    async def create_doc(self, filename: str) -> KnowledgeDoc:
        doc = KnowledgeDoc(filename=filename, status=DocStatus.PROCESSING.value)
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        return doc

    async def get_doc(self, doc_id: int) -> Optional[KnowledgeDoc]:
        result = await self.db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_docs(self) -> List[KnowledgeDoc]:
        result = await self.db.execute(
            select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_doc_status(
        self, doc_id: int, status: str, chunk_count: int = 0, qa_count: int = 0,
        content: Optional[str] = None,
    ) -> Optional[KnowledgeDoc]:
        doc = await self.get_doc(doc_id)
        if doc is None:
            return None
        doc.status = status
        doc.chunk_count = chunk_count
        doc.qa_count = qa_count
        if content is not None:
            doc.content = content
        await self.db.flush()
        await self.db.refresh(doc)
        return doc

    async def delete_doc(self, doc_id: int) -> bool:
        """删除文档及其关联的 chunks 和 qa_pairs（级联删除）。"""
        doc = await self.get_doc(doc_id)
        if doc is None:
            return False
        await self.db.delete(doc)
        await self.db.flush()
        return True

    # ── VectorChunk ──────────────────────────────────────

    async def create_chunks(self, chunks: List[VectorChunk]) -> List[VectorChunk]:
        self.db.add_all(chunks)
        await self.db.flush()
        for chunk in chunks:
            await self.db.refresh(chunk)
        return chunks

    async def get_all_chunks(self) -> List[VectorChunk]:
        """获取所有有 embedding 的切片。"""
        result = await self.db.execute(
            select(VectorChunk).where(VectorChunk.embedding.isnot(None))
        )
        return list(result.scalars().all())

    # ── QAPair ───────────────────────────────────────────

    async def create_qa_pairs(self, pairs: List[QAPair]) -> List[QAPair]:
        self.db.add_all(pairs)
        await self.db.flush()
        for pair in pairs:
            await self.db.refresh(pair)
        return pairs

    async def get_all_qa_pairs(self) -> List[QAPair]:
        """获取所有有 embedding 的 QA 对。"""
        result = await self.db.execute(
            select(QAPair).where(QAPair.embedding.isnot(None))
        )
        return list(result.scalars().all())
