"""FastAPI 主应用：路由 + 前端托管。"""
import json
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import io

from backend.config import settings
from backend.db import init_db, get_conn
from backend.auth import (register, login, logout, get_user, require_master, require_apprentice,
                            require_admin, get_my_apprentices, get_same_master_apprentices,
                            list_companies, get_company_masters, get_pending_users, set_user_status,
                            get_company_users, assign_master, create_post, get_posts,
                            get_apprentice_stats)
from backend.schemas import (LoginReq, RegisterReq, CreateApprenticeReq, IngestPathReq, IngestUrlReq,
                             PlanGenerateReq, AssessmentAnswerReq, ChatReq, CompanyPostReq, AssignMasterReq)
from backend.vectorstore import VectorStore
from backend.ingest import ingest_local_path, ingest_urls, get_or_create_kb
from backend.agents.refiner import refine
from backend.agents.assessor import generate_assessment, grade_answer, get_assessment_result, get_mistakes
from backend.agents.planner import generate_plan, get_plan, update_plan_day, update_plan_task
from backend.agents.tutor import ask, generate_lecture_content
from backend.agents.reviewer import generate_review, grade_review_answer
from backend.pdf_gen import generate_today_pdf

app = FastAPI(title="薪火·师傅带徒 AI 导师系统", version="1.0.0")

# 全局向量库实例
_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore.load(settings.STORE_PATH)
    return _store


# ---------- 启动初始化 ----------
@app.on_event("startup")
def startup():
    init_db()
    conn = get_conn()
    # 预置示例公司
    if not conn.execute("SELECT id FROM companies WHERE id=1").fetchone():
        conn.execute("INSERT INTO companies (id, name) VALUES (1, '示例公司（Demo）')")
        conn.commit()
    # 预置公司管理员
    if not conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone():
        from backend.auth import hash_password
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, company_id, status) "
            "VALUES (?, ?, 'admin', '系统管理员', 1, 'approved')",
            ("admin", hash_password("admin123")),
        )
        conn.commit()
    # 预置示例师傅
    if not conn.execute("SELECT id FROM users WHERE role='master' LIMIT 1").fetchone():
        from backend.auth import hash_password
        conn.execute(
            "INSERT INTO users (username, password_hash, role, company_id, status) "
            "VALUES (?, ?, 'master', 1, 'approved')",
            ("demo_master", hash_password("123456")),
        )
        conn.commit()
    # 已有账号统一归入示例公司
    conn.execute("UPDATE users SET company_id=1 WHERE company_id IS NULL")
    conn.commit()
    print("薪火系统启动完成 -> http://localhost:8000")


