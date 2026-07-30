"""本地中文嵌入：fastembed（轻量、无需 torch），首跑自动下载模型。
提供 is_ready() 状态检查与 get_model_info() 诊断接口，供管理后台使用。

配置模型不可用时自动降级到 BAAI/bge-small-zh-v1.5（512维，中文优化）。
"""
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

# 降级模型：当配置的模型不可用时自动切换到此模型
_FALLBACK_MODEL = "BAAI/bge-small-zh-v1.5"

_MODEL = None
_MODEL_LOAD_ERROR: str | None = None
_ACTIVE_MODEL_NAME: str | None = None  # 实际加载成功的模型名


def _model():
    """懒加载嵌入模型。先尝试配置模型，失败则自动降级到 BAAI/bge-small-zh-v1.5。"""
    global _MODEL, _MODEL_LOAD_ERROR, _ACTIVE_MODEL_NAME
    if _MODEL is not None:
        return _MODEL
    if _MODEL_LOAD_ERROR is not None:
        raise RuntimeError(f"嵌入模型加载失败（已缓存错误）: {_MODEL_LOAD_ERROR}")

    from fastembed import TextEmbedding

    # 候选模型列表：配置优先，降级模型兜底
    candidates = [settings.EMBEDDING_MODEL]
    if _FALLBACK_MODEL not in candidates:
        candidates.append(_FALLBACK_MODEL)

    last_error = None
    for model_name in candidates:
        try:
            _MODEL = TextEmbedding(model_name=model_name)
            _ACTIVE_MODEL_NAME = model_name
            if model_name != settings.EMBEDDING_MODEL:
                logger.warning(
                    "配置模型 %s 不可用，已降级为 %s",
                    settings.EMBEDDING_MODEL, model_name,
                )
            else:
                logger.info("嵌入模型加载成功: %s", model_name)
            return _MODEL
        except Exception as e:
            last_error = e
            logger.warning("模型 %s 加载失败: %s", model_name, e)

    _MODEL_LOAD_ERROR = str(last_error)
    raise RuntimeError(
        f"无法加载任何嵌入模型（已尝试 {candidates}），最后错误: {last_error}"
    ) from last_error


def is_ready() -> bool:
    """检查嵌入模型是否已加载就绪，供启动诊断和管理后台使用。"""
    if _MODEL_LOAD_ERROR is not None:
        return False
    try:
        _model()
        return True
    except RuntimeError:
        return False


def get_model_info() -> dict:
    """返回嵌入模型信息，供管理后台展示。"""
    return {
        "configured_model": settings.EMBEDDING_MODEL,
        "active_model": _ACTIVE_MODEL_NAME,
        "ready": is_ready(),
        "error": _MODEL_LOAD_ERROR,
    }


def embed(texts: list[str]) -> list[list[float]]:
    """批量嵌入，返回向量列表。

    空输入返回空列表；内嵌空字符串用零向量占位以保持输出长度一致。
    """
    if not texts:
        return []
    # 过滤纯空白字符串，记录占位
    valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
    if not valid_indices:
        # 全部为空 → 全部返回零向量（维度从模型获取）
        try:
            dim = _get_embedding_dim()
        except Exception:
            dim = 512
        return [[0.0] * dim for _ in texts]

    valid_texts = [texts[i] for i in valid_indices]
    try:
        valid_vecs = list(_model().embed(valid_texts))
    except Exception as e:
        logger.error("嵌入计算失败: %s", e)
        raise

    # 拼回原始顺序（空文本用零向量占位）
    dim = len(valid_vecs[0]) if valid_vecs else 512
    result = []
    vi = 0
    for i in range(len(texts)):
        if i in valid_indices:
            result.append(valid_vecs[vi].tolist() if hasattr(valid_vecs[vi], "tolist") else list(valid_vecs[vi]))
            vi += 1
        else:
            result.append([0.0] * dim)
    return result


def embed_one(text: str) -> list[float]:
    """单个文本嵌入，直接返回向量。"""
    return embed([text])[0]


def _get_embedding_dim() -> int:
    """获取嵌入向量维度（发送一个短文本探测）。"""
    vecs = list(_model().embed(["维度探测"]))
    return len(vecs[0]) if vecs else 512
