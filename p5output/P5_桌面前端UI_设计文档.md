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

#### 0.1.1 全局铁律：文字背景一律透明

**规则**：本项目中**所有文字控件的背景色必须与其所在容器背景一致，即一律透明**。除非某处明确要求带底色（如 `badge()` 药丸标签、选中态高亮），否则任何 `QLabel` 都不得出现与父容器不同的底色（典型症状：白卡片上的文字呈灰色底块）。

**成因**：Qt 在部分 Windows 主题下，未显式声明 `background` 的 `QLabel` 会回退到系统调色板的 `Button`/`Window` 灰底；而**内联 `setStyleSheet()` 的优先级高于全局 QSS**，一旦内联样式串里只写了 `color`/`font-size` 而漏写 `background`，该 Label 就可能重新暴露灰底。

**两层防护**：

| 层级 | 做法 | 覆盖范围 |
|------|------|----------|
| 第 1 层（兜底） | `GLOBAL_QSS` 的 `QLabel{}` 基础规则中加入 `background: transparent;` | 所有**未设内联样式**、或内联样式经第 2 层补齐的 Label |
| 第 2 层（逐处） | 所有内联 `setStyleSheet()` 的文字控件样式串**必须显式包含 `background:transparent;`** | 全部 6 个页面模块 + `theme.py` 工厂，约 60 处 |

> 第 1 层解决默认情况，但**无法覆盖内联样式**——Qt 中内联 `setStyleSheet` 会整体接管该控件的样式解析，全局规则中的 `background` 不会自动合并进来。因此第 2 层是必需的，二者缺一不可。

**豁免清单**（这些控件**保留**自身底色，不做透明化）：

| 控件 | 保留原因 |
|------|----------|
| `badge()` | 药丸标签，底色即设计语义（成功绿/警告橙等柔和底） |
| `card()` / `stat_card()` 的 `QFrame` 容器 | 卡片本体白底 `Color.SURFACE` |
| `divider()` | 1px 分隔线，靠 `background` 着色 |
| `QPushButton` / `QLineEdit` / `QTextEdit` / `QProgressBar` | 交互控件，有独立底色规范 |
| 侧边栏选中态、`stat_card` 选中态 | 高亮底色为交互反馈 |

**新增代码约定**：今后任何新增的 `QLabel` 内联样式，样式串**必须带 `background:transparent;`**；能用 `theme.py` 工厂（`hint_label`/`section_label`/`guide_item` 等）的一律优先用工厂，工厂内部已统一处理。

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
│ 可选 accent 左边框      │    │  文字层 background:透明 │
└────────────────────────┘                                  │  可选 clickable=True   │
                              │  (手型+▸+悬停/选中态)   │
                              └──────────────────────┘
┌─ hint_label ──────────┐    ┌─ guide_item ─────────┐
│ 通用提示 19px 灰       │    │ 引导卡专用 24px/500   │
│ (十余处共用, 勿改)     │    │ 配 25px/700 卡标题    │
└────────────────────────┘    └──────────────────────┘
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
│  │  🔥 薪火        │  ┌──────────────────────────────────────────────────────┐  │
│  │  师傅带徒·AI    │  │  QScrollArea 可滚动页面画布（紧贴副标题下沿，无边框透明） │  │
│  │ ─────────────  │  │  (卡片 / 指标卡 / 表格 / 表单 …)                       │  │
│  │  导航按钮…      │  │  内部从上向下排布，末尾 addStretch(1) 贴顶              │  │
│  │  (弹性撑开)     │  └──────────────────────────────────────────────────────┘  │
│  │  👤 用户名       │   ← 姓名 24px/700 白；角色 19px/500                        │
│  │     角色         │     两行文字左对齐到 👤 右侧同一基准线                       │
│  │  🚪 退出登录      │                                                           │
│  └────────────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **说明（应用窗口骨架 QScrollArea 布局规范）**：右侧内容区由「固定头部 + 可滚动画布」两层构成：
> - **固定头部**（不随内容滚动）：页面标题 `pageTitle`(30px/800) + 副标题 `pageSubtitle`(15.5px/灰)，置于顶部，与上方标题区无额外间隙。
> - **可滚动画布** `QScrollArea`：紧贴副标题下沿（`setFrameShape(NoFrame)`、透明、横向滚动条常关），其 `widget`(pageInner) 内 `QVBoxLayout` **从上向下排布**卡片/指标卡/表格/表单，顶部 `contentsMargins` 仅留 14px 与副标题分隔、其余方向 0；布局末尾 `addStretch(1)` 保证内容贴顶、底部留白可滚。
> - 这样滚动时标题/副标题常驻，画布紧贴副标题，视觉层次清晰。各角色页面（master/apprentice/admin/social/notify）作为 `_load_page` 的 builder 注入 `pageInner` 画布。

### 0.3 侧边栏（SIDEBAR_QSS 专属，三类共用骨架 / 选项卡按角色不同）

`objectName=="sidebar"` 的 QWidget，仅 SIDEBAR_QSS 生效。侧边栏**宽度放大 1.5 倍（min/max-width `252px → 378px`）**，内部**所有字号增大 5px**（导航按钮 15→20、logo 24→29、logoSub 12.5→17.5）；**导航按钮高度自适应内部文字**（`min-height:56px` + `padding:18px 32px`，不再固定高度，文字完整不截断）。按钮可勾选（`QButtonGroup` 互斥），选中态左边框 4px 白 + 半透明白底；底部 `userinfo` 用户信息块 + `logoutBtn`。**骨架与样式三类完全一致，但选项卡清单由 `ROLE_PAGES[role]` 决定，三类别完全不同**（公共页"🔔 通知 / 💬 交流圈 / 📈 进度排名"三类均有，仅管理员把"进度排名"改为"📈 进度视图"且 pid=`admin_progress`）。各角色完整选项卡清单与专属侧边栏 UI 见 §一/§二/§三章首图。

