# P6 执行指令 · 管理员后台 + 课程/计划/进度

> 本文件是交给**另一个 AI 编程助手**的完整、自包含执行指令。请该 AI 严格按此实现，**不要自行删减核心功能**；歧义时以"贴合比赛评分 + 开箱即跑 + 模块隔离"为最高优先级。

---

## 0. 你的角色与目标
你是团队赛「薪火·师傅带徒 AI 导师系统」的 **P6（管理员后台 + 课程/计划/进度）** 实现者。
- 项目根：`TSForce_MentorAI/`
- 你要补齐 V2 的"公司级管理 + 课程库 + 师傅定制计划 + 今日任务检测 + 三层进度视图 + 异常预警 + 管理员下钻明细"这一整块**业务闭环**。
- 当前这些逻辑大部分**内联在 `backend/main.py`** 里（课程、计划、检测、进度视图），你的工作是**把它们抽取成独立模块文件并增强**，而不是在 `main.py` 里继续堆代码。

---

## 1. 必须首先阅读的文件（顺序）
1. `API_CONTRACT.md` —— 你负责的端点签名、请求/响应字段（单一真相源，**不可擅自改**）
2. `TEAM_PLAN.md` —— 角色红线、Git 规范、待补功能登记（§5）
3. `TEAM_TASKS/P6_管理员后台与进度.md` —— 你的任务卡
4. `backend/main.py` —— 找到内联的 `/api/admin/courses*`、`/api/master/plans*`、`/api/apprentice/quiz/submit`、`/api/master/quizzes/{id}/score`、`/api/master/daily-progress`、`/api/progress/*` 逻辑，作为抽取基线
5. `backend/db.py` —— 确认 32 张表字段（`courses/plan_items/quizzes/daily_progress/plans/mastery/...`）
6. `backend/auth.py` —— 了解 `require_admin/require_master`、`get_company_users` 等可复用函数

---

## 2. 硬约束（红线，违反即算失败）
1. **只写你自己的模块文件**，新建于 `backend/`：
   - `backend/courses.py`（课程库 + 检测题库/模板引擎）
   - `backend/progress_view.py`（三层进度视图 + 可配置排名）
   - `backend/quiz.py`（今日任务检测：提交/历史/终评/自动完成标记）
   - `backend/admin_back.py`（审核辅助、下钻明细、异常预警、用户筛选）
