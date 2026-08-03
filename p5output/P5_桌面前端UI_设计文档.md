# P5 桌面前端 / UI — 设计文档（UIDD）

> 文档状态：基于已完成代码复盘，与 `ui/` 包实际实现逐行对齐。
> 配套需求文档：`P5_桌面前端UI_任务需求文档.md`
> 设计语言：`huashu-design`（红白主题、大字号、大留白、现代卡片化）
> 配图说明：本文所有界面图均为 **ASCII 字符画**，描述实际控件布局与层级，非像素级还原。
> 组织方式：**按师傅 / 徒弟 / 管理员三类角色分类叙述**，三类共用的骨架、主题、登录、通知、交流圈单列"公共部分"，页面内复用组件统一补充说明。

---

## 〇、公共设计基底（三类共用）

### 0.1 设计系统（ui/theme.py）

整体视觉由三件套驱动：**设计令牌（Color / Radius）→ 全局样式表（GLOBAL_QSS / SIDEBAR_QSS）→ 组件工厂**。所有页面只调用工厂函数，绝不手写裸 QSS，且样式**只作用于 QWidget 子类**（铁律，杜绝 Layout.setStyleSheet 历史崩溃）。

```
 背景 BG #faf8f8  │ 品牌红 PRIMARY #dc2626 │ 侧边栏渐变 #8f1414→#6f0e0e
 表面 SURFACE #ffffff │ 语义色 成功#10b981 警告#f59e0b 危险#ef4444 信息#0ea5e9
 圆角 Radius SM8 / MD12 / LG16 / PILL999 │ 投影 apply_shadow(widget)
```

通用组件库（三类页面均调用）：

```
┌─ card ────────────────┐    ┌─ stat_card ──────────┐    ┌─ badge ─────┐
│ 白卡+1px边框+圆角LG16   │    │  43px 大数字 / 20px说明 │    │ PILL圆角 柔和底 │
│ 默认padding 26(放大)   │    │  padding 28(放大)      │    └────────────┘
│ 可选 accent 左边框      │    └──────────────────────┘
└────────────────────────┘
 按钮家族(QPushButton)：[主按钮]红底白字(20px,min-h48) / [次要]白底边框 / [成功]绿 / [危险]深红 / [幽灵]透明红字(20px) / [投喂]白底红框红字(20px,min-h48)
 标签家族：title_label(35/800) subtitle_label(20.5灰) section_label(23/700) hint_label(19px灰) 
 loading_label(21px) / empty_label(21px) / divider / apply_shadow(投影)
 全局字号统一放大 5px：QLabel 基础 19px、QLineEdit/QTextEdit/QComboBox 20px、表格 19.5px/表头19px、GroupBox 21px、单选复选 20px；
 所有按钮加 min-height 防文字截断；card 默认 padding 20→26、stat_card 22→28 增加留白。
```

### 0.2 应用窗口骨架（MainWindow，三类共用）

`QMainWindow`，尺寸 `1520×940`（最小 `1200×780`）。左侧固定侧边栏（252px）+ 右侧 `QStackedWidget` 页面栈。所有角色共用同一骨架，仅侧边栏条目与页面栈内容不同（由 `ROLE_PAGES` 决定）。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ┌────────────────┐  页面标题（30px/800）                                       │
│  │ ▒▒▒ 侧边栏 ▒▒▒ │  副标题（15.5px/灰）                                         │
│  │  🔥 薪火        │  ───────────────────────────────────────────────────────   │
│  │  师傅带徒·AI    │  │  QScrollArea 可滚动页面画布                              │
│  │ ─────────────  │  │  (卡片 / 指标卡 / 表格 / 表单 …)                         │
│  │  导航按钮…      │  │                                                         │
│  │  (弹性撑开)     │  └──────────────────────────────────────────────────────   │
│  │  👤 用户名       │                                                           │
│  │     角色         │                                                           │
│  │  🚪 退出登录      │                                                           │
│  └────────────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 0.3 侧边栏（SIDEBAR_QSS 专属，三类共用骨架 / 选项卡按角色不同）

`objectName=="sidebar"` 的 QWidget，仅 SIDEBAR_QSS 生效。侧边栏**宽度放大 1.5 倍（min/max-width `252px → 378px`）**，内部**所有字号增大 5px**（导航按钮 15→20、logo 24→29、logoSub 12.5→17.5、userinfo 13.5→18.5）；**导航按钮高度自适应内部文字**（`min-height:56px` + `padding:18px 32px`，不再固定高度，文字完整不截断）。按钮可勾选（`QButtonGroup` 互斥），选中态左边框 4px 白 + 半透明白底；底部 `userinfo` + `logoutBtn`。**骨架与样式三类完全一致，但选项卡清单由 `ROLE_PAGES[role]` 决定，三类别完全不同**（公共页"🔔 通知 / 💬 交流圈 / 📈 进度排名"三类均有，仅管理员把"进度排名"改为"📈 进度视图"且 pid=`admin_progress`）。各角色完整选项卡清单与专属侧边栏 UI 见 §一/§二/§三章首图。

```
┌────────────────────┐
│ 🔥 薪火              │  ← logo (29px/800/#fff)
│ 师傅带徒·AI导师       │  ← logoSub (17.5px/#e8b6b6)
│ ────────────────── │
│  [ 导航按钮… ]        │  ← 由 ROLE_PAGES[role] 生成, 20px, min-height 56px 自适应
│  (addStretch)        │
│  👤 张三              │  ← userinfo (#f0c4c4/18.5px) = full_name / username
│     师傅              │  ← role_names: admin=管理员 / master=师傅 / apprentice=徒弟
│  🚪 退出登录           │  ← logoutBtn (#ffd9a8) → _logout()
└────────────────────┘
   导航按钮生成: for pid in page_ids: QPushButton(PAGE_META[pid][0])
   选中态: rgba(255,255,255,.18)+白字+左边框4px白 (SIDEBAR_QSS)
   通知按钮: 进入后 _refresh_notify_badge() 改写文案 "🔔 通知 (N)"
```

