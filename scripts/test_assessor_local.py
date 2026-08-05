"""P1 验证：LLM 返空时，generate_assessment 自动降级到本地出题。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'c:\Users\TS\Downloads\薪火_TSForce_MentorAI')

import backend.db as dbmod
tmp = Path(tempfile.mkdtemp()) / 'test.db'
dbmod.DB_PATH = tmp
dbmod.init_db().close()

from backend.db import get_conn
from backend.auth import hash_password
from backend.agents.assessor import generate_assessment, _local_generate_questions

conn = get_conn()
conn.execute(
    "INSERT INTO users (username, password_hash, role, company_id, status) VALUES (?, ?, 'master', 1, 'approved')",
    ('m', hash_password('x')))
conn.execute("INSERT INTO knowledge_bases (master_id, company_id, name) VALUES (1, 1, 'kb1')")
conn.execute("INSERT INTO dimensions (kb_id, name, description, sort_order) VALUES (1, '交易链路', '下单→支付→履约', 0)")
conn.execute("INSERT INTO dimensions (kb_id, name, description, sort_order) VALUES (1, '幂等设计', '防止重复下单', 1)")
conn.execute(
    "INSERT INTO knowledge_points (dimension_id, title, content, level) VALUES (1, '订单状态机', '理解状态流转', '熟练')")
conn.commit()

# 1) generate_assessment（应触发本地降级，因为真实 LLM 返空）
r = generate_assessment(1, 1)
print('===== generate_assessment =====')
print('success:', r.get('success'))
print('questions count:', len(r.get('questions', [])))
if r.get('questions'):
    q = r['questions'][0]
    print('first q:', q.get('question')[:60], '...')
    print('  dim:', q.get('dimension_name'), 'type:', q.get('qtype'))
    print('  has answer_key:', bool(q.get('answer_key')), 'has options:', bool(q.get('options')))

# 2) grade_answer 走本地粗评
print()
print('===== grade_answer (local) =====')
from backend.agents.assessor import grade_answer, _local_grade
if r.get('questions'):
    qid = r['questions'][0]['id']
    aid = r['assessment_id']
    grade = grade_answer(qid, '订单状态机 是 下单→支付→履约 的核心要点。', aid)
    print('grade result:', grade)

# 3) 直接调 _local_grade（选择题/简答）
print()
print('===== _local_grade choice =====')
g1 = _local_grade('A', {'qtype': 'choice', 'answer_key': 'A'})
print(g1)
g2 = _local_grade('B', {'qtype': 'choice', 'answer_key': 'A'})
print(g2)

print('===== _local_grade short =====')
g3 = _local_grade('包含关键点 订单状态机 与 下单→支付→履约。',
                  {'qtype': 'short', 'answer_key': '订单状态机；下单→支付→履约'})
print(g3)
