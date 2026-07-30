"""Assessor 测评智能体：出题 + 批改 + 定级。"""
import json
from backend.llm import chat_json, chat, use_mock
from backend.db import get_conn


ASSESS_SYSTEM = """你是一位严格的技术测评官。按以下 JSON 格式出题：

{
  "questions": [
    {
      "dimension_name": "维度名称",
      "question": "题目内容",
      "qtype": "choice",
      "difficulty": "易",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "answer_key": "A",
      "explanation": "解析"
    }
  ]
}

要求：
1. 每个维度出 3 题（难度：易、中、难各 1 题）
2. qtype 为 choice（选择）或 short（简答）；short 题 options 为 null
3. 题目要考察真正的理解，不以记忆为主
4. 确保所有文本为中文"""

GRADE_SYSTEM = """你是一位严谨的阅卷官。对徒弟的作答进行批改。

输入格式：题目信息 + 徒弟作答
输出 JSON：
{
  "score": 0-100 的整数,
  "feedback": "评语（含正确答案与解析）",
  "is_correct": true/false
}

评分标准：
- 选择题：答对 100 分，答错 0 分
- 简答题：0-100 分，关键点命中 60% 以上及格
- 无需展示过程，只输出 JSON"""


def generate_assessment(apprentice_id: int, kb_id: int) -> dict:
    """生成摸底考试题目。"""
    conn = get_conn()
    dims = conn.execute(
        "SELECT d.* FROM dimensions d WHERE d.kb_id=? ORDER BY d.sort_order LIMIT 8",
        (kb_id,),
    ).fetchall()
    if not dims:
        return {"success": False, "message": "知识库尚未精炼，请师傅先触发 AI 精炼"}

    dims_list = []
    for d in dims:
        pts = conn.execute(
            "SELECT title, content, level FROM knowledge_points WHERE dimension_id=?",
            (d["id"],),
        ).fetchall()
        dims_list.append({
            "name": d["name"],
            "description": d["description"] or "",
            "points": [dict(p) for p in pts],
        })

    dims_json = json.dumps(dims_list, ensure_ascii=False, indent=2)
    result = chat_json(ASSESS_SYSTEM, f"请基于以下知识维度出摸底考试题：\n\n{dims_json}")

    if not result or "questions" not in result:
        return {"success": False, "message": "题目生成失败"}

    # 创建评估记录
    cur = conn.execute(
        "INSERT INTO assessments (apprentice_id, kb_id, status) VALUES (?, ?, 'in_progress')",
        (apprentice_id, kb_id),
    )
    assessment_id = cur.lastrowid

    # 建立 dimension name -> id 映射
    dim_name_to_id = {d["name"]: d["id"] for d in dims}

    questions = []
    for q in result["questions"]:
        dim_id = dim_name_to_id.get(q.get("dimension_name", ""))
        opts = json.dumps(q.get("options"), ensure_ascii=False) if q.get("options") else None
        cur_q = conn.execute(
            "INSERT INTO assessment_questions (assessment_id, dimension_id, question, qtype, difficulty, answer_key, options) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (assessment_id, dim_id, q["question"], q.get("qtype", "short"),
             q.get("difficulty", "中"), q.get("answer_key", ""), opts),
        )
        q["id"] = cur_q.lastrowid
        q["dimension_id"] = dim_id
        questions.append(q)

    conn.commit()
    return {
        "success": True,
        "assessment_id": assessment_id,
        "questions": questions,
    }


def grade_answer(question_id: int, apprentice_answer: str, assessment_id: int) -> dict:
    """批改单题作答并定级。"""
    conn = get_conn()
    qrow = conn.execute(
        "SELECT * FROM assessment_questions WHERE id=? AND assessment_id=?",
        (question_id, assessment_id),
    ).fetchone()
    if not qrow:
        return {"success": False, "message": "题目不存在"}

    q_data = {
        "question": qrow["question"],
        "qtype": qrow["qtype"],
        "answer_key": qrow["answer_key"] or "",
        "options": qrow["options"],
    }

    prompt = f"题目：{q_data['question']}\n题型：{q_data['qtype']}\n标准答案：{q_data['answer_key']}\n选项：{q_data['options'] or '无'}\n徒弟作答：{apprentice_answer}"

    result = chat_json(GRADE_SYSTEM, prompt)
    score = result.get("score", 0) if isinstance(result, dict) else 0
    feedback = result.get("feedback", "") if isinstance(result, dict) else ""
    is_correct = result.get("is_correct", False) if isinstance(result, dict) else False

    # 持久化作答
    conn.execute(
        "INSERT INTO assessment_answers (assessment_id, question_id, apprentice_answer, score, feedback) VALUES (?, ?, ?, ?, ?)",
        (assessment_id, question_id, apprentice_answer, score, feedback),
    )
    conn.commit()

    # 更新掌握等级
    if qrow["dimension_id"]:
        _update_mastery(assessment_id, qrow["dimension_id"], conn)

    return {
        "success": True,
        "score": score,
        "feedback": feedback,
        "is_correct": is_correct,
        "answer_key": qrow["answer_key"],
    }


