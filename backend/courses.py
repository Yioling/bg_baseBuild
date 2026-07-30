"""课程库 + 检测题库（模板引擎）—— P6 模块。

把 main.py 中内联的 /api/admin/courses* 逻辑抽取并增强：
- 课程 CRUD（支持 document|video|link|quiz_bank 四类）
- 当 type='quiz_bank' 时，允许管理员为课程预制检测题（供 quiz 抽取）
- 所有查询带 company_id 过滤（SaaS 隔离护栏）

本模块只导出函数，由 P1 在 main.py 装配路由，不在此写 @app 路由。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from backend.db import get_conn

# 课程类型白名单（type=quiz_bank 时方可挂预制题目）
ALLOWED_TYPES = {"document", "video", "link", "quiz_bank"}


def _ensure_course_questions(conn) -> None:
    """确保检测题库表存在（P6 新增表，防御式建表；待 P1 固化进 db.py 的 init_db）。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS course_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            qtype TEXT NOT NULL DEFAULT 'short',
            answer_key TEXT,
            options TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    )


def list_courses(company_id: int, conn=None) -> dict:
    """列出本公司全部课程（按 id 倒序）。"""
    conn = conn or get_conn()
    rows = conn.execute(
        "SELECT * FROM courses WHERE company_id=? ORDER BY id DESC", (company_id,)
    ).fetchall()
    return {"success": True, "courses": [dict(r) for r in rows]}


def create_course(
    company_id: int,
    title: str,
    type: str = "document",
    content: str = "",
    created_by: Optional[int] = None,
    conn=None,
) -> dict:
    """创建课程。type 必须为白名单之一。"""
    if type not in ALLOWED_TYPES:
        return {"success": False, "message": f"不支持的课程类型：{type}"}
    conn = conn or get_conn()
    cur = conn.execute(
        "INSERT INTO courses (company_id, title, type, content, created_by) VALUES (?, ?, ?, ?, ?)",
        (company_id, title, type, content, created_by),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM courses WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"success": True, "course": dict(row), "message": "课程已创建"}


def update_course(course_id: int, conn=None, **fields) -> dict:
    """更新课程字段（仅允许 title/type/content）。"""
    conn = conn or get_conn()
    allowed = {"title", "type", "content"}
    sets, vals = [], []
    for k in allowed:
        if k in fields and fields[k] is not None:
            if k == "type" and fields[k] not in ALLOWED_TYPES:
                return {"success": False, "message": f"不支持的课程类型：{fields[k]}"}
            sets.append(f"{k}=?")
            vals.append(fields[k])
    if not sets:
        return {"success": True, "message": "无变更"}
    vals.append(course_id)
    conn.execute(f"UPDATE courses SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    return {"success": True, "message": "课程已更新"}


def delete_course(course_id: int, conn=None) -> dict:
    """删除课程（同时清理其 plan_items 与预制题目，避免孤儿数据）。"""
    conn = conn or get_conn()
    conn.execute("DELETE FROM plan_items WHERE course_id=?", (course_id,))
    # course_questions 由 add_course_question 懒建，表可能不存在，删除需容错
    try:
        conn.execute("DELETE FROM course_questions WHERE course_id=?", (course_id,))
    except sqlite3.OperationalError:
        pass
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    return {"success": True, "message": "课程已删除"}


def add_course_question(
    course_id: int,
    question: str,
    qtype: str = "short",
    answer_key: str = "",
    options=None,
    conn=None,
) -> dict:
    """为课程（尤其是 quiz_bank 类型）预制一道检测题。

    options: 选择题选项列表（如 ["A...","B..."]），可空。
    """
    conn = conn or get_conn()
    _ensure_course_questions(conn)
    opts = json.dumps(options, ensure_ascii=False) if options else None
    cur = conn.execute(
        "INSERT INTO course_questions (course_id, question, qtype, answer_key, options) "
        "VALUES (?, ?, ?, ?, ?)",
        (course_id, question, qtype, answer_key, opts),
    )
    conn.commit()
    return {"success": True, "question_id": cur.lastrowid, "message": "题目已添加"}


def list_course_questions(course_id: int, conn=None) -> dict:
    """列出课程下的全部预制检测题。"""
    conn = conn or get_conn()
    _ensure_course_questions(conn)
    rows = conn.execute(
        "SELECT * FROM course_questions WHERE course_id=? ORDER BY id", (course_id,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["options"] = json.loads(d["options"]) if d["options"] else None
        out.append(d)
    return {"success": True, "questions": out}
