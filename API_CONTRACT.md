# P2 API_CONTRACT — AI 底座接口文档

> **维护者**: TS（P2） | **更新**: 2026-07-30 | **分支**: `origin/p2`
>
> **给 AI 读的**：每个接口给定了精确 import、调用方式、返回值结构、错误行为。
> **给人读的**：第五章按你的模块告诉你要 import 什么，第六章是演示模式速查。

---

## 速查卡片

### LLM 调用
```python
from backend.llm import chat, chat_json, use_mock

text  = chat("你是导师", "问题", temperature=0.3, max_tokens=1600)
obj   = chat_json("你是出题官", "输出JSON: {...}")
mock  = use_mock()  # True=演示模式 False=真实LLM
```

### 文本嵌入
```python
from backend.embeddings import embed, embed_one

vecs  = embed(["文本1","文本2"])          # → list[list[float]]  512维
vec   = embed_one("单个文本")             # → list[float]        512维
```

### 向量检索
```python
from backend.vectorstore import VectorStore, retrieve_context

store = VectorStore.load("path.pkl")      # 从磁盘加载，不存在返回空库
store.add(items, vectors)                 # items: [{"text","source","meta"},...]
hits  = store.search(vec, top_k=5)        # → [{"text","source","score":0.95},...]
hits  = store.query("自然语言", top_k=5)  # 等价于 embed+search 一步完成
ctx   = retrieve_context(store, "问题", top_k=5)  # → 拼好的上下文字符串
store.save("path.pkl")
```

### 知识库净化（仅 P5 用）
```python
from backend.self_purifier import run_purification, get_purification_report, get_purification_stats

run_purification(kb_id=None)       # → dict
get_purification_report()          # → dict
get_purification_stats()           # → {"total_chunks":N, "health_pct":98.5,...}
```

---

## 一、`backend/llm.py` — LLM 客户端

### 1.1 `chat()` — 调大模型拿文本

```python
from backend.llm import chat

answer: str = chat(
    system: str,       # 系统提示词
    user: str,         # 用户输入
    *,
    temperature: float = 0.3,
    max_tokens: int = 1600
) -> str
```

**返回值**：纯文本字符串。永远不会抛异常。

**错误行为（对调用方透明）**：
1. 没配 API Key → 自动走演示模式，返回内置示例文本
2. API 网络超时 → 自动重试 3 次（间隔 0.5s / 1s / 2s）
3. 3 次全失败 → 降级到演示模式

**真实代码示例（来自现有 Agent）**：
```python
# assessor.py / reviewer.py 批改模式
from backend.llm import chat

answer = chat(
    "你是技术审查专家。判断两段知识是否矛盾，只回答YES或NO。",
    f"文本A: {text_a[:500]}\n文本B: {text_b[:500]}\n是否存在矛盾？",
    temperature=0.1,
    max_tokens=10
)
```

```python
# tutor.py RAG陪练模式
from backend.llm import chat

answer = chat(
    TUTOR_SYSTEM,  # "你是薪火导师..." 长提示词
    f"参考资料：\n{context}\n\n徒弟提问：{question}",
    temperature=0.5,
    max_tokens=800
)
```

### 1.2 `chat_json()` — 调大模型拿结构化数据

```python
from backend.llm import chat_json

result: dict | list = chat_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.2
)
```

**返回值**：Python dict 或 list。解析失败返回 `{}`（空 dict）。

**JSON 解析降级链**（全自动，不用管）：
```
原始输出 → 去 ```json 围栏 → json.loads() → 括号匹配截取 → {}
```

**真实代码示例**：
```python
# assessor.py 出题模式
result = chat_json(ASSESS_SYSTEM, f"基于以下知识维度出摸底考试题：\n{dims_json}")
# result = {"questions": [{"question": "...", "qtype": "choice", ...}, ...]}

# planner.py 计划生成
result = chat_json(PLAN_SYSTEM, f"根据掌握情况生成学习计划：\n{dims_json}")
# result = {"plan_overview": "...", "days": [{"day_index": 1, "tasks": [...]}, ...]}
```

### 1.3 `use_mock()` — 判断是否演示模式

```python
from backend.llm import use_mock

if use_mock():
    # 当前在演示模式，可以跳过 LLM 消耗大的操作
    pass
```

### 1.4 `check_llm_ready()` — 诊断（管理后台用）

```python
from backend.llm import check_llm_ready

status = check_llm_ready()
# {"ready": True, "mode": "live", "message": "已连接: https://api.deepseek.com/v1"}
# 或
# {"ready": True, "mode": "mock", "message": "演示模式..."}
```

### 1.5 异步版本（可选）

```python
from backend.llm import achat, achat_json

