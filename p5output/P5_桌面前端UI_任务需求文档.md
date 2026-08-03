# P5 桌面前端 / UI — 任务需求文档（PRD）

> 文档状态：拆分已完成，本文档基于已完成代码复盘梳理"需求 → 实现"的对照，供验收与后续维护使用。
> 任务来源：`TEAM_TASKS/P5_桌面前端UI.md`
> 单一真相源（API）：`API_CONTRACT.md`（冻结版，55 端点）
> 设计语言：`huashu-design`（红白主题、现代、响应式、适度动效）

---

## 一、背景与目标

原 `desktop_app.py` 为 ~1700 行巨文件，维护与多 AI 并行合并冲突风险高（技术债务项）。
P5 目标：

1. 将巨文件按"页面 / 功能"拆分为 `ui/` 包，降低维护成本与合并冲突。
2. 交付高保真、符合 `huashu-design` 的桌面 UI，覆盖全部角色页面。
3. 严格按照 `API_CONTRACT.md` 字段渲染，与各模块 API 正确对接。
4. 消除历史崩溃：不对 `QLayout` 调用 `setStyleSheet()`（此前 8 处崩溃），只作用于 `QWidget` 子类。

---

## 二、范围与边界

### 可写 / 已交付文件

> 下表列出 `ui/` 包下全部 11 个模块，并标注其内部顶层结构（类 / 常量 / 模块级函数），便于追溯职责归属。

| 文件 | 顶层结构 | 职责 |
|------|----------|------|
| `desktop_app.py` | `start_server()`、`launch_desktop(start_server_flag)` | **入口桥接**：在后台线程启动 FastAPI（`uvicorn`），随后构建 `QApplication` → `LoginDialog` → `MainWindow`；`launch_desktop()` 被 `run_exe.py` 复用 |
| `ui/__init__.py` | `LoginDialog`、`MainWindow`（包导出） | 包公开接口，集中导出供 `desktop_app.py` 直接 `from ui import ...` |
| `ui/theme.py` | `Color`（设计令牌类）、`Radius`（圆角令牌类）、`GLOBAL_QSS`、`SIDEBAR_QSS`（全局/侧边栏样式表常量）、工厂函数 `apply_shadow`/`card`/`stat_card`/`title_label`/`subtitle_label`/`section_label`/`hint_label`/`badge`/`primary_button`/`secondary_button`/`success_button`/`danger_button`/`ghost_button`/`loading_label`/`empty_label`/`divider` | **设计系统层**：huashu-design 令牌、全局 QSS、侧边栏专属 QSS、通用组件工厂（全部返回 `QWidget` 子类，样式只作用于 QWidget） |
| `ui/api.py` | `SERVER_PORT`/`BASE_URL`（常量）、`ApiThread(QThread)`、`ApiMixin` | **数据访问层**：后台线程 HTTP 调用（GET/POST/PUT/DELETE）、自动附带 `Bearer` 头、连接失败重试 5 次、PDF 响应落盘桌面；`ApiMixin` 提供 `_api_call()` 与线程回收 |
| `ui/login.py` | `LoginDialog(QDialog)` | **认证层**：登录/注册双模式对话框，注册字段对齐 `RegisterReq`，pending 拦截提示，公司下拉由 `GET /api/companies` 填充 |
| `ui/main_window.py` | `PAGE_META`（pid→侧边栏文案/标题/副标题字典）、`ROLE_PAGES`（角色→pid 列表字典）、`MainWindow(ApiMixin, *6 Mixin, QMainWindow)` | **骨架/装配层**：侧边栏导航 + `QStackedWidget` 页面路由 + 通知红点；持有全部 `_build_*` 分发表；`_load_page()` 统一清空并重渲染 |
| `ui/master.py` | `MasterPagesMixin`、模块级 `_mastery_bar(m)` | **师傅视图层**：概览/投喂/知识库/徒弟管理/定制计划/批改/学情看板 7 个 `_build_*` 方法；`_mastery_bar()` 复用给徒弟看板 |
| `ui/apprentice.py` | 模块级 `_parse_options(opts)`、`ApprenticePagesMixin` | **徒弟视图层**：概览/摸底/计划/复习/错题本/同门战况/我的计划 7 个 `_build_*`；`_parse_options()` 解析选项 JSON；复用 `master._mastery_bar` |
| `ui/admin.py` | 模块级 `_ROLE_NAMES`、`_STATUS_META`、`AdminPagesMixin` | **管理员视图层**：概览/审核/课程库/用户/部门/日志/进度 7 个 `_build_*`，含重绑师傅弹窗 `_open_rebind_dialog` |
| `ui/social.py` | 模块级 `_ROLE_NAMES`、`SocialPagesMixin` | **交流圈层**：发帖/列表/点赞、评论弹窗 `_show_comments()` |
| `ui/notify.py` | `NotifyPagesMixin` | **通知层**：列表/未读计数/全部已读 |
| `ui/progress.py` | `ProgressPagesMixin` | **进度层**：公司/部门/同门三视图切换与排行渲染 |