三类选项卡差异一览（文案取自 `PAGE_META`，由 `ROLE_PAGES` 映射）：

| 角色 | 专属选项卡（pid） | 与公共页之差 |
|------|------------------|--------------|
| 师傅 master | 概览 / 投喂资料 / 知识库 / 徒弟管理 / 定制计划 / 批改检测 / 学情看板 + **进度排名** + 交流圈 + 通知 | 7 个师傅专属 + 进度排名(progress_view) |
| 徒弟 apprentice | 概览 / 摸底考试 / 学习计划 / 当日复习 / 错题本 / 同门战况 / 我的计划 + **进度排名** + 交流圈 + 通知 | 7 个徒弟专属 + 进度排名(progress_view) |
| 管理员 admin | 概览 / 审核注册 / 课程库 / 用户管理 / 部门管理 / 操作日志 + **进度视图** + 交流圈 + 通知 | 6 个管理员专属 + 进度视图(admin_progress) |

### 0.4 登录 / 注册对话框（LoginDialog，三类入口共用）

`QDialog` 固定 `660×980`，红白渐变背景，`_RED_WHITE_QSS` 仅作用于本对话框。整体字号较此前放大 5px（QLabel 14.5→19、loginTitle 28→33、loginSub/loginMsg 14→19、authBtn 17→22、tabBtn 16→21），输入框 `QLineEdit`/`QComboBox` 的**预览文字(placeholder)与输入文字字号同步放大至 19px，与"用户名"等标签字号一致**，输入框竖直内边距再 +3px（`16px→19px` 上下、左右 18px）避免文字被遮挡；dialog 外边距 `72/54/72/46`、根间距 22，登录表单间距 16、注册表单间距 12 且各列(标签↔输入框)间距 10、行内列间距 18。**注册表单（字段多）整体包入 `QScrollArea`，窗口高度不足时滚动而非压缩输入框**。顶部两个可勾选 `tabBtn`（登录/注册，互斥），点击切换内部 `QStackedWidget` 的两种独立表单；**底部提交按钮 `authBtn` 随模式变文案**（`_do_auth` 按 `currentIndex` 分流到 login / register 两个接口）。两个表单为**独立 Widget**，字段完全不同，分别绘制如下。

#### 0.4.1 登录 UI（_build_login_form，currentIndex=0）

仅含用户名 + 密码两项，密码 `EchoMode=Password`，回车（`returnPressed`）直接触发登录。

```
┌────────────────────────────────────┐
│      🔥 薪火 · AI 导师系统          │  ← loginTitle (33px/800/#b91c1c)
│      师傅带徒 · 知识传承 · AI 加速   │  ← loginSub (19px/#9c8a8a)
│  [ 登 录 ]     [ 注 册 ]            │  ← tabBtn(21px)：登录=选中(底部3px红下划线)
│  ────────────────────────────────  │  ← tabLine(QFrame.HLine)
│  用户名                              │  ← 标签 19px
│  [______________________________]  │  ← l_uname (QLineEdit, 19px, placeholder=输入用户名)
│  密码                                │  ← 标签 19px
│  [______________________________]  │  ← l_pwd (19px, Password掩码, placeholder=输入密码)
│                                     │
│                                     │  ← addStretch() 撑出底部空白
└────────────────────────────────────┘
         (下接通用 消息区 + 提交按钮，见 0.4.3)
```

#### 0.4.2 注册 UI（_build_register_form，currentIndex=1）

8 字段两列网格（`row1~row4`）+ 角色/公司下拉 + 提示条。仅"用户名/密码/角色"为必填（标 `*`），其余可选。`r_role` 仅含"师傅/管理员"，**徒弟由师傅在系统内创建，不可在此注册**。

```
┌────────────────────────────────────┐
│      🔥 薪火 · AI 导师系统          │
│  [ 登 录 ]     [ 注 册 ]            │  ← tabBtn：注册=选中(底部3px红下划线)
│  ────────────────────────────────  │
│  ┌ 用户名* ┐  ┌ 密码*   ┐          │  ← row1: r_uname | r_pwd(Password)
│  │[______]│  │[______]│          │
│  └────────┘  └────────┘          │
│  ┌ 姓名   ┐  ┌ 工号    ┐          │  ← row2: r_name | r_empno(placeholder=M001)
│  │[______]│  │[______]│          │
│  └────────┘  └────────┘          │
│  ┌ 手机号  ┐  ┌ 办公账号 ┐         │  ← row3: r_phone | r_office
│  │[______]│  │[______]│          │
│  └────────┘  └────────┘          │
│  ┌ 角色*  ┐  ┌ 公司    ┐          │  ← row4: r_role(QComboBox 师傅|管理员)
│  │[师傅▾]│  │[默认公司▾]│        │  ←      r_company(来自 GET /api/companies)
│  └────────┘  └────────┘          │
│  💡 徒弟账号由师傅在系统内创建；      │  ← tip(18px/#9c8a8a)
│     注册后需管理员审核通过方可登录。  │
└────────────────────────────────────┘
         (下接通用 消息区 + 提交按钮，见 0.4.3)
```

#### 0.4.3 通用底部（两种模式共用）

消息区 `loginMsg` 与提交按钮 `authBtn` 在 `QStackedWidget` 之外，始终常驻；按钮文案由 `_switch_mode` 同步（`登 录` / `注 册`）。

```
┌────────────────────────────────────┐
│      (loginMsg 消息区, 居中可换行)    │  ← 失败红 / 审核橙warn / 成功绿
│      [    登 录 / 注 册    ]        │  ← authBtn 红橙渐变(22px/700, 禁用态灰)
└────────────────────────────────────┘
   登录成功 → token/user 写入, accept() 进入主窗口
   登录被拦(含"审核") → ⏳ 橙色提示, 停留本对话框
   注册成功 → ✅ 绿色提示 + 自动切回登录页并回填用户名
```

