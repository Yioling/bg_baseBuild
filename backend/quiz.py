"""今日任务检测（Quiz）—— P6 模块。

把 main.py 中内联的 /api/apprentice/quiz/submit、/api/apprentice/quizzes、
/api/master/apprentice/{id}/quizzes、/api/master/quizzes/{id}/score、
/api/master/daily-progress 逻辑抽取并增强：

- submit_quiz：徒弟提交检测，调用 P3 的 grade_quiz_answer 做真实 AI 初评（P0），
  未交付/异常时走答案长度兜底，保证可运行、可测试；自动检测计划是否全部完成。
- list_my_quizzes / list_apprentice_quizzes / master_score_quiz / judge_daily_progress。
- 严格 ownership 校验：plan_item 须属于该 user_id；看徒弟须是其师傅的徒弟。

真实 LLM 评分语义归 P3（assessor.grade_quiz_answer），本模块只负责调用 + 兜底 + 持久化。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from backend.db import get_conn

# —— P3 评分函数：防御式导入，未交付则置 None，绝不因 ImportError 中断本模块 ——
try:
    from backend.agents.assessor import grade_quiz_answer
except ImportError:  # pragma: no cover - P3 尚未交付时走此分支
    grade_quiz_answer = None


def _score_with_fallback(plan_item_id: int, answer: str):
    """对接 P3 grade_quiz_answer，任何偏差/异常一律走答案长度兜底。

    归一化返回：dict(缺键兜底) / int(直接当分数) / 异常(兜底) / 未交付(兜底)。
    """
    fallback = min(100, max(10, len(answer or "") * 2)) if answer else 10
    if grade_quiz_answer is None:
        return fallback, "（P3 未交付，评分兜底）"
    try:
        # context 留空，由 P3 内部据 plan_item_id 取 courses.content 作为评分上下文
        res = grade_quiz_answer(plan_item_id, answer)
        if isinstance(res, dict):
            return int(res.get("score", fallback)), str(res.get("feedback", ""))
        if isinstance(res, (int, float)):
            return int(res), ""
        return fallback, "（返回格式异常，评分兜底）"
    except Exception:
        return fallback, "（评分异常，兜底）"


def _ensure_plan_completed_col(conn) -> None:
    """为 plans 增加完成时间列（防御式迁移，待 P1 固化进 db.py）。"""
    try:
        conn.execute("ALTER TABLE plans ADD COLUMN completed_at TIMESTAMP")
    except Exception:
        pass


def _mark_plan_if_complete(conn, plan_id: int) -> bool:
    """若 plan 下全部 plan_items 均已 passed 或师傅已终评，则标记计划完成。"""
    total = conn.execute(
        "SELECT COUNT(*) c FROM plan_items WHERE plan_id=?", (plan_id,)
    ).fetchone()["c"]
    if total == 0:
        return False
    done = conn.execute(
        "SELECT COUNT(DISTINCT q.plan_item_id) c FROM quizzes q "
        "JOIN plan_items pi ON q.plan_item_id = pi.id "
        "WHERE pi.plan_id=? AND (q.status='passed' OR q.master_score IS NOT NULL)",
        (plan_id,),
    ).fetchone()["c"]
    if done >= total:
        _ensure_plan_completed_col(conn)
        conn.execute(
            "UPDATE plans SET completed_at=? WHERE id=? AND completed_at IS NULL",
            (datetime.now().isoformat(timespec="seconds"), plan_id),
        )
        conn.commit()
        return True
    return False


def submit_quiz(user_id: int, plan_item_id: int, answer: str, conn=None) -> dict:
    """徒弟提交今日任务检测，AI 初评，attempt 自动递增。

    返回 {success, quiz_id, attempt, ai_score, feedback, plan_completed, message}，
    状态恒为 pending_review，等待师傅终评。
    """
    conn = conn or get_conn()
    # ownership 校验：plan_item 须属于该 user_id
    item = conn.execute(
        "SELECT pi.*, p.apprentice_id FROM plan_items pi "
        "JOIN plans p ON pi.plan_id = p.id "
        "WHERE pi.id=? AND p.apprentice_id=?",
        (plan_item_id, user_id),
    ).fetchone()
    if not item:
        return {"success": False, "message": "无此学习任务"}

    last = conn.execute(
        "SELECT MAX(attempt) m FROM quizzes WHERE apprentice_id=? AND plan_item_id=?",
        (user_id, plan_item_id),
    ).fetchone()
    attempt = (last["m"] or 0) + 1

    ai_score, feedback = _score_with_fallback(plan_item_id, answer)
    cur = conn.execute(
        "INSERT INTO quizzes (apprentice_id, plan_item_id, attempt, answer, ai_score, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending_review')",
        (user_id, plan_item_id, attempt, answer, ai_score),
    )
    conn.commit()
    quiz_id = cur.lastrowid

    plan_completed = _mark_plan_if_complete(conn, item["plan_id"])
    return {
        "success": True,
        "quiz_id": quiz_id,
        "attempt": attempt,
        "ai_score": ai_score,
        "feedback": feedback,
        "plan_completed": plan_completed,
        "message": "检测已提交，AI初评完成，等待师傅终评",
    }


def list_my_quizzes(user_id: int, conn=None) -> dict:
    """徒弟查看自己的检测历史。"""
    conn = conn or get_conn()
    rows = conn.execute(
        "SELECT q.*, pi.course_id, c.title AS course_title FROM quizzes q "
        "LEFT JOIN plan_items pi ON q.plan_item_id = pi.id "
        "LEFT JOIN courses c ON pi.course_id = c.id "
        "WHERE q.apprentice_id=? ORDER BY q.submitted_at DESC",
        (user_id,),
    ).fetchall()
    return {"success": True, "quizzes": [dict(r) for r in rows]}


def list_apprentice_quizzes(master_id: int, apprentice_id: int, conn=None) -> dict:
    """师傅查看某徒弟的检测记录（须校验是该师傅的徒弟，否则越权拒绝）。"""
    conn = conn or get_conn()
    me = conn.execute(
        "SELECT id FROM users WHERE id=? AND master_id=?", (apprentice_id, master_id)
    ).fetchone()
    if not me:
        return {"success": False, "message": "不是您的徒弟", "quizzes": []}
    rows = conn.execute(
        "SELECT * FROM quizzes WHERE apprentice_id=? ORDER BY submitted_at DESC",
        (apprentice_id,),
    ).fetchall()
    return {"success": True, "quizzes": [dict(r) for r in rows]}


def master_score_quiz(
    quiz_id: int, master_score, status: str = "passed",
    master_id: Optional[int] = None, conn=None,
) -> dict:
    """师傅终评改分（覆盖 AI 初评）。返回 plan_completed 标记计划是否因此完成。

    master_id 可选：若传入，则校验该检测所属徒弟确为该师傅的徒弟（越权防护）。
    """
    conn = conn or get_conn()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
    if not quiz:
        return {"success": False, "message": "检测不存在"}
    # 越权防护：仅允许师傅给本人徒弟的检测终评
    if master_id is not None:
        ok = conn.execute(
            "SELECT id FROM users WHERE id=? AND master_id=?",
            (quiz["apprentice_id"], master_id),
        ).fetchone()
        if not ok:
            return {"success": False, "message": "不是您的徒弟"}
    conn.execute(
        "UPDATE quizzes SET master_score=?, status=? WHERE id=?",
        (master_score, status, quiz_id),
    )
    conn.commit()
    # 终评后若已通过，尝试标记所属计划完成
    pi = conn.execute(
        "SELECT plan_id FROM plan_items WHERE id=?", (quiz["plan_item_id"],)
    ).fetchone()
    plan_completed = _mark_plan_if_complete(conn, pi["plan_id"]) if pi else False
    return {
        "success": True,
        "message": "评分已更新",
        "plan_completed": plan_completed,
    }


def judge_daily_progress(
    master_id: int,
    apprentice_id: int,
    plan_item_id: Optional[int] = None,
    conn=None,
) -> dict:
    """师傅判定徒弟当日任务完成。越权（非其徒弟）拒绝。

    plan_item_id 可选：若提供，额外校验该 task 属于该徒弟。
    """
    conn = conn or get_conn()
    me = conn.execute(
        "SELECT id FROM users WHERE id=? AND master_id=?", (apprentice_id, master_id)
    ).fetchone()
    if not me:
        return {"success": False, "message": "不是您的徒弟"}

    if plan_item_id is not None:
        it = conn.execute(
            "SELECT p.company_id FROM plan_items pi "
            "JOIN plans p ON pi.plan_id = p.id "
            "WHERE pi.id=? AND p.apprentice_id=?",
            (plan_item_id, apprentice_id),
        ).fetchone()
        if not it:
            return {"success": False, "message": "无此学习任务"}
        company_id = it["company_id"]
    else:
        r = conn.execute(
            "SELECT company_id FROM users WHERE id=?", (apprentice_id,)
        ).fetchone()
        company_id = r["company_id"] if r else 1

    conn.execute(
        "INSERT INTO daily_progress "
        "(apprentice_id, plan_item_id, master_judged, judged_by, judged_at, company_id) "
        "VALUES (?, ?, 1, ?, datetime('now'), ?)",
        (apprentice_id, plan_item_id, master_id, company_id),
    )
    conn.commit()
    return {"success": True, "message": "进度已判定"}


def list_daily_progress(master_id: int, apprentice_id: int, conn=None) -> dict:
    """师傅查看某徒弟的每日进度判定记录（须是其徒弟，否则越权拒绝）。

    对应契约 GET /api/master/daily-progress/{apprentice_id}（P6）。
    """
    conn = conn or get_conn()
    me = conn.execute(
        "SELECT id FROM users WHERE id=? AND master_id=?", (apprentice_id, master_id)
    ).fetchone()
    if not me:
        return {"success": False, "message": "不是您的徒弟", "daily_progress": []}
    rows = conn.execute(
        "SELECT dp.*, pi.course_id, c.title AS course_title FROM daily_progress dp "
        "LEFT JOIN plan_items pi ON dp.plan_item_id = pi.id "
        "LEFT JOIN courses c ON pi.course_id = c.id "
        "WHERE dp.apprentice_id=? ORDER BY dp.judged_at DESC",
        (apprentice_id,),
    ).fetchall()
    return {"success": True, "daily_progress": [dict(r) for r in rows]}
