"""管理员后台（下钻/预警/筛选）—— P6 模块。

- get_apprentice_detail：P0 管理员下钻明细（培养计划 + 各检测成绩 + 每日进度判定）。
- get_anomalies：P1 异常预警（长期无进度 / 检测多次不通过）。
- list_users：P1 用户筛选（按 role / status 增强 auth.get_company_users）。
- log_admin_action：敏感操作（重绑、改分）写入 admin_logs 的辅助函数（由 P1 调用）。

所有查询带 company_id 过滤（跨公司不可见）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from backend.db import get_conn


def log_admin_action(
    admin_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    detail: str = "",
    conn=None,
) -> None:
    """记录管理员敏感操作到 admin_logs（重绑/改分等）。"""
    conn = conn or get_conn()
    conn.execute(
        "INSERT INTO admin_logs (admin_id, action, target_type, target_id, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (admin_id, action, target_type, target_id, detail),
    )
    conn.commit()


def get_apprentice_detail(apprentice_id: int, company_id: int, conn=None) -> dict:
    """管理员下钻：返回某新人的培养计划 + 检测成绩(ai_score/master_score/status) + 每日进度判定。

    跨公司校验：仅允许查看本公司新人。
    """
    conn = conn or get_conn()
    u = conn.execute(
        "SELECT * FROM users WHERE id=? AND company_id=?", (apprentice_id, company_id)
    ).fetchone()
    if not u or u["role"] != "apprentice":
        return {"success": False, "message": "该新人不存在或不属于本公司"}

    plans = conn.execute(
        "SELECT p.* FROM plans p WHERE p.apprentice_id=? ORDER BY p.id DESC",
        (apprentice_id,),
    ).fetchall()
    plan_list = []
    for p in plans:
        items = conn.execute(
            "SELECT pi.*, c.title AS course_title, c.type AS course_type FROM plan_items pi "
            "JOIN courses c ON pi.course_id = c.id WHERE pi.plan_id=? ORDER BY pi.order_no",
            (p["id"],),
        ).fetchall()
        plan_list.append({**dict(p), "items": [dict(it) for it in items]})

    quizzes = conn.execute(
        "SELECT id, plan_item_id, attempt, ai_score, master_score, status, submitted_at "
        "FROM quizzes WHERE apprentice_id=? ORDER BY submitted_at DESC",
        (apprentice_id,),
    ).fetchall()
    quiz_view = [
        {
            "quiz_id": q["id"],
            "plan_item_id": q["plan_item_id"],
            "attempt": q["attempt"],
            "ai_score": q["ai_score"],
            "master_score": q["master_score"],
            "status": q["status"],
            "submitted_at": q["submitted_at"],
        }
        for q in quizzes
    ]

    progress = conn.execute(
        "SELECT dp.*, pi.course_id, c.title AS course_title FROM daily_progress dp "
        "LEFT JOIN plan_items pi ON dp.plan_item_id = pi.id "
        "LEFT JOIN courses c ON pi.course_id = c.id "
        "WHERE dp.apprentice_id=? ORDER BY dp.judged_at DESC",
        (apprentice_id,),
    ).fetchall()

    return {
        "success": True,
        "apprentice": dict(u),
        "plan": plan_list[0] if plan_list else None,
        "plans": plan_list,
        "quizzes": quiz_view,
        "daily_progress": [dict(r) for r in progress],
    }


def get_anomalies(
    company_id: int,
    no_progress_days: int = 7,
    fail_threshold: int = 3,
    conn=None,
) -> dict:
    """异常预警：识别长期无进度（>=no_progress_days 天无判定）或检测多次不通过（>=fail_threshold）的徒弟。

    返回 anomalies 列表，每项含 no_progress / last_judged_at / fail_count 标识，便于前端分类提示。
    """
    conn = conn or get_conn()
    cutoff = (datetime.now() - timedelta(days=no_progress_days)).strftime("%Y-%m-%d %H:%M:%S")
    apprentices = conn.execute(
        "SELECT id, username, full_name FROM users "
        "WHERE role='apprentice' AND company_id=? AND status='approved'",
        (company_id,),
    ).fetchall()
    anomalies = []
    for a in apprentices:
        aid = a["id"]
        last = conn.execute(
            "SELECT MAX(judged_at) m FROM daily_progress WHERE apprentice_id=?", (aid,)
        ).fetchone()
        last_judged = last["m"]
        no_progress = (last_judged is None) or (last_judged < cutoff)

        fails = conn.execute(
            "SELECT COUNT(*) c FROM quizzes WHERE apprentice_id=? AND status='failed'",
            (aid,),
        ).fetchone()["c"]

        if no_progress or fails >= fail_threshold:
            anomalies.append({
                "apprentice_id": aid,
                "username": a["username"],
                "full_name": a["full_name"],
                "no_progress": no_progress,
                "last_judged_at": last_judged,
                "fail_count": fails,
            })
    return {
        "success": True,
        "anomalies": anomalies,
        "no_progress_days": no_progress_days,
        "fail_threshold": fail_threshold,
    }


def list_users(
    company_id: int,
    role: Optional[str] = None,
    status: Optional[str] = None,
    conn=None,
) -> dict:
    """按 role / status 筛选公司用户（增强 auth.get_company_users）。"""
    conn = conn or get_conn()
    sql = (
        "SELECT id, username, role, full_name, employee_no, master_id, status, "
        "department, created_at FROM users WHERE company_id=?"
    )
    params: list = [company_id]
    if role:
        sql += " AND role=?"
        params.append(role)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY role, id"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if r["role"] == "apprentice" and r["master_id"]:
            m = conn.execute(
                "SELECT full_name, username FROM users WHERE id=?", (r["master_id"],)
            ).fetchone()
            d["master_name"] = (m["full_name"] or m["username"]) if m else "-"
        else:
            d["master_name"] = "-"
        out.append(d)
    return {"success": True, "users": out}
