"""Agent 智能体测试：TDD 覆盖 grade_quiz_answer + 现有 agent 回归测试。"""
import pytest
from unittest.mock import patch

import backend.db as dbmod
from backend.agents.assessor import grade_quiz_answer
from backend.llm import extract_json


# ---------- grade_quiz_answer 测试 ----------

def test_grade_quiz_answer_no_key_fallback(conn):
    """无 Key 时走兜底返回 {"score", "feedback"}，不抛异常。"""
    res = grade_quiz_answer(1, "示例作答内容", context="课程内容")
    assert isinstance(res, dict)
    assert "score" in res
    assert "feedback" in res
    assert isinstance(res["score"], int)
    assert isinstance(res["feedback"], str)


def test_grade_quiz_answer_empty_answer(conn):
    """空作答走兜底，不抛异常。"""
    res = grade_quiz_answer(1, "", context="课程内容")
    assert isinstance(res, dict)
    assert "score" in res
    assert res["score"] == 20  # 空答案默认 20


def test_grade_quiz_answer_normal(conn):
    """chat_json 返回合法 JSON 时正确解析。"""
    def mock_chat_json(system, user, **kwargs):
        return {"score": 85, "feedback": "回答准确，语言流畅。"}

    with patch("backend.agents.assessor.chat_json", mock_chat_json):
        with patch("backend.agents.assessor.use_mock", lambda: False):
            res = grade_quiz_answer(1, "这是一个正常的回答", context="课程内容")
            assert res["score"] == 85
            assert "回答准确" in res["feedback"]


def test_grade_quiz_answer_malformed_json(conn):
    """LLM 返回畸形 JSON 时走兜底，不抛异常。"""
    def mock_chat_json_bad(system, user, **kwargs):
        return {"bad": "data"}  # 缺 score

    with patch("backend.agents.assessor.chat_json", mock_chat_json_bad):
        res = grade_quiz_answer(1, "回答", context="课程内容")
        assert isinstance(res, dict)
        assert "score" in res
        assert "feedback" in res


def test_grade_quiz_answer_score_parsing_error(conn):
    """score 解析失败时走兜底。"""
    def mock_chat_json_bad(system, user, **kwargs):
        return {"score": "不是数字", "feedback": "评语"}

    with patch("backend.agents.assessor.chat_json", mock_chat_json_bad):
        res = grade_quiz_answer(1, "回答", context="课程内容")
        assert isinstance(res, dict)
        assert "score" in res


def test_grade_quiz_answer_with_context(conn):
    """传入 context 时直接使用，不查库。"""
    called = []

    def mock_chat_json(system, user, **kwargs):
        called.append(True)
        return {"score": 90, "feedback": "基于上下文评分"}

    with patch("backend.agents.assessor.chat_json", mock_chat_json):
        with patch("backend.agents.assessor.use_mock", lambda: False):
            res = grade_quiz_answer(1, "回答", context="自定义课程内容")
            assert res["score"] == 90
            assert len(called) == 1


# ---------- extract_json（llm.py 已有）鲁棒解析测试 ----------

def test_extract_json_with_fence():
    """带 ```json 围栏的输入正确解析。"""
    text = '```json\n{"score": 80, "feedback": "ok"}\n```'
    res = extract_json(text)
    assert res.get("score") == 80


def test_extract_json_without_fence():
    """无围栏纯 JSON 正确解析。"""
    text = '{"score": 75, "feedback": "fine"}'
    res = extract_json(text)
    assert res.get("score") == 75


def test_extract_json_with_extra_text():
    """JSON 前有多余文字，截取首个 { 到匹配括号。"""
    text = '前面有一些文字{"score": 70, "feedback": "还行"}后面也有一些'
    res = extract_json(text)
    assert res.get("score") == 70


def test_extract_json_nested_brackets():
    """嵌套括号场景正确解析。"""
    text = '{"data": {"nested": [1, 2, 3]}}'
    res = extract_json(text)
    assert res.get("data", {}).get("nested") == [1, 2, 3]


def test_extract_json_invalid():
    """完全无效输入返回空 dict。"""
    assert extract_json(None) == {}
    assert extract_json("") == {}
    assert extract_json("不是 JSON") == {}


# ---------- 现有 agent 签名回归测试 ----------

def test_assessor_exports(conn):
    """assessor 现有 4 个函数签名未被破坏。"""
    from backend.agents import assessor
    assert callable(assessor.generate_assessment)
    assert callable(assessor.grade_answer)
    assert callable(assessor.get_assessment_result)
    assert callable(assessor.get_mistakes)


def test_assessor_generate_assessment_returns_success(conn, monkeypatch):
    """generate_assessment 在无维度和无 Key 时返回 {success: False, ...}。"""
    from backend.agents import assessor
    monkeypatch.setattr("backend.llm.use_mock", lambda: True)
    res = assessor.generate_assessment(apprentice_id=1, kb_id=1)
    assert isinstance(res, dict)
    assert "success" in res


def test_assessor_get_mistakes_returns_structure(conn):
    """get_mistakes 返回 {success: True, assess_mistakes: [], review_mistakes: []}。"""
    from backend.agents.assessor import get_mistakes
    res = get_mistakes(apprentice_id=999)
    assert res["success"] is True
    assert "assess_mistakes" in res
    assert "review_mistakes" in res


# ---------- refiner 签名回归 ----------

def test_refiner_exports(conn):
    """refiner.refine 可调用。"""
    from backend.agents.refiner import refine
    assert callable(refine)


# ---------- planner 签名回归 ----------

def test_planner_exports(conn):
    """planner 各函数可调用。"""
    from backend.agents.planner import generate_plan, get_plan, update_plan_day, update_plan_task
    assert callable(generate_plan)
    assert callable(get_plan)
    assert callable(update_plan_day)
    assert callable(update_plan_task)


# ---------- reviewer 签名回归 ----------

def test_reviewer_exports(conn):
    """reviewer 各函数可调用。"""
    from backend.agents.reviewer import generate_review, grade_review_answer
    assert callable(generate_review)
    assert callable(grade_review_answer)


# ---------- tutor 签名回归 ----------

def test_tutor_exports(conn):
    """tutor 各函数可调用。"""
    try:
        from backend.agents.tutor import ask, generate_lecture_content
        assert callable(ask)
        assert callable(generate_lecture_content)
    except ModuleNotFoundError as e:
        if "numpy" in str(e):
            pytest.skip("numpy not installed, skip tutor import test")
        raise
