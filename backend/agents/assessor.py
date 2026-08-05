"""Assessor 测评智能体：出题 + 批改 + 定级。"""
import json
import re
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


def _local_grade(apprentice_answer: str, q_data: dict) -> dict:
    """本地降级评分（LLM 返空时）。

    评分逻辑：
    - 选择题：拿答与 answer_key 比对，完全一致 100 / 否则 0
    - 简答题：拆标准答案为关键词，按命中比例给分（最低 20 分保底）
    - 输出反馈含标准答案 + 命中比例
    """
    answer = (apprentice_answer or "").strip()
    key = (q_data.get("answer_key") or "").strip()
    qtype = (q_data.get("qtype") or "short").lower()
    if not answer:
        return {
            "score": 0,
            "feedback": "未作答。请参考标准答案补充：\n" + (key or "(无标准答案)"),
            "is_correct": False,
        }
    if qtype == "choice":
        # answer 可能是 "A" / "A. xxx"，只取首字母
        a_letter = answer[0].upper() if answer else ""
        k_letter = (key[0].upper() if key else "")
        ok = bool(k_letter) and a_letter == k_letter
        return {
            "score": 100 if ok else 0,
            "feedback": ("选对啦：你的答案与标准选项一致。\n" if ok else "未选对：本题正确选项为 ")
                       + (key or "(无标准答案)") + "。",
            "is_correct": ok,
        }
    # 简答：关键词命中比例
    keywords = [w for w in re.split(r"[，。；、 ,.\u3000]+", key) if len(w) >= 2] or [key]
    if not keywords:
        keywords = [key]
    hit = sum(1 for w in keywords if w and w in answer)
    pct = hit / max(1, len(keywords))
    score = int(min(100, max(20, pct * 100)))
    is_correct = score >= 60
    fb_lines = [
        f"（本地粗评：命中关键点 {hit}/{len(keywords)} = {int(pct*100)}%）",
        f"参考标准答案：{key or '(无)'}",
    ]
    return {
        "score": score,
        "feedback": "\n".join(fb_lines),
        "is_correct": is_correct,
    }


def _local_generate_questions(dims_list: list[dict]) -> list[dict]:
    """本地降级出题：不依赖 LLM，基于师傅知识库的维度名/描述/知识点拼题。

    P1 加：为在无 LLM / LLM 调用失败的环境也能出题。
    - 每个维度出 3 题（易 / 中 / 难），完全基于 dimensions 表的内容，
    - 选择题以 4 选项 + answer_key="A" 模拟起见（永远不会被“判定”为对），
      重点是“选择型 1 题”加 2 道思考简答题。实际评分时若选了选项提示
      “本地占位选项，请参考知识点表述作答”。
    - 题目内容必须与师傅的知识库对齐，不编造。
    """
    out: list[dict] = []
    for d in dims_list:
        name = d["name"]
        desc = (d.get("description") or "").strip()
        pts = d.get("points") or []
        pt_titles = [p.get("title", "") for p in pts if p.get("title")]
        pt_blurb = "、".join(pt_titles[:3]) if pt_titles else ""
        ctx = desc or pt_blurb or name
        # 易 1：选项型 (无标准答案——以“选项作考点提示”逼学员在知识库中查)
        q_easy = {
            "dimension_name": name,
            "question": f"【选择】下列哪一项最贴切地描述“{name}”？（请结合师傅知识库表述作答）",
            "qtype": "choice",
            "difficulty": "易",
            "options": [
                f"A. {name}的核心要点",
                f"B. 与{name}无关的通用概念",
                f"C. 其他模块的关联说明",
                f"D. 以上都不是",
            ],
            "answer_key": "A",
            "explanation": f"请参考维度描述：{ctx or name}",
        }
        # 中 1：简答
        q_mid = {
            "dimension_name": name,
            "question": f"【简答】请用自己的话阐述“{name}”的关键内容（不少于 30 字）。",
            "qtype": "short",
            "difficulty": "中",
            "options": None,
            "answer_key": ctx or pt_blurb or name,
            "explanation": f"关键点：{ctx or pt_blurb or name}",
        }
        # 难 1：应用题（从首个知识点截取为题干）
        pt0 = pt_titles[0] if pt_titles else name
        q_hard = {
            "dimension_name": name,
            "question": f"【应用】以“{pt0}”为背景，举例说明其在“{name}”中的实际应用。",
            "qtype": "short",
            "difficulty": "难",
            "options": None,
            "answer_key": f"应联系“{pt0}”与{name}：{ctx or pt_blurb}",
            "explanation": f"参考答案：结合知识点“{pt0}”与维度描述作答。",
        }
        out.extend([q_easy, q_mid, q_hard])
    return out


