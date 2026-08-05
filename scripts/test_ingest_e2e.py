"""P1 ingest 端到端验证：模拟师傅投喂一个 .py 文件，验证不再向量化失败。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'c:\Users\TS\Downloads\薪火_TSForce_MentorAI')

from backend.config import settings
from backend.db import init_db, get_conn
from backend.vectorstore import VectorStore
from backend.ingest import ingest_local_path

# 用临时 DB
import backend.db as dbmod
tmp = Path(tempfile.mkdtemp()) / 'test.db'
dbmod.DB_PATH = tmp
init_db().close()

# 拿一个 demo_master 风格的师傅
conn = get_conn()
from backend.auth import hash_password
conn.execute(
    "INSERT INTO users (username, password_hash, role, company_id, status) "
    "VALUES (?, ?, 'master', 1, 'approved')",
    ('demo_master', hash_password('123456')))
conn.commit()
master_id = conn.execute("SELECT id FROM users WHERE username='demo_master'").fetchone()['id']
kb_id = conn.execute(
    "INSERT INTO knowledge_bases (master_id, company_id, name) VALUES (?, 1, 'test_kb')",
    (master_id,)).lastrowid
conn.commit()

# 准备一个临时 .py 文件
src_dir = Path(tempfile.mkdtemp())
(src_dir / 'hello.py').write_text(
    'def hello():\n    """智能订单交易系统。订单幂等、分布式事务。"""\n    return 42\n',
    encoding='utf-8',
)

# 投喂
store = VectorStore()
result = ingest_local_path(master_id, kb_id, str(src_dir), store)
print('ingest result:', result['message'])
print('doc_count:', result['doc_count'])
print('chunk_count:', result['chunk_count'])
assert '向量化失败' not in result['message'], '仍然向量化失败！'
print('OK：本地检索链路打通')
