"""Assessor 测评智能体：出题 + 批改 + 定级。"""
import json
from backend.llm import chat_json, chat, use_mock
from backend.db import get_conn


ASSESS_SYSTEM = """你是一位严格的技术测评官。根据提供的知识维度出题，题目从易到难分布，覆盖全面知识点。

严格按 JSON 格式输出：
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
1. 题目难度从易到难分布：简单题约占30%，中等题约占40%，难题约占30%
2. 题目覆盖所有提供的知识维度，不要只考一个维度
3. qtype 为 choice（选择）或 short（简答）；short 题 options 为 null
4. 选择题要有 4 个选项且答案明确；简答题要有明确的评分要点
5. 题目考察真正的理解与应用，不以记忆为主
6. 确保所有文本为中文"""

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


def generate_assessment(apprentice_id: int, kb_id: int, num_questions: int = 10) -> dict:
    """生成摸底考试题目。

    Args:
        apprentice_id: 徒弟ID
        kb_id: 知识库ID
        num_questions: 题目数量（默认10题），由师傅决定
    """
    conn = get_conn()
    dims = conn.execute(
        "SELECT d.* FROM dimensions d WHERE d.kb_id=? ORDER BY d.sort_order",
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
    # 根据师傅要求的题量生成题目，强调难度分布和知识点覆盖
    result = chat_json(ASSESS_SYSTEM,
        f"请基于以下知识维度出 {num_questions} 道摸底考试题。\n"
        f"要求：简单题约{int(num_questions*0.3)}道、中等题约{int(num_questions*0.4)}道、难题约{int(num_questions*0.3)}道。\n"
        f"题目要从易到难，所有知识维度都要覆盖，不要集中在同一个知识点。\n\n{dims_json}")

    if not result or "questions" not in result:
        # LLM 不可用 / 返回畸形 → 本地降级出题，保证徒弟始终能进入考试
        result = _local_generate_questions(dims_list, num_questions)
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
        if not answer or not answer.strip():
            return {
                "score": 0,
                "feedback": "（演示模式）未检测到作答内容，得0分；请补充完整作答后再提交。",
            }
        score = min(100, max(20, len(answer) * 3))
        return {
            "score": score,
            "feedback": "（演示模式）已根据作答长度给出初评；配置真实 LLM 后将以语义理解评分。",
        }

    # 真实 LLM 评分
    prompt = f"课程资料：\n{context}\n\n徒弟作答：\n{answer}\n\n请严格按系统指令仅返回评分 JSON。"
    result = chat_json(QUIZ_GRADE_SYSTEM, prompt)

    # 解析结果
    if not isinstance(result, dict) or "score" not in result:
        if not answer or not answer.strip():
            return {"score": 0, "feedback": "（LLM 解析失败）未检测到作答内容，得0分。"}
        score = min(100, max(20, len(answer) * 3))
        return {"score": score, "feedback": "（LLM 解析失败，已兜底评分）"}
    try:
        return {"score": int(result.get("score", 0)), "feedback": str(result.get("feedback", ""))}
    except (TypeError, ValueError):
        if not answer or not answer.strip():
            return {"score": 0, "feedback": "（分数解析失败）未检测到作答内容，得0分。"}
        score = min(100, max(20, len(answer) * 3))
        return {"score": score, "feedback": "（分数解析失败，已兜底评分）"}


WEAKNESS_ANALYSIS_SYSTEM = """你是一位资深技术导师，擅长分析学员的薄弱点并给出针对性提升建议。

输入：学员的答题情况（包含题目、作答、分数、反馈）
输出：JSON格式的薄弱点分析和提升建议

严格按以下JSON格式输出：
{
  "weakness_summary": "总体薄弱点概述（30字以内）",
  "weak_points": [
    {
      "dimension": "薄弱维度名称",
      "problem_type": "问题类型：如概念不清、记忆模糊、计算错误、理解偏差等",
      "specific_issue": "具体问题描述",
      "recommendation": "针对性提升建议（具体可执行）"
    }
  ],
  "strength_points": ["掌握良好的维度列表"],
  "next_study_priority": ["下一步学习优先级排序（从高到低）"],
  "estimated_improvement": "预计多久可以改善（如：坚持练习2周可明显提升）"
}

要求：
1. 分析要具体，不仅指出"不会"，要说明"哪里不会"和"如何改进"
2. 提升建议要具体可执行，如：需要重新学习哪个知识点、需要做什么练习
3. 优先指出高频错误和关键概念理解偏差
4. 确保所有文本为中文"""

def analyze_weaknesses(assessment_id: int) -> dict:
    """针对作答情况分析薄弱点。

    Args:
        assessment_id: 评估记录ID

    Returns:
        包含薄弱点分析、Strength points、提升建议等
    """
    conn = get_conn()

    # 获取评估信息和所有答题
    ass = conn.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    if not ass:
        return {"success": False, "message": "评估不存在"}

    questions = conn.execute(
        "SELECT * FROM assessment_questions WHERE assessment_id=? ORDER BY id",
        (assessment_id,),
    ).fetchall()

    # 收集答题详情
    answer_details = []
    for q in questions:
        ans = conn.execute(
            "SELECT * FROM assessment_answers WHERE question_id=? AND assessment_id=?",
            (q["id"], assessment_id),
        ).fetchone()

        # 获取维度名称
        dim_row = conn.execute("SELECT name FROM dimensions WHERE id=?", (q["dimension_id"],)).fetchone()
        dim_name = dim_row["name"] if dim_row else "未知维度"

        answer_details.append({
            "dimension": dim_name,
            "question": q["question"],
            "qtype": q["qtype"],
            "difficulty": q["difficulty"],
            "answer_key": q["answer_key"],
            "apprentice_answer": ans["apprentice_answer"] if ans else "未作答",
            "score": ans["score"] if ans else 0,
            "feedback": ans["feedback"] if ans else "",
        })

    if not answer_details:
        return {"success": False, "message": "暂无答题记录"}

    # 构建分析prompt
    prompt = "请分析以下答题情况，找出薄弱点并给出提升建议：\n\n"
    for i, a in enumerate(answer_details, 1):
        prompt += f"第{i}题：[{a['difficulty']}] {a['dimension']}\n"
        prompt += f"题目：{a['question']}\n"
        prompt += f"学员作答：{a['apprentice_answer']}\n"
        prompt += f"得分：{a['score']} | 反馈：{a['feedback']}\n\n"

    # 演示模式兜底
    if use_mock():
        return {
            "success": True,
            "weakness_summary": "需要在并发编程和异常处理方面加强练习",
            "weak_points": [
                {
                    "dimension": "并发编程",
                    "problem_type": "概念理解不深",
                    "specific_issue": "对线程同步机制理解模糊，不能正确选择锁类型",
                    "recommendation": "1. 重新学习线程安全概念；2. 练习使用RLock和Condition；3. 完成并发编程实战练习"
                },
                {
                    "dimension": "异常处理",
                    "problem_type": "处理不当",
                    "specific_issue": "异常捕获后未做适当处理，直接pass",
                    "recommendation": "1. 学习异常处理最佳实践；2. 记录异常日志；3. 根据异常类型做不同处理"
                }
            ],
            "strength_points": ["基础语法", "面向对象概念"],
            "next_study_priority": ["并发编程实战", "异常处理进阶", "设计模式"],
            "estimated_improvement": "针对薄弱点集中练习2-3周可明显提升"
        }

    result = chat_json(WEAKNESS_ANALYSIS_SYSTEM, prompt)

    if not result or not isinstance(result, dict):
        return {
            "success": True,
            "weakness_summary": "建议针对错题进行针对性复习",
            "weak_points": [],
            "strength_points": [],
            "next_study_priority": [],
            "estimated_improvement": "坚持每日练习可逐步改善"
        }

    return {
        "success": True,
        "weakness_summary": result.get("weakness_summary", ""),
        "weak_points": result.get("weak_points", []),
        "strength_points": result.get("strength_points", []),
        "next_study_priority": result.get("next_study_priority", []),
        "estimated_improvement": result.get("estimated_improvement", ""),
    }


TRAINING_RECOMMENDATION_SYSTEM = """你是一位资深的培养计划专家，根据学员的薄弱点分析生成具体可执行的培养建议。

输入：学员的薄弱点分析、各维度掌握情况
输出：JSON格式的具体培养建议

严格按以下JSON格式输出：
{
  "training_overview": "培养总体思路（50字以内）",
  "recommendations": [
    {
      "priority": 1,
      "dimension": "维度名称",
      "target_issue": "针对的具体问题",
      "learning_content": "需要学习的内容（具体）",
      "practical_tasks": ["需要完成的实践任务列表"],
      "resources": ["推荐学习资源"],
      "duration_estimate": "预计需要多长时间（如：3-5天）",
      "success_criteria": "完成标准（如何判断掌握）"
    }
  ],
  "daily_schedule_suggestion": "每日学习时间建议（如：每天30-60分钟）",
  "encouragement": "鼓励语（30字以内）"
}

要求：
1. 每条建议都要具体可执行，不能是空话
2. practical_tasks 要列出具体的任务内容，如：阅读某章节、完成某个练习项目
3. resources 可以是具体的文档链接或书籍章节
4. success_criteria 要有明确的判断标准
5. 按优先级排序，优先解决关键薄弱点
6. 确保所有文本为中文"""

def generate_training_recommendation(apprentice_id: int, assessment_id: int = None) -> dict:
    """根据掌握情况生成下一步培养计划建议。

    Args:
        apprentice_id: 徒弟ID
        assessment_id: 可选，评估ID（如果提供将结合答题情况进行更精准的分析）

    Returns:
        包含具体可执行的培养建议
    """
    conn = get_conn()

    # 获取徒弟信息
    apprentice = conn.execute("SELECT * FROM users WHERE id=?", (apprentice_id,)).fetchone()
    if not apprentice:
        return {"success": False, "message": "徒弟不存在"}

    # 获取掌握等级
    mastery_rows = conn.execute(
        "SELECT m.*, d.name as dim_name FROM mastery m JOIN dimensions d ON m.dimension_id = d.id WHERE m.apprentice_id=?",
        (apprentice_id,),
    ).fetchall()

    # 获取知识维度详情
    dims = conn.execute(
        "SELECT d.*, kb.name as kb_name FROM dimensions d JOIN knowledge_bases kb ON d.kb_id = kb.id WHERE kb.master_id=?",
        (apprentice["master_id"],),
    ).fetchall()

    dim_info = {}
    for d in dims:
        dim_info[d["id"]] = {
            "name": d["name"],
            "description": d["description"] or "",
            "mastery": "未掌握"
        }

    # 更新掌握等级
    for m in mastery_rows:
        if m["dimension_id"] in dim_info:
            dim_info[m["dimension_id"]]["mastery"] = m["level"]

    mastery_summary = []
    weak_dims = []
    for dim_id, info in dim_info.items():
        mastery_summary.append(f"{info['name']}：{info['mastery']}")
        if info["mastery"] in ["未掌握", "了解"]:
            weak_dims.append(info["name"])

    # 如果提供了assessment_id，获取答题详情
    answer_context = ""
    if assessment_id:
        ans_detail = analyze_weaknesses(assessment_id)
        if ans_detail.get("success"):
            answer_context = f"\n\n答题分析结果：\n"
            answer_context += f"薄弱点概述：{ans_detail.get('weakness_summary', '')}\n"
            answer_context += f"薄弱维度：{', '.join(weak_dims)}\n"
            if ans_detail.get("weak_points"):
                answer_context += "\n具体问题：\n"
                for wp in ans_detail["weak_points"][:3]:
                    answer_context += f"- {wp.get('dimension')}: {wp.get('specific_issue', '')}\n"
                    answer_context += f"  建议：{wp.get('recommendation', '')}\n"

    # 演示模式兜底
    if use_mock():
        return {
            "success": True,
            "training_overview": "针对薄弱点制定个性化培养计划，重点突破并发编程和异常处理",
            "recommendations": [
                {
                    "priority": 1,
                    "dimension": "并发编程",
                    "target_issue": "线程同步机制理解模糊，不能正确选择锁类型",
                    "learning_content": "1. 学习线程安全基础概念；2. 深入理解RLock/Condition/Semaphore；3. 了解死锁产生条件及避免方法",
                    "practical_tasks": [
                        "完成线程安全练习：使用锁保护共享资源",
                        "实现一个简单的生产者-消费者模型",
                        "编写一个避免死锁的银行转账程序"
                    ],
                    "resources": ["Python并发编程官方文档", "《Python高性能编程》第三章"],
                    "duration_estimate": "5-7天",
                    "success_criteria": "能正确使用Lock/RLock完成线程同步，独立实现生产者-消费者模式"
                },
                {
                    "priority": 2,
                    "dimension": "异常处理",
                    "target_issue": "异常捕获后未做适当处理，直接pass",
                    "learning_content": "1. 学习异常处理最佳实践；2. 理解常见异常类型及处理方式；3. 异常日志记录方法",
                    "practical_tasks": [
                        "重构现有代码中的异常处理逻辑",
                        "为关键函数添加异常捕获和日志记录",
                        "实现自定义异常类"
                    ],
                    "resources": ["Python异常处理官方文档", "《Python技巧》异常处理章节"],
                    "duration_estimate": "3-5天",
                    "success_criteria": "能编写规范的异常处理代码，能根据异常类型做不同响应"
                },
                {
                    "priority": 3,
                    "dimension": "设计模式",
                    "target_issue": "缺乏设计模式知识，难以写出可维护代码",
                    "learning_content": "1. 理解单例模式、工厂模式、策略模式；2. 学习如何在实际项目中应用",
                    "practical_tasks": [
                        "为现有项目应用单例模式优化配置管理",
                        "使用策略模式重构条件判断代码"
                    ],
                    "resources": ["《设计模式》GoF23", "Python设计模式实战"],
                    "duration_estimate": "7-10天",
                    "success_criteria": "能识别场景并正确应用至少3种设计模式"
                }
            ],
            "daily_schedule_suggestion": "每天学习30-45分钟，分散在早中晚三个时段",
            "encouragement": "坚持每日练习，薄弱点一定会转化为优势！"
        }

    # 构建prompt
    prompt = f"请为徒弟生成个性化的培养建议。\n\n徒弟信息：{apprentice.get('full_name') or apprentice.get('username')}\n"
    prompt += f"当前掌握情况：\n" + "\n".join(mastery_summary) + "\n"
    prompt += f"需要加强的维度：{', '.join(weak_dims) if weak_dims else '暂无明显薄弱点'}\n"
    prompt += answer_context
    prompt += "\n\n请生成分层次、有针对性的培养建议，每条建议都要具体可执行。"

    result = chat_json(TRAINING_RECOMMENDATION_SYSTEM, prompt)

    if not result or not isinstance(result, dict):
        return {
            "success": False,
            "message": "培养建议生成失败，请稍后重试",
            "training_overview": "",
            "recommendations": [],
            "daily_schedule_suggestion": "",
            "encouragement": ""
        }

    return {
        "success": True,
        "training_overview": result.get("training_overview", ""),
        "recommendations": result.get("recommendations", []),
        "daily_schedule_suggestion": result.get("daily_schedule_suggestion", ""),
        "encouragement": result.get("encouragement", ""),
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


# ==================== 本地降级：LLM 不可用时的兜底出题/批改 ====================

def _local_generate_questions(dims_list: list, num_questions: int = 10) -> dict:
    """LLM 不可用时的本地兜底出题。

    根据知识维度生成简答题（short），每题包含 dimension_name/question/qtype/
    difficulty/answer_key，保证 generate_assessment 在无 LLM 时也能出题。

    策略：每个维度轮询出题直到达到 num_questions；题目内容基于维度名/描述/
    知识点标题拼接，answer_key 取该维度首个知识点的 content 作为评分要点。
    """
    if not dims_list:
        return {"questions": []}

    difficulties = ["易", "中", "难"]
    questions = []
    n = max(1, int(num_questions))
    # 轮询维度，保证覆盖
    idx = 0
    while len(questions) < n:
        dim = dims_list[idx % len(dims_list)]
        dim_name = dim.get("name", "未知维度")
        dim_desc = dim.get("description", "")
        points = dim.get("points", []) or []
        point = points[len(questions) % len(points)] if points else None

        if point:
            title = point.get("title", dim_name)
            key = point.get("content", title)
            question = f"请简述 {dim_name} 中「{title}」的核心要点。"
            answer_key = key
        else:
            question = f"请说明 {dim_name} 的主要概念。{dim_desc}".strip()
            answer_key = dim_desc or dim_name

        questions.append({
            "dimension_name": dim_name,
            "question": question,
            "qtype": "short",
            "difficulty": difficulties[len(questions) % len(difficulties)],
            "options": None,
            "answer_key": answer_key,
        })
        idx += 1
        # 安全阀：防止 num_questions 异常大导致死循环
        if idx > n * len(dims_list) + 100:
            break

    return {"questions": questions}


def _local_grade(answer: str, q_data: dict) -> dict:
    """LLM 不可用时的本地兜底批改。

    选择题：精确匹配 answer_key（忽略大小写/空白），对 100 错 0。
    简答题：按 answer_key 的关键字符（>=2 字）在作答中的命中比例打分，
            全命中 ≥ 60，部分命中按比例，空作答 0 分。

    返回 {"score": int, "is_correct": bool, "feedback": str}。
    """
    if not isinstance(q_data, dict):
        return {"score": 0, "is_correct": False, "feedback": "题目数据无效"}

    qtype = q_data.get("qtype", "short")
    key = (q_data.get("answer_key") or "").strip()

    # 选择题：精确匹配
    if qtype == "choice":
        ans = (answer or "").strip()
        is_correct = bool(key) and ans.upper() == key.upper()
        score = 100 if is_correct else 0
        feedback = "回答正确。" if is_correct else f"回答错误，正确答案：{key}"
        return {"score": score, "is_correct": is_correct, "feedback": feedback}

    # 简答题：关键点命中比例
    if not answer or not str(answer).strip():
        return {"score": 0, "is_correct": False, "feedback": "未作答。"}

    if not key:
        # 无标准答案，按作答非空给一个鼓励性分数
        return {"score": 60, "is_correct": True,
                "feedback": "无标准答案，按作答完整性给分。"}

    # 提取关键词（按常见分隔符切分；中文场景下退化为整段）
    import re
    raw_keys = re.split(r"[、,，;；\s]+", key)
    # 过滤掉过短的词（<2 字），避免单字噪音
    keys = [k for k in raw_keys if len(k) >= 2]
    if not keys:
        keys = [key]

    ans_text = str(answer)
    hit = sum(1 for k in keys if k in ans_text)
    ratio = hit / len(keys) if keys else 0
    # 全命中 90，按比例线性映射到 [0, 90]，保证全命中 ≥ 60
    score = int(round(ratio * 90))
    is_correct = score >= 60
    feedback = (f"关键词命中 {hit}/{len(keys)}。"
                f"参考要点：{key}")
    return {"score": score, "is_correct": is_correct, "feedback": feedback}
