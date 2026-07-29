"""测试种子辅助函数（非 test_*.py，不会被 pytest 收集执行）。"""


def make_company(conn, name: str) -> int:
    cur = conn.execute("INSERT INTO companies (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def make_user(
    conn, username, role, company_id=1, master_id=None,
    status="approved", full_name=None, department=None,
) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, company_id, master_id, status, full_name, department) "
        "VALUES (?, 'hash', ?, ?, ?, ?, ?, ?)",
        (username, role, company_id, master_id, status, full_name, department),
    )
    conn.commit()
    return cur.lastrowid


def make_course(conn, company_id, title, type="document", created_by=None) -> int:
    cur = conn.execute(
        "INSERT INTO courses (company_id, title, type, content, created_by) VALUES (?, ?, ?, '', ?)",
        (company_id, title, type, created_by),
    )
    conn.commit()
    return cur.lastrowid


def make_plan(conn, apprentice_id, master_id, company_id=1, name="培养计划") -> int:
    cur = conn.execute(
        "INSERT INTO plans (apprentice_id, master_id, company_id, name) VALUES (?, ?, ?, ?)",
        (apprentice_id, master_id, company_id, name),
    )
    conn.commit()
    return cur.lastrowid


def make_plan_item(conn, plan_id, course_id, company_id=1, order_no=0) -> int:
    cur = conn.execute(
        "INSERT INTO plan_items (plan_id, course_id, company_id, order_no) VALUES (?, ?, ?, ?)",
        (plan_id, course_id, company_id, order_no),
    )
    conn.commit()
    return cur.lastrowid


def insert_quiz(conn, apprentice_id, plan_item_id, status="pending_review",
                ai_score=60, master_score=None, answer="x") -> int:
    cur = conn.execute(
        "INSERT INTO quizzes (apprentice_id, plan_item_id, attempt, answer, ai_score, master_score, status) "
        "VALUES (?, ?, 1, ?, ?, ?, ?)",
        (apprentice_id, plan_item_id, answer, ai_score, master_score, status),
    )
    conn.commit()
    return cur.lastrowid


def insert_daily_progress(conn, apprentice_id, plan_item_id=None, company_id=1,
                         judged_at="2024-01-01 00:00:00", judged_by=1) -> None:
    conn.execute(
        "INSERT INTO daily_progress (apprentice_id, plan_item_id, master_judged, judged_by, judged_at, company_id) "
        "VALUES (?, ?, 1, ?, ?, ?)",
        (apprentice_id, plan_item_id, judged_by, judged_at, company_id),
    )
    conn.commit()