### 禁止触碰（后端契约文件，P5 不改）
`main.py` `db.py` `auth.py` `schemas.py`

---

## 三、架构设计

### 3.1 分层总览

整个桌面前端按"入口 → 包装配 → 能力层 → 视图层"四层组织，`ui/` 包内再细分为**设计系统层、数据访问层、认证层、骨架层、视图层**五个子层：

```
desktop_app.py ────────────── 入口层（进程启动 / 服务拉起 / QApplication）
   │
   └─ ui/ (包)
        │
        ├─ 设计系统层  theme.py
        │     ├─ Color / Radius        设计令牌（颜色、圆角）
        │     ├─ GLOBAL_QSS / SIDEBAR_QSS  全局 & 侧边栏样式表
        │     └─ 组件工厂 (card/stat_card/button*/badge/label…)
        │            │  （所有工厂返回 QWidget，样式仅作用于 QWidget）
        │            ▼ 被所有其余模块 import 复用
        │
        ├─ 数据访问层  api.py
        │     ├─ ApiThread(QThread)     后台 HTTP + 重试 + PDF 落盘
        │     └─ ApiMixin                _api_call() 注入到 MainWindow
        │            ▼ 被 MainWindow 继承，所有视图层通过 self._api_call 取数
        │
        ├─ 认证层      login.py
        │     └─ LoginDialog(QDialog)   双模式登录/注册，输出 token+user
        │
        ├─ 骨架层      main_window.py
        │     ├─ PAGE_META / ROLE_PAGES 路由配置（数据）
        │     └─ MainWindow( ApiMixin + 6×Mixin + QMainWindow )
        │            │  侧边栏 + QStackedWidget + 通知红点
        │            ▼ 运行时多重继承，聚合下列 6 个视图 Mixin
        │
        └─ 视图层（6 个 Mixin，方法签名统一为 _build_*(layout, container)）
              ├─ master.py      MasterPagesMixin    （师傅 7 页 + _mastery_bar）
              ├─ apprentice.py  ApprenticePagesMixin（徒弟 7 页 + _parse_options）
              ├─ admin.py       AdminPagesMixin     （管理员 7 页 + _ROLE_NAMES/_STATUS_META）
              ├─ social.py      SocialPagesMixin    （交流圈 + _show_comments）
              ├─ notify.py      NotifyPagesMixin    （通知中心）
              └─ progress.py    ProgressPagesMixin  （进度三视图）

跨层依赖方向（单向，无环）：
  main_window → {theme, api, 6×Mixin}
  Mixin       → {theme, api}            （视图层只依赖设计系统层与数据访问层）
  apprentice  → master(_mastery_bar)   （徒弟看板复用师傅的掌握度进度条）
  login       → api(ApiThread,BASE_URL)
  所有层      → theme（组件工厂/令牌）
```

### 3.2 各文件内部职责分解

