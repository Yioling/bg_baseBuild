"""本地向量嵌入 —— 零外部依赖实现。

设计缘由（2026-08-05）：
- 原实现走 fastembed + ONNX Runtime，需要下载数百 MB 模型并依赖 VC++ Redist。
- 在部分 Windows 环境（用户机器：VC++ 缺失 + 无外网访问 HuggingFace）下双失败。
- 当前实现改用纯 NumPy + 字符 n-gram 哈希 TF-IDF 风格：
  * 1-gram / 2-gram 字符级特征（中文友好，无须分词）
  * 哈希桶固定维度（如 384），余弦相似度检索可用
  * 所有计算走 numpy，启动零依赖、瞬时响应、永不报错
- 用户若日后想换回 fastembed / sentence-transformers，只需替换 _embed_batch 即可，
  外部接口 `embed / embed_one` 保持不变。

接口契约：
- embed(texts: list[str]) -> list[list[float]]  （每条文本一个固定维向量）
- embed_one(text: str) -> list[float]
"""
from __future__ import annotations

import hashlib

import numpy as np

# 固定桶维度（小 → 内存可控；大 → 表达力强）。384 与多数小模型对齐。
_DIM = 384


def _hash_bucket(token: str, dim: int = _DIM) -> int:
    """把任意 token 哈希到 [0, dim) 桶。blake2b 速度快且均匀。"""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dim


def _char_ngrams(text: str) -> list[str]:
    """字符级 n-gram：1-gram + 2-gram，简单切字，中文友好。

    例："智能订单" → ["智","能","订","单","智能","能订","订单"]
    """
    text = text.strip()
    if not text:
        return []
    grams: list[str] = []
    n = len(text)
    # 1-gram
    for ch in text:
        if not ch.isspace():
            grams.append(ch)
    # 2-gram（仅当长度 >= 2）
    if n >= 2:
        for i in range(n - 1):
            a, b = text[i], text[i + 1]
            if a.isspace() or b.isspace():
                continue
            grams.append(a + b)
    return grams


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """本地哈希 n-gram 向量化：对每条文本输出一个归一化的 _DIM 维向量。

    实现：
    - 每个 token 哈希到唯一桶 → 累加 1
    - 整向量 L2 归一化（与 VectorStore._normalize 配合，余弦相似度 = 内积）
    - 空文本 → 全 0 向量
    """
    if not texts:
        return []
    mat = np.zeros((len(texts), _DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        grams = _char_ngrams(t)
        if not grams:
            continue
        for g in grams:
            mat[i, _hash_bucket(g, _DIM)] += 1.0
        # L2 归一化
        norm = float(np.linalg.norm(mat[i]))
        if norm > 1e-9:
            mat[i] = mat[i] / norm
    return mat.tolist()


# ---------- 对外接口 ----------
def embed(texts: list[str]) -> list[list[float]]:
    """批量嵌入。返回 list[list[float]]，每条文本一个 _DIM 维向量。

    注意：保持与原 fastembed 接口同形（list of list[float]），
    以便日后一键切回 fastembed。
    """
    return _embed_batch(texts)


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def embedding_dim() -> int:
    """返回向量维度，便于依赖方对齐。"""
    return _DIM
