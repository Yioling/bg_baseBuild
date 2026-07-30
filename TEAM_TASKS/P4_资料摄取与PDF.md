# 任务卡 · P4 资料摄取与 PDF

## 你的角色
负责把师傅投喂的本地资料/博客 URL 变成知识库，并生成当日讲义 PDF。

## 你可写的文件
- `backend/ingest.py`
- `backend/pdf_gen.py`
- `backend/data/sample_kb/`（示例知识库）

## 禁止触碰
- `main.py` `db.py` `auth.py` `schemas.py`

## 你要做的事
1. **摄取**（已被调用）：
   - `ingest.ingest_local_path(user_id, kb_id, path, store)` —— 支持 `.md/.txt/.pdf/.docx/代码`
   - `ingest.ingest_urls(user_id, kb_id, urls, store)` —— 博客 URL 抓取正文（用 `trafilatura`）
   - `ingest.get_or_create_kb(user_id)`
   - 确保切片→嵌入→入库（调用 P2 的 embeddings/vectorstore）链路稳定
2. **PDF 讲义**：`pdf_gen.generate_today_pdf(user_id, plan_day_id, store)` 返回 bytes，被 `/api/apprentice/pdf/today` 调用。确保排版规范（参考 `awesome-design-md`）、可生成、可打开。
3. **示例知识库**：维护 `data/sample_kb/` 的"智能订单交易系统"示例（4 个 md），保证开箱即演示闭环。
4. 处理异常（文件不存在/编码/URL 失效）不崩溃。

## 验收标准
- [ ] 本地文件夹 + 博客 URL 两种投喂都能进知识库并被精炼
- [ ] 当日讲义 PDF 可生成、用系统阅读器可打开、内容正确
- [ ] 示例知识库可驱动完整演示闭环

## 给 AI 的开场提示词
"你负责资料摄取与 PDF（P4）：`ingest.py`/`pdf_gen.py`/`data/sample_kb/`。禁止改 main.py/db.py/auth.py/schemas.py。函数签名须匹配 `API_CONTRACT.md` 现有调用。PDF 排版参考 awesome-design-md，禁止丑陋默认样式。异常输入不崩溃。精准替换。"