- **`theme.py`（设计系统层）**
  - `Color`：品牌红 `#dc2626`、语义色（成功/警告/危险/信息）、中性色（背景/表面/侧边栏渐变/边框/文字）、排名奖牌色。
  - `Radius`：SM/MD/LG/PILL 圆角令牌。
  - `GLOBAL_QSS`：作用于 `QMainWindow`/`QDialog`/`QWidget#content`/`QScrollArea`/`QPushButton`/`QLineEdit`/`QTableWidget`/`QProgressBar`/`QGroupBox` 等。
  - `SIDEBAR_QSS`：仅作用于 `objectName=="sidebar"` 的 `QWidget` 及其子按钮，含 `logo`/`logoSub`/`userinfo`/`logoutBtn` 专属样式。
  - 工厂函数：全部返回 `QWidget` 子类（`QFrame`/`QLabel`/`QPushButton`），内部仅对返回对象 `setStyleSheet`，绝不碰 `QLayout`。

- **`api.py`（数据访问层）**
  - `ApiThread(QThread)`：`run()` 内按 method 发请求，自动带 `Authorization` 头，连接错误重试 5 次；识别 `application/json` 与 `application/pdf`（PDF 落盘桌面并 `os.startfile` 打开）。
  - `ApiMixin`：提供 `_api_call(method, url, body, callback)`，持有 `_api_threads` 列表防提前回收，线程结束自动 `_reap_thread()`。

- **`login.py`（认证层）**
  - `LoginDialog(QDialog)`：`_RED_WHITE_QSS` 仅作用于 `QDialog` 及其子 QWidget；`QStackedWidget` 切登录/注册；`_load_companies()` 拉公司；`_do_auth()` 分登录/注册；`_on_login()` 做 pending 拦截；`_on_register()` 成功提示。

- **`main_window.py`（骨架层）**
  - `PAGE_META`：`pid → (侧边栏文案, 页面标题, 副标题)`。
  - `ROLE_PAGES`：角色 → 该角色可见 `pid` 列表。
  - `MainWindow`：多重继承 `ApiMixin` + 6 个 Mixin；`_init_ui()` 装配侧边栏与 `QStackedWidget`；`_create_page()` 生成 `QScrollArea` 容器（样式作用于 `QWidget`）；`_switch_page()`/`_load_page()` 路由；`_refresh_notify_badge()` 刷新红点；`_logout()` 调登出接口并关闭。

- **视图层 6 个 Mixin**（详细页面映射见第四章）：每个 `_build_*(layout, container)` 在 `main_window._load_page` 中被调用，统一先注入标题，再以 `self._api_call` 异步取数渲染；模块级辅助函数（如 `_mastery_bar`/`_parse_options`/`_ROLE_NAMES`）为纯逻辑、无 UI 副作用，便于复用与测试。

### 3.3 页面路由机制
- `MainWindow` 继承 `ApiMixin` + 6 个 `*PagesMixin` + `QMainWindow`。
- 各角色侧边栏页由 `ROLE_PAGES` 字典定义，所有页面均为 `QScrollArea` 容器。
- `_switch_page(pid)` → 清空容器 → 注入 `title_label` / `subtitle_label` → 调用对应 `_build_*` 方法。
- 每个 `_build_*` 方法签名统一为 `(layout, container)`，内部通过 `self._api_call(...)` 拉取数据并渲染。
- 路由分发表位于 `main_window._load_page()` 的 `builders` 字典：新增页面需在 `PAGE_META`、`ROLE_PAGES`、`builders` 三处同步登记。

### 3.4 数据获取
- `ApiMixin._api_call(method, url, body, callback)`：启动 `ApiThread`，`finished` 信号回调 `callback(res)`。
- `ApiThread` 自动附带 `Authorization: Bearer <token>`，对连接失败重试 5 次（后端冷启动场景）。
- PDF 响应（`application/pdf`）自动保存到桌面并调用 `os.startfile` 打开。

### 3.5 设计系统分层（huashu-design 落地方式）
- **令牌层**：`Color`/`Radius` 集中管理色彩与圆角，避免硬编码散落。
- **样式表层**：`GLOBAL_QSS`（全局）、`SIDEBAR_QSS`（侧边栏）两套样式表，由对应顶层容器 `setStyleSheet` 注入。
- **组件工厂层**：`card`/`stat_card`/`badge`/`*_button`/`*_label` 等统一封装成"返回 QWidget + 内联安全样式"的工厂，业务页面只调用工厂、不直接写 QSS，从根本上杜绝对 `QLayout` `setStyleSheet`（历史 8 处崩溃根因）。
- **动效层**：`apply_shadow()` 用 `QGraphicsDropShadowEffect` 给卡片加柔和投影，作用于 widget 而非 layout。

