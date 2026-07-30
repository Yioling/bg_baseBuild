"""quiz 模块测试：提交 attempt 递增、师傅终评覆盖、judge 生效、自动完成、越权拦截。"""
from backend.quiz import (
    submit_quiz, list_my_quizzes, list_apprentice_quizzes,
    master_score_quiz, judge_daily_progress, list_daily_progress,
)
from helpers import make_user, make_course, make_plan, make_plan_item, insert_quiz, insert_daily_progress


def _setup(conn):
    m1 = make_user(conn, "m1", "master", company_id=1)
    m2 = make_user(conn, "m2", "master", company_id=1)
    a1 = make_user(conn, "a1", "apprentice", company_id=1, master_id=m1)
    a2 = make_user(conn, "a2", "apprentice", company_id=1, master_id=m1)
    c1 = make_course(conn, 1, "课程1")
    plan = make_plan(conn, a1, m1)
    pi1 = make_plan_item(conn, plan, c1)
    pi2 = make_plan_item(conn, plan, c1)
    plan2 = make_plan(conn, a2, m1)
    pi_a2 = make_plan_item(conn, plan2, c1)
    return dict(m1=m1, m2=m2, a1=a1, a2=a2, pi1=pi1, pi2=pi2, pi_a2=pi_a2, plan=plan)


def test_submit_attempt_increment(conn):
    d = _setup(conn)
    r1 = submit_quiz(d["a1"], d["pi1"], "这是一段足够长的作答内容", conn=conn)
    assert r1["success"] and r1["attempt"] == 1
    r2 = submit_quiz(d["a1"], d["pi1"], "再次作答内容更长一些用于测试", conn=conn)
    assert r2["attempt"] == 2
    assert r1["quiz_id"] != r2["quiz_id"]
    # 返回字段完整
    assert "ai_score" in r1 and "feedback" in r1 and r1["plan_completed"] is False


def test_submit_ownership_rejected(conn):
    d = _setup(conn)
    # a1 提交属于 a2 的 plan_item → 无此学习任务
    r = submit_quiz(d["a1"], d["pi_a2"], "作答", conn=conn)
    assert r["success"] is False


def test_list_and_master_score(conn):
    d = _setup(conn)
    submit_quiz(d["a1"], d["pi1"], "作答内容", conn=conn)
    my = list_my_quizzes(d["a1"], conn=conn)
    assert my["success"] and len(my["quizzes"]) == 1
    # 师傅查看其徒弟
    view = list_apprentice_quizzes(d["m1"], d["a1"], conn=conn)
    assert view["success"] and len(view["quizzes"]) == 1
    # 非其师傅查看 → 拒绝
    bad = list_apprentice_quizzes(d["m2"], d["a1"], conn=conn)
    assert bad["success"] is False

    qid = my["quizzes"][0]["id"]
    sc = master_score_quiz(qid, 95, "passed", conn=conn)
    assert sc["success"]
    # 终评覆盖：查询 quiz 的 master_score
    from backend.db import get_conn
    row = conn.execute("SELECT master_score, status FROM quizzes WHERE id=?", (qid,)).fetchone()
    assert row["master_score"] == 95 and row["status"] == "passed"


def test_judge_daily_progress(conn):
    d = _setup(conn)
    ok = judge_daily_progress(d["m1"], d["a1"], d["pi1"], conn=conn)
    assert ok["success"]
    # 非其师傅判定 → 拒绝
    bad = judge_daily_progress(d["m2"], d["a1"], d["pi1"], conn=conn)
    assert bad["success"] is False


def test_list_daily_progress(conn):
    d = _setup(conn)
    insert_daily_progress(conn, d["a1"], d["pi1"], company_id=1, judged_at="2026-07-25 00:00:00")
    # 其师傅可查
    ok = list_daily_progress(d["m1"], d["a1"], conn=conn)
    assert ok["success"] and len(ok["daily_progress"]) == 1
    # 非其师傅 → 拒绝
    bad = list_daily_progress(d["m2"], d["a1"], conn=conn)
    assert bad["success"] is False


def test_auto_plan_complete(conn):
    d = _setup(conn)
    submit_quiz(d["a1"], d["pi1"], "作答一", conn=conn)
    submit_quiz(d["a1"], d["pi2"], "作答二", conn=conn)
    # 师傅终评两项均通过
    quizzes = list_my_quizzes(d["a1"], conn=conn)["quizzes"]
    ids = [q["id"] for q in quizzes]
    for qid in ids:
        master_score_quiz(qid, 90, "passed", conn=conn)
    # 计划应被标记完成（completed_at 非空）
    row = conn.execute("SELECT completed_at FROM plans WHERE id=?", (d["plan"],)).fetchone()
    assert row["completed_at"] is not None
