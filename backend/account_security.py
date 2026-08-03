"""账户安全模块 —— P7。

提供密码重置（request_password_reset / reset_password）与登录失败锁定
（check_lock / record_attempt）能力。表 password_resets / login_attempts 已由
db.py 建好，本模块只读写不建表。路由由 P1 在 main.py 装配，auth.login 由 P1 改调
check_lock / record_attempt；本模块不写路由、不改 main/db/auth。

语义：
- request_password_reset(identifier) 按 username / phone 定位 user（users 表无
  email 列，暂不支持 email 匹配），生成 30 分钟有效的 token 写入 password_resets，
  返回 token（P1 决定是否回显 / 发邮件——真实场景会发邮件，此处为可测试直接返回）。
- reset_password(token, new_pwd) 校验 token 未用且未过期，调用 auth.hash_password
  重置密码并标记 token used=1；统一模糊提示"令牌无效或已过期"以防枚举。
- check_lock(username) 统计近 LOCK_WINDOW_MIN 分钟内 success=0 次数，达 MAX_FAILS
  返回 locked。只对存在用户计数（不存在用户不锁，避免放大攻击面）。
- record_attempt(username, success) 记录一次登录尝试；用户不存在则静默跳过。
  成功登录不清零已记失败——失败记录靠 LOCK_WINDOW_MIN 窗口自然过期（语义见测试注释）。

时间口径：
- password_resets.expiry 用 datetime.now() 本地 ISO 写入与比较（Python 侧闭合）。
- login_attempts 窗口用 SQLite datetime('now', ...)（UTC，与 DEFAULT CURRENT_TIMESTAMP
  一致），避免本地时区与 UTC 串比较错位。

所有函数接受 conn=None：None 时自取连接并 commit；传入时不自行 commit（与项目模块
函数模式一致）。返回 {success,...}。
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from backend.db import get_conn

try:  # 防御式导入：优先复用 auth.hash_password，保证重置哈希与 login 校验格式一致
    from backend.auth import hash_password as _hash_password
except ImportError:  # pragma: no cover - auth 未交付时兜底等价实现
    import hashlib

    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(8)
        h = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{h}"

logger = logging.getLogger(__name__)

# ---- 模块常量（P1 装配时直接引用） ----
MAX_FAILS = 5           # 连续失败 N 次锁定
LOCK_WINDOW_MIN = 10    # 锁定计数窗口（分钟）
TOKEN_EXPIRY_MIN = 30    # 重置令牌有效期（分钟）


# ==================== 密码重置 ====================

def request_password_reset(identifier, conn=None, company_id=1):
    """按 username 或 phone 定位用户，生成 30 分钟有效的重置 token。

    identifier 可为 username 或 phone（users 表无 email 列，暂不支持 email）。
    找不到返回 {"success": False, "message": "账号不存在"}。
    成功返回 {"success": True, "token": <token>, "expiry": <expiry_iso>}。
    company_id 参与过滤（多租户隔离，phone 可能跨公司重复）。
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE company_id=? AND (username=? OR phone=?)",
            (company_id, identifier, identifier),
        ).fetchone()
        if not row:
            return {"success": False, "message": "账号不存在"}
        token = secrets.token_hex(32)
        expiry = (datetime.now() + timedelta(minutes=TOKEN_EXPIRY_MIN)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO password_resets (user_id, token, expiry, used) VALUES (?, ?, ?, 0)",
            (row["id"], token, expiry),
        )
        if own_conn:
            conn.commit()
        return {"success": True, "token": token, "expiry": expiry}
    except Exception as exc:
        return {"success": False, "message": f"生成重置令牌失败：{exc}"}
    finally:
        if own_conn:
            conn.close()


def reset_password(token, new_pwd, conn=None):
    """校验 token 未用且未过期，重置密码并标记 token 已用。

    失败统一返回 {"success": False, "message": "令牌无效或已过期"}（不区分不存在 /
    已用 / 过期以防枚举）；空密码返回 {"success": False, "message": "新密码不能为空"}。
    成功返回 {"success": True, "message": "密码已重置"}。
    """
    if not new_pwd:
        return {"success": False, "message": "新密码不能为空"}
    if not token:
        return {"success": False, "message": "令牌无效或已过期"}
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, user_id, expiry, used FROM password_resets WHERE token=?", (token,)
        ).fetchone()
        if not row or row["used"] == 1:
            return {"success": False, "message": "令牌无效或已过期"}
        # expiry 存为本地 ISO 字符串，与 datetime.now() 同时区比较
        try:
            expiry_dt = datetime.fromisoformat(row["expiry"])
        except (ValueError, TypeError):
            return {"success": False, "message": "令牌无效或已过期"}
        if expiry_dt <= datetime.now():
            return {"success": False, "message": "令牌无效或已过期"}
        new_hash = _hash_password(new_pwd)
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?", (new_hash, row["user_id"])
        )
        conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
        if own_conn:
            conn.commit()
        return {"success": True, "message": "密码已重置"}
    except Exception as exc:
        return {"success": False, "message": f"重置密码失败：{exc}"}
    finally:
        if own_conn:
            conn.close()


# ==================== 登录失败锁定 ====================

def check_lock(username, conn=None, company_id=1):
    """检查用户近 LOCK_WINDOW_MIN 分钟内失败次数是否达 MAX_FAILS。

    达阈值返回 {"success": False, "locked": True, "message": "账号已锁定，请 10 分钟后再试"}。
    未达或用户不存在返回 {"success": True, "locked": False}（不存在用户不锁，
    避免放大攻击面；存在性由 login 另行处理）。

    注：username 在 db.py 中为 UNIQUE 全局唯一，auth.login 也仅按 username 查询，
    故此处不按 company_id 过滤（与 login 保持一致，确保 P1 装配无缝）。company_id
    保留在签名中以兼容调用方约定。
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if not row:
            return {"success": True, "locked": False}
        cutoff = f"-{LOCK_WINDOW_MIN} minutes"
        cnt = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE user_id=? AND success=0 "
            "AND attempted_at >= datetime('now', ?)",
            (row["id"], cutoff),
        ).fetchone()[0]
        if cnt >= MAX_FAILS:
            return {"success": False, "locked": True,
                    "message": f"账号已锁定，请 {LOCK_WINDOW_MIN} 分钟后再试"}
        return {"success": True, "locked": False}
    except Exception as exc:
        # 锁定检查为咨询性：异常时不锁（fail-open），由 auth.login 自身逻辑兜底，
        # 避免本模块异常导致全体无法登录的 DoS。
        logger.warning("check_lock 异常 (username=%s): %s", username, exc)
        return {"success": True, "locked": False}
    finally:
        if own_conn:
            conn.close()


def record_attempt(username, success, conn=None, company_id=1):
    """记录一次登录尝试。用户不存在则静默跳过，避免不存在用户名污染表。

    成功写入返回 {"success": True, "recorded": True}。
    用户不存在返回 {"success": True, "recorded": False, "message": "用户不存在"}。
    success 接受 bool / int / None，统一归一为 0/1 存储。
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if not row:
            return {"success": True, "recorded": False, "message": "用户不存在"}
        conn.execute(
            "INSERT INTO login_attempts (user_id, success) VALUES (?, ?)",
            (row["id"], 1 if success else 0),
        )
        if own_conn:
            conn.commit()
        return {"success": True, "recorded": True}
    except Exception as exc:
        return {"success": False, "message": f"记录登录尝试失败：{exc}"}
    finally:
        if own_conn:
            conn.close()