---

## 四、功能需求与实现对照

### 4.1 登录 / 注册（双模式，`ui/login.py`）

**需求**：登录 / 注册双模式切换；注册字段含 工号 / 手机 / 办公账号 / 姓名 / 部门 / 师傅；pending 状态拦截提示。

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_init_ui` | 无 | 构建对话框整体布局、登录/注册 tab 切换（`QStackedWidget`）、提交按钮 |
| `_build_login_form` | 无 | 构建登录表单（用户名、密码） |
| `_build_register_form` | 无 | 构建注册表单（用户名/密码/姓名/工号/手机/办公账号/角色/公司），字段对齐 `RegisterReq` |
| `_switch_mode(idx)` | 无 | 切换登录/注册堆栈页并更新按钮态 |
| `_load_companies` | `GET /api/companies`，无请求体，P1，响应 `{companies:[{id,name}]}` | 拉取公司列表填充注册下拉框 |
| `_on_companies(res)` | 无 | 解析公司响应写入 `r_company` 下拉 |
| `_do_auth` | `POST /api/login`，`{username,password}`，P1，`{success,token,user}`；`POST /api/register`，`{username,password,role,company_id,employee_no,phone,office_account,full_name}`，P1，`{success,message}` | 按当前模式分发登录或注册请求 |
| `_on_login(res)` | 无 | 登录成功存 token/user 并 `accept()`；含"审核/pending"关键字时橙色 `warn` 拦截提示 |
| `_on_register(res)` | 无 | 注册成功提示"等待管理员审核"并切回登录 |
| `_set_msg(text,ok,warn)` | 无 | 统一设置消息区文字与颜色（成功绿/警告橙/错误红） |
| `_lock(locked,text)` | 无 | 提交中禁用按钮并显示"登录中…/注册中…" |

### 4.2 师傅视图（`ui/master.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_build_master_overview` | `GET /api/master/knowledge`，无，main 内联，`{dimensions:[{name,points}]}`；`GET /api/master/apprentices`，无，auth，`{apprentices:[...]}` | 概览指标卡（知识维度/知识点/徒弟数）+ 带徒五步法引导 |
| `_build_master_ingest` | `POST /api/master/ingest`，`{path}`，P4 ingest，`{success,message}`；`POST /api/master/ingest/url`，`{urls:[...]}`，P4 ingest，`{success,message}` | 本地文件夹投喂 + 博客 URL 投喂 + 示例 KB 加载 |
| `_build_master_knowledge` | `GET /api/master/knowledge`（同上）；`POST /api/master/refine`，无，P3 refiner，`{success,...}` | 维度/考点树卡片渲染 + "触发 AI 精炼" |
| `_build_master_apprentices` | `POST /api/master/apprentices`，`{username,password}`，auth，`{...}`；`GET /api/master/apprentices`（同上）；`POST /api/master/plan/generate`，`{apprentice_id}`，P3 planner，`{...}` | 创建徒弟账号 + 徒弟列表 + 行内"生成计划" |
| `_gen_plan(appr_id)` | `POST /api/master/plan/generate`，`{apprentice_id}`，P3 planner | 为指定徒弟触发 AI 计划生成 |
| `_build_master_plans` | `GET /api/master/plans`，无，P6，`{plans:[...]}`；`GET /api/admin/courses`，无，P6，`{courses:[...]}`；`POST /api/master/plans`，`{apprentice_id,name,course_ids:[...]}`，P6 | 勾选课程定制培养计划 + 已有计划列表 |
| `_build_master_grading` | `GET /api/master/apprentice/{apprentice_id}/quizzes`，无，P6，`{quizzes:[...]}`；`POST /api/master/quizzes/{quiz_id}/score`，`{master_score,status}`，P6 | 选择徒弟查看检测提交，终评打分（通过/重做） |
| `_load_quizzes(appr_id,area)` | `GET /api/master/apprentice/{id}/quizzes`（同上） | 异步加载某徒弟检测记录卡片 |
| `_score_quiz(quiz_id,score,status,area)` | `POST /api/master/quizzes/{quiz_id}/score`，`{master_score,status}`，P6 | 提交师傅终评分数与状态 |
| `_build_master_dashboard` | `GET /api/master/apprentices`（同上）；`GET /api/master/dashboard/{apprentice_id}`，无，main 内联，`{mastery,assessments,reviews}` | 选择徒弟并显示其学情看板 |
| `_show_dashboard(appr_id,area)` | `GET /api/master/dashboard/{id}`（同上） | 渲染知识掌握等级进度条 |
| `_mastery_bar(m)`（模块级） | 无 | 纯函数：根据掌握等级（熟练/了解/未知→90/50/20%）生成进度条，被徒弟看板复用 |
| `_clear_layout(sub)`（静态） | 无 | 递归清空布局内 widget，用于局部重渲染 |

### 4.3 徒弟视图（`ui/apprentice.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_parse_options(opts)`（模块级） | 无 | 纯函数：解析选项 JSON 字符串为列表，供选择题渲染 |
| `_build_appr_overview` | `GET /api/apprentice/mistakes`，无，P3 assessor，`{assess_mistakes,review_mistakes}` | 错题统计卡 + 新手上路引导 |
| `_build_appr_assess` | `POST /api/apprentice/assessment/start`，无，P3 assessor，`{assessment_id,questions}` | 摸底考试入口 + 逐题渲染 |
| `_on_assess_start(res)` | 无 | 考试开始回调，缓存题目并刷新页面 |
| `_show_assess_question` | 无 | 渲染当前题（选择/简答）、提交按钮 |
| `_submit_assess(q)` | `POST /api/apprentice/assessment/answer`，`{question_id,answer}`，P3 assessor，`{score,feedback,answer_key}` | 提交单题答案 |
| `_collect_answer(widget)` | 无 | 从按钮组/文本框收集答案，空值弹提示 |
| `_on_assess_answer(res)` | 无 | 显示单题反馈，推进到下一题 |
| `_show_assess_result(res,area)` | `GET /api/apprentice/assessment/result/{assessment_id}`，无，P3 assessor，`{mastery}` | 渲染掌握等级总览 |
| `_build_appr_plan` | `GET /api/apprentice/plan/today`，无，P3 planner，`{today:{day_index,note,tasks}}`；`GET /api/apprentice/pdf/today`，无，P4 pdf_gen，PDF 流；`POST /api/apprentice/ask`，`{question}`，P3 tutor，`{answer}` | 当日计划卡 + PDF 下载按钮 + AI 陪练答疑 |
| `_do_chat(chat_input)` | `POST /api/apprentice/ask`，`{question}`，P3 tutor | 向 AI 导师提问并追加到聊天区 |
| `_build_appr_review` | `GET /api/apprentice/plan/today`（同上）；`POST /api/apprentice/review/start`，`{plan_day_id}`，P3 reviewer，`{review_id,questions}`；`POST /api/apprentice/review/answer`，`{question_id,answer,review_id}`，P3 reviewer，`{score,feedback}` | 当日复习入口 + 逐题 + 即时反馈 |
| `_start_review_check(loading,res)` | 无 | 校验当日计划存在后展示"开始复习"按钮 |
| `_on_review_start(res)` | 无 | 复习开始回调，缓存题目并刷新 |
| `_show_review_question` | 无 | 渲染当前复习题 |
| `_submit_review(q)` | `POST /api/apprentice/review/answer`，`{question_id,answer,review_id}`，P3 reviewer | 提交复习答案 |
| `_on_review_answered(res)` | 无 | 显示复习反馈并推进 |
| `_build_appr_mistakes` | `GET /api/apprentice/mistakes`（同上） | 错题本（考试/复习错题合并展示） |
| `_build_appr_leaderboard` | `GET /api/apprentice/leaderboard`，无，main 内联，`{leaderboard:[{apprentice_id,username,avg_score,mastery_count,mistake_count}],my_id}` | 同门战况排行（高亮"我"，奖牌色） |
| `_build_appr_my_plans` | `GET /api/apprentice/plans`，无，P6，`{plans:[{name,completed_at,items}]}`；`GET /api/apprentice/quizzes`，无，P6，`{quizzes:[...]}`；`POST /api/apprentice/quiz/submit`，`{plan_item_id,answer}`，P6/P3，`{ai_score,...}` | 我的培养计划 + 任务检测弹窗（AI 初评） |
| `_open_quiz_dialog(plan_item_id,title)` | `POST /api/apprentice/quiz/submit`，`{plan_item_id,answer}`，P6/P3 | 弹出任务检测对话框并提交，显示 AI 初评 |

### 4.4 管理员视图（`ui/admin.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_build_admin_overview` | `GET /api/admin/stats`，无，P6/P1，`{total_apprentices,total_masters,pending_review,...}` | 概览指标卡 + 待审核预警卡（点击去审核） |
| `_build_admin_pending` | `GET /api/admin/pending`，无，P6，`{pending:[{id,full_name,username,role,employee_no,phone,office_account}]}`；`POST /api/admin/approve`，`{user_id}`，P6；`POST /api/admin/reject`，`{user_id}`，P6 | 待审核用户卡 + 通过/驳回 |
| `_build_admin_courses` | `GET /api/admin/courses`，无，P6，`{courses:[{id,title,type}]}`；`POST /api/admin/courses`，`{title,type,content}`，P6；`DELETE /api/admin/courses/{id}`，无，P6 | 课程创建 + 列表 + 删除 |
| `_build_admin_users` | `GET /api/admin/users`，无，P6，`{users:[{id,full_name,username,role,status,employee_no,master_name}]}`；`POST /api/admin/rebind-master`，`{apprentice_id,master_id}`，P6 | 用户列表 + 徒弟"重绑师傅" |
| `_open_rebind_dialog(apprentice_id,name,masters)` | `POST /api/admin/rebind-master`，`{apprentice_id,master_id}`，P6 | 重绑师傅弹窗，确认后提交 |
| `_build_admin_departments` | `GET /api/admin/departments`，无，P6，`{departments:[{name}]}`；`POST /api/admin/departments`，`{name}`，P6 | 部门新增 + 列表 |
| `_build_admin_logs` | `GET /api/admin/logs`，无，P6，`{logs:[{action,target_type,target_id,detail,created_at}]}` | 操作日志时间线 |
| `_build_progress_view`（复用 `progress.py`） | `GET /api/progress/company`，无，P6，`{apprentices:[...]}` | 复用进度三视图（管理员仅公司视图） |

### 4.5 交流圈（`ui/social.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_build_social_posts` | `POST /api/posts`，`{content,author_name?}`，P7，`{post_id}`；`GET /api/posts`，无，P7，`{posts:[{id,author_name,author_role,content,likes_count,comments_count,liked_by_me,created_at}]}`；`POST /api/posts/{post_id}/like`，无，P7，`{liked}` | 发帖 + 帖子列表渲染 + 点赞切换（心形/计数） |
| `_show_comments(post_id)` | `GET /api/posts/{post_id}/comments`，无，P7，`{comments:[{author_name,author_id,content}]}`；`POST /api/posts/{post_id}/comments`，`{content}`，P7，`{message}` | 评论弹窗：渲染评论列表 + 发送评论（支持 @ 提醒文本） |

### 4.6 通知中心（`ui/notify.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_build_notifications` | `GET /api/notifications`，无，P7/P1，`{notifications:[{type,content,read,created_at}],unread_count}`；`POST /api/notifications/read`，`{id?}`，P7/P1，`{success}` | 未读计数 + 列表（未读红点 + 主色左边框）+ 全部标为已读（并刷新侧边栏红点） |

### 4.7 进度三视图（`ui/progress.py`）

| 文件内函数名 | 对应方法, 路径, 请求体, 逻辑归属模块, 响应关键字段 | 函数功能 |
|--------------|------------------------------------------------------|----------|
| `_build_progress_view` | `GET /api/progress/company`（同上）；`GET /api/progress/department`，无，P6，`{apprentices:[{apprentice_name,master_name,progress_pct,avg_score,rank}]}`；`GET /api/progress/same-master`，无，P6（同上） | 公司/部门/同门三视图 `QComboBox` 切换（管理员仅 company） |
| `_load_progress(ptype,area)` | 上述三视图之一 | 按当前选中视图异步加载排行数据 |
| `_show_progress(loading,res,area)` | 上述三视图之一 | 渲染排行卡：排名奖牌色 + 进度条 + 均分 |

---

## 五、设计系统要求（huashu-design）

- 主题：品牌红 `#dc2626` + 纯净白，红白 sidebar（`#8f1414` → `#6f0e0e` 渐变）。
- 大字号、大留白、大气排版（标题 30px/800，副标题 15.5px）。
- 通用组件工厂（`ui/theme.py`）：`card` `stat_card` `title_label` `badge` `primary/secondary/success/danger/ghost_button` `loading_label` `empty_label` `divider` `apply_shadow`。
- 所有工厂函数返回 `QWidget` 子类，样式仅作用于 QWidget，绝不作用于 `QLayout`。
- 卡片投影用 `QGraphicsDropShadowEffect`（作用于 widget）。

