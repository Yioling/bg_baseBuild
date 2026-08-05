"""
pytest公共夹具：提供指向临时SQLite库的数据库连接（不依赖外网/LLM）。

启动时自动创建预置用户（admin / demo_master），与 main.py startup 行为一致。
"""
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import backend.db as dbmod
from backend.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """在所有测试开始前创建临时数据库、初始化表结构、预置种子用户。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dbmod.DB_PATH = Path(tmp.name)

    # init_db 返回的 conn 必须关闭
    _conn = dbmod.init_db()
    _conn.close()

    # 预置种子数据（与 main.py startup 行为一致）
    from backend.auth import hash_password
    conn = dbmod.get_conn()
    if not conn.execute("SELECT id FROM companies WHERE id=1").fetchone():
        conn.execute("INSERT INTO companies (id, name) VALUES (1, '示例公司（Demo）')")
    if not conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, company_id, status) "
            "VALUES (?, ?, 'admin', '系统管理员', 1, 'approved')",
            ("admin", hash_password("admin123")),
        )
    if not conn.execute("SELECT id FROM users WHERE role='master' LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO users (username, password_hash, role, company_id, status) "
            "VALUES (?, ?, 'master', 1, 'approved')",
            ("demo_master", hash_password("123456")),
        )
    conn.execute("UPDATE users SET company_id=1 WHERE company_id IS NULL")

    # 预置知识库（避免测试中投喂导致 fastembed 持锁）
    if not conn.execute("SELECT id FROM knowledge_bases WHERE master_id=2 LIMIT 1").fetchone():
        master_id = conn.execute("SELECT id FROM users WHERE username='demo_master'").fetchone()["id"]
        conn.execute("INSERT INTO knowledge_bases (master_id, company_id, name) VALUES (?, 1, '默认知识库')", (master_id,))
        kb_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO kb_documents (kb_id, filename, raw_text) VALUES (?, 'demo.txt', '智能订单交易系统演示文档。交易链路、幂等设计、分布式事务。')",
            (kb_id,))
        conn.execute(
            "INSERT INTO kb_sources (kb_id, source_type, location, title) VALUES (?, 'file', 'demo.txt', '示例文档')",
            (kb_id,))
    conn.commit()

    yield
    # 测试结束后删除临时文件
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


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
