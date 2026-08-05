# 薪火·师傅带徒 AI 导师系统 — API 契约（冻结版）

> **用途**：团队七人并行 AI 编程的"单一真相源"。任何人对接口路径、请求体、响应体的改动，**必须先在本文件登记并由 P1（集成负责人）批准**，否则合并必然冲突。
> **状态**：以下 55 个端点均已存在于 `backend/main.py`（V2 实现）。`响应` 列给出关键字段，前端/调用方以此为准。
> **鉴权统一规则**：除 `GET /` 与 `GET /api/companies*` 外，所有接口必须在 `Authorization: Bearer <token>` 头（或 cookie `token`）携带 token；缺失/无效返回 `401`。角色守卫见各端点标注。

---

## 一、认证 / 用户（P1 拥有逻辑）

| 方法 | 路径 | 守卫 | 请求体 | 响应（关键字段） |
|------|------|------|--------|------------------|
| POST | `/api/register` | 公开 | `{username,password,role}`（当前仅允许 master/admin，徒弟由师傅创建） | `{success,message}` |
| POST | `/api/login` | 公开 | `{username,password}` | `{success,token,user}` |
| POST | `/api/logout` | 登录 | — | `{success,message}` |
| GET | `/api/me` | 登录 | — | `{success,user}` |

> `user` 字典关键字段：`user_id, username, role, company_id, master_id, full_name, employee_no, department, status`。**所有人函数一律从 `user` 字典取值，不要自行查库重复解析。**

---

## 二、师傅端（master）

| 方法 | 路径 | 请求体 | 逻辑归属模块 | 响应关键字段 |
|------|------|--------|--------------|--------------|
| POST | `/api/master/apprentices` | `{username,password}` | auth | 创建徒弟并绑定 `master_id` |
| GET | `/api/master/apprentices` | — | auth | `{apprentices:[...]}` |
| POST | `/api/master/ingest` | `{path}` | P4 ingest | 本地文件夹投喂 |
| POST | `/api/master/ingest/url` | `{urls:[...]}` | P4 ingest | 博客 URL 投喂 |
| POST | `/api/master/refine` | — | P3 refiner | 触发精炼 + 自动净化 |
| GET | `/api/master/knowledge` | — | （main 内联） | `{dimensions:[{name,points:[...]}]}` |
| POST | `/api/master/plan/generate` | `{apprentice_id}` | P3 planner | 生成日历计划 |
| GET | `/api/master/plan/{apprentice_id}` | — | P3 planner | `{days:[...],tasks:[...]}` |
| PUT | `/api/master/plan/day/{day_id}` | `{note,locked}` | P3 planner | 改日计划 |
| PUT | `/api/master/plan/task/{task_id}` | `{...}` | P3 planner | 改任务 |
| GET | `/api/master/dashboard/{apprentice_id}` | — | （main 内联） | `{mastery,assessments,reviews}` |
| POST | `/api/master/plans` | `{apprentice_id,name,course_ids:[...]}` | P6 | 定制培养计划 |
| GET | `/api/master/plans` | — | P6 | `{plans:[...]}` |
| GET | `/api/master/plans/{plan_id}` | — | P6 | `{plan,items}` |
| GET | `/api/master/apprentice/{apprentice_id}/quizzes` | — | P6 | 师傅看徒弟检测 |
| POST | `/api/master/quizzes/{quiz_id}/score` | `{master_score,status}` | P6 | 师傅终评改分 |
| POST | `/api/master/daily-progress` | `{apprentice_id,plan_item_id}` | P6 | 判定当日进度 |
| GET | `/api/master/daily-progress/{apprentice_id}` | — | P6 | 进度记录 |

---

## 三、徒弟端（apprentice）

| 方法 | 路径 | 请求体 | 逻辑归属 | 响应关键字段 |
|------|------|--------|----------|--------------|
| POST | `/api/apprentice/assessment/start` | — | P3 assessor | 生成摸底题 |
| POST | `/api/apprentice/assessment/answer` | `{question_id,answer}` | P3 assessor | 批改+定级 |
| GET | `/api/apprentice/assessment/result/{assessment_id}` | — | P3 assessor | 结果 |
| GET | `/api/apprentice/plan/today` | — | P3 planner | 当日任务 |
| GET | `/api/apprentice/pdf/today` | — | P4 pdf_gen | PDF 流 |
| POST | `/api/apprentice/review/start` | `{plan_day_id}` | P3 reviewer | 复习题 |
| POST | `/api/apprentice/review/answer` | `{question_id,answer,review_id}` | P3 reviewer | 批改 |
| GET | `/api/apprentice/mistakes` | — | P3 assessor | 错题本 |
| POST | `/api/apprentice/ask` | `{question}` | P3 tutor | RAG 答疑 |
| GET | `/api/apprentice/leaderboard` | — | （main 内联） | 同门战况 |
| GET | `/api/apprentice/plans` | — | P6 | 我的培养计划 |
| POST | `/api/apprentice/quiz/submit` | `{plan_item_id,answer}` | P6/P3 | **AI 初评（P0 待接真实 LLM）** |
| GET | `/api/apprentice/quizzes` | — | P6 | 我的检测历史 |

