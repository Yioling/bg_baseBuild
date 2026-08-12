"""P1 集成冒烟 —— 覆盖：
1) 密码重置端到端（POST /api/password/reset-request → /api/password/reset）
2) 注册待审 → 管理员通知自动触发（P0）
3) 三层次进度视图（同分稳定排序、company_id 隔离）
4) 数据库表结构（plans.completed_at、course_questions）已固化

依赖 conftest 的临时 DB 与种子用户（admin / demo_master）。
"""
from __future__ import annotations
import sqlite3

from fastapi.testclient import TestClient


def _login(c: TestClient, username: str, password: str) -> str:
    r = c.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _admin_token(client: TestClient) -> str:
    return _login(client, "admin", "admin123")


def _master_token(client: TestClient) -> str:
    return _login(client, "demo_master", "123456")


# ---------- 1. 密码重置端到端 ----------
def test_password_reset_full_flow(client):
    """完整链路：reset-request → reset → 用新密码登录。"""
    req = client.post("/api/password/reset-request",
                      json={"email": "demo_master"})  # identifier 为 username
    assert req.status_code == 200
    body = req.json()
    assert body.get("success") is True
    token = body.get("token")
    assert token, "未返回 token"

    # 用新密码重置
    reset = client.post("/api/password/reset",
                        json={"token": token, "new_password": "newpass123"})
    assert reset.status_code == 200
    assert reset.json().get("success") is True

    # 用旧密码失败、新密码成功
    bad = client.post("/api/login",
                      json={"username": "demo_master", "password": "123456"})
    assert bad.status_code == 200 and bad.json().get("success") is False
    good = client.post("/api/login",
                       json={"username": "demo_master", "password": "newpass123"})
    assert good.status_code == 200 and good.json().get("success") is True
    # 还原回 123456，避免污染后续用例
    req2 = client.post("/api/password/reset-request", json={"email": "demo_master"})
    tok2 = req2.json().get("token")
    client.post("/api/password/reset", json={"token": tok2, "new_password": "123456"})


