"""RAG 检索服务 — 供员工端对话和坐席端智能助手复用。"""
from __future__ import annotations

from typing import List, Tuple, Optional
import numpy as np

from pycore.core import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.repositories.knowledge import KnowledgeRepository
from backend.src.services.embedding import EmbeddingService, cosine_similarity

logger = get_logger()


class RAGSearchResult:
    """单条检索结果。"""

    def __init__(self, content: str, score: float, source_type: str, source_id: int):
        self.content = content
        self.score = score
        self.source_type = source_type  # "qa" 或 "chunk"
        self.source_id = source_id

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": self.score,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


class RAGSearchService:
    """
    RAG 检索服务。

    检索流程：
    1. 先在 QA 库检索，如果匹配度超过阈值则直接返回 QA 答案
    2. 否则在向量库检索 top_k 个相关切片
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qa_threshold: float = 0.85,
        vector_top_k: int = 3,
    ):
        self.embedding = embedding_service
        self.qa_threshold = qa_threshold
        self.vector_top_k = vector_top_k

    async def search(
        self, query: str, db: AsyncSession,
    ) -> Tuple[Optional[RAGSearchResult], List[RAGSearchResult]]:
        """
        检索知识库。

        返回:
            (qa_hit, chunk_hits)
            - qa_hit: 如果 QA 库命中（相似度 >= qa_threshold），返回最佳 QA 结果；否则 None
            - chunk_hits: 向量库 top_k 匹配的切片列表（按相似度降序）
        """
        repo = KnowledgeRepository(db)

        # 1. 向量化 query
        query_vec = await self.embedding.embed_single(query)

        # 2. 搜索 QA 库
        qa_pairs = await repo.get_all_qa_pairs()
        best_qa: Optional[RAGSearchResult] = None
        best_qa_score = 0.0

        for qa in qa_pairs:
            if qa.embedding is None:
                continue
            qa_vec = np.frombuffer(qa.embedding, dtype=np.float32)
            score = cosine_similarity(query_vec, qa_vec)
            if score > best_qa_score:
                best_qa_score = score
                best_qa = RAGSearchResult(
                    content=f"Q: {qa.question}\nA: {qa.answer}",
                    score=score,
                    source_type="qa",
                    source_id=qa.id,
                )

        # 如果 QA 命中且超过阈值，直接返回
        if best_qa and best_qa_score >= self.qa_threshold:
            logger.info("QA 库命中", score=best_qa_score, qa_id=best_qa.source_id)
            return best_qa, []

        # 3. 搜索向量库
        chunks = await repo.get_all_chunks()
        scored_chunks: List[Tuple[float, RAGSearchResult]] = []

        for chunk in chunks:
            if chunk.embedding is None:
                continue
            chunk_vec = np.frombuffer(chunk.embedding, dtype=np.float32)
            score = cosine_similarity(query_vec, chunk_vec)
            scored_chunks.append((
                score,
                RAGSearchResult(
                    content=chunk.content,
                    score=score,
                    source_type="chunk",
                    source_id=chunk.id,
                ),
            ))

        # 排序取 top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        chunk_hits = [r for _, r in scored_chunks[: self.vector_top_k]]

        if chunk_hits:
            logger.info(
                "向量库检索完成",
                top_score=chunk_hits[0].score,
                results_count=len(chunk_hits),
            )
        else:
            logger.info("知识库无匹配内容")

        return None, chunk_hits
