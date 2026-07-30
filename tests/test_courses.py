"""courses 模块测试：课程 CRUD + company_id 隔离 + 检测题库模板引擎。"""
from backend.courses import (
    list_courses, create_course, update_course, delete_course,
    add_course_question, list_course_questions,
)
from helpers import make_company, make_course


def test_create_and_list_course(conn):
    r = create_course(1, "Python 入门", "document", "内容", created_by=1, conn=conn)
    assert r["success"] is True
    assert r["course"]["type"] == "document"
    out = list_courses(1, conn=conn)
    assert out["success"]
    assert len(out["courses"]) == 1
    assert out["courses"][0]["title"] == "Python 入门"


def test_invalid_type_rejected(conn):
    r = create_course(1, "坏类型", "ebook", conn=conn)
    assert r["success"] is False


def test_quiz_bank_template_engine(conn):
    cid = make_course(conn, 1, "检测题库A", "quiz_bank")
    q = add_course_question(cid, "什么是闭包？", "short", "函数+环境", conn=conn)
    assert q["success"]
    # 选择题带选项
    add_course_question(cid, "1+1=?", "choice", "2", options=["1", "2", "3"], conn=conn)
    lst = list_course_questions(cid, conn=conn)
    assert lst["success"]
    assert len(lst["questions"]) == 2
    opt_q = [x for x in lst["questions"] if x["qtype"] == "choice"][0]
    assert opt_q["options"] == ["1", "2", "3"]


def test_update_and_delete(conn):
    cid = make_course(conn, 1, "旧标题", "video")
    upd = update_course(cid, conn=conn, title="新标题", type="link")
    assert upd["success"]
    row = list_courses(1, conn=conn)["courses"][0]
    assert row["title"] == "新标题" and row["type"] == "link"
    # 删除后列表为空
    delete_course(cid, conn=conn)
    assert list_courses(1, conn=conn)["courses"] == []


def test_company_isolation(conn):
    make_company(conn, "B公司")
    make_course(conn, 1, "A公司课程")
    make_course(conn, 2, "B公司课程")
    a = list_courses(1, conn=conn)["courses"]
    b = list_courses(2, conn=conn)["courses"]
    assert len(a) == 1 and a[0]["title"] == "A公司课程"
    assert len(b) == 1 and b[0]["title"] == "B公司课程"
