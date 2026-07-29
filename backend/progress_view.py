"""三层进度视图 + 可配置权重排名 —— P6 模块。

把 main.py 中内联的 /api/progress/company|department|same-master 的 _build_progress_rows
抽取并增强：
- 综合排名算法：完成率 × 权重 + 平均分 × 权重，权重可配置（默认 (0.6, 0.4)）。
- 返回带 rank 的列表：新人 + 对应师傅 + 完成率 + 平均分 + 综合分。
- 所有查询带 company_id 过滤（跨公司不可见）。
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from backend.db import get_conn


def _attach_master_names(conn, apprentices: List[dict]) -> List[dict]:
    """为徒弟列表补全其师傅姓名（master_name）。"""
    out = []
    for a in apprentices:
        d = dict(a)
        m = None
        if d.get("master_id"):
            m = conn.execute(
                "SELECT full_name, username FROM users WHERE id=?", (d["master_id"],)
            ).fetchone()
        d["master_name"] = (m["full_name"] or m["username"]) if m else "-"
        out.append(d)
    return out


def _build_progress_rows(
    conn,
    apprentices: Sequence[dict],
    company_id: int,
    weights: Tuple[float, float] = (0.6, 0.4),
) -> List[dict]:
    """构建带综合排名的新人进度列表（P1 排名算法）。

    weights: (完成率权重, 平均分权重)。综合分 = 完成率×w0 + 平均分×w1（均 0-100）。
    返回列表按综合分降序排列，并写入 rank 字段。
    """
    w_p, w_s = weights
    rows = []
    for a in apprentices:
        aid = a["id"]
        total = conn.execute(
            "SELECT COUNT(*) c FROM plan_items pi "
            "JOIN plans p ON pi.plan_id = p.id WHERE p.apprentice_id=?",
            (aid,),
        ).fetchone()["c"]
        done = conn.execute(
            "SELECT COUNT(DISTINCT q.plan_item_id) c FROM quizzes q "
            "WHERE q.apprentice_id=? AND (q.status='passed' OR q.master_score IS NOT NULL)",
            (aid,),
        ).fetchone()["c"]
        avg = conn.execute(
            "SELECT AVG(COALESCE(master_score, ai_score)) a FROM quizzes WHERE apprentice_id=?",
            (aid,),
        ).fetchone()["a"]
        avg = avg or 0
        progress_pct = round(done / total * 100, 1) if total > 0 else 0
        combined = round(progress_pct * w_p + avg * w_s, 1)
        rows.append({
            "apprentice_id": aid,
            "apprentice_name": a.get("full_name") or a.get("username"),
            "employee_no": a.get("employee_no"),
            "master_id": a.get("master_id"),
            "master_name": a.get("master_name", "-"),
            "total_items": total,
            "done_items": done,
            "progress_pct": progress_pct,
            "avg_score": round(avg, 1),
            "combined_score": combined,
        })
    rows.sort(
        key=lambda x: (x["combined_score"], x["progress_pct"], x["avg_score"]),
        reverse=True,
    )
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def progress_company(
    company_id: int, weights: Tuple[float, float] = (0.6, 0.4), conn=None
) -> dict:
    """公司级新人培养进度（全部徒弟 + 师傅 + 排名）。"""
    conn = conn or get_conn()
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND company_id=? AND status='approved'",
        (company_id,),
    ).fetchall()
    apps = _attach_master_names(conn, [dict(r) for r in rows])
    return {
        "success": True,
        "company_id": company_id,
        "apprentices": _build_progress_rows(conn, apps, company_id, weights),
    }


def progress_department(
    company_id: int, department: str, weights: Tuple[float, float] = (0.6, 0.4), conn=None
) -> dict:
    """部门级新人培养进度。"""
    conn = conn or get_conn()
    if not department:
        return {"success": False, "message": "未设置部门", "apprentices": []}
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND company_id=? AND department=? AND status='approved'",
        (company_id, department),
    ).fetchall()
    apps = _attach_master_names(conn, [dict(r) for r in rows])
    return {
        "success": True,
        "department": department,
        "apprentices": _build_progress_rows(conn, apps, company_id, weights),
    }


def progress_same_master(
    role: str, user_id: int, company_id: int,
    weights: Tuple[float, float] = (0.6, 0.4), conn=None,
) -> dict:
    """同门新人培养进度（师傅传自身 user_id；徒弟传自身 user_id 取其师傅）。"""
    conn = conn or get_conn()
    if role == "apprentice":
        m = conn.execute(
            "SELECT master_id FROM users WHERE id=?", (user_id,)
        ).fetchone()
        master_id = m["master_id"] if m else None
    else:
        master_id = user_id
    if not master_id:
        return {"success": False, "message": "未绑定师傅", "apprentices": []}
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND master_id=? AND company_id=? AND status='approved'",
        (master_id, company_id),
    ).fetchall()
    apps = [dict(r) for r in rows]
    mname = conn.execute(
        "SELECT full_name, username FROM users WHERE id=?", (master_id,)
    ).fetchone()
    master_name = (mname["full_name"] or mname["username"]) if mname else "-"
    for d in apps:
        d["master_name"] = master_name
    return {
        "success": True,
        "master_id": master_id,
        "apprentices": _build_progress_rows(conn, apps, company_id, weights),
    }
