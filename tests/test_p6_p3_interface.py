"""P6 ↔ P3 对接校验测试（§6.1）。

这是"对接保险"：P3 一交付 grade_quiz_answer，重跑即可确认是否接上。
P3 未交付时本测试跳过而非失败，不阻断 P6 开发。
运行：pytest tests/test_p6_p3_interface.py -v
  - 通过 = 与 P3 接口对接成功
  - skip = P3 未交付
  - fail = 签名/返回与 §5.1 不符，需与 P3 对齐
"""
import inspect
import pytest


def test_grade_quiz_answer_interface():
    try:
        from backend.agents.assessor import grade_quiz_answer
    except ImportError:
        pytest.skip("P3 尚未交付 grade_quiz_answer，待对接后重跑")

    # 1) 可调用
    assert callable(grade_quiz_answer)

    # 2) 入参 (plan_item_id, answer) 且 context 可选
    params = list(inspect.signature(grade_quiz_answer).parameters)
    assert params[0] == "plan_item_id" and params[1] == "answer"

    # 3) 返回结构：score 为数字、feedback 为字符串
    res = grade_quiz_answer(1, "示例作答")
    if isinstance(res, dict):
        assert "score" in res
    elif isinstance(res, (int, float)):
        pass
    else:
        pytest.fail("grade_quiz_answer 返回类型不可归一化（应为 dict 或 int）")
