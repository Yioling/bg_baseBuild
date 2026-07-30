# P2 模块接口契约 · API_CONTRACT.md

> **适用版本**: P2 分支 commit `2f0844f`+  
> **P2 负责人**: TS  
> **最后更新**: 2026-07-30

---

## 模块概览

P2 负责 4 个文件，是全部 AI 能力和知识检索的底座：

| 文件 | 职责 | 核心能力 |
|------|------|----------|
| `backend/llm.py` | LLM 客户端 | 调用大模型、演示模式兜底 |
| `backend/embeddings.py` | 本地中文嵌入 | 文本→向量 |
| `backend/vectorstore.py` | 向量库 | 向量存储、相似度检索 |
| `backend/self_purifier.py` | 知识库自净化 | 脏数据检测与清理 |

---

## 一、LLM 客户端 (`backend/llm.py`)

### 供 P3（Agent 智能体）、P5（ingest/pdf_gen）、管理员后台 使用

```python
from backend.llm import chat, chat_json, use_mock, check_llm_ready
```

#### 1.1 `chat()` — 同步调用 LLM（最常用）

```python
def chat(system: str, user: str, *, temperature: float = 0.3, max_tokens: int = 1600) -> str
```

- **system**: 系统提示词（角色设定）
- **user**: 用户输入/任务描述
- **返回**: LLM 回复的纯文本
- **行为**: 
  - 无 API Key → 自动进入演示模式，返回内置示例回答
  - API 调用失败 → 自动重试 3 次（指数退避），全失败则降级到演示模式

**使用示例（P3 Agent 写法）**：
```python
from backend.llm import chat, use_mock

answer = chat(
    "你是技术导师，用中文回答。",
    "请解释什么是幂等设计",
    temperature=0.5,
    max_tokens=800
)
```

#### 1.2 `chat_json()` — 调用 LLM 并解析 JSON

```python
def chat_json(system: str, user: str, *, temperature: float = 0.2) -> dict | list
```

- 在 `chat()` 基础上自动做 JSON 解析
- 内置多层降级：去掉 ```json 围栏 → 精确解析 → 括号匹配截取
- **返回**: Python dict 或 list（解析失败返回 `{}`）

**使用示例**：
```python
result = chat_json(
    "你是出题官，只输出 JSON。",
    '请出 3 道选择题。格式: {"questions": [...]}'
)
# result = {"questions": [...]}  # 直接可用
```

#### 1.3 `use_mock()` — 判断当前模式

```python
def use_mock() -> bool
```

- 返回 `True` 表示在演示模式（无真实 LLM）
- P3 Agent 可以用它决定是否跳过 LLM 消耗大的操作

#### 1.4 `check_llm_ready()` — 诊断接口（供管理后台）

```python
def check_llm_ready() -> dict
# 返回: {"ready": True/False, "mode": "mock"/"live", "message": "..."}
```

---

## 二、本地中文嵌入 (`backend/embeddings.py`)

### 供 P4（ingest 资料摄取）、P5（自净化）、向量库内部 使用

```python
from backend.embeddings import embed, embed_one, is_ready, get_model_info
```

#### 2.1 `embed()` — 批量嵌入

```python
def embed(texts: list[str]) -> list[list[float]]
```

- **输入**: 文本列表
- **输出**: 对应向量列表（每个是 512 维 float 列表）
- **特性**:
  - 空列表输入 → 返回 `[]`
  - 含空白字符串 → 对应位置返回零向量，不影响其他文本
  - 配置模型不可用 → 自动降级 `BAAI/bge-small-zh-v1.5`

#### 2.2 `embed_one()` — 单个嵌入

```python
def embed_one(text: str) -> list[float]
```

等价于 `embed([text])[0]`。

#### 2.3 `is_ready()` / `get_model_info()` — 状态检查

```python
def is_ready() -> bool               # 模型是否加载成功
def get_model_info() -> dict         # {"configured_model": "...", "active_model": "...", "ready": True/False}
```

---

## 三、向量库 (`backend/vectorstore.py`)

### 供 P5（main 全局实例）、P4（ingest 写入）、P3（tutor RAG） 使用

```python
from backend.vectorstore import VectorStore, retrieve_context
```

#### 3.1 `VectorStore` 类 — 核心

```python
class VectorStore:
    # --- 创建/加载 ---
    def __init__(self)                                  # 空库
    @classmethod
    def load(cls, path) -> VectorStore                  # 从磁盘加载（文件不存在返回空库）

    # --- 写入 ---
    def add(self, items: list[dict], vectors: list[list[float]])
        # items: [{"text": "文本", "source": "来源", "meta": "{}"}, ...]
        # vectors: 对应嵌入向量，数量必须与 items 一致

    # --- 检索 ---
    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]
        # 返回: [{"id": 0, "text": "...", "source": "...", "score": 0.95}, ...]

    def query(self, text: str, top_k: int = 5) -> list[dict]
        # 便利方法：输入自然语言文本，自动嵌入+检索

    # --- 持久化 ---
    def save(self, path)                               # 原子写入（不会损坏已有文件）

    # --- 属性 ---
    count: int                                         # 文档数量
    is_empty: bool                                     # 是否为空
