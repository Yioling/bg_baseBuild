"""LLM 客户端：OpenAI 兼容协议，支持 DeepSeek / 通义 / OpenAI / Ollama。
无 Key 时自动进入示例（mock）模式，保证应用"开箱即演示"。

提供同步（chat/chat_json）和异步（achat/achat_json）两套接口，
异步版通过 asyncio.to_thread 包裹，不阻塞事件循环。
"""
import json
import re
import time
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

_CLIENT = None

# 重试配置
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.5  # 秒（0.5 → 1.0 → 2.0）
DEFAULT_TIMEOUT = 60.0  # 秒


def _client():
    """懒加载 OpenAI 客户端单例，配置超时与禁内置重试。"""
    global _CLIENT
    if _CLIENT is None:
        from openai import OpenAI
        _CLIENT = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=DEFAULT_TIMEOUT,
            max_retries=0,  # 我们自己控制重试策略
        )
    return _CLIENT


def reset_client():
    """清除缓存的客户端单例，允许热切换 API 配置。"""
    global _CLIENT
    _CLIENT = None


def use_mock() -> bool:
    """判断当前是否运行在演示（mock）模式。"""
    if settings.MOCK_MODE == "true":
        return True
    if settings.MOCK_MODE == "false":
        return False
    return not settings.llm_ready  # auto


def check_llm_ready() -> dict:
    """诊断 LLM 连接状态，供管理后台展示。"""
    if use_mock():
        return {"ready": True, "mode": "mock", "message": "演示模式（无 API Key），使用内置示例回答"}
    try:
        _client()
        return {"ready": True, "mode": "live", "message": f"已连接: {settings.LLM_BASE_URL} ({settings.LLM_MODEL})"}
    except Exception as e:
        return {"ready": False, "mode": "live", "message": f"连接失败: {e}"}


# ---------- 核心调用（同步，带重试 + 降级） ----------
def _call_llm(messages: list[dict], *, temperature: float = 0.3,
              max_tokens: int = 1600, max_retries: int = MAX_RETRIES) -> str:
    """带指数退避重试的 LLM 调用。只对网络/超时错误重试，认证错误直接抛出。"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = _client().chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if not _is_retryable(e):
                raise
            if attempt < max_retries:
                delay = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning("LLM 调用失败（第 %d/%d 次），%.1fs 后重试: %s", attempt, max_retries, delay, e)
                time.sleep(delay)
    # 重试耗尽
    logger.error("LLM 调用失败（已重试 %d 次）: %s", max_retries, last_error)
    raise last_error


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否可重试。网络/超时/限流 → 重试；认证/参数错误 → 不重试。"""
    exc_str = str(exc).lower()
    non_retryable = ("401", "403", "invalid api key", "authentication", "insufficient_quota")
    retryable = ("timeout", "connection", "rate", "server", "overloaded", "capacity", "refused")
    for kw in non_retryable:
        if kw in exc_str:
            return False
    for kw in retryable:
        if kw in exc_str:
            return True
    return True  # 未知错误保守重试


# ---------- 同步接口（向后兼容，供 Agent 调用） ----------
def chat(system: str, user: str, *, temperature: float = 0.3, max_tokens: int = 1600) -> str:
    """同步调用 LLM。失败时自动降级到 mock 模式，保证流程不中断。"""
    if use_mock():
        return _mock_chat(system, user)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        return _call_llm(messages, temperature=temperature, max_tokens=max_tokens)
    except Exception as e:
        logger.warning("LLM 调用失败，降级到 mock 模式: %s", e)
        return _mock_chat(system, user)


def chat_json(system: str, user: str, *, temperature: float = 0.2):
    """同步调用 LLM 并返回解析后的 Python 对象（dict/list）。"""
    text = chat(system, user, temperature=temperature, max_tokens=2200)
    return extract_json(text)


# ---------- 异步接口（通过 asyncio.to_thread 不阻塞事件循环） ----------
async def achat(system: str, user: str, *, temperature: float = 0.3, max_tokens: int = 1600) -> str:
    """异步版 chat。同步 SDK 调用通过 asyncio.to_thread 包裹，不阻塞事件循环。"""
    import asyncio
    return await asyncio.to_thread(chat, system, user, temperature=temperature, max_tokens=max_tokens)


async def achat_json(system: str, user: str, *, temperature: float = 0.2):
    """异步版 chat_json。"""
    import asyncio
    text = await achat(system, user, temperature=temperature, max_tokens=2200)
    return extract_json(text)


# ---------- JSON 解析（多层降级，稳健可靠） ----------
def extract_json(text: str):
    """从模型输出里稳健地抽取第一个 JSON 对象 / 数组。

    降级链路：去 Markdown 围栏 → 精确解析 → 括号匹配截取 → 空对象。
    """
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