---

## 六、铁律与防崩溃

1. **禁止对 QLayout 调用 `setStyleSheet()`**。`theme.py` 与所有页面仅对 `QWidget` 子类（含 `QFrame`/`QLabel`/`QPushButton`/`QProgressBar` 等）设样式。
2. 全局 QSS 通过 `MainWindow.setStyleSheet(GLOBAL_QSS)` 作用；侧边栏 QSS 作用于 `objectName=="sidebar"` 的 `QWidget`。
3. 页面容器 `container.setStyleSheet(...)` 作用于 `QWidget`，符合铁律。
4. 异步 HTTP 统一走 `ApiThread`，避免阻塞 UI 主线程。

---

## 七、验收标准

| 验收项 |  说明 |
|--------|------|
| 所有角色页面可用，与 API 正确对接 |   7 个师傅页 + 7 个徒弟页 + 7 个管理员页 + 交流圈 + 通知 + 进度三视图，均按 `API_CONTRACT.md` 字段实现 |
| UI 高保真（huashu-design），无默认丑样式 | `ui/theme.py` 统一设计令牌与组件工厂，无裸默认控件 |
| `desktop_app.py` 已拆分，`ui/` 包结构清晰 |  拆为 11 个模块，入口仅保留服务启动 + 应用启动 |
| 不再出现 Layout.setStyleSheet 类崩溃 |  全部样式作用于 QWidget 子类 |