```

#### 3.2 `retrieve_context()` — RAG 检索函数（供 P3 tutor）

```python
def retrieve_context(store: VectorStore, query: str, top_k: int = 5) -> str
```

- 一次调用完成：嵌入 query → 检索 top_k → 拼成带出处的上下文字符串
- 空库返回 `"（知识库暂无相关内容）"`

**使用示例（P3 tutor.py）**：
```python
from backend.vectorstore import retrieve_context

context = retrieve_context(store, "什么是幂等设计", top_k=4)
# context = "[来源: doc1.txt]\n幂等设计是指...\n\n[来源: doc2.txt]\n..."
```

#### 3.3 全局实例获取

`main.py` 中已提供全局实例（P5 负责装配，其他人不用管）：

```python
# main.py 中（不由你写，只是告诉 P5 怎么装配）：
from backend.vectorstore import VectorStore
from backend.config import settings

_store: VectorStore = None

def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore.load(settings.STORE_PATH)
    return _store
```

---

## 四、知识库自净化 (`backend/self_purifier.py`)

### 供 P5（main.py 管理员 API）调用

```python
from backend.self_purifier import run_purification, get_purification_report, get_purification_stats
```

#### 4.1 三个模块级函数

```python
def run_purification(kb_id: int = None) -> dict
    # 运行一次完整净化，返回报告
    # 异常时不抛错，返回 {"success": False, "message": "..."}

def get_purification_report() -> dict
    # 获取最近一次净化报告
    # 无记录时: {"success": True, "message": "暂无净化记录", "report": None}

def get_purification_stats() -> dict
    # 获取当前知识库健康统计
    # {"success": True, "total_chunks": N, "degraded_chunks": N, "health_pct": 98.5}
```

#### 4.2 对应的 API 端点（P5 在 main.py 中装配）

| 端点 | 调用函数 | 权限 |
|------|----------|------|
| `POST /api/admin/purify` | `run_purification(kb_id)` | admin |
| `GET /api/admin/purify/report` | `get_purification_report()` | admin |
| `GET /api/admin/purify/stats` | `get_purification_stats()` | admin |

---

## 五、各团队快速参考

### P1（后端核心：db/auth/schemas/config）

**不需要直接调用 P2**。但 config.py 中的 LLM/Embedding 配置会被 P2 读取：
- `settings.LLM_API_KEY` → 控制是否进入演示模式
- `settings.LLM_BASE_URL` / `settings.LLM_MODEL` → LLM 服务地址
- `settings.EMBEDDING_MODEL` → 嵌入模型名（默认 `jinaai/jina-embeddings-v2-small-zh`，如不可用自动降级）

### P3（智能体：assessor/tutor/planner/reviewer/refiner）

```python
# 每个 Agent 需要的 import：
from backend.llm import chat, chat_json, use_mock  # 调 LLM
# 仅 tutor.py 额外需要：
from backend.vectorstore import retrieve_context    # RAG 检索
```

不需要直接调 `embeddings.py` 或 `vectorstore.VectorStore`。

### P4（资料摄取 + PDF：ingest/pdf_gen）

```python
# ingest.py:
from backend.embeddings import embed                 # 批量嵌入文档块
from backend.vectorstore import VectorStore          # store.add(chunks, vectors)

# pdf_gen.py:
from backend.llm import chat, use_mock               # 生成讲义内容
from backend.vectorstore import retrieve_context     # 获取参考上下文
```

### P5（API 路由 + 前端：main/index.html）

```python
# main.py 需要：
from backend.vectorstore import VectorStore          # VectorStore.load(path)
from backend.self_purifier import (
    run_purification,                                # POST /api/admin/purify
    get_purification_report,                         # GET  /api/admin/purify/report
    get_purification_stats,                          # GET  /api/admin/purify/stats
)
```

---

## 六、常见问题

**Q: 没有配置 API Key 怎么办？**
A: P2 自动进入演示模式，`chat()` 返回内置示例回答，全流程可用。

**Q: 嵌入模型下载太慢？**
A: 首跑自动下载约 90MB，后续缓存。如需换模型，在 `.env` 设 `EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5`。

**Q: 向量库文件损坏了？**
A: `VectorStore.load()` 自动检测并返回空库（不抛异常），下次 `save()` 会覆盖损坏文件。

**Q: `chat()` 是同步的，会阻塞吗？**
A: P2 同时提供了 `achat()` / `achat_json()` 异步版（通过 `asyncio.to_thread`）。如果你的路由是 `async def`，用 `await achat(...)`；如果是 `def`，直接用 `chat()`。
