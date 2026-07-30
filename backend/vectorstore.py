"""轻量向量库：余弦相似度检索，持久化到磁盘（pickle）。
不依赖外部向量数据库，启动零配置，适合中小规模知识库与比赛演示。

特性：
- 余弦相似度（L2 归一化后点积）
- pickle 原子写入持久化
- 线程安全读写锁
- 损坏文件自动恢复（空库降级）
"""
import pickle
import threading
import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """自研轻量向量库：add / search / query / save / load。"""

    def __init__(self):
        self.docs: list[dict] = []  # {id, text, source, meta}
        self.matrix: np.ndarray | None = None
        self.path: Path | None = None
        self._lock = threading.Lock()

    # ---------- 属性 ----------
    @property
    def count(self) -> int:
        return len(self.docs)

    @property
    def is_empty(self) -> bool:
        return len(self.docs) == 0

    def __len__(self) -> int:
        return len(self.docs)

    # ---------- 写入 ----------
    def add(self, items: list[dict], vectors: list[list[float]]):
        """批量添加文本块及其嵌入向量。

        Args:
            items: [{text, source, meta}, ...]
            vectors: 对应嵌入向量列表，长度必须与 items 一致

        Raises:
            ValueError: items 与 vectors 数量不匹配
        """
        if not items:
            return
        if len(items) != len(vectors):
            raise ValueError(
                f"items 与 vectors 数量不匹配: {len(items)} vs {len(vectors)}"
            )

        with self._lock:
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
        """L2 归一化所有向量，使点积等价于余弦相似度。"""
        if self.matrix is not None and self.matrix.size:
            norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1e-9
            self.matrix = self.matrix / norms

    # ---------- 检索 ----------
    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]:
        """给定查询向量，返回 top_k 最相似文档（含 score 字段）。"""
        with self._lock:
            if self.matrix is None or self.matrix.size == 0:
                return []
            q = np.array(query_vec, dtype=np.float32)
            n = np.linalg.norm(q)
            if n > 0:
                q = q / n
            sims = self.matrix @ q
            k = min(top_k, len(self.docs))
            idx = np.argsort(-sims)[:k]
            return [
                {**self.docs[int(i)], "score": round(float(sims[int(i)]), 4)}
                for i in idx
            ]

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        """端到端查询：输入自然语言文本，自动嵌入后检索。

        等价于 embed_one(text) → search(vec, top_k)，
        是 search() 的上层便利方法。
        """
        if not self.docs:
            return []
        from backend.embeddings import embed_one
        vec = embed_one(text)
        return self.search(vec, top_k=top_k)

    # ---------- 持久化 ----------
    def save(self, path):
        """原子写入：先写临时文件，成功后再替换，防止中途崩溃损坏数据。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with self._lock:
            data = {"docs": self.docs, "matrix": self.matrix}

        try:
            with open(tmp_path, "wb") as f:
                pickle.dump(data, f)
            tmp_path.replace(path)  # 原子替换（Windows 上也支持）
            self.path = path
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path):
        """从磁盘加载向量库。文件不存在或损坏时返回空库（不抛异常）。"""
        p = Path(path)
        store = cls()
        if not p.exists():
            store.path = p
            return store
        try:
            with open(p, "rb") as f:
                data = pickle.load(f)
            store.docs = data.get("docs", [])
            store.matrix = data.get("matrix")
            store._normalize()
            store.path = p
        except (pickle.UnpicklingError, EOFError, KeyError, ValueError) as e:
            logger.warning("向量库文件损坏，使用空库替代: %s", e)
            # 损坏文件保留不删，下次 save 时自动覆盖
            store.path = p
        return store


def retrieve_context(store: VectorStore, query: str, top_k: int = 5) -> str:
    """端到端：把 query 嵌入后在库中检索，拼成带出处的上下文文本。

    保留此函数以向后兼容 tutor.py / pdf_gen.py 的调用方式。
    """
    hits = store.query(query, top_k=top_k)
    if not hits:
        return "（知识库暂无相关内容）"
    lines = []
    for h in hits:
        lines.append(f"[来源: {h['source']}]\n{h['text']}")
    return "\n\n".join(lines)
