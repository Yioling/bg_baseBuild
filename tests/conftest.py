"""
pytest公共夹具：提供指向临时SQLite库的数据库连接（不依赖外网/LLM）。
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
    """在所有测试开始前创建临时数据库并初始化"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dbmod.DB_PATH = Path(tmp.name)
    dbmod.init_db()
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