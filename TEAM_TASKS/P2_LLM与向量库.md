# 任务卡 · P2 LLM 与向量库

## 你的角色
负责 LLM 客户端、本地中文嵌入、自研向量库、知识库自净化。是所有 AI 智能体（P3）和公司底层检索能力的底座。

## 你可写的文件
- `backend/llm.py`
- `backend/embeddings.py`
- `backend/vectorstore.py`
- `backend/self_purifier.py`
- 新增 `backend/llm_client.py` 等也归你

## 禁止触碰
- `main.py` `db.py` `auth.py` `schemas.py`（需新能力时告诉 P1 装配）

## 你要做的事
1. **LLM 客户端**（已有基础）：确认 OpenAI 兼容协议 + 无 Key 兜底（演示模式）健壮；所有同步 SDK 调用用 `asyncio.to_thread` 包裹。
2. **本地中文嵌入**：`fastembed` + `jinaai/jina-embeddings-v2-small-zh`，首跑自动下载，提供 `embed(text)->vector`。
3. **向量库**：余弦相似度 + pickle 持久化（`VectorStore`），提供 `add/query(top_k)`；确保 `get_store()` 能 `load`/`save`。
4. **自净化**：`self_purifier.run_purification(kb_id)` / `get_purification_report()` / `get_purification_stats()` 已被 `main.py` 的 `/api/admin/purify*` 调用，确保接口稳定。
5. **稳定性**：检索 top-k 在空库/大库下不报错；提供清晰错误。

## 关键现有接口（与 P3/P4 对齐）
- `vectorstore.VectorStore.load(path)` / `.add(...)` / `.query(text, k)`
- `llm` 模块：供 P3 agent 调用（具体函数名看 `llm.py`）
- `embeddings`：供 ingest / agent 调用

## 验收标准
- [ ] 无 Key 时进入演示模式，全流程可演示不依赖外网
- [ ] `asyncio.to_thread` 包裹 LLM 调用，不阻塞事件循环
- [ ] 向量检索 top-k 正确，空库/异常输入不崩
- [ ] `run_purification` 与报告接口可用

## 给 AI 的开场提示词
"你负责 LLM 与向量库模块（P2）：`llm.py`/`embeddings.py`/`vectorstore.py`/`self_purifier.py`。禁止改 main.py/db.py/auth.py/schemas.py。函数签名与 `API_CONTRACT.md` 对齐；LLM 调用用 asyncio.to_thread；保证无 Key 兜底与中文嵌入稳定。用精准替换，不整体重写。"
