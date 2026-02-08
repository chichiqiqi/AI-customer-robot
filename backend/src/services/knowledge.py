"""知识库处理服务 — 切片、向量化、QA 生成。"""
from __future__ import annotations

import json
import re
from typing import List, Tuple

import numpy as np
from openai import AsyncOpenAI
from pycore.core import get_logger

from backend.src.db.models import VectorChunk, QAPair
from backend.src.services.embedding import EmbeddingService

logger = get_logger()


# ── 文本切片 ──────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """
    将长文本按字符长度切片，支持 overlap。
    优先在换行符处分割以保持语义完整性。
    """
    if not text or not text.strip():
        return []

    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text.strip())
    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 如果当前 chunk 加上新段落超过限制，先保存当前 chunk
        if current_chunk and len(current_chunk) + len(para) + 1 > chunk_size:
            chunks.append(current_chunk.strip())
            # overlap: 取当前 chunk 末尾部分作为下一个 chunk 的开头
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                current_chunk = current_chunk[-chunk_overlap:] + "\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = (current_chunk + "\n" + para).strip() if current_chunk else para

    # 最后一个 chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # 对于超长单段落进行强制分割
    final_chunks: List[str] = []
    for chunk in chunks:
        if len(chunk) <= chunk_size:
            final_chunks.append(chunk)
        else:
            for i in range(0, len(chunk), chunk_size - chunk_overlap):
                piece = chunk[i : i + chunk_size]
                if piece.strip():
                    final_chunks.append(piece.strip())

    return final_chunks


# ── QA 自动生成 ───────────────────────────────────────────

QA_GENERATION_PROMPT = """你是一个知识库 QA 专家。请根据以下文本内容，生成 2-5 个高质量的问答对。

要求：
1. 问题应该是用户可能会问的实际问题
2. 答案应准确、简洁，基于原文内容
3. 严格返回 JSON 数组格式，不要返回其他内容

返回格式：
[
  {{"question": "问题1", "answer": "答案1"}},
  {{"question": "问题2", "answer": "答案2"}}
]

文本内容：
{text}"""


async def generate_qa_pairs(
    text: str,
    llm_client: AsyncOpenAI,
    llm_model: str,
) -> List[Tuple[str, str]]:
    """
    调用 LLM 根据文本自动生成 QA 对。
    返回: [(question, answer), ...]
    """
    if not text or len(text.strip()) < 20:
        return []

    try:
        response = await llm_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "你是一个知识库 QA 专家，只返回 JSON 数组。"},
                {"role": "user", "content": QA_GENERATION_PROMPT.format(text=text[:2000])},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        content = response.choices[0].message.content.strip()
        logger.debug("LLM QA 原始回复", content=content[:500])

        # 尝试从回复中提取 JSON 数组
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            raw_json = json_match.group()
            parsed = json.loads(raw_json)
            result = []
            if isinstance(parsed, list):
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    q = str(item.get("question", "") or "").strip()
                    a = str(item.get("answer", "") or "").strip()
                    if q and a:
                        result.append((q, a))
            logger.info("QA 解析完成", count=len(result))
            return result
        else:
            logger.warning("QA 生成结果无法解析为 JSON", raw_content=content[:200])
            return []
    except json.JSONDecodeError as e:
        logger.warning("QA JSON 解析失败", error=str(e))
        return []
    except Exception as e:
        import traceback
        logger.error("QA 生成失败\n" + traceback.format_exc())
        return []


# ── 知识处理编排 ──────────────────────────────────────────

class KnowledgeProcessor:
    """编排知识文档的切片、向量化、QA 生成全流程。"""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_api_key: str,
        llm_base_url: str,
        llm_model: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.embedding = embedding_service
        self.llm_client = AsyncOpenAI(api_key=llm_api_key, base_url=llm_base_url)
        self.llm_model = llm_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def process_document(
        self, doc_id: int, content: str,
    ) -> Tuple[List[VectorChunk], List[QAPair]]:
        """
        处理一个文档：切片 → 向量化 → QA 生成 → 返回待入库的对象列表。
        """
        # 1. 切片
        chunk_texts = chunk_text(content, self.chunk_size, self.chunk_overlap)
        logger.info("文档切片完成", doc_id=doc_id, chunk_count=len(chunk_texts))

        if not chunk_texts:
            return [], []

        # 2. 向量化切片
        chunk_embeddings = await self.embedding.embed_texts(chunk_texts)
        vector_chunks: List[VectorChunk] = []
        for idx, (text, emb) in enumerate(zip(chunk_texts, chunk_embeddings)):
            vc = VectorChunk(
                doc_id=doc_id,
                content=text,
                embedding=emb.tobytes(),
                chunk_index=idx,
            )
            vector_chunks.append(vc)

        # 3. 生成 QA 对（对每个切片生成）
        all_qa_pairs: List[QAPair] = []
        for text in chunk_texts:
            pairs = await generate_qa_pairs(text, self.llm_client, self.llm_model)
            for q, a in pairs:
                qa = QAPair(doc_id=doc_id, question=q, answer=a)
                all_qa_pairs.append(qa)

        # 4. 向量化 QA 的 question
        if all_qa_pairs:
            questions = [qa.question for qa in all_qa_pairs]
            qa_embeddings = await self.embedding.embed_texts(questions)
            for qa, emb in zip(all_qa_pairs, qa_embeddings):
                qa.embedding = emb.tobytes()

        logger.info(
            "文档处理完成",
            doc_id=doc_id,
            chunks=len(vector_chunks),
            qa_pairs=len(all_qa_pairs),
        )
        return vector_chunks, all_qa_pairs