# 仅 async def 路由用，def 路由直接用 chat()
text = await achat(system, user, temperature=0.3, max_tokens=1600)
obj  = await achat_json(system, user, temperature=0.2)
```

---

## 二、`backend/embeddings.py` — 本地中文嵌入

### 2.1 `embed()` — 批量文本→向量

```python
from backend.embeddings import embed

vectors: list[list[float]] = embed(texts: list[str])
```

| 输入 | 输出 |
|------|------|
| `["文本1", "文本2"]` | `[[0.12,-0.34,...], [0.56,0.78,...]]` 各 512 维 |
| `[]` | `[]` |
| `["", "文本"]` | `[[0.0]*512, [0.12,-0.34,...]]`（空字符串零向量占位） |

**模型策略**：
- 优先用 `.env` 配置的模型
- 不可用 → 自动降级 `BAAI/bge-small-zh-v1.5`（首跑自动下载 ~90MB）
- 再失败 → 抛 `RuntimeError`

### 2.2 `embed_one()` — 单个文本→向量

```python
from backend.embeddings import embed_one

vec: list[float] = embed_one("单个文本")  # 等价于 embed([text])[0]
```

### 2.3 `is_ready()` / `get_model_info()` — 状态检查

```python
from backend.embeddings import is_ready, get_model_info

is_ready()        # → True/False
get_model_info()  # → {"configured_model":"...","active_model":"...","ready":True}
```

---

## 三、`backend/vectorstore.py` — 向量库

### 3.1 `VectorStore` — 类完整签名

```python
from backend.vectorstore import VectorStore

class VectorStore:
    # 创建 / 加载
    def __init__(self) -> None
    @classmethod
    def load(cls, path: str | Path) -> "VectorStore"

    # 写入（线程安全）
    def add(self, items: list[dict], vectors: list[list[float]]) -> None
        # items 格式: [{"text": str, "source": str, "meta": str}, ...]
        # 要求: len(items) == len(vectors)，否则抛 ValueError

    # 检索（线程安全）
    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]
        # 返回: [{"id":0, "text":"...", "source":"...", "meta":"...", "score":0.95}, ...]
        # 空库返回 []

    def query(self, text: str, top_k: int = 5) -> list[dict]
        # 等价于 embed_one(text) → search(vec, top_k)

    # 持久化（原子写入）
    def save(self, path: str | Path) -> None

    # 属性
    count: int       # 文档数
    is_empty: bool   # 是否为空
```

### 3.2 `retrieve_context()` — RAG 一步到位

```python
from backend.vectorstore import retrieve_context

context: str = retrieve_context(store: VectorStore, query: str, top_k: int = 5)
```

**返回值格式**：
```
[来源: doc1.md]
幂等设计是指在分布式系统中...

[来源: doc2.md]
实现幂等的常见方案有...
```

空库时返回：`"（知识库暂无相关内容）"`

### 3.3 如何获取 `store` 实例

**P3/P4 的 Agent 函数**：`store` 由调用方（main.py 的路由）传入，函数签名里接收即可：

```python
# tutor.py 已有的写法（不用改）：
def ask(apprentice_id: int, kb_id: int, question: str, store: VectorStore) -> dict:
    context = retrieve_context(store, question, top_k=4)
    ...

# ingest.py 已有的写法（不用改）：
def ingest_local_path(master_id: int, kb_id: int, path_str: str, store: VectorStore) -> dict:
    vectors = embed([c["text"] for c in chunks])
    store.add(chunks, vectors)
    store.save(settings.STORE_PATH)
    ...
```

### 3.4 ⚠️ 常见错误

```python
# ❌ 错误：直接把 query 文本传给 search()
store.search("什么是幂等", top_k=5)  # search 需要向量，不是文本！

# ✅ 正确：用 query()（自动嵌入）
store.query("什么是幂等", top_k=5)