接口：`GET /api/companies`（填充 `r_company`）、`POST /api/login`、`POST /api/register`（详见 §4 公共接口表）。

### 0.5 通知中心（NotifyPagesMixin，三类共用）

侧边栏"🔔 通知"入口，进入即拉取并刷新侧边栏红点。

```
┌─ 头部 ────────────────────────────────┐
│ 未读 2 条               [全部标为已读]  │  ← 灰字(600)+次要按钮
└───────────────────────────────────────┘
┌─ 通知卡 (card, accent=红=未读) ────────┐
│ ● [系统] 您的计划已生成       08-03 09  │  ← ●红点+badge(信息)+内容(600)+时间
└───────────────────────────────────────┘
┌─ 通知卡 (无 accent=已读) ─────────────┐
│   [审核] 注册已通过         08-02 18    │  ← 无红点+内容(400)
└───────────────────────────────────────┘
```
接口：`GET /api/notifications`、`POST /api/notifications/read`（并 `_refresh_notify_badge()`）。

### 0.6 交流圈（SocialPagesMixin，三类共用）

侧边栏"💬 交流圈"入口，发帖/列表/点赞/评论。

```
发帖区 (QGroupBox ✍️ 发帖)：
┌──────────────────────────────────────────┐
│ [ 分享想法、可 @同事…            ]          │  ← QTextEdit(84px)
│ (消息)                          [ 发布 ]   │  ← 主按钮(右对齐)
└──────────────────────────────────────────┘
帖子卡 (card, padding14)：
┌──────────────────────────────────────────┐
│ 张三  [师傅]              2026-08-03 10:2 │  ← 15px/700+badge+灰时间
│ 今天带徒复盘，订单幂等讲得不错 👍          │  ← 15.5px 正文
│ 🤍 3    💬 1 评论                       │  ← ghost_button 点赞/评论
└──────────────────────────────────────────┘
         │ 点击"评论" → QDialog(440×460) 含 QScrollArea 评论列表 + 输入行
```
接口：`POST /api/posts`、`GET /api/posts`、`POST /api/posts/{id}/like`、`GET/POST /api/posts/{id}/comments`。

### 0.7 进度三视图（ProgressPagesMixin._build_progress_view，三类共用）

侧边栏"📈 进度排名"（师傅/徒弟 pid=`progress_view`）或"📈 进度视图"（管理员 pid=`admin_progress`）均复用此 Mixin。顶部 `QComboBox` 切换视图，管理员仅"公司"。

```
[ 视图：公司 ▾ ]            ← 管理员仅 [公司]；师傅/徒弟含 [公司][部门][同门]
┌─ 排行卡 (#1, 金边) ───────────────────┐
│ #1  张三 (M001)           [████░░] 80% │  ← 17px/800金 + 姓名 + 进度条 + 百分比(红)
│     师傅: 李师傅          92 分         │  ← 师傅(灰) + 均分(灰)
└───────────────────────────────────────┘
┌─ 排行卡 (#2, 银边) ───────────────────┐
│ #2  王五 (M002)           [███░░░] 65%  │
└───────────────────────────────────────┘
  …（#3 铜边 / #4+ 灰边，颜色取 Color.RANK）
```
接口：`GET /api/progress/company`、`GET /api/progress/department`、`GET /api/progress/same-master`。

---

## 一、师傅（Master）UI 设计

侧边栏条目（`ROLE_PAGES["master"]`）：概览 / 投喂资料 / 知识库 / 徒弟管理 / 定制计划 / 批改检测 / 学情看板 / **进度排名(复用 §0.7)** / **交流圈(复用 §0.6)** / **通知(复用 §0.5)**。

### 1.0 师傅侧边栏（完整选项卡 UI）

骨架同 §0.3，按 `ROLE_PAGES["master"]` 生成 10 个导航按钮，首个"概览"默认选中。

```
┌────────────────┐
│ 🔥 薪火          │  ← logo
│ 师傅带徒·AI导师   │  ← logoSub
│ ─────────────── │
│  📊 概览(选中)    │  ← master_overview (默认勾选)
│  📥 投喂资料      │  ← master_ingest
│  🧠 知识库        │  ← master_knowledge
│  👥 徒弟管理      │  ← master_apprentices
│  📝 定制计划      │  ← master_plans
│  ✅ 批改检测      │  ← master_grading
│  📋 学情看板      │  ← master_dashboard
│  📈 进度排名      │  ← progress_view (复用 §0.7)
│  💬 交流圈        │  ← social_posts (复用 §0.6)
│  🔔 通知          │  ← notifications (复用 §0.5, 有未读显 "(N)")
│  (addStretch)    │
│  👤 张三          │  ← userinfo
│     师傅          │
│  🚪 退出登录       │  ← logoutBtn
└────────────────┘
```

### 1.1 师傅概览（_build_master_overview）

`QGridLayout` 排 4 张 `stat_card`（知识维度/知识点/徒弟数量/桌面版本），下方 `QGroupBox"🚀 带徒五步法"` 引导卡。

```
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│     8      │ │     24     │ │     5      │ │    v2.0    │
│  知识维度   │ │   知识点   │ │  徒弟数量   │ │  桌面版本   │
└────────────┘ └────────────┘ └────────────┘ └────────────┘
   红            绿            橙            红(危险)
┌─ 🚀 带徒五步法 ─────────────────────┐
│ 1.投喂资料 2.AI精炼 3.创建徒弟         │
│ 4.生成计划 5.学情看板(含批改)         │
└──────────────────────────────────────┘
```
接口：`GET /api/master/knowledge`(main内联)`{dimensions:[{name,points}]}`；`GET /api/master/apprentices`(auth)`{apprentices:[...]}`。

### 1.2 投喂资料（_build_master_ingest）

