"""本地中文嵌入：fastembed（轻量、无需 torch），首跑自动下载模型。"""
from functools import lru_cache
from backend.config import settings

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from fastembed import TextEmbedding
        _MODEL = TextEmbedding(model_name=settings.EMBEDDING_MODEL)
    return _MODEL


def embed(texts: list[str]) -> list[list[float]]:
    """批量嵌入，返回向量列表。"""
    if not texts:
        return []
    return list(_model().embed(texts))


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
