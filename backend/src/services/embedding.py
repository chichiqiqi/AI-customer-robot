"""Embedding 服务 — 调用 Qwen text-embedding API 进行向量化。"""
from __future__ import annotations

import numpy as np
from typing import List
from openai import AsyncOpenAI
from pycore.core import get_logger

logger = get_logger()


class EmbeddingService:
    """封装 Embedding 模型调用。"""

    def __init__(self, api_key: str, base_url: str, model: str, dimension: int = 1536):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimension = dimension

    async def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        批量向量化文本。
        返回: list[numpy.ndarray]，每个 ndarray 维度为 (dimension,)。
        """
        if not texts:
            return []

        # OpenAI compatible API: 一次最多传入 batch
        batch_size = 20
        all_embeddings: List[np.ndarray] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                for item in response.data:
                    vec = np.array(item.embedding, dtype=np.float32)
                    all_embeddings.append(vec)
            except Exception as e:
                logger.error("Embedding API 调用失败", error=str(e), batch_index=i)
                # 填充零向量作为降级
                for _ in batch:
                    all_embeddings.append(np.zeros(self.dimension, dtype=np.float32))

        return all_embeddings

    async def embed_single(self, text: str) -> np.ndarray:
        """单条文本向量化。"""
        results = await self.embed_texts([text])
        return results[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度。"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