三个 `QGroupBox`：本地文件夹投喂、博客 URL 投喂、快速演示。"本地文件夹投喂"支持**三种路径录入方式**：① 手动输入路径；② 点击「📂 浏览」按钮唤起系统资源管理器（`QFileDialog.getExistingFile()` / `getOpenFileNames()`）选择文件夹或文件；③ 将本地文件夹/文件直接**拖拽到输入框区域**（`dragEnterEvent`/`dropEvent` 接收 `QUrl` 列表，提取本地路径回填）。

```
┌─ 📁 本地文件夹投喂 ──────────────────┐
│ 输入含 md/txt/pdf/docx/代码的文件夹路径 │
│ ┌──────────────────────────────────┐ │
│ │ [ C:\Users\TS\Desktop\入职学习   ▌] │ │  ← QLineEdit (支持拖拽放置)
│ │   拖拽文件夹 / 文件到此，或点浏览    │ │
│ └──────────────────────────────────┘ │
│ [ 📂 浏览… ]   (消息)  [ 开始投喂 ]   │  ← 浏览=次要按钮; 开始投喂=红框红字按钮(左对齐)
└──────────────────────────────────────┘
┌─ 🌐 博客 URL 投喂 ───────────────────┐
│ [ https://example.com/a            ] │  ← QTextEdit(96px, 每行一个)
│ (消息)  [ 抓取并投喂 ]                │  ← 抓取并投喂=红框红字按钮(左对齐)
└──────────────────────────────────────┘
┌─ 🎯 快速演示 ────────────────────────┐
│ 使用内置"智能订单交易系统"示例知识库    │
│ [ 加载示例知识库 ]                    │  ← 次要按钮
└──────────────────────────────────────┘
```

本地文件夹投喂交互细节：

| 方式 | 控件/事件 | 行为 |
|------|-----------|------|
| 手动输入 | `QLineEdit` | 直接键入绝对路径，回车或点「开始投喂」提交 |
| 资源管理器选择 | 「📂 浏览…」`QPushButton` → `QFileDialog` | 多选模式可同时选文件与文件夹；单选文件夹用 `getExistingFile()`；选区后把路径拼成 `; ` 分隔字符串回填 `QLineEdit` |
| 拖拽放置 | `dragEnterEvent`/`dropEvent`（`setAcceptDrops(True)`） | 拖入时高亮输入框边框；`dropEvent` 取 `event.mimeData().urls()` 转本地路径，追加到 `QLineEdit`（与浏览结果同格式） |

> 说明：浏览与拖拽最终都归一为「路径字符串」填入 `QLineEdit`，点击「开始投喂」仍走 `POST /api/master/ingest`（`{path}`），后端按路径递归扫描 `md/txt/pdf/docx/代码`。
>
> **投喂按钮样式（红框红字）**：「开始投喂」与「抓取并投喂」两个按钮采用 **红色边框 + 红色字体**（白底、`border:1.5px solid #dc2626; color:#dc2626; border-radius:8px`），与全局主按钮（红底白字）视觉区分，强调"发起投喂动作"。悬停 `background:#fef2f2`，按下 `border-color:#b91c1c; color:#b91c1c`。实现上新增 `ui.theme.ingest_button()` 工厂返回带该样式的 `QPushButton`（仍返回 QWidget 子类，遵守铁律）。
接口：`POST /api/master/ingest`(`{path}`,P4)、`POST /api/master/ingest/url`(`{urls:[...]}`,P4)。

### 1.3 知识库（_build_master_knowledge）

顶部"🧪 触发 AI 精炼"成功按钮 + 提示，下方维度卡列表（空态显示 empty_label）。

```
[🧪 触发 AI 精炼]  投喂资料后点击，AI 自动生成知识维度与考点树
┌─ 知识维度卡 (card, accent=红) ────────┐
│ 📦 交易系统基础                        │  ← 16px/700
│ 涵盖订单、支付与对账核心流程            │  ← 描述(灰/14)
│ · 订单创建流程      [掌握]             │  ← 考点行(14.5)
│ · 支付状态机        [了解]             │
│ · 对账差异处理      [未知]             │
└──────────────────────────────────────┘
```
接口：`GET /api/master/knowledge`(main内联)、`POST /api/master/refine`(P3)`{success,...}`。

### 1.4 徒弟管理（_build_master_apprentices）

顶部"➕ 创建徒弟账号"`QGroupBox`（用户名+密码+创建按钮），下方"👥 我的徒弟"表格（`QTableWidget`，列：用户名/创建时间/操作[生成计划]）。

```
┌─ ➕ 创建徒弟账号 ─────────────────────┐
│ [用户名________] [初始密码________]    │  ← 两列 QLineEdit(密码掩码)
│ (消息)  [ 创建徒弟 ]                   │  ← 主按钮(左对齐)
└──────────────────────────────────────┘
👥 我的徒弟
┌────────┬────────────┬──────────┐
│ 用户名  │ 创建时间    │ 操作     │  ← QTableWidget(斑马纹, 无编辑)
│ 王五    │ 2026-08-01 │[生成计划]│  ← 主按钮(单元格内)
└────────┴────────────┴──────────┘
```
接口：`POST /api/master/apprentices`(`{username,password}`,auth)、`GET /api/master/apprentices`(auth)、`POST /api/master/plan/generate`(`{apprentice_id}`,P3)（表格内"生成计划"触发 `_gen_plan`）。

### 1.5 定制培养计划（_build_master_plans）

"➕ 为徒弟定制培养计划"`QGroupBox`：选徒弟下拉 + 课程勾选区（`card` 内 `QCheckBox` 列表，来自课程库）+ 创建按钮；下方"📋 已有计划"卡片列表。