def generate_assessment(apprentice_id: int, kb_id: int) -> dict:
    """生成摸底考试题目。

    优先调真实 LLM 出题；若 LLM 调用失败（连不上/超时/返空），自动降级到
    本地模板出题（基于师傅维度与知识点内容拼题），保证始终能生成题目。
    """
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

    # 降级：LLM 返空或无 questions 字段 → 本地模板出题
    if not result or "questions" not in result or not result["questions"]:
        result = {"questions": _local_generate_questions(dims_list)}
        # 如果连维度都没有，仍无法出题，给出明确提示
        if not result["questions"]:
            return {"success": False, "message": "题目生成失败：知识库维度为空"}

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
    # P1 降级：LLM 返空 → 按“关键点命中比例”本地粗评，保证徒弟提交后能拿到反馈
    if not isinstance(result, dict) or "score" not in result:
        result = _local_grade(apprentice_answer, q_data)
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


QUIZ_GRADE_SYSTEM = """你是一位严谨的阅卷官，依据课程资料对徒弟的作答评分。
仅输出 JSON：{"score": 0-100 的整数, "feedback": "评语，含正确答案与解析"}。
简答题按关键点命中比例给分；无 Key/无法判断时给出合理分并说明。"""


def grade_quiz_answer(plan_item_id: int, answer: str, context: str = None) -> dict:
    """对今日任务检测的徒弟作答做真实 LLM 初评（P0）。
    返回: {"score": int(0-100), "feedback": str}
    - context 为 None 时，内部据 plan_item_id 取 courses.content 作为评分上下文
    - 无 Key / LLM 失败 / 解析失败 → 兜底评分（基于答案长度）并说明
    """
    # 取评分上下文
    if context is None:
        conn = get_conn()
        row = conn.execute(
            "SELECT c.content FROM plan_items pi JOIN courses c ON pi.course_id=c.id WHERE pi.id=?",
            (plan_item_id,),
        ).fetchone()
        context = (row["content"] or "") if row else ""

    # 演示模式兜底
    if use_mock():
        score = min(100, max(20, len(answer or "") * 3)) if answer else 20
        return {
            "score": score,
            "feedback": "（演示模式）已根据作答长度给出初评；配置真实 LLM 后将以语义理解评分。",
        }

    # 真实 LLM 评分
    prompt = f"课程资料：\n{context}\n\n徒弟作答：\n{answer}\n\n请严格按系统指令仅返回评分 JSON。"
    result = chat_json(QUIZ_GRADE_SYSTEM, prompt)

    # 解析结果
    if not isinstance(result, dict) or "score" not in result:
        score = min(100, max(20, len(answer or "") * 3)) if answer else 20
        return {"score": score, "feedback": "（LLM 解析失败，已兜底评分）"}
    try:
        return {"score": int(result.get("score", 0)), "feedback": str(result.get("feedback", ""))}
    except (TypeError, ValueError):
        score = min(100, max(20, len(answer or "") * 3)) if answer else 20
        return {"score": score, "feedback": "（分数解析失败，已兜底评分）"}


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
