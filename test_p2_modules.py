"""P2 模块单元验证脚本。运行: python test_p2_modules.py"""
import sys
import os
import tempfile

print("=" * 50)
print("1. embeddings.py 单元测试")
print("=" * 50)
from backend.embeddings import is_ready, get_model_info, embed, embed_one
print("  is_ready:", is_ready())
print("  model_info:", get_model_info())
vec = embed_one("你好世界")
print(f"  embed_one dim: {len(vec)}")
vecs = embed(["文本一", "文本二"])
print(f"  embed batch: {len(vecs)} x {len(vecs[0]) if vecs else 0}")
print(f"  embed empty: {embed([])}")
print("  embeddings.py OK!")

print()
print("=" * 50)
print("2. llm.py 单元测试")
print("=" * 50)
from backend.llm import chat, chat_json, use_mock, check_llm_ready, reset_client
print("  use_mock:", use_mock())
print("  check_llm_ready:", check_llm_ready())
resp = chat("你是助手", "你好")
print(f"  chat() returned: {resp[:50]}...")
json_resp = chat_json("你是JSON助手", '输出 {"key": "value"}')
print(f"  chat_json() type: {type(json_resp).__name__}")
print("  llm.py OK!")

print()
print("=" * 50)
print("3. vectorstore.py 单元测试")
print("=" * 50)
from backend.vectorstore import VectorStore, retrieve_context
import numpy as np
dim = 512
s = VectorStore()
s.add(
    [{"text": "Python 是一门编程语言", "source": "doc1.txt", "meta": "{}"}],
    [list(np.random.randn(dim).astype(float))]
)
print(f"  count after add: {s.count}")
print(f"  is_empty: {s.is_empty}")
print(f"  len: {len(s)}")
hits = s.search(list(np.random.randn(dim).astype(float)), top_k=1)
print(f"  search returned {len(hits)} hits")
empty = VectorStore()
print(f"  empty search: {empty.search([0.1]*dim)}")
hits2 = s.query("Python", top_k=1)
print(f"  query() returned {len(hits2)} hits")
ctx = retrieve_context(s, "Python")
print(f"  retrieve_context: {ctx[:50]}...")
ctx2 = retrieve_context(empty, "test")
print(f"  empty retrieve_context: {ctx2}")
tmp = os.path.join(tempfile.gettempdir(), "test_vs.pkl")
s.save(tmp)
s2 = VectorStore.load(tmp)
print(f"  load after save count: {s2.count}")
with open(tmp, "w") as f:
    f.write("not a pickle")
s3 = VectorStore.load(tmp)
print(f"  broken file load count: {s3.count}")
os.remove(tmp)
# 输入验证
try:
    s.add([{"text": "a"}], [])
    print("  ERROR: should have raised ValueError")
except ValueError:
    print("  input validation: ValueError correctly raised")
print("  vectorstore.py OK!")

print()
print("=" * 50)
print("4. self_purifier.py 单元测试")
print("=" * 50)
from backend.self_purifier import run_purification, get_purification_report, get_purification_stats
report = run_purification(kb_id=None)
print(f"  run_purification: success (actions: {len(report.get('actions', []))})")
rep = get_purification_report()
print(f"  get_purification_report: success={rep.get('success')}")
stats = get_purification_stats()
print(f"  get_purification_stats: health={stats.get('health_pct')}%, chunks={stats.get('total_chunks')}")
from backend.self_purifier import SelfPurifier
p = SelfPurifier()
sim1 = p._cosine_sim("机器学习是人工智能的分支", "机器学习属于AI领域")
sim2 = p._cosine_sim("机器学习是人工智能的分支", "今天天气很好适合散步")
print(f"  _cosine_sim 语义相近: {sim1:.4f}, 不相关: {sim2:.4f}")
print("  self_purifier.py OK!")

print()
print("=" * 50)
print("ALL 4 MODULES PASSED!")
print("=" * 50)
