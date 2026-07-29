# 任务卡 · P5 桌面前端 / UI

## 你的角色
负责 PyQt5 桌面应用（当前 `desktop_app.py` ~1700 行，需拆分）及所有角色页面的高保真 UI，对接各模块 API。

## 你可写的文件
- `desktop_app.py`（拆分）
- 新建 `ui/` 包（按页面拆模块，如 `ui/login.py` `ui/master.py` `ui/apprentice.py` `ui/admin.py` `ui/social.py` `ui/notify.py`）
- `frontend/index.html`（若保留 Web 版）

## 禁止触碰
- `main.py` `db.py` `auth.py` `schemas.py`（后端契约文件）

## 你要做的事
1. **拆分巨文件**：把 `desktop_app.py` 按页面/功能拆成 `ui/` 下多个模块，降低维护与合并风险（技术债务项）。
2. **高保真 UI**（按 `huashu-design` 设计语言：现代、响应式、适度动效，禁止丑陋默认样式）：
   - 登录/注册（双模式 + 工号/手机/办公账号/姓名/部门/师傅 字段，拦截 pending 提示）
   - 师傅视图：投喂、知识库、计划编辑、学情看板、徒弟管理、定制计划、批改
   - 徒弟视图：摸底、当日计划、PDF 下载、复习、错题本、同门战况、培养计划
   - 管理员视图：审核、用户/部门/课程、总览、异常预警、下钻明细、日志
   - 交流圈：发帖/评论/点赞/附件/@提醒
   - 通知中心：列表 + 已读 + 红点
3. **对接 API**：按 `API_CONTRACT.md` 的字段渲染；P1/P6/P7 新增端点后同步前端。
4. **坑提醒**：不要对 Layout 调 `setStyleSheet()`（此前 8 处崩溃），只对 QWidget 调用。

## 验收标准
- [ ] 所有角色页面可用，与各模块 API 正确对接
- [ ] UI 高保真（huashu-design），无默认丑样式
- [ ] `desktop_app.py` 已拆分，`ui/` 包结构清晰
- [ ] 不再出现 Layout.setStyleSheet 类崩溃

## 给 AI 的开场提示词
"你负责桌面 UI（P5）：PyQt5 `desktop_app.py` 及 `ui/` 包。禁止改后端 main.py/db.py/auth.py/schemas.py。先拆分巨文件再增强；UI 严格按 huashu-design 高保真；API 字段以 `API_CONTRACT.md` 为准；绝不对 Layout 调 setStyleSheet。精准替换。"
