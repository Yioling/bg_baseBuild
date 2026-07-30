"""Tutor 陪练/讲义智能体：RAG 答疑 + 讲义内容生成。"""
import json
from backend.llm import chat, use_mock
from backend.db import get_conn
from backend.vectorstore import VectorStore, retrieve_context
from backend.config import settings


TUTOR_SYSTEM = """你是薪火导师，一位耐心的技术导师。请根据提供的知识库参考资料回答徒弟的问题。

规则：
1. 优先引用知识库中的内容，并标注来源
2. 如果知识库没有相关内容，基于你自己的知识回答，但需说明"以下回答基于通用知识"
3. 用通俗易懂的中文解释
4. 适当给出代码示例或类比帮助理解
5. 回答要结构化，但不要太长（300字以内为宜）"""


def ask(apprentice_id: int, kb_id: int, question: str, store: VectorStore) -> dict:
    """RAG 陪练答疑。"""
    context = retrieve_context(store, question, top_k=4)
    full_prompt = f"参考资料：\n{context}\n\n徒弟提问：{question}"

    answer = chat(TUTOR_SYSTEM, full_prompt, temperature=0.5, max_tokens=800)

    # 记录聊天历史
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (apprentice_id, kb_id, role, content) VALUES (?, ?, 'user', ?)",
        (apprentice_id, kb_id, question),
    )
    conn.execute(
        "INSERT INTO chat_history (apprentice_id, kb_id, role, content) VALUES (?, ?, 'assistant', ?)",
        (apprentice_id, kb_id, answer),
    )
    conn.commit()

    return {"success": True, "answer": answer, "sources": _extract_sources(context)}


def _extract_sources(context: str) -> list[str]:
    sources = []
    for line in context.split("\n"):
        if line.startswith("[来源:"):
            sources.append(line)
    return sources


def generate_lecture_content(apprentice_id: int, plan_day_id: int, store: VectorStore) -> dict:
    """根据当日计划任务生成讲义内容。"""
    conn = get_conn()
    day = conn.execute("SELECT * FROM plan_days WHERE id=?", (plan_day_id,)).fetchone()
    if not day:
        return {"success": False, "message": "计划日不存在"}

    tasks = conn.execute(
        "SELECT pt.*, d.name as dim_name, d.description as dim_desc FROM plan_tasks pt LEFT JOIN dimensions d ON pt.dimension_id = d.id WHERE pt.day_id=? ORDER BY pt.sort_order",
        (plan_day_id,),
    ).fetchall()

    if not tasks:
        return {"success": False, "message": "当日无任务"}

    # 获取相关知识点
    lectures = []
    for task in tasks:
        # RAG 检索相关内容
        query = f"{task['dim_name'] or ''} {task['title']}"
        context = retrieve_context(store, query, top_k=3)

        # 让 LLM 生成讲义
        lecture_system = "你是技术讲师，请将以下知识点整理成适合新人学习的讲义片段（200字左右，含代码示例）。"
        content = chat(lecture_system, f"知识点：{task['title']}\n参考资料：{context}", temperature=0.4, max_tokens=500)

        lectures.append({
            "task_id": task["id"],
            "title": task["title"],
            "dim_name": task["dim_name"],
            "task_type": task["task_type"],
            "duration_min": task["duration_min"],
            "content": content,
        })

    return {
        "success": True,
        "day": dict(day),
        "lectures": lectures,
    }