---

## 八、待办 / 潜在风险（供后续迭代）

1. **P1/P6/P7 新增端点同步**：若 `API_CONTRACT.md` 新增端点，需在对应 Mixin 中补充 `_build_*` 并在 `main_window.py` 的 `PAGE_META` / `ROLE_PAGES` / `builders` 三处登记。
2. **PDF 落盘路径**：当前固定保存到 `~/Desktop`，Linux/macOS 下路径语义不同（当前为 Windows 桌面应用，可接受）。
3. **`appr_assess` / `appr_review` 状态存于实例属性**：跨页面刷新会重置（`_load_page` 重建页面），属已知交互取舍，可后续用持久态优化。
4. **`master_dashboard` 掌握等级映射**：熟练/了解/未知 → 90/50/20% 为前端硬编码，需与 P3 评估等级定义保持一致。
5. **`desktop_app.py` 与 `run.py` 并存**：`run.py` 仍走 pywebview（Web 版），`desktop_app.py` 走 PyQt5。两套入口并存，文档需向用户说明差异。

---

## 九、附录：关键 API 字段映射（前端取数约定）

- `user` 字典统一从 `GET /api/me` 取值：`user_id, username, role, company_id, master_id, full_name, employee_no, department, status`，前端不再自行查库。
- 通知：`notifications[]` + `unread_count`。
- 进度：`apprentices[{apprentice_name, master_name, progress_pct, avg_score, rank}]`。
- 帖子：`posts[{author_name, author_role, content, likes_count, comments_count, liked_by_me, created_at}]`。