```
┌─ ➕ 为徒弟定制培养计划 ───────────────┐
│ 选择徒弟: [ 王五 ▾ ]                   │  ← QComboBox
│ 勾选要加入计划的课程：                 │
│ ┌─ card ──────────────────────────┐  │
│ │ ☑ 订单系统实战 [document]        │  │  ← QCheckBox
│ │ ☐ 支付流程精讲 [video]           │  │
│ └─────────────────────────────────┘  │
│ (消息)  [ 创建计划 ]                  │  ← 主按钮
└──────────────────────────────────────┘
📋 已有计划
┌─ 计划卡 (card, padding12) ───────────┐
│ 定制培养计划 → 王五      2026-08-02…  │  ← 600黑字 + 灰时间
└──────────────────────────────────────┘
```
接口：`GET /api/master/apprentices`(auth)、`GET /api/admin/courses`(P6)`{courses:[{id,title,type}]}`、`POST /api/master/plans`(`{apprentice_id,name,course_ids:[...]}`,P6)。

### 1.6 批改检测（_build_master_grading）

顶部提示 + 徒弟下拉；选择徒弟后异步加载其检测提交卡片（每张含终评分 `QDoubleSpinBox` + 通过/重做按钮）。

```
提示: 选择徒弟，查看检测提交，终评改分与进度判定。
[ -- 选择徒弟 -- ▾ ]
┌─ 检测提交卡 (card, accent=橙) ────────┐
│ 交易系统订单模块    [第1次][待评]      │  ← badge(信息)+badge(橙/警告)
│ 答案: 用户在订单创建后调用 pay()…       │  ← 灰字(14)
│ AI 初评: 82    师傅终评: 未评          │  ← 黑字(14/600)
│ 终评分数: [ 82 ]  [✅通过并保存][需重做]│  ← QDoubleSpinBox(0~100)+成功/次要按钮
└──────────────────────────────────────┘
```
接口：`GET /api/master/apprentice/{apprentice_id}/quizzes`(P6)`{quizzes:[...]}`、`POST /api/master/quizzes/{quiz_id}/score`(`{master_score,status}`,P6)（`_score_quiz`）。

### 1.7 学情看板（_build_master_dashboard）

选徒弟下拉 → 加载其掌握等级，套 `QGroupBox"🎯 知识掌握等级"`，内部逐维度调用 **`_mastery_bar(m)`**（模块级纯函数，被徒弟看板复用，见 §2.7 复用说明）。

```
[ -- 选择徒弟 -- ▾ ]
┌─ 🎯 知识掌握等级 (QGroupBox) ─────────┐
│ 交易系统基础 — 熟练                     │
│ [████████████████████░░░░] 90%        │  ← 绿进度条
│ 支付模块 — 了解                        │
│ [███████████░░░░░░░░░░░░░░] 50%        │  ← 橙进度条
│ 风控模块 — 未知                        │
│ [█████░░░░░░░░░░░░░░░░░░░] 20%        │  ← 红进度条
└──────────────────────────────────────┘
```
接口：`GET /api/master/apprentices`(auth)、`GET /api/master/dashboard/{apprentice_id}`(main内联)`{mastery,assessments,reviews}`。

---

## 二、徒弟（Apprentice）UI 设计

侧边栏条目（`ROLE_PAGES["apprentice"]`）：概览 / 摸底考试 / 学习计划 / 当日复习 / 错题本 / 同门战况 / 我的计划 / **进度排名(复用 §0.7)** / **交流圈(复用 §0.6)** / **通知(复用 §0.5)**。

### 2.0 徒弟侧边栏（完整选项卡 UI）

骨架同 §0.3，按 `ROLE_PAGES["apprentice"]` 生成 10 个导航按钮，首个"概览"默认选中。

```
┌────────────────┐
│ 🔥 薪火          │  ← logo
│ 师傅带徒·AI导师   │  ← logoSub
│ ─────────────── │
│  📊 概览(选中)    │  ← appr_overview (默认勾选)
│  📝 摸底考试      │  ← appr_assess
│  📅 学习计划      │  ← appr_plan
│  🔄 当日复习      │  ← appr_review
│  📕 错题本        │  ← appr_mistakes
│  🏆 同门战况      │  ← appr_leaderboard
│  📋 我的计划      │  ← appr_my_plans
│  📈 进度排名      │  ← progress_view (复用 §0.7)
│  💬 交流圈        │  ← social_posts (复用 §0.6)
│  🔔 通知          │  ← notifications (复用 §0.5, 有未读显 "(N)")
│  (addStretch)    │
│  👤 王五          │  ← userinfo
│     徒弟          │
│  🚪 退出登录       │  ← logoutBtn
└────────────────┘
```

### 2.1 徒弟概览（_build_appr_overview）

"🚀 新手上路"`QGroupBox` 引导卡 + 错题统计 `QGridLayout`（2 张 `stat_card`）。

```
┌─ 🚀 新手上路 ────────────────────────┐
│ 1.摸底考试 2.等师傅生成计划 3.按计划学  │
│ 4.当日复习 5.同门战况                  │
└──────────────────────────────────────┘
┌────────────────┐ ┌────────────────────┐
│    12          │ │    5 / 7           │
│   错题总数      │ │  考试 / 复习错题    │
└────────────────┘ └────────────────────┘
   红(危险)          橙(警告)
```
接口：`GET /api/apprentice/mistakes`(P3)`{assess_mistakes,review_mistakes}`。

### 2.2 摸底考试（_build_appr_assess）

未开始时显示说明 + "🚀 开始摸底考试"主按钮；开始后逐题渲染（选择题 `QRadioButton` / 简答 `QTextEdit`），提交后追加反馈块，末题显示掌握等级（复用 `_mastery_bar`，见 §2.7）。

