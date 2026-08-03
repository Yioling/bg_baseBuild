"""notifications 模块测试：站内通知写入、未读计数、批量封装、SMTP 尽力而为、Webhook 占位。

TDD：先写本文件，跑红（模块不存在），再实现 backend/notifications.py 跑绿。
"""
import smtplib

from backend.notifications import (
    notify,
    notify_register_pending,
    notify_quiz_submitted,
    notify_anomaly,
    notify_via_webhook,
    _send_email,
)
from helpers import make_user


def test_notify_writes_fields_and_unread(conn):
    """notify 写入 notifications 表，五列正确，read 默认 0，未读计数 +1。"""
    uid = make_user(conn, "u1", "apprentice", company_id=2)
    r = notify(uid, "anomaly", "学情异常：a1 分数骤降", ref_id=42, company_id=2, conn=conn)
    conn.commit()
    assert r["success"]
    assert isinstance(r["notification_id"], int)
    row = conn.execute(
        "SELECT user_id, company_id, type, content, ref_id, read FROM notifications WHERE id=?",
        (r["notification_id"],),
    ).fetchone()
    assert row["user_id"] == uid
    assert row["company_id"] == 2
    assert row["type"] == "anomaly"
    assert row["content"] == "学情异常：a1 分数骤降"
    assert row["ref_id"] == 42
    assert row["read"] == 0
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (uid,)
    ).fetchone()[0]
    assert unread == 1


def test_notify_auto_commit_when_no_conn(conn):
    """conn=None 时 notify 自取连接并自行 commit，另起连接即可读到。"""
    uid = make_user(conn, "u1", "apprentice")
    r = notify(uid, "quiz_submitted", "徒弟小明提交了检测", conn=None, company_id=1)
    assert r["success"]
    from backend.db import get_conn
    other = get_conn()
    try:
        cnt = other.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=?", (uid,)
        ).fetchone()[0]
    finally:
        other.close()
    assert cnt == 1


def test_notify_no_commit_when_conn_passed(conn):
    """传入 conn 时 notify 不自行 commit：调用方 commit 前另起连接读不到，commit 后才可见。"""
    uid = make_user(conn, "u1", "apprentice")
    r = notify(uid, "quiz_submitted", "内容", conn=conn)
    assert r["success"]
    nid = r["notification_id"]
    # 调用方尚未 commit → 另起连接读不到
    from backend.db import get_conn
    other = get_conn()
    try:
        cnt = other.execute(
            "SELECT COUNT(*) FROM notifications WHERE id=?", (nid,)
        ).fetchone()[0]
    finally:
        other.close()
    assert cnt == 0
    # 调用方 commit 后可见
    conn.commit()
    other2 = get_conn()
    try:
        cnt = other2.execute(
            "SELECT COUNT(*) FROM notifications WHERE id=?", (nid,)
        ).fetchone()[0]
    finally:
        other2.close()
    assert cnt == 1


def test_notify_register_pending_multiple_admins(conn):
    """对每个 admin_id 各发一条 register_pending 通知，content 含用户名与“待审核”。"""
    a1 = make_user(conn, "admin1", "admin", company_id=1)
    a2 = make_user(conn, "admin2", "admin", company_id=1)
    a3 = make_user(conn, "admin3", "admin", company_id=1)
    r = notify_register_pending([a1, a2, a3], username="newbie", conn=conn, company_id=1)
    assert r["success"] and r["count"] == 3
    rows = conn.execute(
        "SELECT user_id, type, content FROM notifications ORDER BY id"
    ).fetchall()
    assert len(rows) == 3
    assert {row["user_id"] for row in rows} == {a1, a2, a3}
    assert rows[0]["type"] == "register_pending"
    assert "newbie" in rows[0]["content"] and "待审核" in rows[0]["content"]
    # 未传 username 时 content 仍可生成（兜底空串）
    r2 = notify_register_pending([a1], conn=conn, company_id=1)
    assert r2["success"] and r2["count"] == 1