---

## 四、进度三视图（P6）

| 方法 | 路径 | 响应关键字段 |
|------|------|--------------|
| GET | `/api/progress/company` | `{apprentices:[{apprentice_name,master_name,progress_pct,avg_score,rank}]}` |
| GET | `/api/progress/department` | 同上（按 department 过滤） |
| GET | `/api/progress/same-master` | 同上（按 master_id 过滤） |

---

## 五、交流圈（P7）

| 方法 | 路径 | 请求体 | 响应 |
|------|------|--------|------|
| POST | `/api/posts` | `{content,author_name?}` | `{post_id}` |
| GET | `/api/posts` | — | `{posts:[{comments_count,likes_count,liked_by_me}]}` |
| POST | `/api/posts/{post_id}/comments` | `{content}` | `{message}` |
| GET | `/api/posts/{post_id}/comments` | — | `{comments}` |
| POST | `/api/posts/{post_id}/like` | — | `{liked}` |

---

## 六、通知（P7 基建 + P1 触发）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notifications` | `{notifications,unread_count}` |
| POST | `/api/notifications/read` | `{id?}` 标记已读 |

> **内部函数**：`backend/notifications.notify(conn, user_id, ntype, content, ref_id=None, company_id=1)`（已抽模块，含 SMTP 邮件）。
> **P1 已装配的自动触发**（P0 已就绪，2026-08-05）：
> - `auth.register` 注册待审 → 通知本公司全部已批准管理员（type=`register_pending`）
> - `api_submit_quiz` 徒弟提交检测 → 通知绑定师傅（type=`quiz_submitted`）
> - 调用一律 `conn=None`，由通知模块自取连接 + commit，避免多连接事务隔离。

---

## 七、管理员后台（P6 为主，P1 装配）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/courses` / POST / PUT `/{id}` / DELETE `/{id}` | 课程库 CRUD |
| GET | `/api/admin/pending` | 待审核列表 |
| POST | `/api/admin/approve` | `{user_id}` 通过 |
| POST | `/api/admin/reject` | `{user_id}` 驳回 |
| GET | `/api/admin/users` | 公司用户列表 |
| POST | `/api/admin/rebind-master` | `{apprentice_id,master_id}` 重绑 |
| POST/GET | `/api/admin/departments` | 部门维护 |
| GET | `/api/admin/logs` | 操作日志 |
| GET | `/api/admin/stats` | 概览统计 |
| POST/GET/GET | `/api/admin/purify(/report|/stats)` | 知识库自净化（P2 模块） |

---

## 八、公开 / 页面

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/companies` | 公司列表（注册选公司用） |
| GET | `/api/companies/{company_id}/masters` | 该公司师傅列表（注册选师傅用） |
| GET | `/` | 托管前端 `frontend/index.html` |

---

## 九、新增端点的强制流程（防冲突）

1. 任何人在自己的**新模块文件**（如 `backend/courses.py`）里写处理函数，函数签名自定但返回 `{success, ...}`。
2. 在 `API_CONTRACT.md` 本文件登记该端点（路径/方法/请求/响应/归属）。
3. 告诉 **P1**：函数位置 + 想挂的路径 + 角色守卫。
4. **由 P1 在 `main.py` 写 `@app.xxx` 路由并 `from backend.xxx import func` 装配**，其余人不得改 `main.py`。

> 任何人**不得**为了图方便直接在 `main.py` 里写业务逻辑或新建路由——这是合并冲突的头号来源。

---

## 十、账户安全 / 密码重置（P7 逻辑 + P1 装配，P0 已就绪）

| 方法 | 路径 | 请求体 | 响应 |
|------|------|--------|------|
| POST | `/api/password/reset-request` | `{email}`（按 username / phone 定位） | `{success, token?, expiry?}` |
| POST | `/api/password/reset` | `{token, new_password}` | `{success, message}` |

> 逻辑在 `backend/account_security.py`（P7 拥有），P1 仅装配路由 + 引入 Pydantic 请求模型（`schemas.PasswordResetRequestReq` / `PasswordResetReq`）。
> 路由调用模块时一律 `conn=None`，由模块自取连接 + commit，避免多连接事务隔离。