```
未开始态：
  说明: AI 将基于师傅知识库为你出题…   [🚀 开始摸底考试]

题目卡 (card, padding16)：
┌──────────────────────────────────────┐
│ 题目 2 / 10   [中等] [choice]         │  ← 灰字 + badge(橙) + badge(信息)
│ 下列关于订单幂等性的说法，正确的是？    │  ← 17px/700
│ ( ) 重复提交会创建多个订单            │  ← QRadioButton(选项解析自JSON)
│ ( ) 应通过唯一键防止重复             │
│ [ 提交答案 ]                          │  ← 主按钮
└──────────────────────────────────────┘
   ┌─ 反馈块 (背景 绿软/红软) ─────────┐
   │ 得分:80 | 正确答案:B…   [下一题 →] │
   └──────────────────────────────────┘
末题: 🎉 摸底考试完成！ + [掌握等级 QGroupBox(复用_mastery_bar)] + [重新考试]
```
接口：`POST /api/apprentice/assessment/start`(P3)`{assessment_id,questions}`、`POST /api/apprentice/assessment/answer`(`{question_id,answer}`,P3)`{score,feedback,answer_key}`、`GET /api/apprentice/assessment/result/{id}`(P3)`{mastery}`。

### 2.3 学习计划（_build_appr_plan）

今日学习卡（`card` accent=红，含 PDF 下载成功按钮）+ "🤖 AI 陪练答疑"`QGroupBox`（只读聊天区 + 输入框）。

```
┌─ 今日学习卡 (card, accent=红) ────────┐
│ 📖 今日学习 (Day 3)    [📄下载PDF讲义] │  ← 标题 + 成功按钮(落盘桌面)
│ 📝 今天重点掌握订单状态机               │
│ [阅读] 订单状态机详解        20 分钟    │
│ [视频] 支付流程实战          35 分钟    │
│ 总时长: 55 分钟                        │
└──────────────────────────────────────┘
┌─ 🤖 AI 陪练答疑 (QGroupBox) ─────────┐
│ (只读聊天记录区 220px)                 │
│ 🧑 什么是TCC事务？                     │
│ 🤖 TCC 是 Try/Confirm/Cancel…         │
│ [ 向AI导师提问…____________ ] [发送]   │  ← 输入框 + 主按钮
└──────────────────────────────────────┘
```
接口：`GET /api/apprentice/plan/today`(P3)`{today:{day_index,note,tasks}}`、`GET /api/apprentice/pdf/today`(P4, PDF流)、`POST /api/apprentice/ask`(`{question}`,P3)`{answer}`（`_do_chat`）。

### 2.4 当日复习（_build_appr_review）

与摸底结构一致（先取今日计划 → "🔄 开始当日复习" → 逐题卡 + 反馈块）。

```
未开始: 获取今日计划… → 基于今日学习内容，AI 将生成复习题  [🔄 开始当日复习]
题目卡：题目 N/total + 题干 + (单选/简答) + [提交]
   ┌─ 反馈块 ──────────────────────────┐
   │ 得分:75 | 巩固得不错   [下一题 →]   │
   └──────────────────────────────────┘
末题: 🎉 复习完成！ + [再次复习]
```
接口：`GET /api/apprentice/plan/today`(P3)、`POST /api/apprentice/review/start`(`{plan_day_id}`,P3)`{review_id,questions}`、`POST /api/apprentice/review/answer`(`{question_id,answer,review_id}`,P3)`{score,feedback}`。

### 2.5 错题本（_build_appr_mistakes）

合并考试/复习错题，每张 `card`(accent=红) 显示题干 + 你的回答 + 正确答案 + 得分反馈。

```
┌─ 错题卡 (card, accent=红) ───────────┐
│ ❌ 下列关于TCC的说法错误的是？         │  ← 15px/700
│ 你的回答: 选A                         │  ← hint_label
│ 正确答案: B                           │
│ 得分: 40 | 需加强事务一致性理解        │
└──────────────────────────────────────┘
```
接口：`GET /api/apprentice/mistakes`(P3)`{assess_mistakes,review_mistakes}`。

### 2.6 同门战况（_build_appr_leaderboard）

排行卡列表，"我"行高亮品牌红姓名并标注"(我)"（卡片配色取 `Color.RANK` 奖牌色）。

```
┌─ 战况卡 (#1, 金边) ──────────────────┐
│ #1  张三 (我)   均分:92 熟练:5维度 错题:1│  ← 姓名红(700)+灰指标
└──────────────────────────────────────┘
┌─ 战况卡 (#2, 银边) ──────────────────┐
│ #2  王五      均分:85 熟练:3维度 错题:4│
└──────────────────────────────────────┘
```
接口：`GET /api/apprentice/leaderboard`(main内联)`{leaderboard:[{apprentice_id,username,avg_score,mastery_count,mistake_count}],my_id}`。

### 2.7 我的培养计划（_build_appr_my_plans）

计划卡列表（每项含"✍ 提交检测"次要按钮弹窗）+ "🧾 我的检测历史"卡片列表。任务检测弹窗 `QDialog`(460×340) 含 `QTextEdit` + 提交。

```
┌─ 计划卡 (card, accent=红) ───────────┐
│ 📋 定制培养计划   [已完成]             │  ← 标题 + badge(成功)(若completed_at)
│ · 订单系统实战 [document]   [✍提交检测]│  ← 次要按钮(弹窗)
│ · 支付流程精讲 [video]     [✍提交检测]│
└──────────────────────────────────────┘
🧾 我的检测历史
┌─ 检测卡 (card) ──────────────────────┐
│ 订单系统实战 · 第1次  [已通过]  AI:82|终评:—│  ← badge + 灰字
└──────────────────────────────────────┘

任务检测弹窗 QDialog(460×340)：
┌─ 任务检测 — 订单系统实战 ────────────┐
│ 写下学习总结/答题，AI初评，师傅终评。   │
│ [ 输入你的答案…              ]         │  ← QTextEdit
│ (消息)                    [ 提交检测 ] │  ← 主按钮(右对齐)
└──────────────────────────────────────┘
```
接口：`GET /api/apprentice/plans`(P6)`{plans:[{name,completed_at,items}]}`、`GET /api/apprentice/quizzes`(P6)`{quizzes:[...]}`、`POST /api/apprentice/quiz/submit`(`{plan_item_id,answer}`,P6/P3)`{ai_score,...}`（`_open_quiz_dialog`）。

