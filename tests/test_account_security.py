"""account_security 模块测试：密码重置全流程 + 登录失败锁定。

TDD：先写本文件，跑红（模块/函数不存在），再实现 backend/account_security.py 跑绿。

语义说明（check_lock/record_attempt）：
- 只统计 success=0 的失败次数；成功登录写入 success=1 但**不清零**已记失败，
  失败记录靠 10 分钟窗口自然过期。即"4 失败→成功→再 1 失败"仍会累计到 5 锁定。
- 不存在用户不锁定、不记录（避免放大攻击面 / 污染表）。
"""
from datetime import datetime, timedelta

from backend.account_security import (
    LOCK_WINDOW_MIN,
    MAX_FAILS,
    check_lock,
    record_attempt,
    request_password_reset,
    reset_password,
)
from backend.auth import verify_password
from helpers import make_user


# ---- 模块常量 ----

def test_module_constants():
    assert MAX_FAILS == 5
    assert LOCK_WINDOW_MIN == 10


# ---- request_password_reset ----

def test_request_password_reset_creates_token_with_future_expiry(conn):
    """按 username 申请重置：token 落库、expiry 在未来 ~30 分钟、返回 token 与 expiry。"""
    uid = make_user(conn, "alice", "apprentice", company_id=1)
    before = datetime.now()
    r = request_password_reset("alice", conn=conn, company_id=1)
    conn.commit()
    assert r["success"] is True
    token, expiry = r["token"], r["expiry"]
    assert isinstance(token, str) and len(token) == 64  # token_hex(32) -> 64 hex chars
    exp_dt = datetime.fromisoformat(expiry)
    assert exp_dt > before
    assert (exp_dt - before) <= timedelta(minutes=31)
    row = conn.execute(
        "SELECT user_id, token, expiry, used FROM password_resets WHERE token=?", (token,)
    ).fetchone()
    assert row["user_id"] == uid
    assert row["used"] == 0
    assert row["expiry"] == expiry


def test_request_password_reset_by_phone(conn):
    """identifier 为 phone 时也能匹配到用户。"""
    uid = make_user(conn, "bob", "apprentice", company_id=1)
    conn.execute("UPDATE users SET phone=? WHERE id=?", ("13800000000", uid))
    conn.commit()
    r = request_password_reset("13800000000", conn=conn, company_id=1)
    conn.commit()
    assert r["success"] is True
    row = conn.execute(
        "SELECT user_id FROM password_resets WHERE token=?", (r["token"],)
    ).fetchone()
    assert row["user_id"] == uid


def test_request_password_reset_nonexistent_user(conn):
    """不存在的 identifier 返回 success=False、账号不存在，且不写任何 token。"""
    r = request_password_reset("nobody", conn=conn, company_id=1)
    assert r["success"] is False
    assert "不存在" in r["message"]
    cnt = conn.execute("SELECT COUNT(*) FROM password_resets").fetchone()[0]
    assert cnt == 0


def test_request_password_reset_auto_commit(conn):
    """conn=None 时自行 commit，另起连接可读到 token。"""
    make_user(conn, "carol", "apprentice", company_id=1)
    r = request_password_reset("carol", conn=None, company_id=1)
    assert r["success"] is True
    from backend.db import get_conn
    other = get_conn()
    try:
        cnt = other.execute(
            "SELECT COUNT(*) FROM password_resets WHERE token=?", (r["token"],)
        ).fetchone()[0]
    finally:
        other.close()
    assert cnt == 1


# ---- reset_password ----

def test_reset_password_success_and_verifiable(conn):
    """合法 token 重置成功：密码改为新密码，可用 auth.verify_password 验证；token 标记 used=1。"""
    uid = make_user(conn, "dave", "apprentice", company_id=1)
    r = request_password_reset("dave", conn=conn, company_id=1)
    conn.commit()
    token = r["token"]
    r2 = reset_password(token, "NewPass!2026", conn=conn)
    conn.commit()
    assert r2["success"] is True
    assert "已重置" in r2["message"]
    row = conn.execute("SELECT password_hash FROM users WHERE id=?", (uid,)).fetchone()
    assert verify_password("NewPass!2026", row["password_hash"]) is True
    pr = conn.execute("SELECT used FROM password_resets WHERE token=?", (token,)).fetchone()
    assert pr["used"] == 1


def test_reset_password_token_used_fails_second_time(conn):
    """同一 token 第二次重置失败（已用）。"""
    make_user(conn, "eve", "apprentice", company_id=1)
    r = request_password_reset("eve", conn=conn, company_id=1)
    conn.commit()
    token = r["token"]
    assert reset_password(token, "First!123", conn=conn)["success"] is True
    conn.commit()
    r2 = reset_password(token, "Second!456", conn=conn)
    conn.commit()
    assert r2["success"] is False
    assert "无效或已过期" in r2["message"]


def test_reset_password_expired_token_fails(conn):
    """过期 token 重置失败。"""
    uid = make_user(conn, "frank", "apprentice", company_id=1)
    expired = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expiry, used) VALUES (?, ?, ?, 0)",
        (uid, "expired_tok", expired),
    )
    conn.commit()
    r = reset_password("expired_tok", "New!123", conn=conn)
    conn.commit()
    assert r["success"] is False
    assert "无效或已过期" in r["message"]


def test_reset_password_nonexistent_token_fails(conn):
    """不存在的 token 重置失败。"""
    r = reset_password("nonexistent_token_xyz", "New!123", conn=conn)
    conn.commit()
    assert r["success"] is False
    assert "无效或已过期" in r["message"]


