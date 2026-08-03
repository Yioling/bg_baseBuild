"""通知基建 —— P7 模块。

站内通知主路径：写 `notifications` 表（user_id, type, content, ref_id, company_id 五列，
`read`/`created_at` 用默认）。SMTP 邮件为尽力而为附加路径，失败不影响站内通知。
办公软件 Webhook 为 P2 占位接口。

语义封装：
- notify_register_pending(admin_ids, ...)    新用户注册待审核 → 通知管理员
- notify_quiz_submitted(master_id, ...)       徒弟提交检测 → 通知师傅批改
- notify_anomaly(apprentice, detail, ...)     学情异常 → 通知师傅/管理员

所有函数接受 `conn=None`：为 None 时自取连接并 commit；传入时不自行 commit（与现有
`main.py:_notify` 的事务语义一致——只 execute，由调用方控制 commit）。返回 `{success,...}`。

P1 将 `main.py` 内联的 `_notify(conn,...)` 替换为调用本模块 `notify(...)`，并在注册/检测
处接线触发。本模块不写路由、不改 main/db。
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import Iterable, Optional, Union

from backend.db import get_conn

logger = logging.getLogger(__name__)


# ==================== SMTP（尽力而为） ====================

def _send_email(to: str, subject: str, body: str) -> bool:
    """通过 SMTP 发送邮件。环境变量缺失或发送失败均静默返回 False。

    配置项（均为 os.environ）：
        SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM
    SMTP_HOST 缺省 → 直接跳过（占位未配置）；其余缺省走合理默认（端口 25、FROM 取 USER）。
    """
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    try:
        port = int(os.environ.get("SMTP_PORT", "25"))
    except (TypeError, ValueError):
        port = 25
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    frm = os.environ.get("SMTP_FROM") or user or ""
    if not frm:
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = frm
        msg["To"] = to
        msg["Date"] = formatdate()
        with smtplib.SMTP(host, port, timeout=10) as srv:
            if user and pwd:
                srv.login(user, pwd)
            srv.sendmail(frm, [to], msg.as_string())
        return True
    except Exception as exc:  # 邮件失败不得影响站内通知
        logger.warning("SMTP 发送失败 (to=%s): %s", to, exc)
        return False


# ==================== 核心写入 ====================

def notify(
    user_id: int,
    ntype: str,
    content: str,
    ref_id: Optional[int] = None,
    company_id: int = 1,
    conn=None,
) -> dict:
    """写一条站内通知，并尽力发送 SMTP 邮件。

    - conn=None：自取连接并 commit。
    - 传入 conn：只 execute 不 commit（由调用方控制事务，与 main.py:_notify 一致）。
    - 返回 {"success": True, "notification_id": <id>}；失败返回 {"success": False, "message": ...}。
    - SMTP 邮件为附加路径：查该用户邮箱（users 表无 email 列 → 取 username 兜底），
      缺配置/失败均静默，不影响 notify 返回成功。
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO notifications (user_id, type, content, ref_id, company_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, ntype, content, ref_id, company_id),
        )
        if own_conn:
            conn.commit()
        nid = cur.lastrowid
    except Exception as exc:
        if own_conn:
            conn.close()
        return {"success": False, "message": f"写入通知失败：{exc}"}

    # —— SMTP 尽力而为：缺配置则跳过；失败静默 ——
    if os.environ.get("SMTP_HOST"):
        try:
            row = conn.execute(
                "SELECT username FROM users WHERE id=?", (user_id,)
            ).fetchone()
            to = row["username"] if row else None
            if to:
                _send_email(to, f"薪火通知：{ntype}", content)
        except Exception as exc:  # 查询/发送任何异常都不影响站内通知
            logger.warning("SMTP 附加发送失败 (user_id=%s): %s", user_id, exc)

    if own_conn:
        conn.close()
    return {"success": True, "notification_id": nid}


# ==================== 语义封装 ====================

def notify_register_pending(
    admin_ids: Union[Iterable[int], int],
    username: Optional[str] = None,
    conn=None,
    company_id: int = 1,
) -> dict:
    """新用户注册待审核：给每个管理员发一条 register_pending 通知。

    admin_ids 可为可迭代或单个 int（防御式兼容）。返回 {"success": True, "count": <发出条数>}。
    """
    if isinstance(admin_ids, int):
        admin_ids = [admin_ids]
    count = 0
    for aid in admin_ids:
        r = notify(
            aid,
            "register_pending",
            f"有新用户 {username or ''} 注册，待审核",
            conn=conn,
            company_id=company_id,
        )
        if r.get("success"):
            count += 1
    return {"success": True, "count": count}


def notify_quiz_submitted(
    master_id: int,
    apprentice_name: str,
    conn=None,
    company_id: int = 1,
) -> dict:
    """徒弟提交检测：通知师傅批改。返回 notify() 的结果。"""
    return notify(
        master_id,
        "quiz_submitted",
        f"徒弟 {apprentice_name} 提交了一份检测，请批改",
        conn=conn,
        company_id=company_id,
    )


def notify_anomaly(
    apprentice_id_or_name,
    detail: str,
    master_id: Optional[int] = None,
    conn=None,
    company_id: int = 1,
) -> dict:
    """学情异常通知。

    - 给 master_id → 通知该师傅；
    - 无 master_id → 按 company_id 通知该公司所有已批准管理员（company 级兜底）。
    返回 {"success": True, "count": <发出条数>}。
    """
    content = f"学情异常：{apprentice_id_or_name} {detail}"
    if master_id is not None:
        r = notify(master_id, "anomaly", content, conn=conn, company_id=company_id)
        count = 1 if r.get("success") else 0
        return {"success": r.get("success", False), "count": count}
    # 无指定师傅 → 通知该公司全部已批准管理员
    # 查询用临时连接（conn 为 None 时），但 fan out 时把原 conn 透传给 notify：
    # caller 传了 conn 就共享事务，否则每条 notify 自取连接自 commit。
    own_conn = conn is None
    qconn = conn if conn is not None else get_conn()
    try:
        rows = qconn.execute(
            "SELECT id FROM users WHERE role='admin' AND company_id=? AND status='approved'",
            (company_id,),
        ).fetchall()
    except Exception:
        rows = []
    finally:
        if own_conn:
            qconn.close()
    admin_ids = [row["id"] for row in rows]
    count = 0
    for aid in admin_ids:
        r = notify(aid, "anomaly", content, conn=conn, company_id=company_id)
        if r.get("success"):
            count += 1
    return {"success": True, "count": count}


# ==================== P2 占位：办公软件 Webhook ====================

# 支持的平台（企微 / 钉钉 / 飞书）。预留真实发送的 TODO。
_WEBHOOK_PLATFORMS = {"wecom", "dingtalk", "feishu"}


def notify_via_webhook(platform: str, account: str, content: str) -> dict:
    """办公软件 Webhook 占位接口（P2）。

    不阻塞主流程、不抛异常。真实发送待配置各平台 Webhook URL 后实现：
      - wecom（企业微信群机器人）
      - dingtalk（钉钉群机器人）
      - feishu（飞书群机器人）
    当前返回占位结果。
    """
    if platform not in _WEBHOOK_PLATFORMS:
        return {"success": False, "message": f"不支持的平台：{platform}（占位）"}
    # TODO(P2)：配置 Webhook URL 后，按平台协议 POST 到对应机器人。
    return {"success": True, "message": "占位：未实际发送", "platform": platform, "account": account}
