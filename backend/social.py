"""交流圈（social）业务模块：附件上传（外链模式）+ @提醒→通知。

本模块不写 FastAPI 路由（路由由 P1 集成负责人装配在 main.py 中），只暴露纯业务函数。

约定：
- 附件：通过 url 字段引用外部资源（云盘/对象存储/企业文档），不做本地文件存储。
  表 `post_attachments (id, post_id, file_name, url, created_at)` 由 db.py 创建。
- @提醒：解析 @username / @中文全名，匹配同公司 status='approved' 的用户，调用
  notifications.notify 写入 mention 类型通知。
- 鉴权：作者本人或管理员可上传/删除附件；同公司用户可读取。
- conn 语义：传入则不 commit（让调用方控制事务），conn=None 时自取+自提交。
- 公司隔离：所有读/写都按 company_id 过滤，跨租户操作直接拒绝。
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.db import get_conn

# @ 提醒解析：前缀要求不是 ASCII word/点/下划线（避免 email 误判，如 my@host.com），
# 行首/空白/中文/中文标点等均合法。name 允许字母/数字/下划线/中文 1-32 字符。
_MENTION_RE = re.compile(r"(?:^|[^A-Za-z0-9_.])@([A-Za-z0-9_\u4e00-\u9fff]{1,32})")
# 邮箱 TLD：解析后若 name 以这些结尾则丢弃（避免 my@host.com 误识别为 @host.com）
_EMAIL_TLDS = (
    "com", "cn", "org", "net", "io", "me", "cc", "gov", "edu",
    "com.cn", "com.hk", "com.tw", "co.jp", "co.uk",
    "xyz", "info", "biz",
)
MAX_URL_LEN = 2048
MAX_FILENAME_LEN = 255


# ============================================================
# 内部工具
# ============================================================

def _validate_url(url: Any) -> Optional[str]:
    """校验 url，返回 None 表示 OK，否则返回错误信息。"""
    if not isinstance(url, str):
        return "url 必须是字符串"
    url = url.strip()
    if not url:
        return "url 不能为空"
    if len(url) > MAX_URL_LEN:
        return f"url 长度不能超过 {MAX_URL_LEN}"
    if not (url.startswith("http://") or url.startswith("https://")):
        return "url 必须以 http:// 或 https:// 开头"
    return None


def _normalize_filename(name: Any) -> Optional[str]:
    """裁剪/规范化 file_name，返回 None 表示非法。"""
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None
    return name[:MAX_FILENAME_LEN]


def _is_author_or_admin(conn, user_id: int, author_id: int) -> tuple:
    """判断 user_id 是否为帖子作者本人或管理员。返回 (allowed, error_msg)。"""
    u = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        return False, "用户不存在"
    is_admin = u["role"] == "admin"
    is_author = author_id == user_id
    if not (is_admin or is_author):
        return False, "仅作者或管理员可操作附件"
    return True, None


# ============================================================
# 附件（外链模式）
# ============================================================

def add_post_attachment(
    post_id: int,
    file_name: str,
    url: str,
    uploaded_by: int,
    conn=None,
    company_id: int = 1,
) -> Dict[str, Any]:
    """为帖子追加一个附件链接（外链模式）。

    入参：
        post_id: 帖子 ID
        file_name: 显示的文件名
        url: 外部资源 URL（http/https）
        uploaded_by: 当前操作用户 user_id（用于鉴权）
        conn: 已有的数据库连接；None 则函数自取
        company_id: 调用方所在公司 ID，用于跨租户校验

    返回：{success, attachment_id, file_name, url, message?}
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        post = conn.execute(
            "SELECT id, company_id, author_id FROM company_posts WHERE id=?",
            (post_id,),
        ).fetchone()
        if not post:
            return {"success": False, "message": "帖子不存在"}
        if post["company_id"] != company_id:
            return {"success": False, "message": "跨租户，禁止操作"}
        allowed, err = _is_author_or_admin(conn, uploaded_by, post["author_id"])
        if not allowed:
            return {"success": False, "message": err}
        err = _validate_url(url)
        if err:
            return {"success": False, "message": err}
        norm_name = _normalize_filename(file_name)
        if norm_name is None:
            return {"success": False, "message": "file_name 不能为空"}
        clean_url = url.strip()
        cur = conn.execute(
            "INSERT INTO post_attachments (post_id, file_name, url) VALUES (?, ?, ?)",
            (post_id, norm_name, clean_url),
        )
        if own:
            conn.commit()
        return {
            "success": True,
            "attachment_id": cur.lastrowid,
            "file_name": norm_name,
            "url": clean_url,
        }
    finally:
        if own:
            conn.close()