### 2.8 复用说明（徒弟侧）

- **掌握等级进度条 `_mastery_bar(m)`**：摸底结果（§2.2 末题）与师傅学情看板（§1.7）**共用同一模块级纯函数**，熟练/了解/未知 → 90/50/20%，进度条颜色绿/橙/红。
- **进度排名 / 交流圈 / 通知**：分别复用 §0.7 / §0.6 / §0.5，徒弟侧无任何重写。

---

## 三、管理员（Admin）UI 设计

侧边栏条目（`ROLE_PAGES["admin"]`）：概览 / 审核注册 / 课程库 / 用户管理 / 部门管理 / 操作日志 / **进度视图(复用 §0.7)** / **交流圈(复用 §0.6)** / **通知(复用 §0.5)**。

### 3.0 管理员侧边栏（完整选项卡 UI）

骨架同 §0.3，按 `ROLE_PAGES["admin"]` 生成 9 个导航按钮，首个"概览"默认选中。注意管理员把"进度排名"改名为"进度视图"（pid=`admin_progress`，复用 §0.7 但 tabs 仅"公司"）。

```
┌────────────────┐
│ 🔥 薪火          │  ← logo
│ 师傅带徒·AI导师   │  ← logoSub
│ ─────────────── │
│  📊 概览(选中)    │  ← admin_overview (默认勾选)
│  🔍 审核注册      │  ← admin_pending
│  📚 课程库        │  ← admin_courses
│  👥 用户管理      │  ← admin_users
│  🏢 部门管理      │  ← admin_departments
│  🧾 操作日志      │  ← admin_logs
│  📈 进度视图      │  ← admin_progress (复用 §0.7, 仅"公司"tab)
│  💬 交流圈        │  ← social_posts (复用 §0.6)
│  🔔 通知          │  ← notifications (复用 §0.5, 有未读显 "(N)")
│  (addStretch)    │
│  👤 李四          │  ← userinfo
│     管理员         │
│  🚪 退出登录       │  ← logoutBtn
└────────────────┘
```

### 3.1 管理员概览（_build_admin_overview）

4 张 `stat_card`（徒弟数/师傅数/待审核/系统状态），待审核 >0 时显示橙色预警卡 + "去审核"按钮（内部 `_switch_page("admin_pending")`）。

```
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│    20      │ │    3       │ │    2       │ │   正常     │
│   徒弟数     │ │   师傅数    │ │  待审核     │ │  系统状态   │
└────────────┘ └────────────┘ └────────────┘ └────────────┘
   红(危险)       红(品牌)       橙(警告)       绿(成功)
┌─ 预警卡 (card, accent=橙) ───────────┐
│ ⚠️ 有 2 个注册申请待审核   [ 去审核 ]  │  ← 600黑字 + 主按钮
└──────────────────────────────────────┘
```
接口：`GET /api/admin/stats`(P6,P1)`{total_apprentices,total_masters,pending_review,...}`。

### 3.2 审核注册（_build_admin_pending）

待审核用户卡片列表，每张含角色 badge + 工号/手机/办公账号 + 通过(成功)/驳回(危险)按钮。

```
┌─ 待审核卡 (card, accent=橙) ──────────┐
│ 李四 (lisi)              [师傅]       │  ← 16px/700 + badge(红软)
│ 工号:M002  手机:138…  办公:li@ts      │  ← 灰字
│ [✅ 通过]  [❌ 驳回]                   │  ← 成功按钮 + 危险按钮
└──────────────────────────────────────┘
```
接口：`GET /api/admin/pending`(P6)`{pending:[{id,full_name,username,role,employee_no,phone,office_account}]}`、`POST /api/admin/approve`(`{user_id}`,P6)、`POST /api/admin/reject`(`{user_id}`,P6)。

### 3.3 课程库（_build_admin_courses）

"➕ 创建课程"`QGroupBox`（名称 + 类型 `QComboBox`[document/video/link/quiz] + 内容 + 创建按钮）；下方课程卡片列表，每行含删除(危险)按钮。

```
┌─ ➕ 创建课程 ────────────────────────┐
│ [课程名称________] [document ▾]       │  ← QLineEdit + QComboBox
│ [ 内容/描述                    ]      │  ← QTextEdit(70px)
│ (消息)  [ 创建课程 ]                  │  ← 主按钮(左对齐)
└──────────────────────────────────────┘
📚 课程列表
┌─ 课程卡 (card) ──────────────────────┐
│ 订单系统实战  [document]      [删除]  │  ← badge(信息) + 危险按钮
└──────────────────────────────────────┘
```
接口：`POST /api/admin/courses`(`{title,type,content}`,P6)、`GET /api/admin/courses`(P6)`{courses:[{id,title,type}]}`、`DELETE /api/admin/courses/{id}`(P6)。

### 3.4 用户管理（_build_admin_users）

用户卡片列表，每行含角色 badge + 状态 badge（`_STATUS_META`：已通过/待审核/已驳回）+ 师傅名；徒弟行额外有"重绑师傅"次要按钮 → 弹窗 `QDialog`(360×160)。

```
┌─ 用户行卡 (card) ───────────────────────────────┐
│ 王五  [徒弟] [已通过]  工号:M003 师傅:张三 [重绑师傅]│
└──────────────────────────────────────────────────┘

重绑师傅弹窗 QDialog(360×160)：
┌─ 重绑师傅 — 王五 ──────────┐
│ 为该徒弟选择新的师傅：        │
│ [ 张三 ▾ ]                  │  ← QComboBox(仅师傅列表)
│              [ 确认重绑 ]    │  ← 主按钮(右对齐)
└─────────────────────────────┘
```
接口：`GET /api/admin/users`(P6)`{users:[{id,full_name,username,role,status,employee_no,master_name}]}`、`POST /api/admin/rebind-master`(`{apprentice_id,master_id}`,P6)（`_open_rebind_dialog`）。