```
┌────────────────────┐
│ 🔥 薪火              │  ← logo (29px/800/#fff)
│ 师傅带徒·AI导师       │  ← logoSub (17.5px/#e8b6b6)
│ ────────────────── │
│  [ 导航按钮… ]        │  ← 由 ROLE_PAGES[role] 生成, 20px, min-height 56px 自适应
│  (addStretch)        │
│  ┌─────────────────┐ │
│  │ 👤  张三         │ │  ← userinfo 块：头像列 + 文字列(姓名/角色两行左对齐)
│  │     师傅         │ │
│  └─────────────────┘ │
│  🚪 退出登录           │  ← logoutBtn (#ffd9a8) → _logout()
└────────────────────┘
   导航按钮生成: for pid in page_ids: QPushButton(PAGE_META[pid][0])
   选中态: rgba(255,255,255,.18)+白字+左边框4px白 (SIDEBAR_QSS)
   通知按钮: 进入后 _refresh_notify_badge() 改写文案 "🔔 通知 (N)"
```

#### 0.3.1 底部用户信息块（userinfo，字号放大 + 两行左对齐）

原实现为**单个 `QLabel#userinfo`** 用 `\n` 拼「👤 姓名」与「角色」两行，字号仅 18.5px，且第二行「角色」与 👤 图标同起点、未与姓名文字对齐。现改为**头像列 + 文字列的水平结构**，字号加大且两行文字左对齐到同一基准线。

结构（`QWidget#userinfo` 容器，内含 `QHBoxLayout`）：

```
┌ QWidget#userinfo ───────────────────────┐   ← 容器(QWidget, 可安全 setStyleSheet)
│ ┌────────┐ ┌──────────────────────────┐ │
│ │  👤    │ │ 张三                      │ │  ← QLabel#userName  24px/700 #ffffff
│ │ (26px) │ │ 师傅                      │ │  ← QLabel#userRole  19px/500 #f0c4c4
│ └────────┘ └──────────────────────────┘ │
│  头像列      文字列(QVBoxLayout, 左对齐)   │
└──────────────────────────────────────────┘
   ↑ 固定宽 34px           ↑ 两行统一左对齐于 👤 右侧同一基准线 x
   QLabel#userAvatar       AlignLeft | AlignVCenter
```

规格明细：

| 控件 | objectName | 字号 / 字重 | 颜色 | 布局要点 |
|------|-----------|------------|------|----------|
| 容器 | `userinfo` | — | 透明 | `QHBoxLayout`，`contentsMargins 32,10,32,10`，`spacing 12` |
| 头像 | `userAvatar` | 26px | `#f0c4c4` | 固定宽 34px；`AlignTop`（与姓名行顶端对齐，不随角色行下沉） |
| 姓名 | `userName` | **24px / 700** | `#ffffff` | 取 `full_name` 或 `username`；`AlignLeft`；超长省略 |
| 角色 | `userRole` | **19px / 500** | `#f0c4c4` | `role_names`: admin=管理员 / master=师傅 / apprentice=徒弟；`AlignLeft` |
| 文字列 | — | — | — | `QVBoxLayout`，`spacing 2`，`contentsMargins 0`，整体 `AlignVCenter` |

> 关键点：姓名与角色**同属一个 `QVBoxLayout`**，共享左边界，因此两行天然左对齐；👤 独立成列且宽度固定 34px，不再挤占文字起点。样式全部作用于 `QWidget`/`QLabel`（遵守铁律，不对 `QLayout` 调 `setStyleSheet`）。
>
> SIDEBAR_QSS 相应调整：原 `QLabel#userinfo` 规则替换为 `QWidget#userinfo`（背景透明）、`QLabel#userAvatar`、`QLabel#userName`、`QLabel#userRole` 三条。

三类选项卡差异一览（文案取自 `PAGE_META`，由 `ROLE_PAGES` 映射）：

| 角色 | 专属选项卡（pid） | 与公共页之差 |
|------|------------------|--------------|
| 师傅 master | 概览 / 投喂资料 / 知识库 / 公共资料库 / 徒弟管理 / 定制计划 / 批改检测 / 学情看板 + **进度排名** + 交流圈 + 通知 | 8 个师傅专属 + 进度排名(progress_view) |
| 徒弟 apprentice | 概览 / 摸底考试 / 学习计划 / 当日复习 / 错题本 / 同门战况 / 我的计划 + **进度排名** + 交流圈 + 通知 | 7 个徒弟专属 + 进度排名(progress_view) |
| 管理员 admin | 概览 / 审核注册 / 课程库 / 用户管理 / 部门管理 / 操作日志 + **进度视图** + 交流圈 + 通知 | 6 个管理员专属 + 进度视图(admin_progress) |

### 0.4 登录 / 注册对话框（LoginDialog，三类入口共用）

`QDialog` 固定 `660×980`，红白渐变背景，`_RED_WHITE_QSS` 仅作用于本对话框。整体字号较此前放大 5px（QLabel 14.5→19、loginTitle 28→33、loginSub/loginMsg 14→19、authBtn 17→22、tabBtn 16→21），输入框 `QLineEdit`/`QComboBox` 的**预览文字(placeholder)与输入文字字号同步放大至 19px，与"用户名"等标签字号一致**，输入框竖直内边距再 +3px（`16px→19px` 上下、左右 18px）避免文字被遮挡；dialog 外边距 `72/54/72/46`、根间距 22，登录表单间距 16、注册表单间距 12 且各列(标签↔输入框)间距 10、行内列间距 18。**注册表单（字段多）整体包入 `QScrollArea`，窗口高度不足时滚动而非压缩输入框**。顶部两个可勾选 `tabBtn`（登录/注册，互斥），点击切换内部 `QStackedWidget` 的两种独立表单；**底部提交按钮 `authBtn` 随模式变文案**（`_do_auth` 按 `currentIndex` 分流到 login / register 两个接口）。两个表单为**独立 Widget**，字段完全不同，分别绘制如下。

> **登录身份模式（§0.4.1 新增）**：登录表单在"用户名/密码"之上增加一个**「登录身份」`QComboBox`（l_role）**，提供 徒弟 / 师傅 / 管理员 三种模式，以满足三种角色的功能区分。三种模式**字段完全相同**（仍为用户名 + 密码）——依据 `API_CONTRACT.md` 与 `backend/auth.py::login()`，`POST /api/login` 只接收 `{username, password}`，**角色由账号唯一确定**，故登录请求体不携带 `role`、不改后端。角色下拉的作用：① 视觉身份区分（各模式带不同图标/说明文字）；② **前端角色一致性校验**（若所选身份与账号实际角色不符，前端拦截提示，仅本地判断、不请求后端）。