def get_post_attachments(
    post_id: int,
    conn=None,
    company_id: int = 1,
) -> Dict[str, Any]:
    """取帖子附件列表。跨公司时返回 success=False、attachments=[]。"""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        post = conn.execute(
            "SELECT company_id FROM company_posts WHERE id=?", (post_id,)
        ).fetchone()
        if not post or post["company_id"] != company_id:
            return {"success": False, "message": "帖子不存在或跨租户", "attachments": []}
        rows = conn.execute(
            "SELECT id, post_id, file_name, url, created_at "
            "FROM post_attachments WHERE post_id=? ORDER BY id",
            (post_id,),
        ).fetchall()
        return {"success": True, "attachments": [dict(r) for r in rows]}
    finally:
        if own:
            conn.close()


def delete_post_attachment(
    attachment_id: int,
    user_id: int,
    conn=None,
    company_id: int = 1,
) -> Dict[str, Any]:
    """删除附件（作者本人或管理员）。"""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        att = conn.execute(
            "SELECT pa.id, pa.post_id, cp.author_id, cp.company_id "
            "FROM post_attachments pa JOIN company_posts cp ON pa.post_id = cp.id "
            "WHERE pa.id = ?",
            (attachment_id,),
        ).fetchone()
        if not att:
            return {"success": False, "message": "附件不存在"}
        if att["company_id"] != company_id:
            return {"success": False, "message": "跨租户，禁止操作"}
        allowed, err = _is_author_or_admin(conn, user_id, att["author_id"])
        if not allowed:
            return {"success": False, "message": err}
        conn.execute("DELETE FROM post_attachments WHERE id=?", (attachment_id,))
        if own:
            conn.commit()
        return {"success": True, "message": "已删除"}
    finally:
        if own:
            conn.close()


# ============================================================
# @ 提醒
# ============================================================

def parse_mentions(content: Union[str, None]) -> List[str]:
    """从文本中抽取所有 @xxx，保留首次出现顺序、自动去重、过滤邮箱 TLD。

    返回值：name 列表（不含 @ 前缀）。
    """
    if not content:
        return []
    seen = set()
    out: List[str] = []
    for m in _MENTION_RE.findall(str(content)):
        if m in seen:
            continue
        # 过滤邮箱域名后缀，避免 my@host.com 误识别为 @host.com
        if m.lower().endswith(_EMAIL_TLDS):
            continue
        seen.add(m)
        out.append(m)
    return out


def resolve_mentioned_user_ids(
    content: Union[str, None],
    company_id: int,
    exclude_user_id: Optional[int] = None,
    conn=None,
) -> List[int]:
    """把 @xxx 解析为本公司的 user_id 列表。

    匹配优先级：username 精确 → full_name 精确。
    仅命中 status='approved' 用户。自动剔除 exclude_user_id（通常为作者本人）。
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        names = parse_mentions(content)
        if not names:
            return []
        ids: set = set()
        for name in names:
            row = conn.execute(
                "SELECT id FROM users "
                "WHERE company_id=? AND status='approved' AND username=?",
                (company_id, name),
            ).fetchone()
            if row:
                ids.add(row["id"])
                continue
            row = conn.execute(
                "SELECT id FROM users "
                "WHERE company_id=? AND status='approved' AND full_name=?",
                (company_id, name),
            ).fetchone()
            if row:
                ids.add(row["id"])
        if exclude_user_id is not None:
            ids.discard(exclude_user_id)
        return sorted(ids)
    finally:
        if own:
            conn.close()


def notify_mentions(
    content: Union[str, None],
    post_id: int,
    author_id: int,
    author_name: Optional[str] = None,
    conn=None,
    company_id: int = 1,
) -> Dict[str, Any]:
    """解析 @ 并给被提到的人发 mention 通知。

    返回：{success, count, mentioned_user_ids: [int, ...]}
        无 @ 时 count=0、mentioned_user_ids=[]。
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        uids = resolve_mentioned_user_ids(
            content, company_id, exclude_user_id=author_id, conn=conn,
        )
        if not uids:
            return {"success": True, "count": 0, "mentioned_user_ids": []}
        if not author_name:
            u = conn.execute(
                "SELECT full_name, username FROM users WHERE id=?", (author_id,),
            ).fetchone()
            author_name = (u["full_name"] or u["username"]) if u else "某人"
        from backend.notifications import notify
        for uid in uids:
            notify(
                uid, "mention",
                f"{author_name} 在帖子 #{post_id} 中@了你",
                ref_id=post_id, company_id=company_id, conn=conn,
            )
        if own:
            conn.commit()
        return {
            "success": True,
            "count": len(uids),
            "mentioned_user_ids": list(uids),
        }
    finally:
        if own:
            conn.close()


