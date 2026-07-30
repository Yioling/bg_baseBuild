# P3 执行指令 · AI 智能体（5 个）

> 本文件是交给**另一个 AI 编程助手**的完整、自包含执行指令。请该 AI 严格按此实现，**不要自行删减核心功能**；歧义时以"贴合比赛评分 + 开箱即跑 + 模块隔离"为最高优先级。

---

## 0. 你的角色与目标
你是团队赛「薪火·师傅带徒 AI 导师系统」的 **P3（AI 智能体）** 实现者。
- 项目根：`TSForce_MentorAI/`
- 你负责 5 个智能体：`refiner` / `assessor` / `planner` / `tutor` / `reviewer`。
- 核心任务：**P0 实现"今日任务检测的真实 LLM 评分"**（`grade_quiz_answer`），并对全部 agent 做 JSON 鲁棒解析与无 Key 演示兜底增强。

---

## 1. 必须首先阅读的文件（顺序）
1. `API_CONTRACT.md` —— 你负责的端点与函数调用关系（单一真相源）
2. `TEAM_PLAN.md` —— 角色红线、待补功能登记（§5：P0 真实 LLM 评分归你）
3. `TEAM_TASKS/P3_AI智能体.md` —— 你的任务卡
4. `TEAM_TASKS/P6_给AI的执行指令.md` **§5.1** —— 与 P6 锁定的接口契约（必须一致）
5. `backend/agents/refiner.py` `assessor.py` `planner.py` `tutor.py` `reviewer.py` —— 现有实现，**先读懂再改**
6. `backend/llm.py` —— 确认 `chat_json` / `chat` / `use_mock` 的签名与行为（你依赖它们）
7. `backend/db.py` —— 确认 `courses` / `plan_items` 表字段（评分上下文来源）

---

## 2. 硬约束（红线，违反即算失败）
1. **只写 `backend/agents/*.py`**（含可选的 `backend/agents/_jsonutil.py` 共用解析工具）。**禁止修改** `main.py` / `db.py` / `auth.py` / `schemas.py` / `config.py`。
2. **保持现有函数签名不变**（`main.py` 已 import 并依赖，改签名会全线崩溃）：
   - `refiner.refine(kb_id)`
   - `assessor.generate_assessment(user_id, kb_id)` / `grade_answer(question_id, answer, assessment_id)` / `get_assessment_result(assessment_id)` / `get_mistakes(user_id)`
   - `planner.generate_plan(apprentice_id, kb_id)` / `get_plan(apprentice_id)` / `update_plan_day(day_id, note, locked)` / `update_plan_task(task_id, data)`
   - `tutor.ask(user_id, kb_id, question, store)` / `generate_lecture_content(...)`
   - `reviewer.generate_review(user_id, plan_day_id)` / `grade_review_answer(question_id, answer, review_id)`
