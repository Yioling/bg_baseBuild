"""Planner 计划智能体：依掌握等级生成日历式日计划。"""
import json
from datetime import datetime, timedelta
from backend.llm import chat_json, chat, use_mock
from backend.db import get_conn


PLAN_SYSTEM = """你是一位学习计划专家。根据徒弟的知识掌握情况和知识体系，生成分日学习计划。

严格按 JSON 格式输出：
{
  "plan_overview": "整体计划概述（50字以内）",
  "days": [
    {
      "day_index": 1,
      "note": "本日学习重点说明",
      "tasks": [
        {"title": "任务标题", "dimension_name": "所属维度", "task_type": "阅读", "duration_min": 30, "sort_order": 0, "content_hint": "学习内容提示"}
      ]
    }
  ]
}

要求：
1. 把握等级为"未掌握"的维度多排任务（2-3个/天），"了解"维度平均（1-2个），"熟练"维度少量（0-1个）
2. 每天 3-5 个任务，总时长 60-120 分钟
3. 计划共 7-14 天，前密后疏
4. task_type 取"阅读""练习""复习"之一
5. 确保所有文本为中文"""


def generate_plan(apprentice_id: int, kb_id: int) -> dict:
    """为徒弟生成学习计划。"""
    conn = get_conn()

    # 获取掌握等级
    mastery_rows = conn.execute(
        "SELECT m.*, d.name as dim_name FROM mastery m JOIN dimensions d ON m.dimension_id = d.id WHERE m.apprentice_id=?",
        (apprentice_id,),
    ).fetchall()

    # 获取所有维度
    all_dims = conn.execute(
        "SELECT * FROM dimensions WHERE kb_id=? ORDER BY sort_order",
        (kb_id,),
    ).fetchall()

    # 构建输入
    dims_info = []
    dim_name_to_id = {}
    for d in all_dims:
        dim_name_to_id[d["name"]] = d["id"]
        mastery = next((m for m in mastery_rows if m["dim_name"] == d["name"]), None)
        level = mastery["level"] if mastery else "未掌握"
        pts = conn.execute(
            "SELECT title, content FROM knowledge_points WHERE dimension_id=?",
            (d["id"],),
        ).fetchall()
        dims_info.append({
            "name": d["name"],
            "description": d["description"] or "",
            "mastery_level": level,
            "points": [dict(p) for p in pts],
        })

    dims_json = json.dumps(dims_info, ensure_ascii=False, indent=2)
    result = chat_json(PLAN_SYSTEM, f"请基于以下徒弟知识掌握情况生成学习计划：\n\n{dims_json}")

    if not result or "days" not in result:
        return {"success": False, "message": "计划生成失败"}

    # 清除旧计划
    old_plans = conn.execute(
        "SELECT id FROM study_plans WHERE apprentice_id=? AND kb_id=?",
        (apprentice_id, kb_id),
    ).fetchall()
    for op in old_plans:
        conn.execute("DELETE FROM review_questions WHERE review_id IN (SELECT id FROM daily_reviews WHERE plan_day_id IN (SELECT id FROM plan_days WHERE plan_id=?))", (op["id"],))
        conn.execute("DELETE FROM daily_reviews WHERE plan_day_id IN (SELECT id FROM plan_days WHERE plan_id=?)", (op["id"],))
        conn.execute("DELETE FROM plan_tasks WHERE day_id IN (SELECT id FROM plan_days WHERE plan_id=?)", (op["id"],))
        conn.execute("DELETE FROM plan_days WHERE plan_id=?", (op["id"],))
        conn.execute("DELETE FROM study_plans WHERE id=?", (op["id"],))

    # 创建新计划
    cur = conn.execute(
        "INSERT INTO study_plans (apprentice_id, kb_id, status) VALUES (?, ?, 'active')",
        (apprentice_id, kb_id),
    )
    plan_id = cur.lastrowid

    base_date = datetime.now().date()
    days_data = []
    for day in result["days"]:
        day_date = (base_date + timedelta(days=day["day_index"] - 1)).isoformat()
        cur_day = conn.execute(
            "INSERT INTO plan_days (plan_id, day_index, date, note) VALUES (?, ?, ?, ?)",
            (plan_id, day["day_index"], day_date, day.get("note", "")),
        )
        day_id = cur_day.lastrowid

        tasks = []
        for t in day.get("tasks", []):
            dim_id = dim_name_to_id.get(t.get("dimension_name", ""))
            conn.execute(
                "INSERT INTO plan_tasks (day_id, dimension_id, title, task_type, duration_min, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (day_id, dim_id, t["title"], t.get("task_type", "阅读"),
                 t.get("duration_min", 30), t.get("sort_order", 0)),
            )
            tasks.append({**t, "dimension_id": dim_id})

        days_data.append({
            "day_id": day_id,
            "day_index": day["day_index"],
            "date": day_date,
            "note": day.get("note", ""),
            "tasks": tasks,
        })

    conn.commit()
    return {
        "success": True,
        "plan_id": plan_id,
        "plan_overview": result.get("plan_overview", ""),
        "days": days_data,
    }


def get_plan(apprentice_id: int) -> dict:
    """获取徒弟当前活跃学习计划。"""
    conn = get_conn()
    plan = conn.execute(
        "SELECT * FROM study_plans WHERE apprentice_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
        (apprentice_id,),
    ).fetchone()
    if not plan:
        return {"success": False, "message": "暂无学习计划"}

    days = conn.execute(
        "SELECT * FROM plan_days WHERE plan_id=? ORDER BY day_index",
        (plan["id"],),
    ).fetchall()

    days_data = []
    for d in days:
        tasks = conn.execute(
            "SELECT pt.*, d2.name as dim_name FROM plan_tasks pt LEFT JOIN dimensions d2 ON pt.dimension_id = d2.id WHERE pt.day_id=? ORDER BY pt.sort_order",
            (d["id"],),
        ).fetchall()
        days_data.append({
            **dict(d),
            "tasks": [dict(t) for t in tasks],
        })

    return {
        "success": True,
        "plan_id": plan["id"],
        "days": days_data,
    }


def update_plan_day(day_id: int, note: str = None, locked: int = None) -> dict:
    """师傅修改某天的计划。"""
    conn = get_conn()
    if note is not None:
        conn.execute("UPDATE plan_days SET note=? WHERE id=?", (note, day_id))
    if locked is not None:
        conn.execute("UPDATE plan_days SET locked=? WHERE id=?", (locked, day_id))
    conn.commit()
    return {"success": True, "message": "已更新"}


def update_plan_task(task_id: int, updates: dict) -> dict:
    """修改某任务。"""
    conn = get_conn()
    fields = []
    vals = []
    for k, v in updates.items():
        if v is not None and k in ("title", "task_type", "duration_min", "sort_order"):
            fields.append(f"{k}=?")
            vals.append(v)
    if fields:
        vals.append(task_id)
        conn.execute(f"UPDATE plan_tasks SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
    return {"success": True, "message": "已更新"}
