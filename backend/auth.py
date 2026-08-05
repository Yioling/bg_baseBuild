"""注册、登录、鉴权。密码使用哈希。"""
import hashlib
import secrets
from datetime import datetime
from backend.db import get_conn


# ---------- P1 接入 P7 通知模块 ----------
from backend.notifications import notify_register_pending


# 简单的基于 token 的鉴权（无需 JWT 库依赖）
_tokens: dict[str, dict] = {}  # token -> {user_id, username, role, ...}


def hash_password(password: str) -> str:
    """使用 sha256 哈希（简单可靠，零额外依赖）。"""
    salt = secrets.token_hex(8)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt, h = parts
    return hashlib.sha256((password + salt).encode()).hexdigest() == h


def _user_info(row) -> dict:
    return {
        "user_id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "master_id": row["master_id"],
        "company_id": row["company_id"],
        "full_name": row["full_name"],
        "employee_no": row["employee_no"],
        "status": row["status"],
    }


def register(username: str, password: str, role: str, master_id: int | None = None,
             company_id: int | None = None, employee_no: str | None = None,
             phone: str | None = None, office_account: str | None = None,
             full_name: str | None = None, status: str = "pending") -> dict:
    """注册新用户（默认待审核）。返回 {success, message, user?}。"""
    conn = get_conn()

    # 如果指定了师傅但未指定公司，从师傅继承 company_id
    if company_id is None and master_id is not None:
        master = conn.execute(
            "SELECT company_id FROM users WHERE id=?", (master_id,)
        ).fetchone()
        if master:
            company_id = master["company_id"]

    try:
        pwh = hash_password(password)
        cur = conn.execute(
            """INSERT INTO users
               (username, password_hash, role, master_id, company_id, employee_no,
                phone, office_account, full_name, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (username, pwh, role, master_id, company_id, employee_no,
             phone, office_account, full_name, status),
        )
        conn.commit()
        uid = cur.lastrowid


        # ===== 注册待审通知：通知本公司全部已批准管理员 =====
        # 重要：通知必须发在 conn.close() 之前或独立连接完成，不能复用即将关闭的 conn。
        # 下面采用：先查 admin_ids（复用事务内连接），再传 None 让 notify 模块自取连接并提交，
        # 避免“连接被关闭后再 execute”的报错，同时也避免跨连接事务隔离问题。
        admin_ids = []
        try:
            rows = conn.execute(
                "SELECT id FROM users WHERE role='admin' AND company_id=? AND status='approved'",
                (company_id or 1,)
            ).fetchall()
            admin_ids = [a["id"] for a in rows]
        except Exception as e:
            print(f"查管理员列表异常（不影响主流程）: {e}")
        conn.close()
        if admin_ids:
            try:
                notify_register_pending(admin_ids, username=username, conn=None,
                                        company_id=company_id or 1)
            except Exception as e:
                print(f"注册通知发送异常（不影响主流程）: {e}")
        return {"success": True, "message": "注册成功，等待公司管理员审核",
                "user": {"id": uid, "username": username, "role": role, "status": status}}
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        if "UNIQUE" in str(e):
            return {"success": False, "message": "用户名已存在"}
        return {"success": False, "message": str(e)}


def login(username: str, password: str) -> dict:
    """登录。返回 {success, message, token?, user?}。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return {"success": False, "message": "用户名不存在"}
        if not verify_password(password, row["password_hash"]):
            return {"success": False, "message": "密码错误"}
        if row["status"] == "pending":
            return {"success": False, "message": "账号正在审核中，请等待公司管理员通过"}
        if row["status"] == "rejected":
            return {"success": False, "message": "账号未通过审核，请联系公司管理员"}
        token = secrets.token_hex(32)
        _tokens[token] = _user_info(row)
        return {
            "success": True,
            "message": "登录成功",
            "token": token,
            "user": _user_info(row),
        }
    finally:
        conn.close()


def get_user(token: str) -> dict | None:
    return _tokens.get(token)


def logout(token: str):
    _tokens.pop(token, None)


def require_master(user: dict) -> bool:
    return user is not None and user.get("role") == "master"


def require_apprentice(user: dict) -> bool:
    return user is not None and user.get("role") == "apprentice"


def require_admin(user: dict) -> bool:
    return user is not None and user.get("role") == "admin"


# ---------- 公司 / 管理 ----------
def list_companies() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_company_masters(company_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no FROM users "
        "WHERE role='master' AND company_id=? AND status='approved' ORDER BY id",
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_pending_users(company_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, full_name, employee_no, phone, office_account, "
        "company_id, master_id, created_at FROM users "
        "WHERE status='pending' AND company_id=? ORDER BY created_at DESC",
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_user_status(user_id: int, status: str, by: int):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET status=?, approved_by=?, approved_at=? WHERE id=?",
        (status, by, datetime.now().isoformat(timespec="seconds"), user_id),
    )
    conn.commit()


def get_company_users(company_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, full_name, employee_no, master_id, status, created_at "
        "FROM users WHERE company_id=? ORDER BY role, id",
        (company_id,),
    ).fetchall()

    # 批量获取所有师傅姓名（避免 N+1 查询）
    master_ids = {r["master_id"] for r in rows if r["role"] == "apprentice" and r["master_id"]}
    master_map = {}
    if master_ids:
        placeholders = ",".join("?" * len(master_ids))
        masters = conn.execute(
            f"SELECT id, full_name, username FROM users WHERE id IN ({placeholders})",
            tuple(master_ids),
        ).fetchall()
        master_map = {m["id"]: (m["full_name"] or m["username"]) for m in masters}

    out = []
    for r in rows:
        d = dict(r)
        d["master_name"] = master_map.get(r["master_id"], "-") if r["role"] == "apprentice" else "-"
        out.append(d)
    return out


def assign_master(apprentice_id: int, master_id: int) -> dict:
    """调整师徒绑定（谁是谁的徒弟）。"""
    conn = get_conn()
    m = conn.execute("SELECT id FROM users WHERE id=? AND role='master'", (master_id,)).fetchone()
    a = conn.execute("SELECT id FROM users WHERE id=? AND role='apprentice'", (apprentice_id,)).fetchone()
    if not m or not a:
        return {"success": False, "message": "师傅或徒弟账号不存在"}
    conn.execute("UPDATE users SET master_id=? WHERE id=?", (master_id, apprentice_id))
    conn.commit()
    return {"success": True, "message": "师徒绑定已更新"}


# ---------- 公司交流圈 ----------
def create_post(company_id: int, author_id: int, author_name: str,
                author_role: str, content: str) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO company_posts (company_id, author_id, author_name, author_role, content) "
        "VALUES (?, ?, ?, ?, ?)",
        (company_id, author_id, author_name, author_role, content),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM company_posts WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_posts(company_id: int, limit: int = 200) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM company_posts WHERE company_id=? ORDER BY id DESC LIMIT ?",
        (company_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- 同门 / 我的徒弟 ----------
def get_my_apprentices(master_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, full_name, created_at FROM users "
        "WHERE role='apprentice' AND master_id=? ORDER BY created_at DESC",
        (master_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_same_master_apprentices(apprentice_id: int) -> list:
    """获取同门组所有徒弟。"""
    conn = get_conn()
    me = conn.execute("SELECT master_id FROM users WHERE id=?", (apprentice_id,)).fetchone()
    if not me or not me["master_id"]:
        return []
    rows = conn.execute(
        "SELECT id, username, full_name, created_at FROM users "
        "WHERE role='apprentice' AND master_id=? AND id!=?",
        (me["master_id"], apprentice_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_apprentice_stats(apprentice_id: int) -> dict:
    """计算某徒弟的进度概览（用于跨组看板）。"""
    conn = get_conn()
    assess_avg = conn.execute(
        "SELECT AVG(aa.score) as avg FROM assessment_answers aa "
        "JOIN assessments a2 ON aa.assessment_id = a2.id WHERE a2.apprentice_id=?",
        (apprentice_id,),
    ).fetchone()
    review_avg = conn.execute(
        "SELECT AVG(rq.score) as avg FROM review_questions rq "
        "JOIN daily_reviews dr ON rq.review_id = dr.id WHERE dr.apprentice_id=?",
        (apprentice_id,),
    ).fetchone()
    avg = (assess_avg["avg"] or 0) * 0.5 + (review_avg["avg"] or 0) * 0.5
    mastery = conn.execute(
        "SELECT COUNT(*) as cnt FROM mastery WHERE apprentice_id=? AND level='熟练'",
        (apprentice_id,),
    ).fetchone()
    mistakes = conn.execute(
        "SELECT COUNT(*) as cnt FROM assessment_answers "
        "WHERE assessment_id IN (SELECT id FROM assessments WHERE apprentice_id=?) AND score < 60",
        (apprentice_id,),
    ).fetchone()
    rev_mistakes = conn.execute(
        "SELECT COUNT(*) as cnt FROM review_questions rq "
        "JOIN daily_reviews dr ON rq.review_id = dr.id "
        "WHERE dr.apprentice_id=? AND rq.score < 60",
        (apprentice_id,),
    ).fetchone()
    plan_days = conn.execute(
        "SELECT COUNT(*) as cnt FROM study_plans sp JOIN plan_days pd ON pd.plan_id=sp.id "
        "WHERE sp.apprentice_id=?",
        (apprentice_id,),
    ).fetchone()
    return {
        "avg_score": round(avg, 1),
        "mastery_count": mastery["cnt"] or 0,
        "mistake_count": (mistakes["cnt"] or 0) + (rev_mistakes["cnt"] or 0),
        "plan_days": plan_days["cnt"] or 0,
    }