def test_reset_password_empty_password_fails(conn):
    """空密码重置失败，即使 token 合法。"""
    make_user(conn, "grace", "apprentice", company_id=1)
    r = request_password_reset("grace", conn=conn, company_id=1)
    conn.commit()
    r2 = reset_password(r["token"], "", conn=conn)
    conn.commit()
    assert r2["success"] is False
    assert "不能为空" in r2["message"]


def test_reset_password_empty_token_fails(conn):
    """空 token 重置失败。"""
    r = reset_password("", "New!123", conn=conn)
    assert r["success"] is False
    assert "无效或已过期" in r["message"]


def test_reset_password_auto_commit(conn):
    """conn=None 时 reset_password 自行 commit：另起连接可读到密码已改、token 已用。"""
    uid = make_user(conn, "heidi", "apprentice", company_id=1)
    r = request_password_reset("heidi", conn=conn, company_id=1)
    conn.commit()
    token = r["token"]
    r2 = reset_password(token, "Auto!2026", conn=None)
    assert r2["success"] is True
    from backend.db import get_conn
    other = get_conn()
    try:
        row = other.execute("SELECT password_hash FROM users WHERE id=?", (uid,)).fetchone()
        pr = other.execute("SELECT used FROM password_resets WHERE token=?", (token,)).fetchone()
    finally:
        other.close()
    assert verify_password("Auto!2026", row["password_hash"]) is True
    assert pr["used"] == 1


# ---- record_attempt + check_lock ----

def test_check_lock_unlocked_below_threshold(conn):
    """失败 N-1 次未锁定。"""
    make_user(conn, "ivan", "apprentice", company_id=1)
    for _ in range(MAX_FAILS - 1):
        record_attempt("ivan", False, conn=conn)
    conn.commit()
    r = check_lock("ivan", conn=conn, company_id=1)
    assert r["success"] is True
    assert r["locked"] is False


def test_check_lock_locked_at_threshold(conn):
    """第 N 次失败后 check_lock 返回 locked=True、message 含"锁定"。"""
    make_user(conn, "judy", "apprentice", company_id=1)
    for _ in range(MAX_FAILS):
        record_attempt("judy", False, conn=conn)
    conn.commit()
    r = check_lock("judy", conn=conn, company_id=1)
    assert r["success"] is False
    assert r["locked"] is True
    assert "锁定" in r["message"]


def test_check_lock_nonexistent_user_not_locked(conn):
    """不存在用户不锁定。"""
    r = check_lock("ghost", conn=conn, company_id=1)
    assert r["success"] is True
    assert r["locked"] is False


def test_record_attempt_nonexistent_user_silent_skip(conn):
    """记录不存在用户的尝试：静默跳过，recorded=False，不写表。"""
    r = record_attempt("phantom", False, conn=conn)
    conn.commit()
    assert r["success"] is True
    assert r["recorded"] is False
    assert "不存在" in r["message"]
    cnt = conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0]
    assert cnt == 0


def test_check_lock_window_expiry(conn):
    """窗口外的失败不计入：5 次 11 分钟前的失败不锁定。

    用 SQLite datetime('now','-11 minutes') 插入，与 DEFAULT CURRENT_TIMESTAMP 同为 UTC，
    避免本地时区与 UTC 不一致导致的窗口判定错误。
    """
    uid = make_user(conn, "karl", "apprentice", company_id=1)
    for _ in range(MAX_FAILS):
        conn.execute(
            "INSERT INTO login_attempts (user_id, attempted_at, success) "
            "VALUES (?, datetime('now', '-11 minutes'), 0)",
            (uid,),
        )
    conn.commit()
    r = check_lock("karl", conn=conn, company_id=1)
    assert r["success"] is True
    assert r["locked"] is False


def test_record_attempt_success_writes_success_one(conn):
    """成功登录记录写入 success=1。"""
    uid = make_user(conn, "leo", "apprentice", company_id=1)
    r = record_attempt("leo", True, conn=conn)
    conn.commit()
    assert r["success"] is True and r["recorded"] is True
    row = conn.execute("SELECT success FROM login_attempts WHERE user_id=?", (uid,)).fetchone()
    assert row["success"] == 1


def test_check_lock_ignores_successful_attempts(conn):
    """成功登录不计入失败锁定计数。"""
    make_user(conn, "nina", "apprentice", company_id=1)
    for _ in range(MAX_FAILS):
        record_attempt("nina", True, conn=conn)
    conn.commit()
    r = check_lock("nina", conn=conn, company_id=1)
    assert r["locked"] is False


def test_check_lock_success_does_not_clear_failures(conn):
    """语义：成功登录不清零已记失败；4 失败+成功+1 失败 仍达 5 锁定（靠窗口自然过期）。"""
    make_user(conn, "oscar", "apprentice", company_id=1)
    for _ in range(4):
        record_attempt("oscar", False, conn=conn)
    record_attempt("oscar", True, conn=conn)
    conn.commit()
    assert check_lock("oscar", conn=conn, company_id=1)["locked"] is False
    record_attempt("oscar", False, conn=conn)
    conn.commit()
    assert check_lock("oscar", conn=conn, company_id=1)["locked"] is True


def test_record_attempt_auto_commit(conn):
    """conn=None 时 record_attempt 自行 commit：另起连接可读到。"""
    make_user(conn, "mike", "apprentice", company_id=1)
    r = record_attempt("mike", False, conn=None)
    assert r["success"] is True and r["recorded"] is True
    from backend.db import get_conn
    other = get_conn()
    try:
        u = other.execute("SELECT id FROM users WHERE username='mike'").fetchone()
        cnt = other.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE user_id=?", (u["id"],)
        ).fetchone()[0]
    finally:
        other.close()
    assert cnt == 1