# ---------- 鉴权依赖 ----------
def auth_user(request: Request) -> dict:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        # 尝试从 cookie 获取
        token = request.cookies.get("token", "")
    user = get_user(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


# ---------- 前端托管 ----------
@app.get("/", response_class=HTMLResponse)
def index():
    html_path = settings.FRONTEND_HTML
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>前端文件未找到，请确保 frontend/index.html 存在</h1>"


# ---------- 认证 ----------
@app.post("/api/register")
def api_register(req: RegisterReq):
    if req.role == "apprentice":
        return {"success": False, "message": "徒弟账号需由师傅创建"}
    return register(req.username, req.password, req.role)


@app.post("/api/login")
def api_login(req: LoginReq):
    return login(req.username, req.password)


@app.post("/api/logout")
def api_logout(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("token", "")
    logout(token)
    return {"success": True, "message": "已退出"}


@app.get("/api/me")
def api_me(user: dict = Depends(auth_user)):
    return {"success": True, "user": user}


# ---------- 师傅 API ----------
@app.post("/api/master/apprentices")
def api_create_apprentice(req: CreateApprenticeReq, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    return register(req.username, req.password, "apprentice", master_id=user["user_id"])


@app.get("/api/master/apprentices")
def api_list_apprentices(user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    return {"success": True, "apprentices": get_my_apprentices(user["user_id"])}


@app.post("/api/master/ingest")
def api_ingest_path(req: IngestPathReq, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    kb = get_or_create_kb(user["user_id"])
    store = get_store()
    return ingest_local_path(user["user_id"], kb["id"], req.path, store)


@app.post("/api/master/ingest/url")
def api_ingest_url(req: IngestUrlReq, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    kb = get_or_create_kb(user["user_id"])
    store = get_store()
    return ingest_urls(user["user_id"], kb["id"], req.urls, store)


@app.post("/api/master/refine")
def api_refine(user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    kb = get_or_create_kb(user["user_id"])
    result = refine(kb["id"])
    # 精炼后自动触发自净化（异步，不影响返回）
    if result.get("success"):
        import threading
        def _auto_purify():
            try:
                from backend.self_purifier import run_purification
                run_purification(kb["id"])
            except: pass
        threading.Thread(target=_auto_purify, daemon=True).start()
    return result


@app.get("/api/master/knowledge")
def api_get_knowledge(user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    kb = get_or_create_kb(user["user_id"])
    conn = get_conn()
    dims = conn.execute(
        "SELECT * FROM dimensions WHERE kb_id=? ORDER BY sort_order",
        (kb["id"],),
    ).fetchall()
    dims_data = []
    for d in dims:
        pts = conn.execute(
            "SELECT * FROM knowledge_points WHERE dimension_id=? ORDER BY level",
            (d["id"],),
        ).fetchall()
        dims_data.append({**dict(d), "points": [dict(p) for p in pts]})
    return {"success": True, "kb_id": kb["id"], "dimensions": dims_data}


@app.post("/api/master/plan/generate")
def api_generate_plan(req: PlanGenerateReq, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    kb = get_or_create_kb(user["user_id"])
    return generate_plan(req.apprentice_id, kb["id"])


@app.get("/api/master/plan/{apprentice_id}")
def api_get_plan(apprentice_id: int, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    return get_plan(apprentice_id)


@app.put("/api/master/plan/day/{day_id}")
def api_update_plan_day(day_id: int, data: dict, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    return update_plan_day(day_id, data.get("note"), data.get("locked"))


@app.put("/api/master/plan/task/{task_id}")
def api_update_plan_task(task_id: int, data: dict, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    return update_plan_task(task_id, data)


@app.get("/api/master/dashboard/{apprentice_id}")
def api_dashboard(apprentice_id: int, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    # 掌握等级
    mastery = conn.execute(
        "SELECT m.*, d.name as dim_name FROM mastery m JOIN dimensions d ON m.dimension_id = d.id WHERE m.apprentice_id=?",
        (apprentice_id,),
    ).fetchall()
    # 评估记录
    assessments = conn.execute(
        "SELECT * FROM assessments WHERE apprentice_id=? ORDER BY created_at DESC",
        (apprentice_id,),
    ).fetchall()
    # 复习记录
    reviews = conn.execute(
        "SELECT dr.*, COUNT(rq.id) as q_count, AVG(rq.score) as avg_score FROM daily_reviews dr LEFT JOIN review_questions rq ON dr.id = rq.review_id WHERE dr.apprentice_id=? GROUP BY dr.id ORDER BY dr.created_at DESC",
        (apprentice_id,),
    ).fetchall()
    return {
        "success": True,
        "apprentice_id": apprentice_id,
        "mastery": [dict(m) for m in mastery],
        "assessments": [dict(a) for a in assessments],
        "reviews": [dict(r) for r in reviews],
    }


# ---------- 徒弟 API ----------
@app.post("/api/apprentice/assessment/start")
def api_start_assessment(user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    kb = get_or_create_kb(user["master_id"])
    return generate_assessment(user["user_id"], kb["id"])


@app.post("/api/apprentice/assessment/answer")
def api_answer_assessment(req: AssessmentAnswerReq, user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    conn = get_conn()
    # 找到该题目所属的测评
    qrow = conn.execute(
        "SELECT assessment_id FROM assessment_questions WHERE id=?", (req.question_id,)
    ).fetchone()
    if not qrow:
        raise HTTPException(status_code=404, detail="题目不存在")
    return grade_answer(req.question_id, req.answer, qrow["assessment_id"])


@app.get("/api/apprentice/assessment/result/{assessment_id}")
def api_assessment_result(assessment_id: int, user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    return get_assessment_result(assessment_id)


@app.get("/api/apprentice/plan/today")
def api_today_plan(user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    result = get_plan(user["user_id"])
    if not result.get("success"):
        return result
    # 返回当日计划
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    today_day = next((d for d in result["days"] if d.get("date", "").startswith(today)), None)
    if not today_day and result["days"]:
        today_day = result["days"][0]  # 返回第一天
    return {"success": True, "today": today_day, "all_days": result["days"]}


@app.get("/api/apprentice/pdf/today")
def api_today_pdf(user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    result = get_plan(user["user_id"])
    if not result.get("success"):
        return StreamingResponse(io.BytesIO(b"No plan"), media_type="application/pdf")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    today_day = next((d for d in result["days"] if d.get("date", "").startswith(today)), None)
    if not today_day and result["days"]:
        today_day = result["days"][0]
    if not today_day:
        return StreamingResponse(io.BytesIO(b"No plan day"), media_type="application/pdf")

    store = get_store()
    pdf_bytes = generate_today_pdf(user["user_id"], today_day["id"], store)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                           headers={"Content-Disposition": "attachment; filename=lecture.pdf"})


@app.post("/api/apprentice/review/start")
def api_start_review(data: dict, user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    plan_day_id = data.get("plan_day_id")
    if not plan_day_id:
        return {"success": False, "message": "缺少 plan_day_id"}
    return generate_review(user["user_id"], plan_day_id)


@app.post("/api/apprentice/review/answer")
def api_review_answer(data: dict, user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    return grade_review_answer(data["question_id"], data["answer"], data["review_id"])


@app.get("/api/apprentice/mistakes")
def api_mistakes(user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    return get_mistakes(user["user_id"])


@app.post("/api/apprentice/ask")
def api_ask(req: ChatReq, user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    kb = get_or_create_kb(user["master_id"])
    store = get_store()
    return ask(user["user_id"], kb["id"], req.question, store)


@app.get("/api/apprentice/leaderboard")
def api_leaderboard(user: dict = Depends(auth_user)):
    """同门战况/排行榜。"""
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")

    conn = get_conn()
    # 获取同门所有徒弟
    me = conn.execute("SELECT master_id FROM users WHERE id=?", (user["user_id"],)).fetchone()
    if not me or not me["master_id"]:
        return {"success": False, "message": "未绑定师傅"}

    apprentices = conn.execute(
        "SELECT id, username FROM users WHERE role='apprentice' AND master_id=?",
        (me["master_id"],),
    ).fetchall()

    leaderboard = []
    for a in apprentices:
        # 累计评分
        assess_avg = conn.execute(
            "SELECT AVG(aa.score) as avg FROM assessment_answers aa JOIN assessments a2 ON aa.assessment_id = a2.id WHERE a2.apprentice_id=?",
            (a["id"],),
        ).fetchone()
        review_avg = conn.execute(
            "SELECT AVG(rq.score) as avg FROM review_questions rq JOIN daily_reviews dr ON rq.review_id = dr.id WHERE dr.apprentice_id=?",
            (a["id"],),
        ).fetchone()
        avg_score = (assess_avg["avg"] or 0) * 0.5 + (review_avg["avg"] or 0) * 0.5

        # 掌握维度数
        mastery_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM mastery WHERE apprentice_id=? AND level='熟练'",
            (a["id"],),
        ).fetchone()

        # 错题数
        mistake_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM assessment_answers WHERE assessment_id IN (SELECT id FROM assessments WHERE apprentice_id=?) AND score < 60",
            (a["id"],),
        ).fetchone()

        leaderboard.append({
            "apprentice_id": a["id"],
            "username": a["username"],
            "avg_score": round(avg_score, 1),
            "mastery_count": mastery_count["cnt"] or 0,
            "mistake_count": mistake_count["cnt"] or 0,
        })

    leaderboard.sort(key=lambda x: x["avg_score"], reverse=True)

    return {
        "success": True,
        "leaderboard": leaderboard,
        "my_id": user["user_id"],
    }


# ==================== V2：课程库（管理员维护） ====================
from backend.auth import require_admin

@app.get("/api/admin/courses")
def api_list_courses(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM courses WHERE company_id=? ORDER BY id DESC",
        (user["company_id"],)
    ).fetchall()
    return {"success": True, "courses": [dict(r) for r in rows]}


@app.post("/api/admin/courses")
def api_create_course(data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO courses (company_id, title, type, content, created_by) VALUES (?, ?, ?, ?, ?)",
        (user["company_id"], data.get("title", ""), data.get("type", "document"),
         data.get("content", ""), user["user_id"])
    )
    conn.commit()
    row = conn.execute("SELECT * FROM courses WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"success": True, "course": dict(row), "message": "课程已创建"}


@app.put("/api/admin/courses/{course_id}")
def api_update_course(course_id: int, data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    fields, vals = [], []
    for k in ["title", "type", "content"]:
        if k in data and data[k] is not None:
            fields.append(f"{k}=?")
            vals.append(data[k])
    if fields:
        vals.append(course_id)
        conn.execute(f"UPDATE courses SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
    return {"success": True, "message": "课程已更新"}


@app.delete("/api/admin/courses/{course_id}")
def api_delete_course(course_id: int, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    conn.execute("DELETE FROM plan_items WHERE course_id=?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    return {"success": True, "message": "课程已删除"}


# ==================== V2：培养计划（师傅定制） ====================
@app.post("/api/master/plans")
def api_create_plan(data: dict, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO plans (apprentice_id, master_id, company_id, name) VALUES (?, ?, ?, ?)",
        (data["apprentice_id"], user["user_id"], user["company_id"], data.get("name", "培养计划"))
    )
    plan_id = cur.lastrowid
    course_ids = data.get("course_ids", [])
    for i, cid in enumerate(course_ids):
        conn.execute(
            "INSERT INTO plan_items (plan_id, course_id, company_id, order_no) VALUES (?, ?, ?, ?)",
            (plan_id, cid, user["company_id"], i)
        )
    conn.commit()
    row = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    items = conn.execute(
        "SELECT pi.*, c.title as course_title, c.type as course_type FROM plan_items pi "
        "JOIN courses c ON pi.course_id = c.id WHERE pi.plan_id=? ORDER BY pi.order_no",
        (plan_id,)
    ).fetchall()
    return {"success": True, "plan": dict(row), "items": [dict(it) for it in items], "message": "计划已创建"}


@app.get("/api/master/plans")
def api_list_plans(user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.*, u.full_name as apprentice_name FROM plans p "
        "JOIN users u ON p.apprentice_id = u.id "
        "WHERE p.master_id=? ORDER BY p.id DESC",
        (user["user_id"],)
    ).fetchall()
    return {"success": True, "plans": [dict(r) for r in rows]}


@app.get("/api/master/plans/{plan_id}")
def api_plan_detail(plan_id: int, user: dict = Depends(auth_user)):
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    plan = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        return {"success": False, "message": "计划不存在"}
    items = conn.execute(
        "SELECT pi.*, c.title as course_title, c.type as course_type FROM plan_items pi "
        "JOIN courses c ON pi.course_id = c.id WHERE pi.plan_id=? ORDER BY pi.order_no",
        (plan_id,)
    ).fetchall()
    return {"success": True, "plan": dict(plan), "items": [dict(it) for it in items]}


@app.get("/api/apprentice/plans")
def api_apprentice_plans(user: dict = Depends(auth_user)):
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.* FROM plans p WHERE p.apprentice_id=? ORDER BY p.id DESC",
        (user["user_id"],)
    ).fetchall()
    plans = []
    for p in rows:
        items = conn.execute(
            "SELECT pi.*, c.title as course_title, c.type as course_type FROM plan_items pi "
            "JOIN courses c ON pi.course_id = c.id WHERE pi.plan_id=? ORDER BY pi.order_no",
            (p["id"],)
        ).fetchall()
        plans.append({**dict(p), "items": [dict(it) for it in items]})
    return {"success": True, "plans": plans}


# ==================== V2：今日任务检测（Quiz） ====================
@app.post("/api/apprentice/quiz/submit")
def api_submit_quiz(data: dict, user: dict = Depends(auth_user)):
    """徒弟提交检测，AI初评。可反复提交（attempt递增）。"""
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    conn = get_conn()
    item = conn.execute("SELECT pi.*, p.apprentice_id FROM plan_items pi JOIN plans p ON pi.plan_id=p.id WHERE pi.id=? AND p.apprentice_id=?",
                        (data["plan_item_id"], user["user_id"])).fetchone()
    if not item:
        return {"success": False, "message": "无此学习任务"}
    # attempt递增
    last = conn.execute("SELECT MAX(attempt) as m FROM quizzes WHERE apprentice_id=? AND plan_item_id=?",
                        (user["user_id"], data["plan_item_id"])).fetchone()
    attempt = (last["m"] or 0) + 1
    # AI评分（简化：根据答案长度打分；实际应调LLM）
    answer = data.get("answer", "")
    ai_score = min(100, max(10, len(answer) * 2 if answer else 0))
    cur = conn.execute(
        "INSERT INTO quizzes (apprentice_id, plan_item_id, attempt, answer, ai_score, status) VALUES (?, ?, ?, ?, ?, 'pending_review')",
        (user["user_id"], data["plan_item_id"], attempt, answer, ai_score))
    conn.commit()
    return {"success": True, "quiz_id": cur.lastrowid, "attempt": attempt, "ai_score": ai_score,
            "message": "检测已提交，AI初评完成，等待师傅终评"}


@app.get("/api/apprentice/quizzes")
def api_apprentice_quizzes(user: dict = Depends(auth_user)):
    """徒弟查看自己的检测记录"""
    if not require_apprentice(user):
        raise HTTPException(status_code=403, detail="仅徒弟可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT q.*, pi.course_id, c.title as course_title FROM quizzes q "
        "LEFT JOIN plan_items pi ON q.plan_item_id = pi.id "
        "LEFT JOIN courses c ON pi.course_id = c.id "
        "WHERE q.apprentice_id=? ORDER BY q.submitted_at DESC",
        (user["user_id"],)).fetchall()
    return {"success": True, "quizzes": [dict(r) for r in rows]}


@app.get("/api/master/apprentice/{apprentice_id}/quizzes")
def api_master_view_quizzes(apprentice_id: int, user: dict = Depends(auth_user)):
    """师傅查看某徒弟的检测记录"""
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    # 确认是该师傅的徒弟
    me = conn.execute("SELECT id FROM users WHERE id=? AND master_id=?", (apprentice_id, user["user_id"])).fetchone()
    if not me:
        raise HTTPException(status_code=403, detail="不是您的徒弟")
    rows = conn.execute(
        "SELECT * FROM quizzes WHERE apprentice_id=? ORDER BY submitted_at DESC", (apprentice_id,)).fetchall()
    return {"success": True, "quizzes": [dict(r) for r in rows]}


@app.post("/api/master/quizzes/{quiz_id}/score")
def api_master_score_quiz(quiz_id: int, data: dict, user: dict = Depends(auth_user)):
    """师傅修改检测评分（终评）"""
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
    if not quiz:
        return {"success": False, "message": "检测不存在"}
    new_status = data.get("status", "passed")
    conn.execute("UPDATE quizzes SET master_score=?, status=? WHERE id=?",
                 (data["master_score"], new_status, quiz_id))
    conn.commit()
    return {"success": True, "message": "评分已更新"}


# ==================== V2：每日进度判定 ====================
@app.post("/api/master/daily-progress")
def api_judge_daily_progress(data: dict, user: dict = Depends(auth_user)):
    """师傅判定徒弟当日任务完成"""
    if not require_master(user):
        raise HTTPException(status_code=403, detail="仅师傅可操作")
    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_progress (apprentice_id, plan_item_id, master_judged, judged_by, judged_at, company_id) "
        "VALUES (?, ?, 1, ?, datetime('now'), ?)",
        (data["apprentice_id"], data.get("plan_item_id"), user["user_id"], user["company_id"]))
    conn.commit()
    return {"success": True, "message": "进度已判定"}


@app.get("/api/master/daily-progress/{apprentice_id}")
def api_get_daily_progress(apprentice_id: int, user: dict = Depends(auth_user)):
    """查看某个徒弟的每日进度"""
    if not require_master(user) and not require_admin(user):
        raise HTTPException(status_code=403, detail="仅师傅/管理员可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT dp.*, pi.course_id, c.title as course_title FROM daily_progress dp "
        "LEFT JOIN plan_items pi ON dp.plan_item_id = pi.id "
        "LEFT JOIN courses c ON pi.course_id = c.id "
        "WHERE dp.apprentice_id=? ORDER BY dp.judged_at DESC",
        (apprentice_id,)).fetchall()
    return {"success": True, "progress": [dict(r) for r in rows]}


# ==================== V2：三层次进度视图 ====================
def _build_progress_rows(conn, apprentices: list, company_id: int):
    """通用：构建带排名的新人进度列表"""
    rows = []
    for a in apprentices:
        total = conn.execute("SELECT COUNT(*) as c FROM plan_items pi JOIN plans p ON pi.plan_id=p.id WHERE p.apprentice_id=?",
                             (a["id"],)).fetchone()["c"]
        done = conn.execute(
            "SELECT COUNT(DISTINCT q.plan_item_id) as c FROM quizzes q "
            "WHERE q.apprentice_id=? AND (q.status='passed' OR q.master_score IS NOT NULL)",
            (a["id"],)).fetchone()["c"]
        avg = conn.execute("SELECT AVG(COALESCE(master_score, ai_score)) as a FROM quizzes WHERE apprentice_id=?",
                           (a["id"],)).fetchone()["a"]
        progress_pct = round(done / total * 100, 1) if total > 0 else 0
        rows.append({
            "apprentice_id": a["id"], "apprentice_name": a["full_name"] or a["username"],
            "employee_no": a["employee_no"], "master_id": a.get("master_id"),
            "master_name": a.get("master_name", "-"),
            "total_items": total, "done_items": done,
            "progress_pct": progress_pct, "avg_score": round(avg or 0, 1)
        })
    rows.sort(key=lambda x: (x["progress_pct"], x["avg_score"]), reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


@app.get("/api/progress/company")
def api_progress_company(user: dict = Depends(auth_user)):
    """公司新人培养进度（全部徒弟+师傅+排名）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND company_id=? AND status='approved'",
        (user["company_id"],)).fetchall()
    apps = []
    for r in rows:
        d = dict(r)
        m = conn.execute("SELECT full_name, username FROM users WHERE id=?", (d["master_id"],)).fetchone() if d["master_id"] else None
        d["master_name"] = (m["full_name"] or m["username"]) if m else "-"
        apps.append(d)
    return {"success": True, "company_id": user["company_id"],
            "apprentices": _build_progress_rows(conn, apps, user["company_id"])}


@app.get("/api/progress/department")
def api_progress_department(user: dict = Depends(auth_user)):
    """部门新人培养进度"""
    conn = get_conn()
    dept = conn.execute("SELECT department FROM users WHERE id=?", (user["user_id"],)).fetchone()
    if not dept or not dept["department"]:
        return {"success": False, "message": "未设置部门"}
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND company_id=? AND department=? AND status='approved'",
        (user["company_id"], dept["department"])).fetchall()
    apps = []
    for r in rows:
        d = dict(r)
        m = conn.execute("SELECT full_name, username FROM users WHERE id=?", (d["master_id"],)).fetchone() if d["master_id"] else None
        d["master_name"] = (m["full_name"] or m["username"]) if m else "-"
        apps.append(d)
    return {"success": True, "department": dept["department"],
            "apprentices": _build_progress_rows(conn, apps, user["company_id"])}


@app.get("/api/progress/same-master")
def api_progress_same_master(user: dict = Depends(auth_user)):
    """同门新人培养进度"""
    conn = get_conn()
    master_id = user.get("master_id") if user["role"] == "apprentice" else user["user_id"]
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no, master_id FROM users "
        "WHERE role='apprentice' AND master_id=? AND status='approved'",
        (master_id,)).fetchall()
    apps = [dict(r) for r in rows]
    for d in apps:
        d["master_name"] = user.get("full_name") or user.get("username") if user["role"] == "master" else (
            conn.execute("SELECT full_name FROM users WHERE id=?", (master_id,)).fetchone()["full_name"] or ""
        )
    return {"success": True, "master_id": master_id,
            "apprentices": _build_progress_rows(conn, apps, user["company_id"])}


# ==================== V2：交流圈 ====================
@app.post("/api/posts")
def api_create_post(data: dict, user: dict = Depends(auth_user)):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO company_posts (company_id, author_id, author_name, author_role, content) VALUES (?, ?, ?, ?, ?)",
        (user["company_id"], user["user_id"], data.get("author_name", user.get("full_name", user["username"])),
         user["role"], data["content"]))
    conn.commit()
    return {"success": True, "post_id": cur.lastrowid}


@app.get("/api/posts")
def api_get_posts(user: dict = Depends(auth_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM company_posts WHERE company_id=? ORDER BY id DESC LIMIT 200", (user["company_id"],)).fetchall()
    posts = []
    for r in rows:
        d = dict(r)
        d["comments_count"] = conn.execute("SELECT COUNT(*) FROM post_comments WHERE post_id=?", (r["id"],)).fetchone()[0]
        d["likes_count"] = conn.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (r["id"],)).fetchone()[0]
        d["liked_by_me"] = bool(conn.execute("SELECT id FROM post_likes WHERE post_id=? AND user_id=?",
                                             (r["id"], user["user_id"])).fetchone())
        posts.append(d)
    return {"success": True, "posts": posts}


@app.post("/api/posts/{post_id}/comments")
def api_add_comment(post_id: int, data: dict, user: dict = Depends(auth_user)):
    conn = get_conn()
    conn.execute("INSERT INTO post_comments (post_id, author_id, content) VALUES (?, ?, ?)",
                 (post_id, user["user_id"], data["content"]))
    conn.commit()
    return {"success": True, "message": "评论成功"}


@app.get("/api/posts/{post_id}/comments")
def api_get_comments(post_id: int, user: dict = Depends(auth_user)):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM post_comments WHERE post_id=? ORDER BY id", (post_id,)).fetchall()
    return {"success": True, "comments": [dict(r) for r in rows]}


@app.post("/api/posts/{post_id}/like")
def api_toggle_like(post_id: int, user: dict = Depends(auth_user)):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user["user_id"])).fetchone()
    if existing:
        conn.execute("DELETE FROM post_likes WHERE id=?", (existing["id"],))
        conn.commit()
        return {"success": True, "liked": False}
    conn.execute("INSERT OR IGNORE INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, user["user_id"]))
    conn.commit()
    return {"success": True, "liked": True}


# ==================== V2：通知系统 ====================
@app.get("/api/notifications")
def api_notifications(user: dict = Depends(auth_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND company_id=? ORDER BY id DESC LIMIT 100",
        (user["user_id"], user["company_id"])).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user["user_id"],)).fetchone()[0]
    return {"success": True, "notifications": [dict(r) for r in rows], "unread_count": unread}


@app.post("/api/notifications/read")
def api_read_notification(data: dict, user: dict = Depends(auth_user)):
    conn = get_conn()
    nid = data.get("id")
    if nid:
        conn.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (nid, user["user_id"]))
    else:
        conn.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user["user_id"],))
    conn.commit()
    return {"success": True}


def _notify(conn, user_id: int, ntype: str, content: str, ref_id: int = None, company_id: int = 1):
    conn.execute("INSERT INTO notifications (user_id, type, content, ref_id, company_id) VALUES (?,?,?,?,?)",
                 (user_id, ntype, content, ref_id, company_id))


# ==================== V2：管理员后台 ====================
@app.get("/api/admin/pending")
def api_admin_pending(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, full_name, employee_no, phone, office_account, company_id, master_id, created_at "
        "FROM users WHERE status='pending' AND company_id=? ORDER BY created_at DESC",
        (user["company_id"],)).fetchall()
    return {"success": True, "pending": [dict(r) for r in rows]}


@app.post("/api/admin/approve")
def api_admin_approve(data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    conn.execute("UPDATE users SET status='approved', approved_by=?, approved_at=datetime('now') WHERE id=?",
                 (user["user_id"], data["user_id"]))
    conn.commit()
    return {"success": True, "message": "已通过审核"}


@app.post("/api/admin/reject")
def api_admin_reject(data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    conn.execute("UPDATE users SET status='rejected' WHERE id=?", (data["user_id"],))
    conn.commit()
    return {"success": True, "message": "已驳回"}


@app.get("/api/admin/users")
def api_admin_users(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from backend.auth import get_company_users
    return {"success": True, "users": get_company_users(user["company_id"])}


@app.post("/api/admin/rebind-master")
def api_admin_rebind(data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    conn.execute("UPDATE users SET master_id=? WHERE id=? AND role='apprentice'",
                 (data["master_id"], data["apprentice_id"]))
    conn.execute("INSERT INTO admin_logs (admin_id, action, target_type, target_id, detail) VALUES (?, 'rebind_master', 'user', ?, ?)",
                 (user["user_id"], data["apprentice_id"], f"->master {data['master_id']}"))
    conn.commit()
    return {"success": True, "message": "师徒关系已更新"}


@app.post("/api/admin/departments")
def api_admin_departments(data: dict, user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    if data.get("name") and not conn.execute("SELECT id FROM departments WHERE name=? AND company_id=?",
                                             (data["name"], user["company_id"])).fetchone():
        conn.execute("INSERT INTO departments (company_id, name) VALUES (?, ?)", (user["company_id"], data["name"]))
        conn.commit()
    rows = conn.execute("SELECT * FROM departments WHERE company_id=?", (user["company_id"],)).fetchall()
    return {"success": True, "departments": [dict(r) for r in rows]}


@app.get("/api/admin/departments")
def api_list_departments(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM departments WHERE company_id=?", (user["company_id"],)).fetchall()
    return {"success": True, "departments": [dict(r) for r in rows]}


@app.get("/api/admin/logs")
def api_admin_logs(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 200").fetchall()
    return {"success": True, "logs": [dict(r) for r in rows]}


@app.get("/api/admin/stats")
def api_admin_stats(user: dict = Depends(auth_user)):
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    conn = get_conn()
    total_apprentices = conn.execute("SELECT COUNT(*) FROM users WHERE role='apprentice' AND company_id=?",
                                     (user["company_id"],)).fetchone()[0]
    total_masters = conn.execute("SELECT COUNT(*) FROM users WHERE role='master' AND company_id=?",
                                 (user["company_id"],)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM users WHERE status='pending' AND company_id=?",
                           (user["company_id"],)).fetchone()[0]
    return {"success": True, "total_apprentices": total_apprentices, "total_masters": total_masters,
            "pending_review": pending}


# ==================== 公开API（无需登录） ====================
@app.get("/api/companies")
def api_companies():
    conn = get_conn()
    rows = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
    return {"success": True, "companies": [dict(r) for r in rows]}


@app.get("/api/companies/{company_id}/masters")
def api_company_masters(company_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, full_name, employee_no FROM users WHERE role='master' AND company_id=? AND status='approved'",
        (company_id,)).fetchall()
    return {"success": True, "masters": [dict(r) for r in rows]}


# ==================== V2：数据库自净化引擎 ====================
@app.post("/api/admin/purify")
def api_run_purification(data: dict = None, user: dict = Depends(auth_user)):
    """管理员触发知识库自净化"""
    if not require_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from backend.self_purifier import run_purification
    kb_id = data.get("kb_id") if data else None
    report = run_purification(kb_id)
    return {"success": True, "report": report}


@app.get("/api/admin/purify/report")
def api_purification_report(user: dict = Depends(auth_user)):
    """获取最近净化报告"""
    from backend.self_purifier import get_purification_report
    return get_purification_report()


@app.get("/api/admin/purify/stats")
def api_purification_stats(user: dict = Depends(auth_user)):
    """获取知识库健康统计"""
    from backend.self_purifier import get_purification_stats
    return get_purification_stats()
