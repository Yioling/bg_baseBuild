"""
pytest公共夹具：提供指向临时SQLite库的数据库连接（不依赖外网/LLM）。

启动时自动创建预置用户（admin / demo_master），与 main.py startup 行为一致。
每个测试函数执行前自动重置业务数据（保留种子数据），消除跨测试状态污染。
"""
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import backend.db as dbmod
from backend.main import app


def _seed_data(conn):
    """插入种子数据：公司、admin、demo_master、默认知识库。

    与 main.py startup 行为一致；id 固定（admin=1, demo_master=2），
    便于测试断言与 test_p1_integration 等依赖。
    """
    from backend.auth import hash_password
    # 幂等插入：init_db 可能已预置 id=1 的公司，用 OR IGNORE 避免冲突
    conn.execute(
        "INSERT OR IGNORE INTO companies (id, name) VALUES (1, '示例公司（Demo）')"
    )
    # 先清掉可能存在的 admin/demo_master 旧记录（改用固定 id）
    conn.execute("DELETE FROM users WHERE id IN (1, 2)")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, full_name, company_id, status) "
        "VALUES (1, 'admin', ?, 'admin', '系统管理员', 1, 'approved')",
        (hash_password("admin123"),),
    )
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, company_id, status) "
        "VALUES (2, 'demo_master', ?, 'master', 1, 'approved')",
        (hash_password("123456"),),
    )
    # 预置知识库（避免测试中投喂导致 fastembed 持锁）
    conn.execute("DELETE FROM knowledge_bases WHERE id=1")
    conn.execute(
        "INSERT INTO knowledge_bases (id, master_id, company_id, name) VALUES (1, 2, 1, '默认知识库')"
    )
    conn.execute(
        "INSERT INTO kb_documents (kb_id, filename, raw_text) VALUES (1, 'demo.txt', '智能订单交易系统演示文档。交易链路、幂等设计、分布式事务。')"
    )
    conn.execute(
        "INSERT INTO kb_sources (kb_id, source_type, location, title) VALUES (1, 'file', 'demo.txt', '示例文档')"
    )


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """在所有测试开始前创建临时数据库、初始化表结构。

    同时强制 MOCK_MODE=true，保证整个测试会话的 LLM 调用走 mock 兜底，
    不依赖外网/Key，且行为可预测（个别测试可用 monkeypatch 临时覆盖）。
    """
    os.environ["MOCK_MODE"] = "true"
    # settings 在导入时缓存了 MOCK_MODE，需同步覆盖类属性，确保整个测试会话走 mock
    from backend.config import settings as _settings
    _settings.MOCK_MODE = "true"
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dbmod.DB_PATH = Path(tmp.name)

    # init_db 返回的 conn 必须关闭
    _conn = dbmod.init_db()
    _conn.close()

    # 初始种子数据
    conn = dbmod.get_conn()
    _seed_data(conn)
    conn.commit()
    conn.close()

    yield
    # 测试结束后删除临时文件
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


# 业务表清单（按外键安全顺序）；sqlite_% 系统表与 sqlite_sequence 不在此列。
# 注意：companies / users(id 1,2) / knowledge_bases(1) 为种子数据，不在此清空。
_RESET_TABLES = [
    "post_likes",
    "post_comments",
    "post_attachments",
    "company_posts",
    "notifications",
    "admin_logs",
    "password_resets",
    "login_attempts",
    "daily_progress",
    "quizzes",
    "review_questions",
    "daily_reviews",
    "plan_tasks",
    "plan_days",
    "study_plans",
    "plan_items",
    "plans",
    "courses",
    "course_questions",
    "departments",
    "mastery",
    "assessment_answers",
    "assessment_questions",
    "assessments",
    "knowledge_points",
    "dimensions",
    "vector_chunks",
    "chat_history",
]
# 注意：kb_documents / kb_sources 是种子 KB 的文档数据，保留不清空，
# 避免破坏 E2E refine 流程（refine 检查 kb_documents 非空）。


@pytest.fixture(autouse=True)
def _reset_db(request):
    """每个测试函数前自动重置业务表数据，保留种子数据（公司/admin/demo_master/默认KB）。

    消除跨测试状态污染：之前 session-scoped DB 导致 test_courses/test_progress/
    test_account_security/test_notifications/test_social 等的 COUNT/列表断言失败。

    实现：DELETE 所有业务表（种子数据所在表单独按条件清理），再重置
    sqlite_sequence，保证 AUTOINCREMENT 从 1 开始，使测试对 id 可预测。

    例外：TestE2EDemoFlow 是顺序端到端测试，步骤间需要状态传递
    （step03 精炼的 dimensions 要留给 step03b/step06 用），故跳过清理。
    """
    # E2E 顺序测试需要状态在步骤间传递，跳过清理
    cls_name = request.cls.__name__ if request.cls else None
    if cls_name == "TestE2EDemoFlow":
        yield
        return
    conn = dbmod.get_conn()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for t in _RESET_TABLES:
            conn.execute(f'DELETE FROM "{t}"')
        # 清理非种子用户（保留 id 1=admin, 2=demo_master）
        conn.execute("DELETE FROM users WHERE id NOT IN (1, 2)")
        # 重置自增序列，保证测试中插入的 id 可预测
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ("
            "'companies','users','knowledge_bases','courses','plans','plan_items',"
            "'quizzes','daily_progress','company_posts','post_comments','post_likes',"
            "'post_attachments','notifications','admin_logs','password_resets',"
            "'login_attempts','dimensions','knowledge_points','assessments',"
            "'assessment_questions','assessment_answers','mastery','study_plans',"
            "'plan_days','plan_tasks','daily_reviews','review_questions','chat_history',"
            "'vector_chunks','kb_documents','kb_sources','departments','course_questions'"
            ")"
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()
    yield


@pytest.fixture
def client():
    """返回 FastAPI TestClient 实例"""
    return TestClient(app)


@pytest.fixture
def conn():
    """返回指向临时数据库的 SQLite 连接，测试结束后自动关闭。"""
    c = dbmod.get_conn()
    yield c
    c.close()
