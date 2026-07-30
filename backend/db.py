"""SQLite 数据库初始化与连接管理 — V2 多租户 SaaS 地基。"""
import sqlite3
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    import os as _os
    DATA_DIR = Path(_os.getenv('APPDATA', str(Path.home()))) / 'TSForce_MentorAI'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "mentor.db"
else:
    DB_PATH = Path(__file__).resolve().parent / "data" / "mentor.db"


def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys=OFF")  # 建表期间关闭外键

    # 预置公司
    conn.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    if not conn.execute("SELECT id FROM companies WHERE id=1").fetchone():
        conn.execute("INSERT INTO companies (id, name) VALUES (1, 'ThunderSoft')")

    # 备份旧用户数据
    old_users = _backup_old_users(conn)

    # 删除依赖 users 的旧表
    for t in ['users', 'knowledge_bases', 'kb_documents', 'kb_sources',
              'dimensions', 'knowledge_points', 'assessments', 'assessment_questions',
              'assessment_answers', 'mastery', 'study_plans', 'plan_days', 'plan_tasks',
              'daily_reviews', 'review_questions', 'chat_history', 'vector_chunks',
              'departments', 'courses', 'plans', 'plan_items', 'quizzes',
              'daily_progress', 'company_posts', 'post_comments', 'post_likes',
              'post_attachments', 'notifications', 'admin_logs', 'password_resets',
              'login_attempts']:
        conn.execute(f"DROP TABLE IF EXISTS {t}")

    # === 用户表（V2 完整） ===
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','master','apprentice')),
        master_id INTEGER,
        employee_no TEXT,
        phone TEXT,
        office_account TEXT,
        full_name TEXT,
        company_id INTEGER DEFAULT 1,
        department TEXT,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
        approved_by INTEGER,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # 恢复旧用户
    _restore_old_users(conn, old_users)

    # === 知识库 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_bases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        master_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL DEFAULT '默认知识库',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS kb_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kb_id INTEGER NOT NULL,
        filename TEXT NOT NULL, raw_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS kb_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kb_id INTEGER NOT NULL,
        source_type TEXT NOT NULL CHECK(source_type IN ('file','url')),
        location TEXT NOT NULL, title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS dimensions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kb_id INTEGER NOT NULL,
        name TEXT NOT NULL, description TEXT, sort_order INTEGER DEFAULT 0)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dimension_id INTEGER NOT NULL,
        title TEXT NOT NULL, content TEXT, source_ref TEXT,
        level TEXT DEFAULT '了解')""")

    conn.execute("""CREATE TABLE IF NOT EXISTS vector_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kb_id INTEGER NOT NULL,
        text TEXT NOT NULL, embedding BLOB, meta TEXT)""")

    # === 评估 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        kb_id INTEGER NOT NULL, status TEXT DEFAULT 'in_progress',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS assessment_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL,
        dimension_id INTEGER, question TEXT NOT NULL,
        qtype TEXT NOT NULL CHECK(qtype IN ('choice','short')),
        difficulty TEXT NOT NULL CHECK(difficulty IN ('易','中','难')),
        answer_key TEXT, options TEXT)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS assessment_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL, apprentice_answer TEXT,
        score REAL DEFAULT 0, feedback TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS mastery (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        dimension_id INTEGER NOT NULL,
        level TEXT NOT NULL CHECK(level IN ('未掌握','了解','熟练')),
        score REAL DEFAULT 0, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(apprentice_id, dimension_id))""")

    # === V1 学习计划 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS study_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        kb_id INTEGER NOT NULL, status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS plan_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
        day_index INTEGER NOT NULL, date TEXT, locked INTEGER DEFAULT 0,
        note TEXT)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS plan_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, day_id INTEGER NOT NULL,
        dimension_id INTEGER, title TEXT NOT NULL,
        task_type TEXT NOT NULL CHECK(task_type IN ('阅读','练习','复习')),
        content_ref TEXT, duration_min INTEGER DEFAULT 30,
        sort_order INTEGER DEFAULT 0)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS daily_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        plan_day_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS review_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, review_id INTEGER NOT NULL,
        question TEXT NOT NULL, qtype TEXT NOT NULL CHECK(qtype IN ('choice','short')),
        answer_key TEXT, apprentice_answer TEXT,
        score REAL DEFAULT 0, feedback TEXT)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        kb_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 部门 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL)""")

    # === V2 课程库 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL DEFAULT 1,
        title TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'document',
        content TEXT, created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 培养计划 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        master_id INTEGER NOT NULL, company_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL, company_id INTEGER NOT NULL DEFAULT 1,
        order_no INTEGER DEFAULT 0, required INTEGER DEFAULT 1,
        done INTEGER DEFAULT 0)""")

    # === V2 今日任务检测 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        plan_item_id INTEGER, attempt INTEGER DEFAULT 1, answer TEXT,
        ai_score REAL DEFAULT 0, master_score REAL,
        status TEXT DEFAULT 'pending_review',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 每日进度判定 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT, apprentice_id INTEGER NOT NULL,
        plan_item_id INTEGER, master_judged INTEGER DEFAULT 0,
        judged_by INTEGER, judged_at TIMESTAMP,
        company_id INTEGER NOT NULL DEFAULT 1)""")

    # === V2 交流圈 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS company_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL DEFAULT 1,
        author_id INTEGER NOT NULL, author_name TEXT, author_role TEXT,
        content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS post_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL, content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS post_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(post_id, user_id))""")

    conn.execute("""CREATE TABLE IF NOT EXISTS post_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL,
        file_name TEXT, url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 通知 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL DEFAULT 1,
        type TEXT NOT NULL, content TEXT, ref_id INTEGER,
        read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 管理员日志 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER NOT NULL,
        action TEXT NOT NULL, target_type TEXT, target_id INTEGER,
        detail TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # === V2 密码重置 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        token TEXT NOT NULL, expiry TIMESTAMP NOT NULL, used INTEGER DEFAULT 0)""")

    # === V2 登录失败记录 ===
    conn.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, success INTEGER DEFAULT 0)""")

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return conn


def _backup_old_users(conn):
    """备份旧 users 表数据"""
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
        rows = conn.execute("SELECT * FROM users").fetchall()
        return [dict(r) for r in rows]
    return []


def _restore_old_users(conn, old_users):
    """将旧用户数据恢复到新表"""
    for u in old_users:
        try:
            conn.execute(
                """INSERT INTO users (id, username, password_hash, role, master_id, company_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, COALESCE(?, 1), 'approved', ?)""",
                (u['id'], u['username'], u['password_hash'], u['role'],
                 u.get('master_id'), u.get('company_id', 1), u.get('created_at')))
        except:
            pass
