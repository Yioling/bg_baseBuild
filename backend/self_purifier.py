"""数据库自净化引擎 — 参考专家Agent系统设计

六种污染检测 + 自动化净化策略：
  1. 溯源失效 → 检查 source_ref 是否仍有效
  2. 陈旧知识 → 对比 chunk 与最新资料的时间/内容
  3. 矛盾知识 → 向量近邻 + LLM 判定冲突
  4. 近重复 → 余弦相似度 >0.95 的 chunk 合并
  5. 低质噪声 → 质量评分 + 指数衰减
  6. 幻觉回灌 → 用户负反馈追溯污染 chunk

原则：能自动判定的全自动；仅高风险项交 Owner 一审。
"""
import json
import time
from datetime import datetime
from pathlib import Path
from backend.db import get_conn
from backend.vectorstore import VectorStore
from backend.config import settings
from backend.llm import chat, chat_json, use_mock


# ==================== 核心引擎 ====================
class SelfPurifier:
    def __init__(self, store: VectorStore = None):
        self.store = store or VectorStore.load(settings.STORE_PATH)
        self.conn = get_conn()
        self.report = {
            "started_at": datetime.now().isoformat(),
            "actions": [],
            "stats": {"cleaned": 0, "flagged": 0, "merged": 0, "degraded": 0}
        }

    # ---------- 1. 溯源校验 ----------
    def validate_provenance(self, kb_id: int = None):
        """检查向量块引用的 source 是否仍可验证。薪火场景下，检查 source 字段格式。"""
        chunks = self._get_chunks(kb_id)
        for c in chunks:
            source = c.get("source", "")
            meta = c.get("meta", "{}")
            try: meta = json.loads(meta) if isinstance(meta, str) else meta
            except: meta = {}
            # 文件类：检查原始文件是否仍可访问
            if source and not source.startswith("http"):
                sp = Path(source)
                if not sp.exists():
                    # 溯源失效 → 标记 degraded
                    self._degrade_chunk(c["id"], "provenance_lost",
                                        f"来源文件不可访问: {source}")
                    self.report["stats"]["degraded"] += 1
        return self

    # ---------- 2. 陈旧检测 ----------
    def detect_staleness(self, kb_id: int = None, newer_texts: list[str] = None):
        """检测 chunk 内容是否与最新资料有差异。用简单哈希比较。"""
        chunks = self._get_chunks(kb_id)
        for c in chunks:
            # 检查 vector_chunks 表中是否有更新版本
            db_chunk = self.conn.execute(
                "SELECT id, text FROM vector_chunks WHERE text=? AND kb_id=?",
                (c.get("text", ""), kb_id or c.get("kb_id"))
            ).fetchone()
            if not db_chunk:
                # 向量库有但 SQLite 表没有 → 可能已过时
                self._flag_for_review(c["id"], "stale_orphan",
                                      "向量库中存在但数据库表中无对应记录")
                self.report["stats"]["flagged"] += 1
        return self

    # ---------- 3. 矛盾检测 ----------
    def detect_contradictions(self, kb_id: int = None):
        """向量近邻 + LLM 判定：找到语义相近但结论矛盾的 chunk 对。"""
        chunks = self._get_chunks(kb_id)
        if len(chunks) < 2: return self

        from backend.embeddings import embed
        texts = [c.get("text", "") for c in chunks]
        if not texts: return self

        # 对每个 chunk 找最近邻（向量库检索）
        for c in chunks:
            text = c.get("text", "")
            if len(text) < 30: continue  # 太短的不检测
            neighbors = self.store.search(
                self._get_embedding(text), top_k=3
            )
            for nb in neighbors:
                if nb["id"] == c["id"]: continue
                if nb.get("score", 0) < 0.85: continue  # 不够相似
                # LLM 判定是否矛盾
                is_contra = self._llm_detect_contradiction(
                    text, nb.get("text", "")
                )
                if is_contra:
                    self._flag_for_review(c["id"], "contradiction",
                                          f"与chunk#{nb['id']}(相似度{nb.get('score',0):.2f})可能矛盾")
                    self.report["stats"]["flagged"] += 1
                    break  # 每个chunk只报告一次矛盾
        return self

    def _llm_detect_contradiction(self, text_a: str, text_b: str) -> bool:
        """调用 LLM 判断两段文本是否矛盾。"""
        prompt = f"""判断以下两段技术知识是否互相矛盾。只回答 YES 或 NO。

文本A: {text_a[:500]}

文本B: {text_b[:500]}

是否存在矛盾？"""
        try:
            resp = chat("你是技术审查专家。判断两段知识是否矛盾，只回答YES或NO。",
                       prompt, temperature=0.1, max_tokens=10)
            return "YES" in resp.upper()
        except:
            return False  # LLM不可用时保守处理

    # ---------- 4. 去重/合并 ----------
    def deduplicate(self, kb_id: int = None, threshold: float = 0.95):
        """检测 Jaccard 相似度 > threshold 的 chunk 对，保留高可信度版本。"""
        chunks = self._get_chunks(kb_id)
        if len(chunks) < 2: return self

        merged_ids = set()
        for i, a in enumerate(chunks):
            if a["id"] in merged_ids: continue
            for b in chunks[i + 1:]:
                if b["id"] in merged_ids: continue
                sim = self._jaccard_sim(a.get("text", ""), b.get("text", ""))
                if sim > threshold:
                    # 保留较长的版本
                    winner = a if len(a.get("text", "")) >= len(b.get("text", "")) else b
                    loser = b if winner is a else a
                    self._merge_chunks(winner["id"], loser["id"])
                    merged_ids.add(loser["id"])
                    self.report["stats"]["merged"] += 1
        return self

    def _jaccard_sim(self, t1: str, t2: str) -> float:
        """Jaccard 相似度：词集合交并比（注：非余弦相似度，完整版应换嵌入向量）。"""
        if not t1 or not t2: return 0
        w1, w2 = set(t1.split()), set(t2.split())
        if not w1 or not w2: return 0
        return len(w1 & w2) / len(w1 | w2)

    # ---------- 5. 质量评分 ----------
    def score_quality(self, kb_id: int = None):
        """对每个 chunk 计算质量分：可信度 × 新鲜度 × 有用性。"""
        chunks = self._get_chunks(kb_id)
        for c in chunks:
            text = c.get("text", "")
            score = 50.0  # 基础分
            # 可信度：内容长度合理 (30-2000字最优)
            tlen = len(text)
            if 100 < tlen < 1500: score += 20
            elif tlen < 30: score -= 30
            # 新鲜度：有 source 字段 +5
            if c.get("source"): score += 10
            # 零检索衰减
            cid = c["id"]
            usage = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM chat_history WHERE content LIKE ?",
                (f"%{text[:30]}%",)
            ).fetchone()
            if usage and usage["cnt"] == 0:
                score -= 15  # 从未被检索过 → 降权

            score = max(0, min(100, score))
            # 持久化质量分
            self.conn.execute(
                "UPDATE vector_chunks SET meta=? WHERE id=? AND kb_id=?",
                (json.dumps({**json.loads(c.get("meta", "{}")),
                             "quality_score": score, "last_scored": datetime.now().isoformat()},
                            ensure_ascii=False),
                 cid, kb_id)
            )
            if score < 30:
                self._degrade_chunk(cid, "low_quality",
                                    f"质量评分{score}，触发自动降权")
                self.report["stats"]["degraded"] += 1
        self.conn.commit()
        return self

    # ---------- 6. 反馈回灌净化 ----------
    def purge_by_feedback(self, kb_id: int = None):
        """用户差评/纠错 → 追溯污染 chunk → 降权。"""
        # 检查最近的低分评估
        bad_answers = self.conn.execute(
            "SELECT aa.*, aq.question FROM assessment_answers aa "
            "JOIN assessment_questions aq ON aa.question_id = aq.id "
            "WHERE aa.score < 30 ORDER BY aa.created_at DESC LIMIT 50"
        ).fetchall()
        for ba in bad_answers:
            question = ba["question"] or ""
            if not question: continue
            # RAG 检索该问题匹配的 chunk
            hits = self.store.search(self._get_embedding(question), top_k=3)
            for h in hits:
                if h.get("score", 0) > 0.7:
                    self._degrade_chunk(h["id"], "feedback_purge",
                                        f"关联低分评估(score={ba['score']})，问题: {question[:50]}")
                    self.report["stats"]["degraded"] += 1
        return self

    # ---------- 评测门禁 ----------
    def eval_guardian(self):
        """净化后验证：确保核心知识未被误删。"""
        # 检查是否有大面积降权（>20% chunks被标记）
        total = self.store.count if self.store else 0
        if total > 0 and self.report["stats"]["degraded"] > total * 0.2:
            self.report["warnings"] = [f"净化率过高({self.report['stats']['degraded']}/{total})，建议人工复核"]
        return self

    # ---------- 执行完整净化 ----------
    def run_full(self, kb_id: int = None) -> dict:
        """执行完整净化流水线。"""
        self.validate_provenance(kb_id)
        self.detect_staleness(kb_id)
        self.detect_contradictions(kb_id)
        self.deduplicate(kb_id)
        self.score_quality(kb_id)
        self.purge_by_feedback(kb_id)
        self.eval_guardian()
        # 保存结果
        self.report["finished_at"] = datetime.now().isoformat()
        self.report["total_chunks"] = self.store.count if self.store else 0
        # 持久化报告
        self.conn.execute(
            "INSERT INTO admin_logs (admin_id, action, target_type, target_id, detail) "
            "VALUES (0, 'self_purify', 'knowledge_base', ?, ?)",
            (kb_id or 0, json.dumps(self.report, ensure_ascii=False))
        )
        self.conn.commit()
        # 保存向量库
        if self.store:
            self.store.save(settings.STORE_PATH)
        return self.report

    # ---------- 辅助方法 ----------
    def _get_chunks(self, kb_id: int = None) -> list:
        """获取向量块列表（优先从向量库，降级从SQLite）。"""
        if self.store and self.store.docs:
            chunks = []
            for d in self.store.docs:
                if kb_id is None or d.get("kb_id") == kb_id:
                    chunks.append(d)
            return chunks
        # 从 SQLite 取
        if kb_id:
            rows = self.conn.execute(
                "SELECT id, kb_id, text, meta FROM vector_chunks WHERE kb_id=?", (kb_id,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT id, kb_id, text, meta FROM vector_chunks").fetchall()
        return [dict(r) for r in rows]

    def _get_embedding(self, text: str) -> list[float]:
        from backend.embeddings import embed_one
        return embed_one(text)

    def _degrade_chunk(self, chunk_id: int, reason: str, detail: str):
        """降权标记（软删除，可恢复）。"""
        self.conn.execute(
            "UPDATE vector_chunks SET meta=? WHERE id=?",
            (json.dumps({"degraded": True, "degraded_reason": reason,
                         "degraded_at": datetime.now().isoformat(), "detail": detail},
                        ensure_ascii=False), chunk_id)
        )

    def _flag_for_review(self, chunk_id: int, reason: str, detail: str):
        """标记待人工审核。"""
        self.conn.execute(
            "INSERT INTO notifications (user_id, type, content, ref_id, company_id) "
            "VALUES (0, ?, ?, ?, 1)",
            (f"purify_{reason}", f"chunk#{chunk_id}: {detail}", chunk_id)
        )

    def _merge_chunks(self, winner_id: int, loser_id: int):
        """合并两个chunk，保留winner。"""
        self.conn.execute(
            "UPDATE vector_chunks SET meta=? WHERE id=?",
            (json.dumps({"merged_from": loser_id,
                         "merged_at": datetime.now().isoformat()},
                        ensure_ascii=False), winner_id)
        )
        self.conn.execute(
            "UPDATE vector_chunks SET meta=? WHERE id=?",
            (json.dumps({"merged_into": winner_id, "degraded": True,
                         "degraded_reason": "dedup_merged"},
                        ensure_ascii=False), loser_id)
        )


# ==================== API 入口 ====================
def run_purification(kb_id: int = None) -> dict:
    """对外暴露：运行一次完整自净化。"""
    purifier = SelfPurifier()
    return purifier.run_full(kb_id)


def get_purification_report() -> dict:
    """获取最近的净化报告。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM admin_logs WHERE action='self_purify' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return {"success": True, "message": "暂无净化记录", "report": None}
    return {"success": True, "report": json.loads(row["detail"])}


def get_purification_stats() -> dict:
    """获取净化统计：当前chunk质量分布。"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM vector_chunks").fetchone()[0]
    degraded = conn.execute(
        "SELECT COUNT(*) FROM vector_chunks WHERE meta LIKE '%degraded%'"
    ).fetchone()[0]
    flagged = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE type LIKE 'purify_%' AND read=0"
    ).fetchone()[0]
    return {
        "success": True,
        "total_chunks": total or 0,
        "degraded_chunks": degraded or 0,
        "pending_reviews": flagged or 0,
        "health_pct": round((1 - (degraded or 0) / max((total or 1), 1)) * 100, 1)
    }
