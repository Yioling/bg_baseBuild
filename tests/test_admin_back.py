"""admin_back 测试：下钻明细字段完整、异常预警识别、用户筛选生效。"""
from datetime import datetime

from backend.admin_back import get_apprentice_detail, get_anomalies, list_users
from helpers import (
    make_company, make_user, make_course, make_plan, make_plan_item,
    insert_quiz, insert_daily_progress,
)


def _setup(conn):
    make_company(conn, "B公司")
    m1 = make_user(conn, "m1", "master", company_id=1)
    a1 = make_user(conn, "a1", "apprentice", company_id=1, master_id=m1, full_name="新人甲")
    a2 = make_user(conn, "apprentice2", "apprentice", company_id=1, master_id=m1)
    c1 = make_course(conn, 1, "课程")
    plan = make_plan(conn, a1, m1)
    pi1 = make_plan_item(conn, plan, c1)
    # a1 的检测与进度
    qid = insert_quiz(conn, a1, pi1, status="passed", ai_score=70, master_score=85)
    # a1 为健康新人：判定时间设为近期（7 天内），不应被「长期无进度」命中
    insert_daily_progress(
        conn, a1, pi1, company_id=1,
        judged_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return dict(m1=m1, a1=a1, a2=a2, pi1=pi1, plan=plan)


def test_apprentice_detail_fields(conn):
    d = _setup(conn)
    out = get_apprentice_detail(d["a1"], 1, conn=conn)
    assert out["success"]
    assert out["apprentice"]["username"] == "a1"
    assert out["plan"] is not None
    assert len(out["quizzes"]) == 1
    q = out["quizzes"][0]
    assert "ai_score" in q and "master_score" in q and "status" in q
    assert q["master_score"] == 85
    assert len(out["daily_progress"]) == 1


def test_detail_cross_company_rejected(conn):
    d = _setup(conn)
    # 以公司2 视角查公司1 的新人 → 拒绝
    out = get_apprentice_detail(d["a1"], 2, conn=conn)
    assert out["success"] is False


def test_anomalies_detect(conn):
    d = _setup(conn)
    # a2：无 daily_progress（长期无进度）
    # 构造一个多次不通过的徒弟
    a3 = make_user(conn, "a3", "apprentice", company_id=1)
    c1 = 1
    plan = make_plan(conn, a3, d["m1"])
    pi = make_plan_item(conn, plan, make_course(conn, 1, "x"))
    for _ in range(3):
        insert_quiz(conn, a3, pi, status="failed", ai_score=20)

    out = get_anomalies(1, no_progress_days=7, fail_threshold=3, conn=conn)
    assert out["success"]
    ids = [a["apprentice_id"] for a in out["anomalies"]]
    # a2 长期无进度应被识别
    assert d["a2"] in ids
    # a3 三次不通过应被识别
    assert a3 in ids
    # a1 既有进度又通过，不应出现在异常
    assert d["a1"] not in ids


def test_list_users_filters(conn):
    d = _setup(conn)
    # 按 role 筛选
    masters = list_users(1, role="master", conn=conn)
    assert masters["success"]
    assert all(u["role"] == "master" for u in masters["users"])
    # 按 status 筛选
    approved = list_users(1, status="approved", conn=conn)
    assert all(u["status"] == "approved" for u in approved["users"])
    # 组合筛选
    comb = list_users(1, role="apprentice", status="approved", conn=conn)
    assert all(u["role"] == "apprentice" and u["status"] == "approved" for u in comb["users"])
    # 跨公司不可见
    assert list_users(2, conn=conn)["users"] == []