#### 0.4.1 登录 UI（_build_login_form，currentIndex=0）

在"用户名/密码"之上增加 **「登录身份」`QComboBox`（l_role）**，提供 徒弟 / 师傅 / 管理员 三种模式。三模式**字段相同**（用户名 + 密码，密码 `EchoMode=Password`），回车（`returnPressed`）直接触发登录。

**登录身份下拉规格（l_role）**：

| 项 | 说明 |
|----|------|
| 选项 | `👤 徒弟` / `👤 师傅` / `👤 管理员`（value 分别为 `apprentice`/`master`/`admin`，与 `user.role` 对齐） |
| 默认 | 徒弟（`apprentice`） |
| 切换行为 | ① 更新输入框 `placeholder`（徒弟「输入学徒账号」/师傅「输入工号或用户名」/管理员「输入管理员账号」）；② 更新下方模式提示文案 |
| 模式提示 | 徒弟：「登录后进入学习计划与复习」；师傅：「登录后管理徒弟与知识库」；管理员：「登录后管理审核与系统」 |
| 一致性校验 | `_do_auth` 登录时对比 `l_role.currentData()` 与后端返回 `user.role`：不一致则 `_set_msg("该账号为{实际角色}，请切换对应身份登录", warn=True)` 拦截，不 `accept()` |
| 请求体 | **仍只传 `{username, password}`**（`POST /api/login`，不改后端，角色由账号唯一确定） |

```
┌────────────────────────────────────┐
│      🔥 薪火 · AI 导师系统          │  ← loginTitle (33px/800/#b91c1c)
│      师傅带徒 · 知识传承 · AI 加速   │  ← loginSub (19px/#9c8a8a)
│  [ 登 录 ]     [ 注 册 ]            │  ← tabBtn(21px)：登录=选中(底部3px红下划线)
│  ────────────────────────────────  │  ← tabLine(QFrame.HLine)
│  登录身份                            │  ← 标签 19px
│  [ 👤 徒弟  ▾ ]                     │  ← l_role (QComboBox, 19px, 徒弟/师傅/管理员)
│  用户名                              │  ← 标签 19px
│  [______________________________]  │  ← l_uname (QLineEdit, 19px, placeholder随身份切换)
│  密码                                │  ← 标签 19px
│  [______________________________]  │  ← l_pwd (19px, Password掩码, placeholder=输入密码)
│  💡 登录后进入学习计划与复习           │  ← roleTip (18px/#9c8a8a, 随身份切换文案)
│                                     │  ← addStretch() 撑出底部空白
└────────────────────────────────────┘
         (下接通用 消息区 + 提交按钮，见 0.4.3)
```

> 接口：`POST /api/login`（请求体仅 `{username,password}`，与 §4 公共接口表一致）。角色一致性校验为**纯前端本地判断**，不新增端点、不改后端。

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

