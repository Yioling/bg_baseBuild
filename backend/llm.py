"""LLM 客户端：OpenAI 兼容协议，支持 DeepSeek / 通义 / OpenAI / Ollama。
无 Key 时自动进入示例（mock）模式，保证应用“开箱即演示”。"""
import json
import re
from backend.config import settings

_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        from openai import OpenAI
        _CLIENT = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
    return _CLIENT


def use_mock() -> bool:
    if settings.MOCK_MODE == "true":
        return True
    if settings.MOCK_MODE == "false":
        return False
    return not settings.llm_ready  # auto


def chat(system: str, user: str, *, temperature: float = 0.3, max_tokens: int = 1600) -> str:
    if use_mock():
        return _mock_chat(system, user)
    resp = _client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, *, temperature: float = 0.2):
    """调用 LLM 并返回解析后的 Python 对象（dict/list）。"""
    text = chat(system, user, temperature=temperature, max_tokens=2200)
    return extract_json(text)


def extract_json(text: str):
    """从模型输出里稳健地抽取第一个 JSON 对象 / 数组。"""
    if text is None:
        return {}
    s = text.strip()
    # 去掉 ```json 围栏
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 截取首个 { 或 [ 到末尾匹配括号
    start = None
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            break
    if start is None:
        return {}
    opener, closer = s[start], "}" if s[start] == "{" else "]"
    depth = 0
    for i in range(start, len(s)):
        if s[i] == opener:
            depth += 1
        elif s[i] == closer:
            depth -= 1
            if depth == 0:
                snippet = s[start : i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return {}
    return {}


# ---------- 无 Key 兜底：内置示例回答，保证可演示 ----------
def _mock_chat(system: str, user: str) -> str:
    u = user.lower()
    if "知识图谱" in user or "课程大纲" in user or "抽取" in user or "请分析以下知识资料" in user:
        return json.dumps(
            {
                "project_summary": "示例项目：智能订单交易系统（演示模式，未接入真实 LLM）。",
                "dimensions": [
                    {"name": "交易链路", "description": "下单→风控→扣减库存→支付→履约", "sort_order": 0},
                    {"name": "幂等设计", "description": "防止重复下单与重复支付", "sort_order": 1},
                    {"name": "分布式事务", "description": "TCC / 消息最终一致性", "sort_order": 2},
                ],
                "points": [
                    {"dimension": "交易链路", "title": "订单状态机", "content": "理解订单从创建到完成的状态流转", "source_ref": "", "level": "熟练"},
                    {"dimension": "交易链路", "title": "风控校验", "content": "下单前的风控规则与黑白名单", "source_ref": "", "level": "了解"},
                    {"dimension": "交易链路", "title": "库存扣减", "content": "预占库存与实扣的区别", "source_ref": "", "level": "熟练"},
                    {"dimension": "幂等设计", "title": "幂等键设计", "content": "使用唯一订单号+Redis实现幂等", "source_ref": "", "level": "精通"},
                    {"dimension": "幂等设计", "title": "重复支付防护", "content": "支付回调幂等处理", "source_ref": "", "level": "熟练"},
                    {"dimension": "分布式事务", "title": "TCC模式", "content": "Try-Confirm-Cancel 三阶段", "source_ref": "", "level": "了解"},
                    {"dimension": "分布式事务", "title": "消息最终一致性", "content": "RocketMQ 事务消息", "source_ref": "", "level": "了解"},
                ],
            },
            ensure_ascii=False,
        )
    if "学习路径" in user or "培养计划" in user or "请基于以下徒弟知识掌握情况" in user:
        return json.dumps(
            {
                "plan_overview": "个性化学习计划（演示模式）",
                "days": [
                    {
                        "day_index": 1,
                        "note": "交易链路基础",
                        "tasks": [
                            {"title": "订单状态机", "dimension_name": "交易链路", "task_type": "阅读", "duration_min": 30, "sort_order": 0, "content_hint": "理解订单状态流转"},
                            {"title": "风控校验机制", "dimension_name": "交易链路", "task_type": "练习", "duration_min": 30, "sort_order": 1, "content_hint": "编写风控规则"},
                        ],
                    },
                    {
                        "day_index": 2,
                        "note": "幂等设计",
                        "tasks": [
                            {"title": "幂等键设计", "dimension_name": "幂等设计", "task_type": "阅读", "duration_min": 30, "sort_order": 0, "content_hint": "唯一订单号方案"},
                            {"title": "重复支付防护", "dimension_name": "幂等设计", "task_type": "练习", "duration_min": 40, "sort_order": 1, "content_hint": "支付回调幂等"},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        )
    if "测验" in user or "题目" in user or "出题" in user or "摸底" in user or "复习" in user or "出一些复习题" in user or "当天学习内容" in user:
        return json.dumps(
            {
                "questions": [
                    {
                        "dimension_name": "交易链路",
                        "question": "为什么下单接口需要做幂等？请举例说明实现方式。",
                        "qtype": "short",
                        "difficulty": "中",
                        "options": None,
                        "answer_key": "防止网络重试/重复点击造成重复下单；可用唯一订单号+Redis 分布式锁或乐观锁版本号实现。",
                        "score": 50,
                    },
                    {
                        "dimension_name": "幂等设计",
                        "question": "TCC 模式的三个阶段分别是什么？",
                        "qtype": "short",
                        "difficulty": "易",
                        "options": None,
                        "answer_key": "Try（预留资源）、Confirm（确认执行）、Cancel（回滚释放）",
                        "score": 50,
                    },
                ],
            },
            ensure_ascii=False,
        )
    return (
        "（演示模式）我是你的 AI 导师。当前未配置 LLM_API_KEY，"
        "回答为内置示例。请在 .env 填入 Key 后获得真实智能答疑。"
    )
