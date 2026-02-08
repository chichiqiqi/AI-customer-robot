"""坐席端智能助手服务 — 意图识别 + RAG检索 + 推荐回复。"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from pycore.core import get_logger

from backend.src.services.rag import RAGSearchService

logger = get_logger()

# ── 提示词 ───────────────────────────────────────────────

INTENT_EXTRACT_PROMPT = """分析以下客服对话，识别用户的核心意图。
返回 JSON 格式：{{"intent": "意图标签(简短)", "confidence": 0.0到1.0之间的置信度, "keywords": ["关键词1", "关键词2"]}}
只返回 JSON，不要返回其他内容。

对话记录：
{conversation}"""

SUGGEST_REPLY_PROMPT = """你是一个专业的客服坐席助手。根据以下信息为坐席生成推荐回复。

用户意图：{intent}
知识库参考内容：
{context}

对话记录：
{conversation}

请生成一段专业、友好的客服回复。直接给出回复内容，不要包含"回复："等前缀。"""


class AgentAssistService:
    """
    坐席端智能助手。

    流程：
    1. 从对话记录中提取意图和关键词
    2. 用关键词进行 RAG 检索知识库
    3. 构造推荐回复
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str,
        llm_model: str,
        rag_service: RAGSearchService,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.llm = AsyncOpenAI(api_key=llm_api_key, base_url=llm_base_url)
        self.llm_model = llm_model
        self.rag = rag_service
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def _chat(self, system: str, user: str, temperature: Optional[float] = None) -> str:
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

    async def assist(
        self,
        messages: List[dict],
        db: AsyncSession,
    ) -> dict:
        """
        智能助手入口。

        参数:
            messages: 对话消息列表 [{"role": "user", "content": "..."}, ...]
            db: 数据库会话

        返回:
            {
                "intent": "意图标签",
                "confidence": 0.92,
                "keywords": ["关键词1", ...],
                "suggestion": "推荐回复文本",
                "sources": [{"content": "...", "score": 0.9, "source_type": "chunk"}]
            }
        """
        # 构建对话文本
        conversation_text = ""
        for msg in messages:
            role_label = {"user": "用户", "ai": "AI", "agent": "坐席"}.get(msg["role"], msg["role"])
            conversation_text += f"{role_label}: {msg['content']}\n"

        logger.info("坐席智能助手开始分析", message_count=len(messages))

        # 1. 意图识别
        intent_result = await self._extract_intent(conversation_text)
        intent = intent_result.get("intent", "未知")
        confidence = intent_result.get("confidence", 0.5)
        keywords = intent_result.get("keywords", [])

        logger.info("意图识别完成", intent=intent, confidence=confidence)

        # 2. RAG 检索 — 使用关键词拼接查询
        query = " ".join(keywords) if keywords else intent
        # 同时用用户最后一条消息作为补充
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        search_query = f"{query} {last_user_msg}".strip()

        qa_hit, chunk_hits = await self.rag.search(search_query, db)

        # 构建知识上下文
        context = ""
        sources = []

        if qa_hit and qa_hit.score >= self.rag.qa_threshold:
            context = qa_hit.content
            sources.append(qa_hit.to_dict())
        elif chunk_hits:
            context = "\n---\n".join([h.content for h in chunk_hits])
            sources = [h.to_dict() for h in chunk_hits]

        # 3. 生成推荐回复
        suggestion = await self._generate_suggestion(
            intent=intent,
            context=context or "暂无知识库相关内容",
            conversation=conversation_text,
        )

        logger.info("推荐回复生成完成", suggestion_length=len(suggestion))

        return {
            "intent": intent,
            "confidence": confidence,
            "keywords": keywords,
            "suggestion": suggestion,
            "sources": sources,
        }

    async def _extract_intent(self, conversation: str) -> dict:
        """从对话中提取意图。"""
        try:
            content = await self._chat(
                "你是客服对话分析专家，只返回 JSON。",
                INTENT_EXTRACT_PROMPT.format(conversation=conversation),
                temperature=0.1,
            )
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning("意图提取失败", error=str(e))
        return {"intent": "未知", "confidence": 0.5, "keywords": []}

    async def _generate_suggestion(self, intent: str, context: str, conversation: str) -> str:
        """生成推荐回复。"""
        try:
            return await self._chat(
                "你是专业的客服坐席助手。",
                SUGGEST_REPLY_PROMPT.format(
                    intent=intent,
                    context=context,
                    conversation=conversation,
                ),
            )
        except Exception as e:
            logger.warning("推荐回复生成失败", error=str(e))
            return "抱歉，智能助手暂时无法生成推荐回复。"
