"""Refiner 精炼智能体：资料 → 知识维度 + 考点树。"""
import json
from backend.llm import chat_json, use_mock
from backend.db import get_conn


SYSTEM_PROMPT = """你是一位资深技术培训专家。请分析以下资料，抽取结构化的知识体系。

严格按以下 JSON 格式输出（只输出 JSON，不要其他文字）：
{
  "project_summary": "项目整体概述，100字以内",
  "dimensions": [
    {"name": "维度名称", "description": "维度描述", "sort_order": 0}
  ],
  "points": [
    {"dimension": "所属维度名称", "title": "知识点标题", "content": "知识点内容（100字以内）", "source_ref": "出处", "level": "了解/熟练/精通"}
  ]
}

要求：
1. 维度 3-8 个，覆盖资料的核心领域
2. 每个维度至少 3 个知识点
3. level 分为"了解""熟练""精通"三等
4. 确保所有文本为中文"""


def refine(kb_id: int) -> dict:
    """对知识库运行精炼，返回维度与考点并持久化。"""
    from backend.ingest import get_kb_texts
    texts = get_kb_texts(kb_id)
    if not texts.strip():
        if use_mock():
            texts = "智能订单交易系统（演示模式），包含交易链路、幂等设计、分布式事务等核心模块。"
        else:
            return {"success": False, "message": "知识库为空，请先投喂资料"}

    result = chat_json(SYSTEM_PROMPT, f"请分析以下知识资料：\n\n{texts[:8000]}")
    if not result or not isinstance(result, dict):
        return {"success": False, "message": "AI 精炼失败，请重试", "raw": str(result)}

    # 持久化到数据库
    conn = get_conn()
    # 清除旧维度/考点
    conn.execute("DELETE FROM knowledge_points WHERE dimension_id IN (SELECT id FROM dimensions WHERE kb_id=?)", (kb_id,))
    conn.execute("DELETE FROM dimensions WHERE kb_id=?", (kb_id,))

    dim_map = {}
    for i, d in enumerate(result.get("dimensions", [])):
        cur = conn.execute(
            "INSERT INTO dimensions (kb_id, name, description, sort_order) VALUES (?, ?, ?, ?)",
            (kb_id, d["name"], d.get("description", ""), i),
        )
        dim_map[d["name"]] = cur.lastrowid

    for p in result.get("points", []):
        dim_name = p.get("dimension", "")
        dim_id = dim_map.get(dim_name)
        if dim_id:
            conn.execute(
                "INSERT INTO knowledge_points (dimension_id, title, content, source_ref, level) VALUES (?, ?, ?, ?, ?)",
                (dim_id, p["title"], p.get("content", ""), p.get("source_ref", ""), p.get("level", "了解")),
            )

    conn.commit()

    # 获取持久化后的完整数据返回
    dims = [dict(r) for r in conn.execute("SELECT * FROM dimensions WHERE kb_id=? ORDER BY sort_order", (kb_id,)).fetchall()]
    for d in dims:
        pts = conn.execute("SELECT * FROM knowledge_points WHERE dimension_id=? ORDER BY level", (d["id"],)).fetchall()
        d["points"] = [dict(p) for p in pts]

    return {
        "success": True,
        "message": "知识精炼完成",
        "project_summary": result.get("project_summary", ""),
        "dimensions": dims,
    }
