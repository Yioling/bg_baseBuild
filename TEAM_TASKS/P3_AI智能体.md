# 任务卡 · P3 AI 智能体（5 个）

## 你的角色
实现/完善 5 个 AI 智能体：Refiner / Assessor / Planner / Tutor / Reviewer。复杂度评分核心。

## 你可写的文件
- `backend/agents/refiner.py`
- `backend/agents/assessor.py`
- `backend/agents/planner.py`
- `backend/agents/tutor.py`
- `backend/agents/reviewer.py`

## 禁止触碰
- `main.py` `db.py` `auth.py` `schemas.py`

## 你要做的事
1. **5 个 agent 现状核对**（已被 `main.py` 调用，签名不可随意改）：
   - `refiner.refine(kb_id)`
   - `assessor.generate_assessment(user_id, kb_id)` / `grade_answer(question_id, answer, assessment_id)` / `get_assessment_result(assessment_id)` / `get_mistakes(user_id)`
   - `planner.generate_plan(apprentice_id, kb_id)` / `get_plan(apprentice_id)` / `update_plan_day(day_id, note, locked)` / `update_plan_task(task_id, data)`
   - `tutor.ask(user_id, kb_id, question, store)` / `generate_lecture_content(...)`
   - `reviewer.generate_review(user_id, plan_day_id)` / `grade_review_answer(question_id, answer, review_id)`
2. **P0：Quiz 真实 LLM 评分**：当前 `main.py` 的 `api_submit_quiz` 用答案长度当分数（简易算法）。你需提供一个**真实 LLM 批改函数**（如 `assessor.grade_quiz_answer(plan_item_id, answer)` 返回 0~100 分 + 解析），由 P6 在 quiz 路由调用、P1 装配。结构化输出必须鲁棒解析。
3. **JSON 鲁棒性**：所有 LLM 结构化输出做多层降级（去 ```json 围栏 → 精确解析 → 括号匹配截取首个 `{`/`[`）。
4. **演示模式兜底**：无 Key 时返回内置示例，保证全流程可演示。

## 验收标准
- [ ] 5 个 agent 可被 `main.py` 现有调用正常驱动
- [ ] 新增真实 LLM 评分函数经 P1/P6 装配后，`/api/apprentice/quiz/submit` 返回真实 AI 初评（P0 完成）
- [ ] 所有结构化输出解析稳定，不因 LLM 格式波动崩溃
- [ ] 无 Key 时全部 agent 走演示兜底

## 给 AI 的开场提示词
"你负责 5 个 AI 智能体（P3）。只改 `backend/agents/*.py`，禁止碰 main.py/db.py/auth.py/schemas.py。函数签名必须与 `API_CONTRACT.md` 现有调用完全一致（见上）。实现 P0 真实 LLM 评分函数供 quiz 调用；JSON 解析必须鲁棒；无 Key 走演示模式。精准替换，不重写。"