def _update_mastery(assessment_id: int, dimension_id: int, conn):
    """按维度聚合正确率，更新掌握等级。"""
    # 获取该测评中此维度的全部答题
    answers = conn.execute(
        """SELECT aa.score FROM assessment_answers aa
           JOIN assessment_questions aq ON aa.question_id = aq.id
           WHERE aa.assessment_id = ? AND aq.dimension_id = ?""",
        (assessment_id, dimension_id),
    ).fetchall()
    if not answers:
        return
    avg = sum(a["score"] for a in answers) / len(answers)
    if avg >= 80:
        level = "熟练"
    elif avg >= 50:
        level = "了解"
    else:
        level = "未掌握"

    assessment = conn.execute("SELECT apprentice_id FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    if not assessment:
        return
    apprentice_id = assessment["apprentice_id"]

    conn.execute(
        """INSERT INTO mastery (apprentice_id, dimension_id, level, score)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(apprentice_id, dimension_id) DO UPDATE SET level=excluded.level, score=excluded.score, updated_at=CURRENT_TIMESTAMP""",
        (apprentice_id, dimension_id, level, avg),
    )
    conn.commit()


def get_assessment_result(assessment_id: int) -> dict:
    """获取某次摸底考试的完整结果。"""
    conn = get_conn()
    ass = conn.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    if not ass:
        return {"success": False, "message": "评估不存在"}

    questions = conn.execute(
        "SELECT * FROM assessment_questions WHERE assessment_id=? ORDER BY id",
        (assessment_id,),
    ).fetchall()

    result_questions = []
    for q in questions:
        ans = conn.execute(
            "SELECT * FROM assessment_answers WHERE question_id=? AND assessment_id=?",
            (q["id"], assessment_id),
        ).fetchone()
        result_questions.append({
            "id": q["id"],
            "question": q["question"],
            "qtype": q["qtype"],
            "difficulty": q["difficulty"],
            "options": json.loads(q["options"]) if q["options"] else None,
            "answer_key": q["answer_key"],
            "apprentice_answer": ans["apprentice_answer"] if ans else None,
            "score": ans["score"] if ans else None,
            "feedback": ans["feedback"] if ans else None,
        })

    # 获取掌握等级
    mastery_rows = conn.execute(
        "SELECT m.*, d.name as dim_name FROM mastery m JOIN dimensions d ON m.dimension_id = d.id WHERE m.apprentice_id=?",
        (ass["apprentice_id"],),
    ).fetchall()

    return {
        "success": True,
        "assessment_id": assessment_id,
        "status": ass["status"],
        "questions": result_questions,
        "mastery": [dict(m) for m in mastery_rows],
    }


def get_mistakes(apprentice_id: int) -> dict:
    """获取徒弟的错题本。"""
    conn = get_conn()
    # 摸底考试错题
    assess_mistakes = conn.execute(
        """SELECT aa.*, aq.question, aq.qtype, aq.difficulty, aq.answer_key, aq.options,
                  aa.created_at as answered_at
           FROM assessment_answers aa
           JOIN assessment_questions aq ON aa.question_id = aq.id
           JOIN assessments a ON aa.assessment_id = a.id
           WHERE a.apprentice_id = ? AND aa.score < 60
           ORDER BY aa.created_at DESC""",
        (apprentice_id,),
    ).fetchall()

    # 复习错题
    review_mistakes = conn.execute(
        """SELECT rq.*, dr.created_at as review_date
           FROM review_questions rq
           JOIN daily_reviews dr ON rq.review_id = dr.id
           WHERE dr.apprentice_id = ? AND rq.score < 60
           ORDER BY dr.created_at DESC""",
        (apprentice_id,),
    ).fetchall()

    return {
        "success": True,
        "assess_mistakes": [dict(m) for m in assess_mistakes],
        "review_mistakes": [dict(m) for m in review_mistakes],
    }
