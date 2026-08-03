"""social 模块测试：交流圈附件（外链模式）+ @提醒解析与通知。

TDD：先写本文件，跑红（模块不存在），再实现 backend/social.py 跑绿。

设计要点：
- 附件通过 url 引用外部资源（云盘/对象存储/企业文档），不做本地文件存储
- 鉴权：作者本人或管理员可上传；同租户可见
- @提醒：解析 @username / @中文全名，匹配本公司已批准用户
- 纯函数：不写 FastAPI 路由，由 P1 集成负责人装配
- conn 语义：传入则不 commit（让调用方控制事务），None 则自取+自提交
"""
from backend import social
from backend.social import (
    add_post_attachment,
    delete_post_attachment,
    get_post_attachments,
    notify_mentions,
    parse_mentions,
    resolve_mentioned_user_ids,
)
from helpers import make_user


# ---- 测试种子 ----

def _make_post(conn, author_id, company_id=1, content="帖子内容") -> int:
    cur = conn.execute(
        "INSERT INTO company_posts (company_id, author_id, author_name, author_role, content) "
        "VALUES (?, ?, ?, ?, ?)",
        (company_id, author_id, "作者", "apprentice", content),
    )
    conn.commit()
    return cur.lastrowid


# ============================================================
# parse_mentions：纯文本解析
# ============================================================

def test_parse_mentions_basic_username():
    assert parse_mentions("请 @alice 和 @bob 看一下") == ["alice", "bob"]


def test_parse_mentions_dedup_preserve_order():
    """重复 @ 不重复返回，保留首次出现顺序。"""
    assert parse_mentions("@alice @bob @alice") == ["alice", "bob"]


def test_parse_mentions_chinese_fullname():
    """支持 @中文全名。"""
    assert parse_mentions("@张三 辛苦啦") == ["张三"]


def test_parse_mentions_mixed_and_punct():
    """@ 前后允许常见中文/英文标点。"""
    assert parse_mentions("，@张三；@lisi！") == ["张三", "lisi"]


def test_parse_mentions_excludes_email():
    """邮箱中的 @host.com / @host.cn 不被识别为提醒。"""
    assert parse_mentions("联系 my@host.com 或 help@svc.cn") == []
    # 同一文本中合法的 @alice 仍命中
    assert parse_mentions("请 @alice 确认 my@host.com") == ["alice"]


def test_parse_mentions_no_at_returns_empty():
    assert parse_mentions("没有任何 @ 符号的纯文本") == []
    assert parse_mentions("") == []
    assert parse_mentions(None) == []


def test_parse_mentions_keeps_at_within_word():
    """紧贴 word 字符的 @ 不解析（避免 a@user 误判）。"""
    assert parse_mentions("a@user 也会 @valid") == ["valid"]


def test_parse_mentions_length_cap():
    """超过 32 字符的 @xxx 截断为前 32。"""
    long_name = "a" * 40
    assert parse_mentions(f"@{long_name}") == ["a" * 32]


# ============================================================
# resolve_mentioned_user_ids：解析到 user_id
# ============================================================

def test_resolve_by_username(conn):
    uid_alice = make_user(conn, "alice", "apprentice", company_id=1)
    make_user(conn, "bob", "apprentice", company_id=1)
    ids = resolve_mentioned_user_ids("@alice @bob", 1, conn=conn)
    assert isinstance(ids, list) and len(ids) == 2
    assert uid_alice in ids
    bob = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()
    assert bob["id"] in ids


def test_resolve_by_full_name_when_username_missing(conn):
    """username 未命中时退回到 full_name 精确匹配。"""
    make_user(conn, "u1", "apprentice", company_id=1, full_name="张三")
    ids = resolve_mentioned_user_ids("@张三", 1, conn=conn)
    assert len(ids) == 1
    u = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()
    assert ids[0] == u["id"]


def test_resolve_username_takes_priority(conn):
    """username 命中优先于 full_name 命中。"""
    uid_a = make_user(conn, "alice", "apprentice", company_id=1, full_name="甲")
    make_user(conn, "u2", "apprentice", company_id=1, full_name="alice")
    ids = resolve_mentioned_user_ids("@alice", 1, conn=conn)
    assert ids == [uid_a]


def test_resolve_excludes_self(conn):
    """作者 @ 自己不应被通知。"""
    uid = make_user(conn, "alice", "apprentice", company_id=1)
    ids = resolve_mentioned_user_ids("@alice", 1, exclude_user_id=uid, conn=conn)
    assert ids == []


def test_resolve_company_isolation(conn):
    """跨公司的用户不应被本公司解析命中。"""
    make_user(conn, "alice", "apprentice", company_id=1)
    make_user(conn, "bob", "apprentice", company_id=2)
    ids = resolve_mentioned_user_ids("@bob", 1, conn=conn)
    assert ids == []  # company 2 的 bob 不应被 company 1 解析
    # 同理 @alice 只命中 company 1 的 alice
    ids2 = resolve_mentioned_user_ids("@alice", 1, conn=conn)
    assert len(ids2) == 1
    row = conn.execute("SELECT id FROM users WHERE username='alice' AND company_id=1").fetchone()
    assert ids2[0] == row["id"]