def test_notify_register_pending_accepts_single_int(conn):
    """单个 int 也应被当作单元素列表处理（防御式）。"""
    a1 = make_user(conn, "admin1", "admin", company_id=1)
    r = notify_register_pending(a1, username="x", conn=conn, company_id=1)
    assert r["success"] and r["count"] == 1


def test_notify_quiz_submitted_content(conn):
    """notify_quiz_submitted 写入 type=quiz_submitted、content 含徒弟名与“批改”、发给师傅。"""
    m1 = make_user(conn, "m1", "master", company_id=1)
    r = notify_quiz_submitted(m1, "小明", conn=conn, company_id=1)
    assert r["success"] and "notification_id" in r
    row = conn.execute(
        "SELECT user_id, type, content FROM notifications WHERE id=?",
        (r["notification_id"],),
    ).fetchone()
    assert row["user_id"] == m1
    assert row["type"] == "quiz_submitted"
    assert "小明" in row["content"] and "批改" in row["content"]


def test_notify_anomaly_to_master(conn):
    """给 master_id 时发给该师傅，content 含“学情异常”/徒弟标识/详情。"""
    m1 = make_user(conn, "m1", "master", company_id=1)
    r = notify_anomaly("小明", "分数骤降", master_id=m1, conn=conn, company_id=1)
    assert r["success"] and r["count"] == 1
    row = conn.execute(
        "SELECT user_id, type, content FROM notifications WHERE user_id=?", (m1,)
    ).fetchone()
    assert row["type"] == "anomaly"
    assert "学情异常" in row["content"]
    assert "小明" in row["content"] and "分数骤降" in row["content"]


def test_notify_anomaly_to_admins_when_no_master(conn):
    """无 master_id 时按 company 发给所有已批准管理员，不发师傅。"""
    a1 = make_user(conn, "admin1", "admin", company_id=1)
    a2 = make_user(conn, "admin2", "admin", company_id=1)
    make_user(conn, "m1", "master", company_id=1)  # 不应收到
    r = notify_anomaly("小明", "异常", conn=conn, company_id=1)
    assert r["success"] and r["count"] == 2
    rows = conn.execute("SELECT user_id FROM notifications").fetchall()
    assert {row["user_id"] for row in rows} == {a1, a2}


def test_notify_via_webhook_placeholder_no_raise():
    """Webhook 占位接口对任意平台都不抛异常，返回 dict 且含 success。"""
    for p in ("wecom", "dingtalk", "feishu", "unknown"):
        r = notify_via_webhook(p, "acc123", "通知内容")
        assert isinstance(r, dict)
        assert "success" in r


def test_notify_smtp_no_config_still_success(conn, monkeypatch):
    """SMTP 缺配置时 notify() 仍成功（站内通知是主路径，邮件尽力而为）。"""
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    uid = make_user(conn, "u1", "apprentice")
    r = notify(uid, "quiz_submitted", "内容", conn=conn)
    assert r["success"]


def test_send_email_no_config_returns_false(monkeypatch):
    """无 SMTP_HOST 时 _send_email 静默返回 False。"""
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    assert _send_email("to@example.com", "主题", "正文") is False


def test_send_email_with_config(monkeypatch):
    """配齐 SMTP 环境并 mock smtplib.SMTP，验证 host/port/login/sendmail 调用正确。"""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")

    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None, *args, **kwargs):
            calls["host"] = host
            calls["port"] = port

        def login(self, user, pwd):
            calls["login"] = (user, pwd)

        def sendmail(self, frm, to, msg):
            calls["sendmail"] = (frm, to, msg)

        def quit(self):
            calls["quit"] = True

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    ok = _send_email("to@example.com", "薪火通知", "正文内容")
    assert ok is True
    assert calls["host"] == "smtp.example.com"
    assert calls["port"] == 587
    assert calls["login"] == ("user", "pass")
    assert calls["sendmail"][0] == "from@example.com"
    assert calls["sendmail"][1] == ["to@example.com"]