3. **仅"新增"** `grade_quiz_answer` 到 `assessor.py`，签名必须与下方 §4 完全一致。
4. 函数返回统一 `{success: bool, ...}`（评分函数除外，见 §4）；字段名与 `API_CONTRACT.md` 一致。
5. **中文优先**：提示词、注释、生成内容均中文。
6. LLM 调用用 `asyncio.to_thread` 包裹（若在主流程同步调用，确保不阻塞；P1 装配时会处理线程）。
7. JSON 解析必须鲁棒（去 ```json 围栏 → 精确解析 → 截取首个 `{`/`[` 到匹配括号）。
8. 保证 `python run.py` 能起、不影响现有 55 个 API 路由。

---

## 3. 必须使用的本地 Skill（执行中按场景调用）
- **`awesome-python`**：每次写 Python/后端前必调，遵循其 FastAPI/异步/类型标注/成熟库最佳实践。
- **`test-driven-development`**：为新增的 `grade_quiz_answer` 及 JSON 解析工具补 pytest（含无 Key 兜底、解析失败兜底、正常评分三路径）。
- **`requesting-code-review`**：整体实现完成后发起自审。
- **`systematic-debugging`**：遇运行/测试报错时系统定位，不盲目改。
> 不要调用 `huashu-design`（前端归 P5）。

---

## 4. P0 核心任务：今日任务检测的真实 LLM 评分

### 4.1 接口契约（与 P6 §5.1 完全一致，勿改）
在 `backend/agents/assessor.py` **新增**：

```python
def grade_quiz_answer(plan_item_id: int, answer: str, context: str = None) -> dict:
    """对今日任务检测的徒弟作答做真实 LLM 初评（P0）。
    返回: {"score": int(0-100), "feedback": str}
    - context 为 None 时，内部据 plan_item_id 取 courses.content 作为评分上下文
    - 无 Key / LLM 失败 / 解析失败 → 兜底评分（基于答案长度）并说明
    """
```
> **对接说明**：P6 会**防御性消费**本函数（容错 int 返回 / 缺键 / 异常），但你仍须稳定返回 `{"score": int, "feedback": str}`，且前两个参数必须是 `(plan_item_id, answer)`、`context` 必须有默认值 `None`。P6 侧已有 `tests/test_p6_p3_interface.py` 会在你交付后校验本契约——若它的断言失败，说明实现与契约不符，请对齐本 §4.1。

### 4.2 推荐实现（参考，可优化）
```python
from backend.llm import chat_json, use_mock
from backend.db import get_conn

QUIZ_GRADE_SYSTEM = """你是一位严谨的阅卷官，依据课程资料对徒弟的作答评分。
仅输出 JSON：{"score": 0-100 的整数, "feedback": "评语，含正确答案与解析"}。
简答题按关键点命中比例给分；无 Key/无法判断时给出合理分并说明。"""

def grade_quiz_answer(plan_item_id: int, answer: str, context: str = None) -> dict:
    if context is None:
        conn = get_conn()
        row = conn.execute(
            "SELECT c.content FROM plan_items pi JOIN courses c ON pi.course_id=c.id WHERE pi.id=?",
            (plan_item_id,)).fetchone()
        context = (row["content"] or "") if row else ""
    if use_mock():
        score = min(100, max(20, len(answer or "") * 3)) if answer else 20
        return {"score": score, "feedback": "（演示模式）已根据作答长度给出初评；配置真实 LLM 后将以语义理解评分。"}
    prompt = f"课程资料：\n{context}\n\n徒弟作答：\n{answer}\n\n请严格按系统指令仅返回评分 JSON。"
    result = chat_json(QUIZ_GRADE_SYSTEM, prompt)
    if not isinstance(result, dict) or "score" not in result:
        score = min(100, max(20, len(answer or "") * 3)) if answer else 20
        return {"score": score, "feedback": "（LLM 解析失败，已兜底评分）"}
    try:
        return {"score": int(result.get("score", 0)), "feedback": str(result.get("feedback", ""))}
    except (TypeError, ValueError):
        return {"score": 0, "feedback": "（分数解析失败）"}
```

> P6 会把返回写入 `quizzes.ai_score`，状态 `pending_review`，师傅可在后台终评（`master_score`）。

---

## 5. 增强任务（在保持签名前提下）
1. **JSON 鲁棒解析**：把"去围栏 → 精确解析 → 括号匹配截取"封装为 `backend/agents/_jsonutil.py` 的 `safe_json(text)`，供 5 个 agent 复用（替换各处 `chat_json` 后的脆弱解析）。
2. **无 Key 演示兜底**：确认 `use_mock()` 为 True 时，5 个 agent 都返回结构完整、可演示的示例（当前已部分实现，补全缺失分支）。
3. **稳定性**：LLM 超时/异常不导致接口 500，统一降级为兜底结果。

---

## 6. 测试要求（test-driven-development）
在 `tests/` 写 `test_agents.py`：
- `grade_quiz_answer`：无 Key 走兜底返回 `{"score","feedback"}`；构造 mock `chat_json` 返回合法 JSON 时正确解析；返回畸形 JSON 时走兜底不抛异常。
- `safe_json`：对带 ```json 围栏、缺括号、嵌套括号的输入都能正确解析。
- 现有 5 个 agent 在 `use_mock()` 下能返回 `{success:True,...}` 不报错（回归）。

---

## 7. 交付物
1. `backend/agents/assessor.py` 新增 `grade_quiz_answer`（签名同 §4.1），现有函数签名不变。
2. （可选）`backend/agents/_jsonutil.py` + 5 个 agent 切换到 `safe_json`。
3. `tests/test_agents.py` 通过。
4. 自测报告：对照 §8 验收清单逐项确认。

---

## 8. 验收标准总表
- [ ] `grade_quiz_answer(plan_item_id, answer, context=None) -> {"score","feedback"}` 签名与 P6 §5.1 完全一致
- [ ] 真实 LLM 下返回语义评分；无 Key / 解析失败走兜底且不抛异常
- [ ] 评分上下文自动取自 `courses.content`（context 为 None 时）
- [ ] 5 个 agent 现有签名未被破坏，`main.py` 现有调用不受影响
- [ ] `safe_json` 鲁棒解析各类 LLM 输出格式
- [ ] 无 Key 时全流程演示兜底正常
- [ ] `tests/test_agents.py` 全绿；`requesting-code-review` 自审已执行

---

## 9. 执行纪律（给执行 AI 的开场语建议）
"你是 P3。先读 `API_CONTRACT.md`/`TEAM_PLAN.md`/`TEAM_TASKS/P3_*.md` 与 `backend/agents/*.py`/`backend/llm.py`。只改 `backend/agents/*.py`，**禁止碰 main.py/db.py/auth.py/schemas.py**。保持现有 5 个 agent 的函数签名不变；在 assessor.py **新增** `grade_quiz_answer(plan_item_id, answer, context=None) -> {"score","feedback"}`（契约见 P6 §5.1，必须与 P6 一致）。中文优先；用 awesome-python 规范；test-driven-development 补 pytest；requesting-code-review 自审；遇错 systematic-debugging。无 Key 走演示兜底。"
