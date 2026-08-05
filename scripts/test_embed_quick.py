"""P1 临时验证脚本：跑通新本地 embeddings + 向量库检索链路。

非测试用例，工程内一次性脚本。可手动执行验证后删除。
"""
import sys
sys.path.insert(0, r'c:\Users\TS\Downloads\薪火_TSForce_MentorAI')

from backend.embeddings import embed, embed_one, embedding_dim
from backend.vectorstore import VectorStore
import numpy as np

# 1) 直接嵌入
texts = [
    '智能订单交易系统采用分布式架构',
    '订单幂等设计与事务一致性',
    '分布式系统的高可用方案',
    'hello world',
]
v = embed(texts)
print('dim:', embedding_dim(), 'count:', len(v))
m = np.array(v)
print('sim(text0, text1):', float(m[0] @ m[1]))
print('sim(text0, text2):', float(m[0] @ m[2]))
print('sim(text0, text3):', float(m[0] @ m[3]))  # 应较低

# 2) 通过 VectorStore 检索
store = VectorStore()
items = [{'text': t, 'source': f'doc{i}', 'meta': '{}'} for i, t in enumerate(texts)]
store.add(items, v)
qvec = embed_one('订单事务一致性')
hits = store.search(qvec, top_k=2)
print('hits:', [(h['source'], h['score']) for h in hits])
print('OK')
