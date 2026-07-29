"""progress_view 测试：三层视图带 rank、权重可配置、跨公司不可见。"""
from backend.progress_view import (
    progress_company, progress_department, progress_same_master, _build_progress_rows,
)
from helpers import make_company, make_user, make_course, make_plan, make_plan_item, insert_quiz


def _setup(conn):
    make_company(conn, "B公司")
    m1 = make_user(conn, "m1", "master", company_id=1)
    # 公司1 两位徒弟，分属不同部门
    a1 = make_user(conn, "a1", "apprentice", company_id=1, master_id=m1, department="研发", full_name="新人甲")
    a2 = make_user(conn, "a2", "apprentice", company_id=1, master_id=m1, department="研发", full_name="新人乙")
    # 公司2 一位徒弟
    mB = make_user(conn, "mB", "master", company_id=2)
    aB = make_user(conn, "aB", "apprentice", company_id=2, master_id=mB, department="研发")
    c1 = make_course(conn, 1, "课程")
    # a1 完成 1/1，a2 完成 0/1
    p1 = make_plan(conn, a1, m1)
    make_plan_item(conn, p1, c1)
    p2 = make_plan(conn, a2, m1)
    make_plan_item(conn, p2, c1)
    # 给 a1 一个已通过检测（高均分），a2 无检测
    pi1 = conn.execute("SELECT id FROM plan_items WHERE plan_id=?", (p1,)).fetchone()["id"]
    insert_quiz(conn, a1, pi1, status="passed", ai_score=80, master_score=90)
    return dict(m1=m1, a1=a1, a2=a2, aB=aB, mB=mB)


def test_company_view_with_rank(conn):
    d = _setup(conn)
    out = progress_company(1, conn=conn)
    assert out["success"]
    apps = out["apprentices"]
    assert len(apps) == 2  # 仅公司1 的两位徒弟
    assert all("rank" in a and "combined_score" in a for a in apps)
    # 跨公司不可见
    b = progress_company(2, conn=conn)["apprentices"]
    assert len(b) == 1 and b[0]["apprentice_name"] == "aB"


def test_rank_order_by_combined(conn):
    d = _setup(conn)
    apps = progress_company(1, conn=conn)["apprentices"]
    # a1 完成率高且均分高，应排第一
    assert apps[0]["apprentice_name"] == "新人甲"
    ranks = [a["rank"] for a in apps]
    assert ranks == [1, 2]


def test_weights_configurable(conn):
    d = _setup(conn)
    # 仅看完成率权重时，combined 应等于 progress_pct
    apps = progress_company(1, weights=(1.0, 0.0), conn=conn)["apprentices"]
    for a in apps:
        assert a["combined_score"] == a["progress_pct"]


def test_department_view(conn):
    d = _setup(conn)
    out = progress_department(1, "研发", conn=conn)
    assert out["success"]
    assert len(out["apprentices"]) == 2
    # 无部门 → 失败
    assert progress_department(1, "", conn=conn)["success"] is False


def test_same_master_view(conn):
    d = _setup(conn)
    out = progress_same_master("master", d["m1"], 1, conn=conn)
    assert out["success"]
    assert len(out["apprentices"]) == 2
    # 徒弟视角：取其师傅
    out2 = progress_same_master("apprentice", d["a1"], 1, conn=conn)
    assert out2["success"] and len(out2["apprentices"]) == 2


def test_build_progress_rows_direct(conn):
    d = _setup(conn)
    apps = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND company_id=1"
    ).fetchall()
    rows = _build_progress_rows(conn, [dict(r) for r in apps], 1, weights=(0.6, 0.4))
    assert len(rows) == 2 and all("rank" in r for r in rows)