def test_password_reset_invalid_token(client):
    """无效 token 应被模糊提示，不泄露细节。"""
    r = client.post("/api/password/reset",
                    json={"token": "this-token-does-not-exist", "new_password": "abc12345"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "令牌无效或已过期" in body.get("message", "")


def test_password_reset_unknown_user(client):
    """未知 identifier 应返回 账号不存在，不发邮件、不发令牌。"""
    r = client.post("/api/password/reset-request",
                    json={"email": "nonexistent_user_xyz"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "不存在" in body.get("message", "")


# ---------- 2. 注册待审 → 管理员通知 ----------
def test_register_triggers_admin_notification(client, conn):
    """新师傅注册 → 管理员收到 register_pending 通知。"""
    # 清理本测试遗留
    conn.execute("DELETE FROM notifications WHERE content LIKE '%notif_trigger%'")
    conn.execute("DELETE FROM users WHERE username='notif_trigger'")
    conn.commit()

    # 先以管理员身份登录拿 token（用于查询通知）
    admin_tok = _admin_token(client)
    # 注册前管理员未读通知基线
    before = client.get("/api/notifications", headers={"Authorization": f"Bearer {admin_tok}"}).json()
    before_unread = before.get("unread_count", 0)

    # 注册一个待审用户
    reg = client.post("/api/register", json={
        "username": "notif_trigger",
        "password": "123456",
        "role": "master",
        "full_name": "通知触发测试",
    })
    assert reg.status_code == 200
    assert reg.json().get("success") is True

    # 管理员通知数 +1
    after = client.get("/api/notifications", headers={"Authorization": f"Bearer {admin_tok}"}).json()
    after_unread = after.get("unread_count", 0)
    assert after_unread == before_unread + 1, f"unread {before_unread} -> {after_unread}"

    # 最新一条是 register_pending 且内容含用户名
    notifs = after.get("notifications", [])
    assert notifs, "通知列表为空"
    top = notifs[0]
    assert top["type"] == "register_pending"
    assert "notif_trigger" in top["content"]


# ---------- 3. quiz 提交 → 师傅通知 ----------
def test_quiz_submit_triggers_master_notification(client, conn):
    """徒弟提交检测 → 师傅收到 quiz_submitted 通知。"""
    from backend.auth import hash_password
    # 准备师徒：master=demo_master, apprentice=quiz_apprentice
    conn.execute("DELETE FROM notifications WHERE content LIKE '%quiz_apprentice%'")
    conn.execute("DELETE FROM users WHERE username='quiz_apprentice'")
    conn.commit()
    master_id = conn.execute("SELECT id FROM users WHERE username='demo_master'").fetchone()["id"]
    conn.execute(
        "INSERT INTO users (username, password_hash, role, master_id, company_id, status) "
        "VALUES (?, ?, 'apprentice', ?, 1, 'approved')",
        ("quiz_apprentice", hash_password("123456"), master_id))
    conn.commit()
    apprentice_id = conn.execute("SELECT id FROM users WHERE username='quiz_apprentice'").fetchone()["id"]

    # 给徒弟建一个 plan + plan_item
    conn.execute(
        "INSERT INTO plans (apprentice_id, master_id, company_id, name) VALUES (?, ?, 1, '通知测试计划')",
        (apprentice_id, master_id))
    plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO courses (company_id, title, type, content, created_by) VALUES (1, '通知课程', 'document', '测试', ?)",
        (master_id,))
    course_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO plan_items (plan_id, course_id, company_id, order_no) VALUES (?, ?, 1, 0)",
        (plan_id, course_id))
    plan_item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    master_tok = _master_token(client)
    before = client.get("/api/notifications", headers={"Authorization": f"Bearer {master_tok}"}).json()
    before_unread = before.get("unread_count", 0)

    # 徒弟登录并提交
    appr_tok = _login(client, "quiz_apprentice", "123456")
    submit = client.post(
        "/api/apprentice/quiz/submit",
        json={"plan_item_id": plan_item_id, "answer": "我是一个测试答案，验证自动通知。"},
        headers={"Authorization": f"Bearer {appr_tok}"},
    )
    assert submit.status_code == 200
    assert submit.json().get("success") is True

    # 师傅应收到一条 quiz_submitted
    after = client.get("/api/notifications", headers={"Authorization": f"Bearer {master_tok}"}).json()
    assert after.get("unread_count", 0) == before_unread + 1
    top = after["notifications"][0]
    assert top["type"] == "quiz_submitted"
    assert "quiz_apprentice" in top["content"]


# ---------- 4. 三层次进度视图（公司/部门/同门） + 同分稳定排序 ----------
def test_progress_views_company_and_same_master(client, conn):
    """公司级 / 同门级进度视图必须带 rank 且排名稳定。"""
    from backend.auth import hash_password
    # 清空本测试残留
    conn.execute("DELETE FROM users WHERE username IN ('prog_app_1', 'prog_app_2')")
    conn.execute("DELETE FROM plans WHERE name='进度测试计划'")
    conn.commit()
    master_id = conn.execute("SELECT id FROM users WHERE username='demo_master'").fetchone()["id"]

    # 2 个徒弟，都没做过 quiz（应当 progress_pct=0）
    for uname in ("prog_app_1", "prog_app_2"):
        conn.execute(
            "INSERT INTO users (username, password_hash, role, master_id, company_id, status, full_name) "
            "VALUES (?, ?, 'apprentice', ?, 1, 'approved', ?)",
            (uname, hash_password("123456"), master_id, f"测试-{uname}"))
    conn.commit()

    admin_tok = _admin_token(client)
    company = client.get("/api/progress/company", headers={"Authorization": f"Bearer {admin_tok}"})
    assert company.status_code == 200
    apprentices = company.json().get("apprentices", [])
    assert isinstance(apprentices, list)
    # 至少有 rank 字段且唯一
    ranks = [a["rank"] for a in apprentices]
    assert len(ranks) == len(set(ranks)), "rank 不唯一"
    # 验证排序键稳定：同分情况下应按 apprentice_id 升序
    sorted_apprentices = sorted(apprentices, key=lambda x: (-x["progress_pct"], -x["avg_score"], x["apprentice_id"]))
    assert [a["apprentice_id"] for a in apprentices] == [a["apprentice_id"] for a in sorted_apprentices]

    # 同门视图（师傅视角）
    master_tok = _master_token(client)
    same = client.get("/api/progress/same-master", headers={"Authorization": f"Bearer {master_tok}"})
    assert same.status_code == 200
    body = same.json()
    assert body.get("success") is True
    for row in body.get("apprentices", []):
        assert "master_name" in row and row["master_name"]  # master_name 非空


def test_progress_views_company_isolation(client, conn):
    """跨公司数据不应串到本公司进度视图。"""
    from backend.auth import hash_password
    # 新建第二个公司 + 一名徒弟
    conn.execute("INSERT OR IGNORE INTO companies (id, name) VALUES (2, 'B 公司')")
    conn.execute(
        "INSERT INTO users (username, password_hash, role, company_id, status, full_name) "
        "VALUES (?, ?, 'apprentice', 2, 'approved', 'B 公司徒弟')",
        ("b_app", hash_password("123456")))
    conn.commit()

    admin_tok = _admin_token(client)
    body = client.get("/api/progress/company", headers={"Authorization": f"Bearer {admin_tok}"}).json()
    usernames_in_view = [a.get("apprentice_name") for a in body.get("apprentices", [])]
    # B 公司徒弟不应出现在 company=1 的视图里
    assert "B 公司徒弟" not in usernames_in_view, "company_id 隔离失败：跨公司数据泄露"


# ---------- 5. db.py schema 固化 ----------
def test_db_schema_p0_registrations(conn):
    """plans.completed_at 列与 course_questions 表都应存在。"""
    plans_cols = [r["name"] for r in conn.execute("PRAGMA table_info(plans)").fetchall()]
    assert "completed_at" in plans_cols, f"plans 缺 completed_at: {plans_cols}"

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='course_questions'"
    ).fetchone()
    assert row is not None, "course_questions 表未创建"


# ---------- 6. 公开 API（无需登录） ----------
def test_public_company_list(client):
    r = client.get("/api/companies")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("companies"), list)
    assert any(c["id"] == 1 for c in body["companies"])


