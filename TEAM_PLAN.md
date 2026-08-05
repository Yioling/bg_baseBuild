# 薪火团队赛 — 七人协作计划（AI 编程兼容保障）

> 本文件 + `API_CONTRACT.md` + `TEAM_TASKS/P1~P7` 任务卡，是全员（及各自使用的 AI 编程助手）必须首先阅读的"团队上下文"。**先读后写，按契约干活。**

---

## 0. 一句话定位
Windows 上双击/命令即可运行的 Web+桌面应用：师傅投喂资料→AI 精炼知识库→徒弟摸底定级→日历学习计划→当日讲义 PDF→当日复习批改→学情看板/同门战况，并预留公司级多租户 SaaS 地基（三角色 + `company_id` 隔离）。

## 1. 角色划分（已确认，七人）

| 代号 | 角色 | 拥有文件（可写） | 不得触碰（只读） |
|------|------|------------------|------------------|
| **P1** | 集成负责人 / 契约 Owner | `db.py` `auth.py` `main.py` `schemas.py` `config.py` `run.py` `run_exe.py` `tests/` | （唯一可改枢纽者） |
| **P2** | LLM 与向量库 | `llm.py` `embeddings.py` `vectorstore.py` `self_purifier.py`（新增 `backend/llm_client` 等也归此） | `main.py` `db.py` |
| **P3** | AI 智能体（5个） | `agents/refiner.py` `assessor.py` `planner.py` `tutor.py` `reviewer.py` | `main.py` `db.py` |
| **P4** | 资料摄取与 PDF | `ingest.py` `pdf_gen.py` `data/sample_kb/` | `main.py` `db.py` |
| **P5** | 桌面前端 / UI | `desktop_app.py` + 新建 `ui/` 包 | `main.py` `db.py` `schemas.py` |
| **P6** | 管理员后台 + 课程/计划/进度 | 新建 `backend/courses.py` `backend/progress_view.py` `backend/quiz.py` `backend/admin_back.py` | `main.py` `db.py`（逻辑写新文件，P1 装配） |
| **P7** | 交流圈 + 通知 + 账户安全 | 新建 `backend/notifications.py` `backend/account_security.py` `backend/social.py` | `main.py` `db.py`（逻辑写新文件，P1 装配） |

> **铁律**：只有 P1 能改 `main.py` / `db.py` / `auth.py` / `schemas.py`。其余人**新增功能一律写进自己名下的新文件或既有模块文件**，再由 P1 装配路由。

## 2. 模块隔离的"新文件模式"（避免抢改 main.py）

- P6 / P7 的绝大部分逻辑**不要内联进 `main.py`**，而是写成 `backend/` 下的新模块（如 `courses.py`），导出函数。
- P1 负责在 `main.py` 写薄路由：`@app.get("/api/...") def ...: return courses.list_courses(user)`。
- 这样 7 人并行时 git 文本冲突几乎只可能发生在 `main.py`/`db.py`，而这两文件由 P1 独占 → **冲突可控**。

## 3. 数据库变更流程
- `db.py` 已含 32 张表（V2 多租户地基），**原则上不再改表结构**。
- 若某功能确需加字段/表：先在本文件 §5 登记，P1 评估后在 `db.py` 统一加，**绝不私下改**。
- 所有业务查询必须带 `company_id` 过滤（SaaS 数据隔离护栏）。

## 4. Git 分支规范
- `main` 分支 = 冻结契约基线，**受保护**，只有 P1 能直接推。
- 每人开 `feature/Px-模块名` 分支（如 `feature/P3-agents`）。
- 小步提交、频繁 `rebase main`；每日至少一次把进度合回 `main`（由 P1 审核合并）。
- 合并前确保：`pip install -r requirements.txt && python run.py` 能起、`http://localhost:8000` 不报错、不影响现有 55 个路由。

## 5. 待补功能登记（来自 `薪火的过程/功能实现状态报告.md`）

| 优先级 | 功能 | 负责 | 备注 |
|--------|------|------|------|
| P0 | Quiz AI 评分接入真实 LLM | P3（逻辑）+ P6（路由） | 替换 `api_submit_quiz` 里的简易算法 |
| P0 | 通知自动化触发 | P7（基建）+ P1（注册/检测触发） | 注册待审→管理员；提交检测→师傅 |
| P0 | 密码重置 | P7（逻辑）+ P1（路由/装配） | 表 `password_resets` 已有 |
| P0 | 管理员下钻明细 | P6 | 点新人→培养明细+检测成绩 |
| P1 | 注册部门下拉 / 师傅下拉(UI) | P5 | API 已有 |
| P1 | 登录失败自动锁定 | P7 | 表 `login_attempts` 已有 |
| P1 | 管理员操作日志前端展示 | P5 + P6 | |
| P1 | 课程 type=检测题库 + 模板引擎 | P6 | |
| P1 | 徒弟"已完成"标记自动更新 | P6 | |
| P1 | 异常预警（长期无进度/多次不通过） | P6 | |
| P1 | SMTP 邮件发送 | P7 | 站内已实现，补邮件 |
| P1 | 用户列表按角色/状态筛选 | P6 | |
| P1 | 综合排名算法（权重可配置） | P6 | |
| P2 | 企微/钉钉/飞书 Webhook | P7（占位） | |
| P2 | 交流圈附件上传 | P7 | 表 `post_attachments` 已有 |
| P2 | @提醒 | P7 | |
| P0 | course_questions 表懒建移入 db.py init_db | P1+P6 | P6 当前运行期懒建，需固化为 schema（2026-08-05 登记） |
| P0 | plans.completed_at 列加入 db.py plans 表 | P1+P6 | 同上（2026-08-05 登记） |


## 6. 给每人 AI 编程助手的"开场纪律"（写进每个会话首条提示词）
> "你只负责 **<Px 模块>** 的代码。严格遵守 `API_CONTRACT.md` 与 `TEAM_PLAN.md`：
> 1) 禁止修改 `db.py` / `auth.py` / `main.py` / `schemas.py` / `config.py`（枢纽文件归 P1）；
> 2) 新增功能写到你自己的模块文件，函数返回 `{success, ...}`；需要新路由时只告诉 P1 装配，不要自己改 `main.py`；
> 3) 函数签名、JSON 字段必须与契约一致；
> 4) 用精准替换（targeted edit），不要整体重写文件；
> 5) 改动后保证不影响现有 55 个 API 路由；
> 6) 中文优先；LLM 调用用 `asyncio.to_thread` 包裹；JSON 解析需鲁棒（去 ```json 围栏、截取首个 `{`/`[` 到匹配括号）。"

## 7. 集成与验收（P1 主责）
- 每个 feature 分支合并前：跑通主流程（注册→审核→投喂→精炼→摸底→计划→PDF→复习→看板→交流圈→通知）。
- `tests/` 当前为空：P1 建立最小 pytest 冒烟（注册双模式、审核拦截、company_id 隔离、三进度视图排名、通知触发），各组员为自己的模块补 1~2 个用例。
- 对照 V2 需求 §16 自测清单逐项确认后再封版打包。

## 8. 当前已知坑（勿重复踩）
- `desktop_app.py` ~1700 行未拆分（P5 任务之一）；此前 8 处 `Layout.setStyleSheet()` 崩溃已修，勿再用。
- token 存内存，重启失效（技术债务，暂不治）。
- fastembed 首启需下载 ~200MB 模型。
- `api_submit_quiz` 当前用答案长度当分数（P0 待替换）。
