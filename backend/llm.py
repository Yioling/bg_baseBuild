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
    if "知识图谱" in user or "课程大纲" in user or "抽取" in user:
        return json.dumps(
            {
                "project_summary": "示例项目：智能订单交易系统（演示模式，未接入真实 LLM）。",
                "knowledge_points": [
                    {"topic": "交易链路", "desc": "下单→风控→扣减库存→支付→履约", "level": "核心"},
                    {"topic": "幂等设计", "desc": "防止重复下单与重复支付", "level": "核心"},
                    {"topic": "分布式事务", "desc": "TCC / 消息最终一致性", "level": "进阶"},
                ],
                "workflows": [
                    ["用户下单", "网关校验", "风控审核", "创建订单", "发起支付"],
                ],
                "pitfalls": ["库存超卖", "回调乱序", "热点账户"],
                "skills": ["Spring Cloud", "Redis", "RocketMQ", "MySQL 分库分表"],
            },
            ensure_ascii=False,
        )
    if "学习路径" in user or "培养计划" in user:
        return (
            "【演示模式·个性化学习路径】\n"
            "第 1 周：业务认知——交易主流程与领域术语\n"
            "第 2 周：核心模块——订单服务与幂等设计（含动手实验）\n"
            "第 3 周：高并发——缓存、MQ 与限流熔断\n"
            "第 4 周：稳定性——分布式事务与压测演练"
        )
    if "测验" in user or "题目" in user or "出题" in user:
        return json.dumps(
            [
                {
                    "question": "为什么下单接口需要做幂等？请举例说明实现方式。",
                    "type": "简答",
                    "answer_key": "防止网络重试/重复点击造成重复下单；可用唯一订单号+Redis 分布式锁或乐观锁版本号实现。",
                    "level": "核心",
                }
            ],
            ensure_ascii=False,
        )
    return (
        "（演示模式）我是你的 AI 导师。当前未配置 LLM_API_KEY，"
        "回答为内置示例。请在 .env 填入 Key 后获得真实智能答疑。"
    )