# ============================================================
# 本地二进制附件（本地文件上传/存储模式）
# ============================================================
# 与外链模式（上面 add_post_attachment）互补：外链存外部 URL；本组把用户
# 上传的本地文件实体落盘 `backend/data/post_files/`，url 字段存相对磁盘路径，
# 供桌面端“从本地选图片/文件上传 → 展示/下载”交互使用。
# post_attachments 表 post_id 为 NOT NULL：上传阶段先用 -1 占位，
# 发帖成功后 bind_attachments_to_post 按 id 精确更新为真实 post_id。

ATTACH_ROOT = Path(__file__).resolve().parent / "data" / "post_files"
MAX_ATTACH_SIZE = 20 * 1024 * 1024  # 单文件 20MB


def upload_attachment_binary(
    user: dict,
    file_name: str,
    data: bytes,
    conn=None,
) -> Dict[str, Any]:
    """本地二进制附件：落盘 + 写 post_attachments 元数据（post_id=-1 占位）。

    返回：{success, attachment_id, file_name, url, mime, size}。
    大小超限返回 success=False。
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        # 前端上传时把中文文件名做了 percent-encode（绕开 multipart 对非 ASCII 的解析乱码），
        # 这里 unquote 还原为原始 UTF-8 文件名，保证帖子里中文名正确显示。
        if file_name and "%" in file_name:
            try:
                from urllib.parse import unquote
                file_name = unquote(file_name)
            except Exception:
                pass
        fname = (file_name or "unnamed").split("/")[-1].split("\\")[-1]
        if not data:
            return {"success": False, "message": "空文件"}
        if len(data) > MAX_ATTACH_SIZE:
            return {"success": False, "message": f"文件超过 {MAX_ATTACH_SIZE // 1024 // 1024}MB 上限"}
        cur = conn.execute(
            "INSERT INTO post_attachments (post_id, file_name, url) VALUES (?, ?, ?)",
            (-1, fname, ""),
        )
        att_id = cur.lastrowid
        # 落盘文件名：id + 纯字母数字扩展名（防路径穿越 / 注入）
        ext = Path(fname).suffix.lower()
        body = ext.lstrip(".")
        if not (ext.startswith(".") and body and body.isalnum()):
            ext = ""
        stored = f"{att_id}{ext}"
        rel = f"post_files/{stored}"
        ATTACH_ROOT.mkdir(parents=True, exist_ok=True)
        (ATTACH_ROOT / stored).write_bytes(data)
        conn.execute("UPDATE post_attachments SET url=? WHERE id=?", (rel, att_id))
        if own:
            conn.commit()
        return {
            "success": True,
            "attachment_id": att_id,
            "file_name": fname,
            "url": f"/api/attachments/{att_id}/content",
            "mime": _guess_mime(fname),
            "size": len(data),
        }
    finally:
        if own:
            conn.close()


def get_attachment_content(att_id: int, conn=None) -> Optional[Dict[str, Any]]:
    """按附件 id 读取本地文件字节。返回 {id, file_name, mime, data} 或 None。"""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM post_attachments WHERE id=?", (att_id,)
        ).fetchone()
        if not row:
            return None
        rel = row["url"] or ""
        p = Path(__file__).resolve().parent / "data" / rel
        if not p.exists():
            return None
        return {
            "id": row["id"],
            "file_name": row["file_name"],
            "mime": _guess_mime(row["file_name"] or "file.bin"),
            "data": p.read_bytes(),
        }
    finally:
        if own:
            conn.close()


def bind_attachments_to_post(post_id: int, attachment_ids: list, conn=None) -> None:
    """把已上传的临时附件（post_id=-1 占位）绑定到新帖 post_id。"""
    if not attachment_ids:
        return
    own = conn is None
    if own:
        conn = get_conn()
    try:
        for aid in attachment_ids:
            try:
                # 精确更新该 id 且仍处于未绑定占位态的行，避免误改他人附件
                conn.execute(
                    "UPDATE post_attachments SET post_id=? WHERE id=? AND post_id=-1",
                    (post_id, aid),
                )
            except Exception:
                pass
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def _guess_mime(file_name: str, default: str = "application/octet-stream") -> str:
    """按扩展名推断 MIME（图片用 image/*，其余 octet-stream）。"""
    ext = Path(file_name).suffix.lower() if file_name else ""
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }.get(ext)
    return mime or default