# ✅ 正确：手动嵌入
vec = embed_one("什么是幂等")
store.search(vec, top_k=5)
```

---

## 四、`backend/self_purifier.py` — 知识库自净化

### 仅 P5（main.py）调用，其他人不需要

```python
from backend.self_purifier import (
    run_purification,         # def(kb_id: int = None) -> dict
    get_purification_report,  # def() -> dict
    get_purification_stats,   # def() -> dict
)
```

`main.py` 中已有的装配方式（P5 照搬即可）：

```python
@app.post("/api/admin/purify")
def api_run_purification(data: dict = None, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from backend.self_purifier import run_purification
    kb_id = data.get("kb_id") if data else None
    report = run_purification(kb_id)
    return {"success": True, "report": report}

@app.get("/api/admin/purify/report")
def api_purification_report(user: dict = Depends(auth_user)):
    from backend.self_purifier import get_purification_report
    return get_purification_report()

@app.get("/api/admin/purify/stats")
def api_purification_stats(user: dict = Depends(auth_user)):
    from backend.self_purifier import get_purification_stats
    return get_purification_stats()
```

---

## 五、按团队分发的 Import 清单

### P3 — 智能体开发（assessor / tutor / planner / reviewer / refiner）

```python
# ===== 每个 Agent 的标准头部 =====
from backend.llm import chat, chat_json, use_mock
from backend.db import get_conn         # P1 提供
# ===== 仅 tutor.py 额外需要 =====
from backend.vectorstore import retrieve_context
```

**你不需要** `import embeddings` 或 `import VectorStore`。

**store 对象**由 main.py 的路由传给你的函数，声明参数 `store: VectorStore` 接收即可。

### P4 — 资料摄取 & PDF（ingest.py / pdf_gen.py）

```python
# ===== ingest.py =====
from backend.embeddings import embed
from backend.vectorstore import VectorStore
from backend.db import get_conn              # P1 提供
from backend.config import settings          # P1 提供

# ===== pdf_gen.py =====
from backend.llm import chat, use_mock
from backend.vectorstore import retrieve_context
```

### P5 — API 路由 & 前端（main.py）

```python
from backend.vectorstore import VectorStore
from backend.self_purifier import (
    run_purification,
    get_purification_report,
    get_purification_stats,
)
```

### P1 — 数据库 & 认证（db / auth / schemas / config）

不需要 import P2 的任何东西。只需确保 `.env` / `config.py` 里的配置项存在即可（见第七章）。

---

## 六、演示模式（无 Key 兜底）— P3 必读

没配 `LLM_API_KEY` 时，`chat()` 不进真实大模型，按 `user` 参数的关键词返回内置示例。

**当前覆盖范围（`backend/llm.py` → `_mock_chat()`）**：

| 你的 Agent | user 里包含 | 返回格式 |
|-----------|------------|---------|
| Refiner 精炼 | "知识图谱" / "课程大纲" / "抽取" | `{"project_summary":"...", "knowledge_points":[...]}` |
| Planner 计划 | "学习路径" / "培养计划" | 纯文本：4 周学习路径 |
| Assessor/Reviewer | "测验" / "题目" / "出题" | `[{"question":"...", "type":"简答", "answer_key":"..."}]` |
| Tutor / 其他 | 以上都不匹配 | `（演示模式）我是你的 AI 导师...` |

**如果你新增了 Agent 场景**（比如 user 里有新的关键词），来 P2 这加一个 `if` 分支：
```python
# 在 _mock_chat() 里加：
if "你的关键词" in user:
    return json.dumps({...})  # 或 return "纯文本"
```

---

## 七、配置项参考（P1 维护，P2 读取）

`.env` 或 `config.py` 中的这些配置会影响 P2 行为：

| 配置项 | 默认值 | P2 读取位置 | 说明 |
|--------|--------|-----------|------|
| `LLM_API_KEY` | `""` | `llm.py` | 为空 → 演示模式 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | `llm.py` | OpenAI 兼容地址 |
| `LLM_MODEL` | `deepseek-chat` | `llm.py` | 模型名 |
| `EMBEDDING_MODEL` | `jinaai/jina-embeddings-v2-small-zh` | `embeddings.py` | 不可用时自动降级 `BAAI/bge-small-zh-v1.5` |
| `MOCK_MODE` | `auto` | `llm.py` | `true`=强开演示 `false`=强制真实 `auto`=自动检测 |
| `STORE_PATH` | `backend/data/vectorstore.pkl` | `vectorstore.py` | 向量库持久化路径 |

---

## 八、各团队自检清单

改完代码后跑一遍，确认对接没问题：

```bash
# P2 基础健康检查（全部团队通用）
python -c "
from backend.llm import chat, chat_json, use_mock, check_llm_ready
from backend.embeddings import embed, embed_one, is_ready
from backend.vectorstore import VectorStore, retrieve_context

# LLM 能调
print('LLM:', chat('你是助手','你好')[:30])
# 嵌入能用
print('Embed:', len(embed_one('测试')) == 512)
# 向量库能读写
s = VectorStore()
s.add([{'text':'hi','source':'t.txt','meta':'{}'}], [embed_one('hi')])
print('Search:', len(s.query('hi')) > 0)
print('ALL OK')
"
```

- [ ] 上述命令不报错
- [ ] 无 `.env` 时启动不崩
- [ ] 自己的 Agent 在演示模式下有合理返回（不白屏不报错）
- [ ] 自己的 Agent 在真实 Key 下正常返回
