"""pytest 公共夹具：提供指向临时 SQLite 库的数据库连接（不依赖外网/LLM）。"""
import os
import tempfile
from pathlib import Path

import pytest

import backend.db as dbmod


@pytest.fixture
def conn():
    """每个测试独立临时库，避免污染真实数据（也不依赖外部服务）。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dbmod.DB_PATH = Path(tmp.name)
    c = dbmod.init_db()
    yield c
    c.close()
    try:
        os.unlink(tmp.name)
    except OSError:
        pass