def test_resolve_only_approved_users(conn):
    """pending / rejected 用户不接收提醒。"""
    make_user(conn, "pending_one", "apprentice", company_id=1, status="pending")
    ids = resolve_mentioned_user_ids("@pending_one", 1, conn=conn)
    assert ids == []


def test_resolve_unknown_user_silent(conn):
    """@不存在的用户静默忽略。"""
    make_user(conn, "alice", "apprentice", company_id=1)
    ids = resolve_mentioned_user_ids("@ghost_user", 1, conn=conn)
    assert ids == []


def test_resolve_auto_commit(conn):
    """conn=None 时也能命中并返回。"""
    make_user(conn, "auto1", "apprentice", company_id=1)
    ids = resolve_mentioned_user_ids("@auto1", 1, conn=None)
    assert len(ids) == 1


# ============================================================
# notify_mentions：实际写入通知
# ============================================================

def test_notify_mentions_writes_notifications(conn):
    """@2 个用户 → 写 2 条 mention 通知，content 含作者名与帖子号。"""
    author = make_user(conn, "author", "master", company_id=1, full_name="王师傅")
    make_user(conn, "alice", "apprentice", company_id=1)
    make_user(conn, "bob", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = notify_mentions("请 @alice 和 @bob 看看", post_id, author, author_name="王师傅",
                        conn=conn, company_id=1)
    assert r["success"] is True
    assert r["count"] == 2
    assert len(r["mentioned_user_ids"]) == 2
    rows = conn.execute(
        "SELECT user_id, type, content, ref_id FROM notifications WHERE type='mention' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["ref_id"] == post_id
        assert "王师傅" in row["content"] and f"#{post_id}" in row["content"]


def test_notify_mentions_no_mentions(conn):
    """无 @ 时不发通知，count=0。"""
    author = make_user(conn, "author", "master", company_id=1)
    _make_post(conn, author, company_id=1)
    r = notify_mentions("纯文本无 @", 1, author, conn=conn, company_id=1)
    assert r == {"success": True, "count": 0, "mentioned_user_ids": []}
    cnt = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    assert cnt == 0


def test_notify_mentions_self_excluded(conn):
    """作者 @ 自己不写通知。"""
    author = make_user(conn, "selfie", "master", company_id=1, full_name="我")
    _make_post(conn, author, company_id=1)
    r = notify_mentions("@selfie 看一下", 1, author, conn=conn, company_id=1)
    assert r["count"] == 0
    cnt = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    assert cnt == 0


def test_notify_mentions_auto_fetches_author_name(conn):
    """未传 author_name 时自动从 users 取。"""
    author = make_user(conn, "auto_a", "master", company_id=1, full_name="陈师傅")
    make_user(conn, "alice", "apprentice", company_id=1)
    _make_post(conn, author, company_id=1)
    r = notify_mentions("@alice", 1, author, conn=conn, company_id=1)
    assert r["count"] == 1
    row = conn.execute("SELECT content FROM notifications").fetchone()
    assert "陈师傅" in row["content"]


def test_notify_mentions_auto_commit(conn):
    """conn=None 时通知写入并可由另一连接读到。"""
    author = make_user(conn, "author", "master", company_id=1, full_name="周师傅")
    make_user(conn, "alice", "apprentice", company_id=1)
    _make_post(conn, author, company_id=1)
    r = notify_mentions("@alice", 1, author, conn=None, company_id=1)
    assert r["count"] == 1
    from backend.db import get_conn
    other = get_conn()
    try:
        cnt = other.execute(
            "SELECT COUNT(*) FROM notifications WHERE type='mention'"
        ).fetchone()[0]
    finally:
        other.close()
    assert cnt == 1


# ============================================================
# add_post_attachment
# ============================================================

def test_add_attachment_author_success(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "资料.pdf",
                            "https://pan.example.com/x.pdf",
                            author, conn=conn, company_id=1)
    assert r["success"] is True
    assert isinstance(r["attachment_id"], int)
    assert r["file_name"] == "资料.pdf"
    assert r["url"] == "https://pan.example.com/x.pdf"
    row = conn.execute(
        "SELECT post_id, file_name, url FROM post_attachments WHERE id=?",
        (r["attachment_id"],),
    ).fetchone()
    assert row["post_id"] == post_id
    assert row["file_name"] == "资料.pdf"
    assert row["url"] == "https://pan.example.com/x.pdf"


def test_add_attachment_admin_success(conn):
    """管理员可代上传（即使非作者）。"""
    author = make_user(conn, "author", "apprentice", company_id=1)
    admin = make_user(conn, "admin1", "admin", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "doc.pdf", "https://x/y.pdf", admin, conn=conn, company_id=1)
    assert r["success"] is True


def test_add_attachment_other_user_forbidden(conn):
    """非作者、非管理员无权重试 → 失败，不写表。"""
    author = make_user(conn, "author", "apprentice", company_id=1)
    other = make_user(conn, "other", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "x.pdf", "https://x/y.pdf", other, conn=conn, company_id=1)
    assert r["success"] is False
    assert "无权" in r["message"] or "仅作者" in r["message"]
    cnt = conn.execute("SELECT COUNT(*) FROM post_attachments").fetchone()[0]
    assert cnt == 0


def test_add_attachment_cross_tenant_rejected(conn):
    """跨公司身份访问 → 失败。"""
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "x.pdf", "https://x/y.pdf", author, conn=conn, company_id=2)
    assert r["success"] is False
    assert "跨租户" in r["message"] or "不存在" in r["message"]


def test_add_attachment_invalid_url(conn):
    """非 http(s)、过长、空 url → 拒绝。"""
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    for bad in ["", "   ", "ftp://x/y", "javascript:alert(1)", "x" * 3000]:
        r = add_post_attachment(post_id, "f.pdf", bad, author, conn=conn, company_id=1)
        assert r["success"] is False, f"应拒绝 url={bad!r}"
    cnt = conn.execute("SELECT COUNT(*) FROM post_attachments").fetchone()[0]
    assert cnt == 0


def test_add_attachment_empty_filename(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "", "https://x/y.pdf", author, conn=conn, company_id=1)
    assert r["success"] is False
    r = add_post_attachment(post_id, "   ", "https://x/y.pdf", author, conn=conn, company_id=1)
    assert r["success"] is False


def test_add_attachment_post_not_exist(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    r = add_post_attachment(99999, "x.pdf", "https://x/y.pdf", author, conn=conn, company_id=1)
    assert r["success"] is False
    assert "不存在" in r["message"]


def test_add_attachment_url_whitespace_stripped(conn):
    """url 前后空白自动去除。"""
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r = add_post_attachment(post_id, "a.pdf", "  https://x/y.pdf  ", author,
                            conn=conn, company_id=1)
    assert r["success"] is True
    assert r["url"] == "https://x/y.pdf"


# ============================================================
# get_post_attachments
# ============================================================

def test_get_attachments_returns_list(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    add_post_attachment(post_id, "b.pdf", "https://x/b.pdf", author, conn=conn, company_id=1)
    r = get_post_attachments(post_id, conn=conn, company_id=1)
    assert r["success"] is True
    assert len(r["attachments"]) == 2
    assert [a["file_name"] for a in r["attachments"]] == ["a.pdf", "b.pdf"]


def test_get_attachments_cross_tenant_empty(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    r = get_post_attachments(post_id, conn=conn, company_id=999)
    assert r["success"] is False
    assert r["attachments"] == []


def test_get_attachments_post_not_exist(conn):
    r = get_post_attachments(99999, conn=conn, company_id=1)
    assert r["success"] is False
    assert r["attachments"] == []


# ============================================================
# delete_post_attachment
# ============================================================

def test_delete_attachment_by_author(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r1 = add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    aid = r1["attachment_id"]
    r2 = delete_post_attachment(aid, author, conn=conn, company_id=1)
    assert r2["success"] is True
    cnt = conn.execute("SELECT COUNT(*) FROM post_attachments WHERE id=?", (aid,)).fetchone()[0]
    assert cnt == 0


def test_delete_attachment_by_admin(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    admin = make_user(conn, "admin1", "admin", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r1 = add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    aid = r1["attachment_id"]
    r2 = delete_post_attachment(aid, admin, conn=conn, company_id=1)
    assert r2["success"] is True
    cnt = conn.execute("SELECT COUNT(*) FROM post_attachments WHERE id=?", (aid,)).fetchone()[0]
    assert cnt == 0


def test_delete_attachment_other_user_forbidden(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    other = make_user(conn, "other", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r1 = add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    aid = r1["attachment_id"]
    r2 = delete_post_attachment(aid, other, conn=conn, company_id=1)
    assert r2["success"] is False
    assert "仅作者" in r2["message"]
    cnt = conn.execute("SELECT COUNT(*) FROM post_attachments WHERE id=?", (aid,)).fetchone()[0]
    assert cnt == 1


def test_delete_attachment_not_exist(conn):
    r = delete_post_attachment(99999, 1, conn=conn, company_id=1)
    assert r["success"] is False
    assert "不存在" in r["message"]


def test_delete_attachment_cross_tenant(conn):
    author = make_user(conn, "author", "apprentice", company_id=1)
    post_id = _make_post(conn, author, company_id=1)
    r1 = add_post_attachment(post_id, "a.pdf", "https://x/a.pdf", author, conn=conn, company_id=1)
    aid = r1["attachment_id"]
    r2 = delete_post_attachment(aid, author, conn=conn, company_id=999)
    assert r2["success"] is False
    assert "跨租户" in r2["message"]