2. **禁止修改** `main.py` / `db.py` / `auth.py` / `schemas.py` / `config.py`（枢纽文件归 P1）。
3. 路由装配交给 P1：你**只导出函数**，并在本任务末尾产出一份《P1 装配清单》（见 §7），写明"函数位置 + 想挂的路径 + 角色守卫 + 请求/响应"。
4. 函数返回统一 `{success: bool, ...}`；字段名必须与 `API_CONTRACT.md` 一致。
5. **中文优先**：注释、界面文案、生成内容均中文。
6. 改动最小化：用精准替换/新增文件，不整体重写既有文件。
7. 保证 `pip install -r requirements.txt && python run.py` 能起、`http://localhost:8000` 不报错、不影响现有 55 个 API 路由。
8. LLM 调用（若用到）用 `asyncio.to_thread` 包裹；JSON 解析需鲁棒（去 ```json 围栏 → 精确解析 → 截取首个 `{`/`[` 到匹配括号）。

---

## 3. 必须使用的本地 Skill（执行中按场景调用）
- **`awesome-python`**：每次写 Python/后端前必调，遵循其推荐的 FastAPI/SQLAlchemy/pydantic/trafilatura 等最佳实践、规范结构、异步、类型标注。
- **`test-driven-development`**：每实现一个模块，立即为它补 pytest 用例（放 `tests/`，函数级，覆盖关键路径与越权拦截），作为 Bug 测试主框架。
- **`requesting-code-review`**：整体实现完成后发起自审，查漏补缺。
- **`systematic-debugging`**：遇到运行/测试报错时按系统化流程定位根因，不盲目改。
> 不要调用 `huashu-design`（那是 P5 前端职责）。

---

## 4. 具体任务清单

### 4.1 `backend/courses.py`（课程库 + 检测题库/模板引擎）
- 抽取并增强 `main.py` 中的 `/api/admin/courses*` 逻辑：
  - `list_courses(company_id)` / `create_course(company_id, title, type, content, created_by)` / `update_course(course_id, **fields)` / `delete_course(course_id)`
  - `type` 支持 `document|video|link|quiz_bank`；当 `type='quiz_bank'` 时允许挂题目。
- **P1 检测题模板引擎**：`add_course_question(course_id, question, qtype, answer_key, options)` / `list_course_questions(course_id)`，让管理员为课程预制题目（供 quiz 抽取）。
- 所有查询带 `company_id` 过滤（SaaS 隔离护栏）。

### 4.2 `backend/quiz.py`（今日任务检测）
- 抽取 `/api/apprentice/quiz/submit`、`/api/apprentice/quizzes`、`/api/master/apprentice/{id}/quizzes`、`/api/master/quizzes/{id}/score`、`/api/master/daily-progress` 逻辑：
  - `submit_quiz(user_id, plan_item_id, answer)`：**P0 真实 LLM 评分**——调用 P3 提供的 `grade_quiz_answer`（签名与容错规则见 §5.1）。**必须按 §5.1 的"对接容错"写法消费该函数**：防御性 import + 归一化返回 + 任何异常走答案长度兜底，保证 P3 未交付或实现有偏差时本模块仍可运行、可测试。返回 `{quiz_id, attempt, ai_score, feedback, message}`，状态 `pending_review`。**必须保留 ownership 校验**：`plan_item` 须属于该 `user_id`（参考 main.py 现有 `JOIN plans p ON pi.plan_id=p.id WHERE ... AND p.apprentice_id=?` 校验）。
  - `list_my_quizzes(user_id)` / `list_apprentice_quizzes(master_id, apprentice_id)`（校验是该师傅徒弟）/ `master_score_quiz(quiz_id, master_score, status)`（师傅终评）。
  - `judge_daily_progress(master_id, apprentice_id, plan_item_id)`（师傅判定当日完成）。
  - **P1 自动完成标记**：`submit_quiz` 后检测该 `plan` 下所有 `plan_items` 是否均已 `passed` 或 `master_score` 非空，若是则标记计划完成（写日志/字段）。

### 4.3 `backend/progress_view.py`（三层进度视图 + 排名）
- 抽取 `/api/progress/company|department|same-master` 的 `_build_progress_rows`：
  - `build_progress_rows(conn, apprentices, company_id, weights=(0.6,0.4))`：**P1 综合排名算法**——完成率×权重 + 平均分×权重，权重可配置（先写死默认，参数可传）。
  - `progress_company(company_id)` / `progress_department(company_id, department)` / `progress_same_master(role, user_id, company_id)`：均返回带 `rank` 的列表（新人+对应师傅+完成率+平均分）。
  - 所有查询带 `company_id` 过滤。

### 4.4 `backend/admin_back.py`（下钻/预警/筛选）
- **P0 管理员下钻明细**：`get_apprentice_detail(apprentice_id, company_id)` → 返回该新人 `{plan, quizzes:[{ai_score, master_score, status}], daily_progress}`，供 `GET /api/admin/apprentice/{id}/detail`。
- **P1 异常预警**：`get_anomalies(company_id, no_progress_days=7, fail_threshold=3)` → 返回长期无进度/检测多次不通过的徒弟列表。
- **P1 用户筛选**：`list_users(company_id, role=None, status=None)`（复用/增强 `auth.get_company_users`）。
- 敏感操作（重绑、改分）写入 `admin_logs`（已有 `api_admin_rebind` 逻辑可参考，抽到此处由 P1 调用）。

---

## 5. 与 P3 / P1 的协作接口（务必遵守）
- **真实 LLM 评分依赖 P3**：你在 `quiz.py` 调用 `assessor.grade_quiz_answer(...)`，该函数由 **P3** 在 `backend/agents/assessor.py` 提供。**不要自己重写评分算法**（那是 P3 职责）；你只负责调用 + 兜底 + 持久化。

### 5.1 与 P3 的接口契约（双方必须一致，勿各自发挥）
P3 在 `backend/agents/assessor.py` 中**新增**以下函数，P6 按此签名调用：

```python
def grade_quiz_answer(plan_item_id: int, answer: str, context: str = None) -> dict:
    """对今日任务检测的徒弟作答做真实 LLM 初评（P0）。
    返回: {"score": int(0-100), "feedback": str}
    - context 为 None 时，内部据 plan_item_id 取 courses.content 作为评分上下文
    - 无 Key / LLM 失败 / 解析失败 → 兜底评分（基于答案长度）并说明
    """
```

P6 调用示例（在 `quiz.py` 的 `submit_quiz` 内，**必须按此容错写法**）：
```python
try:
    from backend.agents.assessor import grade_quiz_answer
except ImportError:
    grade_quiz_answer = None

# —— 对接容错消费：无论 P3 实现细节如何偏差，本模块都不崩 ——
def _score_with_fallback(plan_item_id, answer):
    fallback = min(100, max(10, len(answer or "") * 2)) if answer else 10
    if grade_quiz_answer is None:
        return fallback, "（P3 未交付，评分兜底）"
    try:
        res = grade_quiz_answer(plan_item_id, answer)   # context 留空，由 P3 内部取课程资料
        if isinstance(res, dict):
            return int(res.get("score", fallback)), str(res.get("feedback", ""))
        if isinstance(res, (int, float)):
            return int(res), ""
        return fallback, "（返回格式异常，评分兜底）"
    except Exception:
        return fallback, "（评分异常，兜底）"

ai_score, feedback = _score_with_fallback(plan_item_id, answer)
```

#### 对接容错规则（P6 必须遵守，确保接上 P3）
- **防御性 import**：`grade_quiz_answer` 不存在时置 `None`，不报 ImportError 中断。
- **归一化返回**：P3 约定返回 `{"score":int,"feedback":str}`，但你须容忍：返回 int（直接当分数）、返回 dict 缺键（缺 score→兜底、缺 feedback→空串）、抛异常（兜底）。
- **不依赖 context 参数**：P6 只传 `(plan_item_id, answer)`；context 由 P3 内部取 `courses.content`。即便 P3 以后加必填参数，因 `context=None` 有默认值也向后兼容。
- **绝不自己实现评分算法**：打分语义归 P3，你只负责调用 + 兜底 + 持久化。

> 该契约已逐字写入 `TEAM_TASKS/P3_给AI的执行指令.md` §4.1，两指令同步生效。若 P3 调整签名，须由 P3 通知你同步本调用。
- **路由与触发归 P1**：你不在 `main.py` 写 `@app` 路由。所有新端点由 P1 装配。你只需保证函数可被 import 调用。
- **通知触发归 P1/P7**：检测提交后"通知师傅"的副作用，由 P1 在装配时调用 P7 的 `notify()`，你无需实现通知发送。

---

## 6. 测试要求（test-driven-development）
在 `tests/` 为你的四个模块各写 pytest：
- `test_courses.py`：课程 CRUD + `company_id` 隔离（A 公司看不到 B 公司课程）。
- `test_quiz.py`：`submit_quiz` attempt 递增、师傅终评覆盖、`judge_daily_progress` 生效、越权（非本人/非其师傅）被拒。
- `test_progress.py`：三层视图返回带 rank、权重可配置、跨公司不可见。
- `test_admin_back.py`：下钻明细字段完整、异常预警能识别长期无进度者、用户筛选按 role/status 生效。
- `test_p6_p3_interface.py`：**对接校验**（见 §6.1）。
> 测试用真实 SQLite 临时库，不依赖外网/LLM（评分走兜底也能过）。

### 6.1 对接校验测试 `tests/test_p6_p3_interface.py`（确保与 P3 接上）
此测试是你的"对接保险"：**P3 一交付，你重跑即可确认是否接上**。P3 未交付时它跳过而非失败，不阻断你的开发。
```python
import pytest

def test_grade_quiz_answer_interface():
    try:
        from backend.agents.assessor import grade_quiz_answer
    except ImportError:
        pytest.skip("P3 尚未交付 grade_quiz_answer，待对接后重跑")
    # 1) 可调用
    assert callable(grade_quiz_answer)
    # 2) 入参 (plan_item_id, answer) 且 context 可选
    import inspect
    params = list(inspect.signature(grade_quiz_answer).parameters)
    assert params[0] == "plan_item_id" and params[1] == "answer"
    # 3) 返回结构：score 为数字、feedback 为字符串（用 mock 上下文或真实库）
    #    注意：真实评分需 DB；此处仅校验"返回可归一化"，与 §5.1 容错一致
    res = grade_quiz_answer(1, "示例作答")
    if isinstance(res, dict):
        assert "score" in res
    elif isinstance(res, (int, float)):
        pass
    else:
        pytest.fail("grade_quiz_answer 返回类型不可归一化（应为 dict 或 int）")
```
> 运行：`pytest tests/test_p6_p3_interface.py -v`。通过 = 与 P3 接口对接成功；skip = P3 未交付；fail = 签名/返回与 §5.1 不符，需与 P3 对齐。

---

## 7. 交付物（向 P1 / 团队提交的内容）
1. 四个新模块文件：`courses.py` `quiz.py` `progress_view.py` `admin_back.py`，可 import、含类型标注与中文注释。
2. **《P1 装配清单》**（单独一节写在你的回复里），逐条列出：
   - 路径 / 方法 / 角色守卫 / 请求体 / 调用函数（含 import 路径）/ 预期响应
   - 示例：`POST /api/apprentice/quiz/submit` → `from backend.quiz import submit_quiz`；`GET /api/admin/apprentice/{id}/detail` → `from backend.admin_back import get_apprentice_detail`
3. `tests/` 下 4 个测试文件，运行通过。
4. 自测报告：对照 §8 验收清单逐项确认。

---

## 8. 验收标准总表
- [ ] 课程库 CRUD 可用，`type=quiz_bank` 可挂预制题目（检测题模板引擎 P1）
- [ ] 今日任务检测提交走**真实 LLM 初评**（P0，依赖 P3；未就绪时有兜底且标注）
- [ ] 师傅可对检测终评改分，终评覆盖初评
- [ ] 徒弟"已完成"标记在全部项通过后自动更新（P1）
- [ ] 三层进度视图（公司/部门/同门）均返回新人+师傅+完成率+平均分+rank，跨公司不可见
- [ ] 综合排名权重可配置（P1）
- [ ] 管理员下钻明细可用（P0），字段完整
- [ ] 异常预警列表可用（P1）
- [ ] 用户列表可按 role/status 筛选（P1）
- [ ] 所有函数由 P1 装配，未私自改 `main.py`/`db.py`
- [ ] `tests/test_p6_p3_interface.py` 在 P3 交付后运行通过（未交付时标记 skip，不阻断）；确认 `grade_quiz_answer` 签名/返回与 §5.1 一致
- [ ] `tests/` 用例全绿；`requesting-code-review` 自审已执行并修复问题

---

## 9. 执行纪律（给执行 AI 的开场语建议）
"你是 P6。先读 `API_CONTRACT.md`/`TEAM_PLAN.md`/`TEAM_TASKS/P6_*.md` 与 `backend/main.py`/`db.py`。只写 `backend/courses.py` `quiz.py` `progress_view.py` `admin_back.py`，**禁止改 main.py/db.py/auth.py/schemas.py**。字段对齐契约；中文优先；用 awesome-python 规范；每模块用 test-driven-development 补 pytest；完成用 requesting-code-review 自审；遇错用 systematic-debugging。真实 LLM 评分调用 P3 的 `assessor.grade_quiz_answer`，未就绪走兜底。最后产出《P1 装配清单》与自测报告。"