### 3.5 部门管理（_build_admin_departments）

"➕ 新增部门"`QGroupBox`（单行 `QHBoxLayout`：输入框 + 添加按钮）；下方部门卡片列表。

```
┌─ ➕ 新增部门 ────────────────────────┐
│ [ 部门名称________ ]  [ 添加 ]        │  ← QLineEdit + 主按钮
└──────────────────────────────────────┘
🏢 部门列表
┌─ 部门卡 (card) ──────────────────────┐
│ 🏢 交易研发部                        │
└──────────────────────────────────────┘
```
接口：`POST /api/admin/departments`(`{name}`,P6)、`GET /api/admin/departments`(P6)`{departments:[{name}]}`。

### 3.6 操作日志（_build_admin_logs）

日志卡片列表（时间线式），每行：动作(品牌红) + 目标类型/ID/详情 + 灰时间。

```
┌─ 日志卡 (card, padding8) ────────────┐
│ [approve]  用户 #12 审核通过  2026-08-03│  ← 红字(700)+黑字+灰时间
└──────────────────────────────────────┘
```
接口：`GET /api/admin/logs`(P6)`{logs:[{action,target_type,target_id,detail,created_at}]}`。

### 3.7 复用说明（管理员侧）

- **进度视图**：复用 §0.7 `ProgressPagesMixin._build_progress_view`，且 `role=="admin"` 时 `tabs` 仅保留"公司"视图（代码 `if role=="admin": tabs=[("公司","company")]`）。
- **交流圈 / 通知**：复用 §0.6 / §0.5。

---

## 四、公共接口对照表（登录 / 通知 / 交流圈 / 进度 / 数据层）

| 模块 | 控件 | 接口（方法 路径 / 请求体 / 模块 / 响应关键字段） |
|------|------|-------------------------------------------|
| 登录 | 公司下拉初始化 | `GET /api/companies` / 无 / P1 / `{companies:[{id,name}]}` |
| 登录 | 提交(登录) | `POST /api/login` / `{username,password}` / P1 / `{success,token,user}` |
| 登录 | 提交(注册) | `POST /api/register` / `{username,password,role,company_id,employee_no,phone,office_account,full_name}` / P1 / `{success,message}` |
| 侧边栏 | 通知红点 | `GET /api/notifications` / 无 / P7,P1 / `{unread_count}` |
| 侧边栏 | 退出登录 | `POST /api/logout` / 无 / — |
| 通知 | 列表 | `GET /api/notifications`(P7,P1)`{notifications:[{type,content,read,created_at}],unread_count}` |
| 通知 | 全部已读 | `POST /api/notifications/read`(`{id?}`,P7,P1)`{success}`（并刷新红点） |
| 交流圈 | 发帖 | `POST /api/posts`(`{content,author_name?}`,P7)`{post_id}` |
| 交流圈 | 列表 | `GET /api/posts`(P7)`{posts:[{id,author_name,author_role,content,likes_count,comments_count,liked_by_me,created_at}]}` |
| 交流圈 | 点赞 | `POST /api/posts/{post_id}/like` / 无 / P7 / `{liked}` |
| 交流圈 | 评论 | `GET/POST /api/posts/{post_id}/comments`(`{content}`,P7)`{comments:[...]}/{message}` |
| 进度 | 公司/部门/同门 | `GET /api/progress/company`、`/department`、`/same-master`(P6)`{apprentices:[{apprentice_name,master_name,progress_pct,avg_score,rank}]}` |
| 数据层 | 全部 `_api_call` | `ApiThread(QThread)`：自动 `Bearer` 头、连接失败重试 5 次、PDF 落盘桌面并打开、`finished`→`callback(res)` |

> 师傅/徒弟/管理员各自专属接口已分别列于 §1 / §2 / §3 各小节。

---

## 五、设计系统落地要点（与代码一致）

1. **令牌集中**：颜色/圆角全部来自 `Color` / `Radius`，业务页面不硬编码色值。
2. **两套 QSS**：`GLOBAL_QSS`（作用于 `QMainWindow`/`QDialog`/`QWidget#content` 及通用控件）、`SIDEBAR_QSS`（仅 `objectName=="sidebar"`）。
3. **组件工厂返回 QWidget**：`card/stat_card/badge/*_button/*_label/divider/loading_label/empty_label` 全部返回 QWidget 子类，样式仅作用于 widget。
4. **投影作用 widget**：`apply_shadow()` 用 `QGraphicsDropShadowEffect` 加在卡片上（绝不作用于 layout）。
5. **铁律**：无任意 `QLayout.setStyleSheet()` 调用，历史上 8 处崩溃根因已根除。

---

## 六、与 PRD 的差异 & 备注（供验收对齐）

- 实际侧边栏宽度 `252px`（PRD 未标注，以代码 `min/max-width:252px` 为准）。
- "进度视图"命名：师傅/徒弟侧 pid=`progress_view`（侧边栏"📈 进度排名"），管理员侧 pid=`admin_progress`（侧边栏"📈 进度视图"），二者复用同一 `ProgressPagesMixin`。
- 复用清单：**`_mastery_bar`**（师傅看板 §1.7 ↔ 徒弟摸底结果 §2.2）；**`_build_progress_view`**（三类均用 §0.7）；**登录/通知/交流圈**（三类共用 §0.4/0.5/0.6）。
- 新增页面须在三处同步登记：`PAGE_META` / `ROLE_PAGES` / `_load_page()` 的 `builders` 字典（见 PRD 第八节风险点）。

---

> 本文档所有 ASCII 图均依据 `ui/` 包实际源码逐控件还原，按师傅/徒弟/管理员三类组织，可作为前端视觉走查与后端联调的对照基线。
