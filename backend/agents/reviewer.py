"""Reviewer 复习智能体：依当天内容生成问题 + 批改。"""
import json
from backend.llm import chat_json, chat
from backend.db import get_conn


REVIEW_SYSTEM = """你是一位复习导师。根据当天学习内容出一些复习题，检验徒弟的掌握程度。

严格按 JSON 格式输出：
{
  "questions": [
    {
      "question": "题目内容",
      "qtype": "choice",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "answer_key": "A",
      "score": 10
    }
  ]
}

要求：
1. 出 5 题，覆盖当天主要知识点
2. qtype 为 choice（选择）或 short（简答）；short 题 options 为 null
3. score 为每题分值（总分 100）
4. 确保所有文本为中文"""

GRADE_SYSTEM = """你是一位阅卷官。批改复习题作答。

输入：题目 + 标准答案 + 徒弟作答
输出 JSON：
{
  "score": 整数（0 到该题满分）,
  "feedback": "简短评语",
  "is_correct": true/false
}"""


def generate_review(apprentice_id: int, plan_day_id: int) -> dict:
    """生成当日复习题。"""
    conn = get_conn()
    tasks = conn.execute(
        "SELECT pt.title, d.name as dim_name FROM plan_tasks pt LEFT JOIN dimensions d ON pt.dimension_id = d.id WHERE pt.day_id=?",
        (plan_day_id,),
    ).fetchall()
    if not tasks:
        return {"success": False, "message": "当日无学习任务"}

    tasks_text = "\n".join(f"- [{t['dim_name'] or '综合'}] {t['title']}" for t in tasks)
    result = chat_json(REVIEW_SYSTEM, f"当天学习内容：\n{tasks_text}\n\n请出复习题。")

    if not result or "questions" not in result:
        return {"success": False, "message": "题目生成失败"}

    # 创建复习记录
    cur = conn.execute(
        "INSERT INTO daily_reviews (apprentice_id, plan_day_id) VALUES (?, ?)",
        (apprentice_id, plan_day_id),
    )
    review_id = cur.lastrowid

    questions = []
    for q in result["questions"]:
        opts = json.dumps(q.get("options"), ensure_ascii=False) if q.get("options") else None
        cur_q = conn.execute(
            "INSERT INTO review_questions (review_id, question, qtype, answer_key) VALUES (?, ?, ?, ?)",
            (review_id, q["question"], q.get("qtype", "short"), q.get("answer_key", "")),
        )
        q["id"] = cur_q.lastrowid
        q["max_score"] = q.get("score", 20)
        questions.append(q)

    conn.commit()
    return {
        "success": True,
        "review_id": review_id,
        "questions": questions,
    }


def grade_review_answer(question_id: int, apprentice_answer: str, review_id: int) -> dict:
    """批改复习题作答。"""
    conn = get_conn()
    qrow = conn.execute(
        "SELECT * FROM review_questions WHERE id=? AND review_id=?",
        (question_id, review_id),
    ).fetchone()
    if not qrow:
        return {"success": False, "message": "题目不存在"}

    prompt = f"题目：{qrow['question']}\n标准答案：{qrow['answer_key']}\n徒弟作答：{apprentice_answer}"
    result = chat_json(GRADE_SYSTEM, prompt)

    score = result.get("score", 0) if isinstance(result, dict) else 0
    feedback = result.get("feedback", "") if isinstance(result, dict) else ""

    conn.execute(
        "UPDATE review_questions SET apprentice_answer=?, score=?, feedback=? WHERE id=?",
        (apprentice_answer, score, feedback, question_id),
    )
    conn.commit()

    return {
        "success": True,
        "score": score,
        "feedback": feedback,
        "answer_key": qrow["answer_key"],
    }
