"""轻量向量库：余弦相似度检索，持久化到磁盘（pickle）。
不依赖外部向量数据库，启动零配置，适合中小规模知识库与比赛演示。"""
import logging
import os
import pickle
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.docs: list[dict] = []  # {id, text, source, meta}
        self.matrix: np.ndarray | None = None
        self.path: Path | None = None

    # ---------- 写入 ----------
    def add(self, items: list[dict], vectors: list[list[float]]):
        """items: [{text, source, meta}], vectors: 对应向量。"""
        start = len(self.docs)
        for i, it in enumerate(items):
            self.docs.append({"id": start + i, **it})
        mat = np.array(vectors, dtype=np.float32)
        if self.matrix is None:
            self.matrix = mat
        else:
            self.matrix = np.vstack([self.matrix, mat])
        self._normalize()

    def _normalize(self):
        if self.matrix is not None and self.matrix.size:
            norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1e-9
            self.matrix = self.matrix / norms

    # ---------- 检索 ----------
    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]:
        if self.matrix is None or self.matrix.size == 0:
            return []
        q = np.array(query_vec, dtype=np.float32)
        n = np.linalg.norm(q)
        if n > 0:
            q = q / n
        sims = self.matrix @ q
        idx = np.argsort(-sims)[:top_k]
        return [
            {**self.docs[int(i)], "score": round(float(sims[int(i)]), 4)}
            for i in idx
        ]

    @property
    def count(self) -> int:
        return len(self.docs)

    # ---------- 持久化 ----------
    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"docs": self.docs, "matrix": self.matrix}, f)
        os.replace(str(tmp), str(path))  # 原子替换

    @classmethod
    def load(cls, path):
        p = Path(path)
        store = cls()
        if p.exists():
            try:
                with open(p, "rb") as f:
                    data = pickle.load(f)
                store.docs = data.get("docs", [])
                store.matrix = data.get("matrix")
                store._normalize()
                store.path = p
            except Exception as exc:
                # 反序列化可抛异常类型无法穷举（格式错/截断/类移动/版本不兼容），
                # 目标是"任何失败都降级为空库不崩溃"。KeyboardInterrupt/SystemExit
                # 继承 BaseException，不会被本句捕获。
                logger.warning("向量库加载失败，降级为空库: %s", exc)
                store.docs = []
                store.matrix = None
        return store


def retrieve_context(store: VectorStore, query: str, top_k: int = 5) -> str:
    """端到端：把 query 嵌入后在库中检索，拼成带出处的上下文文本。"""
    from backend.embeddings import embed_one

    vec = embed_one(query)
    hits = store.search(vec, top_k=top_k)
    if not hits:
        return "（知识库暂无相关内容）"
    lines = []
    for h in hits:
        lines.append(f"[来源: {h['source']}]\n{h['text']}")
    return "\n\n".join(lines)
