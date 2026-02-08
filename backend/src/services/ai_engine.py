"""AI 对话引擎 — 意图识别 + Query 改写 + RAG 检索 + 模型问答。"""
from __future__ import annotations

import json
import re
from typing import Optional, List

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from pycore.core import get_logger

from backend.src.services.embedding import EmbeddingService
from backend.src.services.rag import RAGSearchService

logger = get_logger()


# ── 提示词 ───────────────────────────────────────────────

INTENT_DETECTION_PROMPT = """分析用户问题的意图是否清晰。如果问题模糊、缺少关键信息，返回 {{"clear": false, "reason": "缺少的信息"}}
如果问题清晰明确，返回 {{"clear": true}}
只返回 JSON，不要返回其他内容。
用户问题：{query}"""

QUERY_REWRITE_PROMPT = """将用户问题改写为适合知识库检索的简洁表达，保留关键实体与意图。
只返回改写后的查询文本，不要返回其他内容。
用户问题：{query}
改写结果："""

CLARIFICATION_PROMPT = """用户的问题不够清晰：{query}
缺少的信息：{reason}
请生成一个友好的反问，引导用户提供更多细节。只返回反问内容，不要返回其他信息。"""

RAG_RESPONSE_PROMPT = """基于以下知识库内容回答用户问题。

知识库内容：
{context}

对话历史：
{history}

用户问题：{query}

请提供准确、有帮助的回答。如果知识库内容不足以回答，请如实说明并尽力给出建议。"""

NO_CONTEXT_PROMPT = """你是一个智能客服助手。用户问了以下问题，但知识库中暂未找到相关信息。

对话历史：
{history}

用户问题：{query}

请尽力给出有帮助的回答，并提示用户如果问题未能解决可以转接人工客服。"""


class AIEngine:
    """
    AI 对话引擎。

    完整 RAG 流程：
    1. 意图识别 — 判断用户 Query 是否清晰
    2. Query 改写 — 清晰问题改写为检索友好表达
    3. 知识库检索 — QA 库 + 向量库双路检索
    4. 模型问答 — 拼接上下文调用 LLM 生成回复
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str,
        llm_model: str,
        embedding_service: EmbeddingService,
        rag_service: RAGSearchService,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.llm = AsyncOpenAI(api_key=llm_api_key, base_url=llm_base_url)
        self.llm_model = llm_model
        self.embedding = embedding_service
        self.rag = rag_service
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def _chat(self, system: str, user: str, temperature: Optional[float] = None) -> str:
        """通用 LLM 调用。"""
        response = await self.llm.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content.strip()

    # ── Step 1: 意图识别 ──────────────────────────────────

    async def detect_intent(self, query: str) -> dict:
        """
        分析用户问题是否清晰。
        返回: {"clear": True/False, "reason": "..."}
        """
        try:
            content = await self._chat(
                "你是意图分析专家，只返回 JSON。",
                INTENT_DETECTION_PROMPT.format(query=query),
                temperature=0.1,
            )
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except Exception as e:
            logger.warning("意图识别失败，默认为清晰", error=str(e))
        return {"clear": True}

    # ── Step 2: Query 改写 ────────────────────────────────

    async def rewrite_query(self, query: str) -> str:
        """将用户问题改写为适合检索的表达。"""
        try:
            rewritten = await self._chat(
                "你是查询改写专家，只返回改写后的文本。",
                QUERY_REWRITE_PROMPT.format(query=query),
                temperature=0.1,
            )
            # 去掉可能的引号
            rewritten = rewritten.strip('"\'')
            if rewritten and len(rewritten) > 2:
                return rewritten
        except Exception as e:
            logger.warning("Query 改写失败，使用原始 query", error=str(e))
        return query

    # ── Step 3: 生成引导反问 ──────────────────────────────

    async def generate_clarification(self, query: str, reason: str) -> str:
        """当意图不清晰时，生成引导用户的反问。"""
        try:
            return await self._chat(
                "你是友好的客服助手。",
                CLARIFICATION_PROMPT.format(query=query, reason=reason),
                temperature=0.5,
            )
        except Exception as e:
            logger.warning("生成反问失败", error=str(e))
            return "您的问题我还不太明确，能否提供更多细节呢？"

    # ── Step 4: 完整 RAG 对话 ─────────────────────────────

    async def process_query(
        self,
        query: str,
        db: AsyncSession,
        history_messages: Optional[List[dict]] = None,
    ) -> str:
        """
        完整 RAG 流程：意图识别 → 改写 → 检索 → 生成回复。

        参数:
            query: 用户原始问题
            db: 数据库会话（用于 RAG 检索）
            history_messages: 对话历史 [{"role": "user", "content": "..."}, ...]

        返回: AI 回复文本
        """
        # 构建历史上下文
        history_text = ""
        if history_messages:
            for msg in history_messages[-6:]:  # 最近 6 条
                role_label = {"user": "用户", "ai": "AI", "agent": "坐席"}.get(msg["role"], msg["role"])
                history_text += f"{role_label}: {msg['content']}\n"

        logger.info("AI 引擎处理开始", query=query)

        # 1. 意图识别
        intent = await self.detect_intent(query)
        logger.info("意图识别结果", clear=intent.get("clear"), reason=intent.get("reason"))

        if not intent.get("clear", True):
            # 意图不清晰 → 生成引导反问
            reason = intent.get("reason", "信息不足")
            clarification = await self.generate_clarification(query, reason)
            logger.info("触发引导反问", reason=reason)
            return clarification

        # 2. Query 改写
        rewritten_query = await self.rewrite_query(query)
        logger.info("Query 改写完成", original=query, rewritten=rewritten_query)

        # 3. RAG 检索
        qa_hit, chunk_hits = await self.rag.search(rewritten_query, db)

        if qa_hit and qa_hit.score >= self.rag.qa_threshold:
            # QA 直接命中
            context = qa_hit.content
            logger.info("QA 库直接命中", score=qa_hit.score)
        elif chunk_hits:
            # 向量库命中
            context = "\n---\n".join([hit.content for hit in chunk_hits])
            logger.info("向量库命中", count=len(chunk_hits), top_score=chunk_hits[0].score)
        else:
            context = ""

        # 4. 生成回复
        if context:
            reply = await self._chat(
                "你是一个专业、友好的智能客服助手。",
                RAG_RESPONSE_PROMPT.format(
                    context=context,
                    history=history_text or "无历史对话",
                    query=query,
                ),
            )
        else:
            reply = await self._chat(
                "你是一个专业、友好的智能客服助手。",
                NO_CONTEXT_PROMPT.format(
                    history=history_text or "无历史对话",
                    query=query,
                ),
            )
            logger.info("知识库无匹配，使用通用回复")

        logger.info("AI 回复生成完成", reply_length=len(reply))
        return reply