侧边栏"💬 交流圈"入口，发帖/列表/点赞/评论/**上传图片/文件**。支持附件（图片 + 任意文件），发帖时附带附件，帖子卡展示并可下载。

```
发帖区 (QGroupBox ✍️ 发帖)：
┌────────────────────────────────────────────────┐
│ [ 分享想法、可 @同事…                  ]          │  ← QTextEdit(84px)
│ [🖼️ 上传图片] [📎 上传文件]  · 已选: 图1.png ×    │  ← 附件行(QHBoxLayout): 次要按钮 + chip
│ (消息)                                [ 发布 ]   │  ← 主按钮(右对齐)
└────────────────────────────────────────────────┘
帖子卡 (card, padding22、行距10，放大以便阅读)：
┌──────────────────────────────────────────────┐
│ 张三  [师傅]                    2026-08-03 10:2  │  ← 作者24px/700 + badge20px + 灰时间20px
│ 今天带徒复盘，订单幂等讲得不错 👍                 │  ← 正文25px
│ ┌───────────────┐  📎 订单流程图.pdf             │  ← 附件区: 图片直接内嵌(300×210) + 文件chip22px
│ │   (图片直接    │                                │          (点击下载)
│ │    内嵌显示)   │                                │
│ └───────────────┘                                │
│ 🤍 3    💬 1 评论                                │  ← ghost_button 22px 点赞/评论
└──────────────────────────────────────────────┘
         │ 点击"评论" → QDialog(520×560) 含 QScrollArea 评论列表 + 输入行
```

> **帖子卡放大基准**（用户反馈文字/图片/附件名偏小后放大）：作者名 `20→24px`、角色徽章 `17.5→20px`、时间 `18→20px`、正文 `20.5→25px`、图片缩略 `200×140→300×210`、附件名 chip `18→22px`、点赞/评论 `20→22px`、card 内边距 `14→22px`、行距 `6→10px`、评论对话框 `440×460→520×560`。

**附件上传交互（发帖区）**：

| 项 | 说明 |
|----|------|
| 「🖼️ 上传图片」 | `QPushButton`(ghost) → `QFileDialog.getOpenFileNames()` 过滤图片（png/jpg/jpeg/gif/webp/bmp），多选 |
| 「📎 上传文件」 | `QPushButton`(ghost) → `QFileDialog.getOpenFileNames()` 任意文件，多选 |
| 已选附件 | 底部附件行以 **chip**（`QFrame#attachChip`：文件名 + `×` 移除按钮）展示；可重复添加、可移除；附加上限 9 个、单文件上限 20MB（超出 `post_msg` 提示并忽略） |
| 发布流程 | 先逐个 `POST /api/attachments`（multipart 上传）取回 `{attachment_id,url}`，再 `POST /api/posts` 携带 `attachment_ids:[...]`；任一上传失败则整帖中止并提示 |
| 发布中 | 附件行与发布按钮禁用，`post_msg` 显示"上传中…/发布中…" |

**帖子卡附件展示（交互约定）**：

| 附件类型 | 渲染 / 交互 |
|----------|-------------|
| 图片（`attachments[].mime` 以 `image/` 开头） | **在界面内直接内嵌显示**：`QLabel` 缩略图（`setPixmap` 按 `Qt.KeepAspectRatio` 缩放至 ≤200×140），加载即展示，**不弹窗**、不做点击跳转，仅做图片预览 |
| 非图片文件 | chip `📎 {file_name}`（可附大小），**点击执行下载到本地**：`_api_call GET` 落盘桌面并 `os.startfile` 打开 |

> 交互原则：**图片=直接展示；文件=点击下载**。图片不做放大弹窗（直接可见），文件不做内联预览（点击下载）。

**接口契约（本次新增/扩展）**：

| 方法 | 路径 | 守卫 | 请求体 | 响应关键字段 |
|------|------|------|--------|--------------|
| POST | `/api/attachments` | 登录 | multipart `file` | `{success,attachment_id,file_name,url,mime,size}` |
| GET | `/api/attachments/{id}/content` | 登录 | — | 文件字节流（`application/octet-stream` / `image/*`） |
| POST | `/api/posts`（扩展） | 登录 | `{content,author_name?,attachment_ids?:[...]}` | `{success,post_id}` |
| GET | `/api/posts`（扩展） | 登录 | — | `posts[]` 增加 `attachments:[{id,file_name,url,mime,size}]`（`mime`/`size` 由后端按文件名推断补充，**必含**，前端据此区分图片/文件） |

> **数据层**：复用 `db.py` 已预建的 `post_attachments` 表（`id, post_id, file_name, url, created_at`）。文件实体存磁盘目录（`backend/data/post_files/`，按 attachment_id 命名），数据库仅存元数据；`POST /api/attachments` 先落盘再写表返回 `attachment_id`，`POST /api/posts` 收到 `attachment_ids` 后把附件绑定到新帖 `post_id`。
>
> **实现边界**（仅限本次修改）：本地二进制附件逻辑**并入既有 `backend/social.py`**（新增 `upload_attachment_binary` / `get_attachment_content` / `bind_attachments_to_post`，与既有外链 `add_post_attachment` 互补，不新增模块），在 `main.py` 装配 `/api/attachments` 与扩展 `/api/posts` 读写附件；不在 `auth.py`/`db.py`/`schemas.py` 新增字段。前端在 `ui/social.py` 实现上传 UI 与附件展示，`ui/theme.py` 新增 `chip()` 工厂。中文文件名经前端 percent-encode、后端 `unquote` 还原，规避 multipart 对非 ASCII 文件名的解析乱码；附件字节流经 `Content-Disposition` 下载（中文名用 `filename*` RFC 5987 编码）。

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

### 0.8 屏幕自适应布局系统（Screen-Adaptive Layout，本次新增）

> **背景**：当前主窗口尺寸 `1520×940`、侧边栏 `378px`、内容区外边距 `(52,28,52,20)`、各组件字号/内边距/弹窗尺寸均为**硬编码定值**。在小屏笔记本（1366×768）或高分屏上，要么内容被裁切、要么左右大量留白，布局不够自适应、不够舒展。本次引入**运行时读取当前屏幕可用尺寸 → 动态计算窗口/侧边栏/内容区/组件缩放系数 → 美化布局与 UI**。

#### 0.8.1 屏幕尺寸获取（运行时，非硬编码）

新增 `ui/theme.py::screen_metrics()` 模块级函数，作为**唯一取屏入口**，替代散落各处的 `QApplication.desktop().availableGeometry()`：

| 返回字段 | 含义 | 取值 |
|----------|------|------|
| `width` / `height` | 当前屏幕**可用**宽/高（不含任务栏） | `QApplication.primaryScreen().availableGeometry()` |
| `scale` | 全局缩放系数（相对 1080p 基准） | `clamp(height / 1040, 0.82, 1.25)`，步进 `0.02` 取整 |
| `wide` | 是否为宽屏布局 | `width / height >= 1.6` |
| `font_delta` | 字号增量（px） | `round((scale - 1) * 6)` |

> 约定：`scale` 是**唯一定尺**。凡需随屏幕变化的尺寸（外边距、卡片内边距、弹窗、进度条宽、头像列宽等）一律乘以 `scale` 取整；字号用 `font_delta` 做整体 +N 放大（与既有"全局放大 5px"理念一致，做二次适配）。

#### 0.8.2 主窗口尺寸与侧边栏（main_window.py）

`MainWindow.__init__` 改为按屏幕计算，替换硬编码：

| 项 | 原（硬编码） | 新（动态） |
|----|--------------|------------|
| 窗口宽 | `1520` | `min(round(屏宽 × 0.92), 1660)` |
| 窗口高 | `940` | `min(round(屏高 × 0.90), 1000)` |
| 最小宽 | `1200` | `max(1120, round(屏宽 × 0.72))` |
| 最小高 | `780` | `round(屏高 × 0.72)` |
| 侧边栏宽 | 固定 `378px` | `round(300 × scale)`（约 246~375px），仍 `min/max-width` 双设 |

> 窗口默认**铺满当前屏幕约九成**，避免小屏窗口溢出任务栏、大屏左右留白过多。侧边栏随 `scale` 缩放，导航按钮 `min-height:56px`、`padding:18px 32px` 保持，字号 20px 随 `font_delta` 微调。

#### 0.8.3 内容区与页面画布（main_window.py `_create_page`）

| 项 | 原 | 新 |
|----|-----|-----|
| 内容区外边距 | `(52, 28, 52, 20)` | `(round(48×scale), round(26×scale), round(48×scale), round(20×scale))` |
| 页面画布上边距 | `(0,14,0,0)` | `(0, round(14×scale), 0, 0)` |
| 画布内纵向间距 | `20` | `round(20×scale)` |

> 宽屏（`wide=True`）时，内容区横向外边距**额外 +8px**，进一步压缩左右留白，让卡片更饱满。

#### 0.8.4 组件与字号随屏缩放（theme.py 工厂）

所有通用工厂内可调尺寸改为按 `scale` 缩放：

| 组件 | 原 | 新 |
|------|-----|-----|
| `card` 默认内边距 | 26 | `round(26×scale)` |
| `stat_card` 内边距 | 28 | `round(28×scale)` |
| 指标卡数值字号 | 43 | `round(43×scale)` |
| 指标卡说明字号 | 20 | `round(20×scale)+font_delta` |
| `title_label` | 35 | 不随屏（页面标题恒定醒目） |
| `subtitle_label` | 20.5 | `round(20.5×scale)` |
| `hint_label`/`guide_item` | 19 / 24 | `round(x×scale)` |
| 弹窗默认尺寸 | 硬编码 | 见 §0.8.5 |
| `badge`/`chip` 内边距 | 3,12 / 6,14 | `round(x×scale)` |

> **字号上限约束**：任一随屏字号 `max(尺寸, 屏幕≥2160 时上限)` 不设硬上限，仅靠 `scale` 截断在 `[0.82,1.25]` 内，保证大字不溢出、小屏可读。

#### 0.8.5 弹窗尺寸自适应

散落各处的 `QDialog.resize(W,H)` 统一改为按 `scale` 缩放（`round(W×scale), round(H×scale)`）：

| 弹窗 | 位置 | 原尺寸 |
|------|------|--------|
| 课程详情 | `master.py _view_library_course` | 560×600 |
| 任务检测 | `apprentice.py _open_quiz_dialog` | 460×340 |
| 评论 | `social.py _show_comments` | 440×460 |
| 重绑师傅 | `admin.py _open_rebind_dialog` | 360×160 |
| 登录/注册 | `login.py` | 660×980（另见 §0.4，随屏缩放） |

> 登录/注册对话框（660×980）在 `scale<1` 时同步缩放，避免小屏放不下。

#### 0.8.6 各页面布局美化（本次一并落地）

在屏幕自适应基础上，对以下页面做**布局与留白美化**：

1. **师傅概览**（§1.1）：指标卡 `QGridLayout` 列间距 14→`round(16×scale)`；详情区固定高 `clamp(屏高×0.34, 300, 460)` 保留，但基准改为 `screen_metrics().height`；知识点条形图维度名 `setFixedWidth(220)` → `round(220×scale)`。
2. **徒弟概览**（§2.1）：错题统计 `stat_card` 保持两列，卡片内边距随屏缩放。
3. **进度排行**（§0.7）：进度条 `setFixedWidth(140)` → `round(140×scale)`；姓名/分数列 `min-width` 随屏缩放。
4. **投喂资料**（§1.2）：三个 `QGroupBox` 上边距统一，按钮与消息行对齐；输入框随屏留白。
5. **知识库**（§1.3）：维度卡内边距 14→`round(14×scale)`，标题 21→`round(21×scale)`。
6. **交流圈**（§0.6）：帖子卡内边距 22→`round(22×scale)`，图片缩略 300×210 随 `scale` 等比放大。
7. **表格**（徒弟管理/审核等）：`QTableWidget` 单元格内边距 `padding:14px`→`round(14×scale)`，行高随屏微调。

> **实现边界**：全部改动限定在 `ui/` 包（theme.py / main_window.py / master.py / apprentice.py / admin.py / social.py / notify.py / progress.py / login.py），**不改后端**（main.py / db.py / auth.py / schemas.py）。新增 `screen_metrics()` 为唯一取屏入口，其余模块 `import` 复用；保留既有"工厂返回 QWidget、样式只作用于 QWidget"铁律。

---

## 一、师傅（Master）UI 设计

侧边栏条目（`ROLE_PAGES["master"]`）：概览 / 投喂资料 / 知识库 / 公共资料库 / 徒弟管理 / 定制计划 / 批改检测 / 学情看板 / **进度排名(复用 §0.7)** / **交流圈(复用 §0.6)** / **通知(复用 §0.5)**。

### 1.0 师傅侧边栏（完整选项卡 UI）

骨架同 §0.3，按 `ROLE_PAGES["master"]` 生成 11 个导航按钮，首个"概览"默认选中。

```
┌────────────────┐
│ 🔥 薪火          │  ← logo
│ 师傅带徒·AI导师   │  ← logoSub
│ ─────────────── │
│  📊 概览(选中)    │  ← master_overview (默认勾选)
│  📥 投喂资料      │  ← master_ingest
│  🧠 知识库        │  ← master_knowledge
│  📖 公共资料库    │  ← master_library (新增 §1.8)
│  👥 徒弟管理      │  ← master_apprentices
│  📝 定制计划      │  ← master_plans
│  ✅ 批改检测      │  ← master_grading
│  📋 学情看板      │  ← master_dashboard
│  📈 进度排名      │  ← progress_view (复用 §0.7)
│  💬 交流圈        │  ← social_posts (复用 §0.6)
│  🔔 通知          │  ← notifications (复用 §0.5, 有未读显 "(N)")
│  (addStretch)    │
│  👤  张三         │  ← userinfo 块 (§0.3.1)：姓名 24px/700 白
│      师傅         │  ← 角色 19px/500，与姓名左对齐
│  🚪 退出登录       │  ← logoutBtn
└────────────────┘
```

### 1.1 师傅概览（_build_master_overview）

`QGridLayout` 排 4 张 `stat_card`（知识维度/知识点/徒弟数量/桌面版本）。**前 3 张为可交互卡片**，点击后在页面上部**就地展开概览图**；第 4 张「桌面版本」为纯展示。下方 `QGroupBox"🚀 带徒五步法"` 引导卡。

页面纵向为**固定三段式**（顶部指标卡 / 中部固定高详情区 / 底部引导卡），整体紧贴页面顶部，不再被拉伸到底部：

```
━━━ 页面顶部 (title/subtitle 之下) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│     8      │ │     24     │ │     5      │ │    v2.0    │
│  知识维度   │ │   知识点   │ │  徒弟数量   │ │  桌面版本   │
└────────────┘ └────────────┘ └────────────┘ └────────────┘
   红 ✋可点      绿 ✋可点      橙 ✋可点      红(危险) 静态
        ↓ 点击任一张 → 下方 detailArea 切换对应概览图
┌─ 📊 概览详情区 (detailArea, 固定高, 内部滚动) ───────────────┐
│  ← 见 1.1.2 三种图形                                    ▲   │
│                                                         █   │← 内容超出时
│                                                         ▼   │  仅此区滚动
└──────────────────────────────────────────────────────────────┘
┌─ 🚀 带徒五步法 (标题 25px/700) ────────────────────────┐
│ 1. 投喂资料 → 上传本地文档或博客 URL      ← 每行 24px/500 │
│ 2. AI 精炼 → 自动生成知识维度与考点树                    │
│ 3. 创建徒弟 → 为学徒注册账号                            │
│ 4. 生成计划 → AI 自动排课或定制培养计划                  │
│ 5. 学情看板 → 追踪徒弟学习进展并批改检测                 │
└──────────────────────────────────────────────────────────┘
```
接口：`GET /api/master/knowledge`(main内联)`{dimensions:[{name,points}]}`；`GET /api/master/apprentices`(auth)`{apprentices:[...]}`。
> 两个接口的返回**已包含全部绘图所需数据**，交互展开时**不再发起新请求**（首屏结果缓存在 `self._ov_dims` / `self._ov_apprs`），因此不新增任何端点，不触碰后端。

#### 1.1.1 指标卡背景透明化（stat_card 修正）

现象：卡内「知识维度」等说明文字呈灰底色块，与卡片白底不一致。根因见 §0.1.1——内联样式串漏写 `background`，在部分 Windows 主题下 QLabel 取到默认 `Button` 灰底。本节为该全局规则在 `stat_card` 上的具体落地。

修正：给两个 QLabel 的样式串**显式加 `background:transparent;`**。

| 元素 | 原样式 | 新样式 |
|------|--------|--------|
| 数值 QLabel | `font-size:43px;font-weight:800;color:{color};` | 追加 `background:transparent;` |
| 说明 QLabel | `font-size:20px;color:{TEXT_SUB};font-weight:500;` | 追加 `background:transparent;` |

> 卡片本身白底 `Color.SURFACE` 与左侧 4px `accent` 竖条保持不变；仅让文字层透出卡片白底。

#### 1.1.2 可交互指标卡与概览图

**卡片交互规格**（`stat_card` 新增可选参数 `clickable=False`）：

| 状态 | 表现 |
|------|------|
| 可点击 | 鼠标指针 `Qt.PointingHandCursor`；卡片右下角加 `▸` 提示符（14px，`Color.TEXT_SUB`） |
| 悬停 | 阴影加强（`apply_shadow blur 18→26, alpha 18→32`），左侧 accent 竖条 4px→6px |
| 选中 | 卡片底色 `Color.SURFACE` → accent 的 8% 透明叠加；accent 竖条 6px 常驻 |
| 点击 | 发出信号 → 切换 `detailArea` 内容；同组互斥（同时只有一张选中） |

> 实现要点：`QFrame` 无 `clicked` 信号，采用 `f.mousePressEvent = lambda e, k=key: on_pick(k)` 绑定；**样式全部作用于 `QFrame`/`QLabel`，不对 `QLayout` 调 `setStyleSheet()`**（铁律）。

**三种概览图**（统一画在 `detailArea` 这一 `QFrame#card` 内，纯 QWidget 绘制，不引入 matplotlib 等新依赖）：

**① 知识维度** — 横向条形图，每个维度一行，条长 ∝ 该维度考点数

```
┌─ 📚 知识维度分布 (共 8 个维度 / 24 个知识点) ──────────────┐
│  嵌入式基础   ████████████████████  6                     │
│  Linux 驱动   ██████████████        4                     │
│  通信协议     ██████████            3                     │
│  …(按考点数降序, 最多 10 行, 超出显示"其余 N 个维度")        │
└────────────────────────────────────────────────────────────┘
```
数据：`dimensions[].name` + `len(points)`；条形用 `QProgressBar`（max=最大考点数）或定宽 `QFrame` 着色，颜色 `Color.PRIMARY`。

**② 知识点** — 维度→考点的分组标签云（`QGridLayout` 排 `badge()`）

```
┌─ 🧩 知识点总览 (24 个) ────────────────────────────────────┐
│  嵌入式基础 (6)                                            │
│   [GPIO] [中断] [定时器] [ADC] [PWM] [看门狗]              │
│  Linux 驱动 (4)                                            │
│   [字符设备] [platform] [设备树] [内核模块]                 │
│  …(每维度一段, 整体置于 QScrollArea, 最多渲染 60 个考点)     │
└────────────────────────────────────────────────────────────┘
```
数据：`dimensions[].points[]`；每个考点渲染为 `badge(point_name, Color.SUCCESS)`。

> **考点名称字段容错约定（本次新增）**：后端 `points[]` 元素 dict 的考点名称字段**约定为 `title`**（与 `GET /api/master/knowledge` 实际返回一致，元素含 `id / dimension_id / title / content / source_ref / level`）。前端取值按 **`title` 优先 → `name` 兜底 → 退回 `str(point)` 但需截断到 30 字符防字典展开** 三级容错，**严禁直接把 dict 当字符串渲染**（否则会渲染出 `{'id': 2, 'dimension_id': 1, 'title': '风控校验', ...}` 这种原始 JSON，破坏 badge 视觉）。该约定与 §1.3 知识库维度卡考点行、§1.1 概览图 ① 条形图考点计数等所有读取 `points[].title/name` 的地方统一。

**③ 徒弟数量** — 徒弟名册卡片墙（每行 3 个）

```
┌─ 👥 徒弟概览 (共 5 人) ────────────────────────────────────┐
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                      │
│  │ 👤 王五  │ │ 👤 赵六  │ │ 👤 孙七  │                      │
│  │ 待激活   │ │ 已激活   │ │ 已激活   │  ← status 徽章       │
│  └─────────┘ └─────────┘ └─────────┘                      │
│  空态: "暂无徒弟，前往 👥 徒弟管理 创建"                     │
└────────────────────────────────────────────────────────────┘
```
数据：`apprentices[]` 的 `full_name`/`username` 与 `status`；`status=="active"` 用 `Color.SUCCESS` 徽章，否则 `Color.WARNING`。

**默认与空态**：进入页面默认选中「知识维度」并渲染图 ①；任一数据为 0 时，`detailArea` 用 `empty_label()` 显示对应空提示，卡片仍可点击。

#### 1.1.3 「🚀 带徒五步法」引导卡字号放大

现状：五步条目直接复用通用 `hint_label()`（`theme.py` 内固定 `font-size:19px`，`Color.TEXT`），在 1520px 宽窗口下偏小。

> 注意：`hint_label()` 被投喂页、创建徒弟、生成计划等**十余处共用**，**不可直接改它的默认字号**，否则全局副作用。故为引导卡新增独立样式档。

方案：新增组件工厂 `guide_item(text)`（`theme.py`），专供引导卡条目使用。

| 元素 | 原 | 新 |
|------|-----|-----|
| 卡片标题「🚀 带徒五步法」 | 21px / 700（`QGroupBox` 全局 QSS） | **25px / 700**，仅对该 GroupBox 单独 `setStyleSheet` 覆写 |
| 五步条目文字 | 19px / 400（`hint_label`） | **24px / 500**，`Color.TEXT` |
| 条目行距 `spacing` | 8 | **14** |
| 条目左内边距 | 0 | **padding-left:6px**（序号与卡片边缘留白） |

```
┌─ 🚀 带徒五步法 ────────────────────────── 25px/700 ─┐
│                                                      │
│  1. 投喂资料 → 上传本地文档或博客 URL     ← 24px/500  │
│                                          ↕ spacing 14│
│  2. AI 精炼 → 自动生成知识维度与考点树                │
│                                                      │
│  3. 创建徒弟 → 为学徒注册账号                         │
│                                                      │
│  4. 生成计划 → AI 自动排课或定制培养计划              │
│                                                      │
│  5. 学情看板 → 追踪徒弟学习进展并批改检测             │
└──────────────────────────────────────────────────────┘
```

> 同步：徒弟端「🚀 新手上路」引导卡（§2.1）为同类引导卡，一并改用 `guide_item()`，保持两端视觉一致。样式作用于 `QLabel`/`QGroupBox`，不对 `QLayout` 调 `setStyleSheet()`。

#### 1.1.4 概览页垂直布局：顶部对齐 + 详情区固定高

**问题 1：内容整体下沉到页面底部。**
根因在 `main_window.py::_create_page()` 建立的页面 `QVBoxLayout` **末尾没有 stretch 兜底**。当页面内所有控件的高度之和小于容器高度时，`QVBoxLayout` 会把多余空间**按伸展因子分摊给各控件**，指标卡与引导卡因此被撑开并整体推向垂直中部/底部，视觉上"不在顶部"。异步回调（两次 HTTP 后才 `addWidget`）会放大该现象。

修正：概览页构建完成后，在页面布局末尾追加 `layout.addStretch(1)`，把所有剩余空间收归底部弹簧，内容自然**紧贴顶部**。

```
修正前(无 stretch)                修正后(末尾 addStretch)
┌───────────────┐                ┌───────────────┐
│               │ ← 空间被均分     │ [指标卡 ×4]    │ ← 紧贴顶部
│ [指标卡 ×4]    │   控件被下推     │ [详情区 固定高] │
│ [详情区]       │                │ [带徒五步法]    │
│ [带徒五步法]    │                │               │ ← 弹簧吸收余量
└───────────────┘                └───────────────┘
```

**问题 2：详情区初始过窄。**
`detailArea` 未设高度，初始按内容自适应，仅有一两行时高度塌陷。

修正：详情区改为 **`QScrollArea` 包裹内容 + 固定高度**，高度按屏幕自适应计算：

| 项 | 规则 |
|----|------|
| 计算基准 | `QApplication.primaryScreen().availableGeometry().height()` |
| 详情区固定高 | `clamp(屏幕可用高 × 0.34, 300, 460)` px |
| 设定方式 | `setFixedHeight(h)`（高度锁定，不随内容变化） |
| 内部滚动 | `QScrollArea(widgetResizable=True)`，纵向按需滚动条，横向 `ScrollBarAlwaysOff` |
| 边框 | `QFrame.NoFrame`（外层 `card()` 已有边框，避免双层边框） |

> 举例：1080p 屏（可用高约 1040）→ `1040×0.34 ≈ 354px`；4K 屏取上限 460px；小屏笔记本取下限 300px。
>
> 高度固定后，三种概览图切换时**页面不再跳动**；内容超出仅在详情区内部滚动，从而保证"指标卡恒在顶部、带徒五步法恒在底部"的三段式结构稳定成立。

**最终纵向结构**：

```
title / subtitle                 ← _load_page() 注入
指标卡 QGridLayout               ← 固定内容高
detailArea (QFrame#card)         ← setFixedHeight(334~460)
  └ QScrollArea → 内容 QWidget   ← 超出时内部滚动
🚀 带徒五步法 QGroupBox           ← 固定内容高
addStretch(1)                    ← 弹簧兜底，吸收所有剩余空间
```

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

顶部"🧪 触发 AI 精炼"按钮 + 提示，下方维度卡列表（空态显示 empty_label）。

> **触发 AI 精炼按钮样式（红框红字）**：「🧪 触发 AI 精炼」采用 **红色边框 + 红色字体**（白底、`border:1.5px solid #dc2626; color:#dc2626; border-radius:8px`），与全局主按钮（红底白字）及"开始投喂"按钮视觉一致，强调"触发 AI 精炼"是一次性的重要动作。悬停 `background:#fef2f2`，按下 `border-color:#b91c1c; color:#b91c1c`。实现上新增 `ui.theme.refine_button()` 工厂返回带该样式的 `QPushButton`（仍返回 QWidget 子类，遵守铁律）。

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

> **考点行字段容错（与 §1.1.2 ② 统一）**：知识库维度卡的考点行 `· {point_title}  [{level}]` 中，**`point_title` 同样遵循 `title` 优先 → `name` 兜底 → 截断到 30 字符**三级容错，避免后端字段微调导致整张维度卡变成 JSON 字典列表。

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

### 1.8 公司公共资料库（_build_master_library）

管理员在「课程库」(§3.3，`admin_courses`) 维护的公司预置课程，是**给师傅的默认预置知识库**。师傅端新增独立页面查看这些公共课程资源（文档 / 视频 / 链接 / 题库四类），并可展开查看完整内容。

```
📖 公司公共资料库  (标题)
由管理员维护的公司统一课程资源，可查看与使用
┌─ 公共资料库 (QGroupBox) ────────────────────────────────┐
│ [ 📄 筛选类型: 全部 ▾ ]                (课程数量 N 条)     │  ← QComboBox 按 type 过滤
│ ┌─ 课程卡 (card, accent=红, padding20) ───────────────┐  │
│ │ 📚 订单系统实战                        [document]     │  │  ← 标题24px/700 + type badge
│ │ 从订单创建到支付对账全流程，含幂等设计与状态机            │  │  ← 摘要19px 灰(截断两行)
│ │ [📖 查看详情]   [➕ 加入我的知识库]                  │  │  ← 查看详情 + 一键加入知识库
│ └───────────────────────────────────────────────────┘  │
│  …(课程卡逐张列出, 空态 empty_label)                     │
└───────────────────────────────────────────────────────┘
```

**交互与规格**：

| 项 | 说明 |
|----|------|
| 数据源 | `GET /api/master/courses`（复用 §1.5 定制计划同源接口，`courses_list_courses`），返回 `{success, courses:[{id,title,type,content,...}]}` |
| 类型筛选 | 顶部 `QComboBox` 提供 `全部 / document / video / link / quiz_bank`，选择后仅展示对应类型课程（本地过滤，不新增请求） |
| 课程卡 | `card`(padding20, accent=红)：标题 `24px/700` + 类型 `badge`；下方摘要 `19px` 灰（`content` 前 60 字，超长省略） |
| 查看详情 | 点击「📖 查看详情」→ `QDialog(560×600)`，标题 + 类型 badge + `QScrollArea` 内展示 `content` 全文（`setWordWrap`），仅供查看，不可编辑 |
| **一键加入我的知识库** | 课程卡「➕ 加入我的知识库」按钮：`POST /api/master/library/import/{course_id}`，把课程文本按投喂流程纳入**当前师傅**的默认知识库（写 `kb_sources`/`kb_documents` + 分块嵌入），随后可在「知识库」页对该课程精炼。**幂等**：重复点击提示"已加入你的知识库"，不重复入库 |
| 已加入态 | 页面加载时 `GET /api/master/library/imported` 返回已纳入本师傅知识库的课程 id 集合；已加入的课程卡按钮变为 `ghost_button("✓ 已加入", 禁用)` |
| 空态 | 无课程时 `empty_label("暂无公共资料，请联系管理员在课程库添加")` |
| 定位 | 与"定制计划选课"共用课程库数据；本页专注**查看/浏览 + 一键纳入个人知识库**，定制计划页专注**勾选入计划** |

```
┌─ 查看详情 QDialog (560×600) ────────────────┐
│ 📚 订单系统实战                  [document]  │  ← 标题24px/700 + type badge
│ ┌─ QScrollArea(全文) ────────────────────┐  │
│ │ 从订单创建到支付对账全流程，                    │  │  ← content 全文, wordWrap
│ │ …(完整内容滚动阅读)                       │  │
│ └───────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

接口（仅本次修改新增/扩展）：

| 方法 | 路径 | 守卫 | 说明 |
|------|------|------|------|
| GET | `/api/master/courses` | 师傅 | 复用既有，返回公司课程库 `{courses:[{id,title,type,content}]}` |
| GET | `/api/master/library/imported` | 师傅 | 返回已纳入本师傅知识库的课程 id 集合 `{imported:[course_id,...]}` |
| POST | `/api/master/library/import/{course_id}` | 师傅 | 把课程内容按投喂流程纳入当前师傅默认知识库，幂等（已纳入返回 success + already=true） |

> **后端实现**：在 `backend/ingest.py` 或独立函数实现"课程→知识库"投喂：取 `courses` 行 → 生成 `kb_sources`（来源标为 `course:{id}`）+ `kb_documents.raw_text` → 复用分块/嵌入逻辑入库 → 返回 success。`main.py` 装配上述 3 个路由。**不新增 `courses` 表字段、不改 `refiner.py`**（精炼仍只读师傅已投喂的 `kb_documents`，课程加入后即自然可精炼）。

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
│  👤  王五         │  ← userinfo 块 (§0.3.1)：姓名 24px/700 白
│      徒弟         │  ← 角色 19px/500，与姓名左对齐
│  🚪 退出登录       │  ← logoutBtn
└────────────────┘
```

### 2.1 徒弟概览（_build_appr_overview）

"🚀 新手上路"`QGroupBox` 引导卡 + 错题统计 `QGridLayout`（2 张 `stat_card`）。引导卡条目统一使用 `guide_item()`（标题 25px/700、条目 24px/500、spacing 14），与师傅端「带徒五步法」一致，见 §1.1.3。

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
│  👤  李四         │  ← userinfo 块 (§0.3.1)：姓名 24px/700 白
│      管理员       │  ← 角色 19px/500，与姓名左对齐
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

日志卡片列表（时间线式），每行：动作(品牌红) + 目标类型/ID/详情 + 灰时间。**各段以空格间隔**；**仅展示用户操作日志，隐藏系统自动任务日志**。

```
┌─ 日志卡 (card, padding8) ────────────┐
│ [approve]  用户 #12 审核通过  2026-08-03│  ← 红字(700)+空格+黑字(目标+detail)+空格+灰时间
└──────────────────────────────────────┘
```
接口：`GET /api/admin/logs`(P6)`{logs:[{action,target_type,target_id,detail,created_at}]}`。

> **审核日志写入**（仅本次修改）：`POST /api/admin/approve` / `reject` 现在**真正写入 `admin_logs`**——`action='approve'`（`detail='审核通过'`）/ `action='reject'`（`detail='驳回'`），`target_type='user'`、`target_id`=被审核用户 id、`admin_id`=操作管理员 id。
>
> **隐藏系统日志**：`GET /api/admin/logs` 过滤掉系统自动任务日志（`self_purify` 等 `admin_id=0` 或系统类 `action`），**只返回用户操作日志**，界面不再出现看不懂的 JSON 文本。
>
> **渲染规范**：`[action]`(红700) + **两空格** + `{target_type} #{target_id}  {detail}`(黑字) + **两空格** + `{created_at}`(灰)。审核日志 detail 为友好短文本（审核通过/驳回），无需截断。

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