def test_role_guards(client):
    """非师傅访问师傅端接口应被 403。"""
    admin_tok = _admin_token(client)
    r = client.post("/api/master/apprentices",
                    json={"username": "should_fail", "password": "x"},
                    headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 403, f"应被 403，实得 {r.status_code}"

    # 未登录访问应 401
    r2 = client.get("/api/me")
    assert r2.status_code == 401


# ---------- 7. Assessor 本地降级（LLM 失败也能出题） ----------
def test_assessor_local_fallback(client, conn):
    """LLM 返空时，generate_assessment 自动降级到本地出题，确保徒弟始终能进入考试。

    P1 在 backend/agents/assessor.py 加了 _local_generate_questions / _local_grade
    两个纯本地函数，覆盖 LLM 不可用、仅机调用失败、网络隔离等场景。
    """
    from backend.agents.assessor import (
        generate_assessment, _local_generate_questions, _local_grade,
    )
    # 准备师傅 + 知识库 + 2 个维度
    conn.execute("DELETE FROM users WHERE username='assess_master'")
    conn.execute(
        "INSERT INTO users (username, password_hash, role, company_id, status) "
        "VALUES ('assess_master', 'x', 'master', 1, 'approved')")
    master_id = conn.execute(
        "SELECT id FROM users WHERE username='assess_master'"
    ).fetchone()["id"]
    conn.execute("DELETE FROM knowledge_bases WHERE master_id=?", (master_id,))
    conn.execute(
        "INSERT INTO knowledge_bases (master_id, company_id, name) "
        "VALUES (?, 1, 'assess_kb')", (master_id,))
    kb_id = conn.execute(
        "SELECT id FROM knowledge_bases WHERE master_id=? ORDER BY id DESC LIMIT 1",
        (master_id,)).fetchone()["id"]
    conn.execute(
        "INSERT INTO dimensions (kb_id, name, description, sort_order) "
        "VALUES (?, '维度甲', '描述甲', 0)",
        (kb_id,))
    conn.execute(
        "INSERT INTO dimensions (kb_id, name, description, sort_order) "
        "VALUES (?, '维度乙', '描述乙', 1)",
        (kb_id,))
    conn.commit()

    # 调 generate_assessment：mock chat_json 返空以触发本地降级出题
    # （测试环境 MOCK_MODE=true 时 chat_json 会返回内置示例，此处强制模拟 LLM 失败）
    from unittest.mock import patch
    with patch("backend.agents.assessor.chat_json", lambda *a, **k: {}):
        r = generate_assessment(master_id, kb_id)
    assert r.get("success") is True, f"应能出题，实得: {r}"
    assert len(r["questions"]) >= 3, f"应至少 3 题，实得 {len(r['questions'])}"
    for q in r["questions"]:
        assert q.get("dimension_name") in ("维度甲", "维度乙"), f"未知维度: {q}"
        assert q.get("question"), "题目不能为空"
        assert q.get("answer_key") is not None, "answer_key 不能为空"

    # _local_grade 选择题
    g1 = _local_grade("A", {"qtype": "choice", "answer_key": "A"})
    assert g1["score"] == 100 and g1["is_correct"] is True
    g2 = _local_grade("B", {"qtype": "choice", "answer_key": "A"})
    assert g2["score"] == 0 and g2["is_correct"] is False
    # _local_grade 简答
    g3 = _local_grade("提及 描述甲 、 描述乙",
                      {"qtype": "short", "answer_key": "描述甲、描述乙"})
    assert g3["score"] >= 60, f"全命中应 ≥ 60，实得 {g3['score']}"
    # 清理
    conn.execute("DELETE FROM users WHERE username='assess_master'")
    conn.execute("DELETE FROM knowledge_bases WHERE master_id=?", (master_id,))
    conn.commit()


# ---------- 8. 师傅可见课程列表（定制培养计划选课） ----------
def test_master_courses_endpoint(client, conn):
    """P1 装配 /api/master/courses：师傅身份可拉到本公司课程。

    区分于 /api/admin/courses（需 admin 守卫）；师傅调 admin 端点会被 403。
    """
    # 造一门课
    conn.execute(
        "INSERT INTO courses (company_id, title, type, content, created_by) "
        "VALUES (1, '集成测试课程', 'document', '内容', 1)"
    )
    conn.commit()
    course_id = conn.execute(
        "SELECT id FROM courses WHERE title='集成测试课程' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]

    # 管理员调 admin 端点 — 应成功
    admin_tok = _admin_token(client)
    r_admin = client.get("/api/admin/courses", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_admin.status_code == 200
    assert any(c["id"] == course_id for c in r_admin.json().get("courses", []))

    # 师傅调 admin 端点 — 应 403（确认上轮修复必需）
    master_tok = _master_token(client)
    r_block = client.get("/api/admin/courses", headers={"Authorization": f"Bearer {master_tok}"})
    assert r_block.status_code == 403, f"管理员端点不应被师傅访问，实得 {r_block.status_code}"

    # 师傅调新 master 端点 — 应 200，能看到课程
    r_master = client.get("/api/master/courses", headers={"Authorization": f"Bearer {master_tok}"})
    assert r_master.status_code == 200, r_master.text
    body = r_master.json()
    assert body.get("success") is True
    titles = [c["title"] for c in body.get("courses", [])]
    assert "集成测试课程" in titles, f"师傅应能本公司课程，实际列表={titles}"

    # 清理
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
