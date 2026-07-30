"""全局配置：从 .env 读取，路径统一以项目根目录为基准。"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# PyInstaller 打包后路径处理
_FROZEN = getattr(sys, 'frozen', False)
if _FROZEN:
    BUNDLE_DIR = Path(sys._MEIPASS)  # 只读的临时解压目录
    BASE_DIR = BUNDLE_DIR
else:
    BUNDLE_DIR = None
    BASE_DIR = Path(__file__).resolve().parent.parent

BACKEND_DIR = BASE_DIR / "backend" if (BASE_DIR / "backend").exists() else BASE_DIR

load_dotenv(BASE_DIR / ".env")

# 可写数据目录（打包后使用 %APPDATA%，开发时使用 backend/data）
if _FROZEN:
    DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "TSForce_MentorAI"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    DATA_DIR = BACKEND_DIR / "data"


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (BASE_DIR / p)


class Settings:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-small-zh")

    # KB_DIR: 示例知识库（打包后在只读 bundle，开发时在 backend/data）
    _default_kb = "backend/data/sample_kb"
    KB_DIR = _resolve(os.getenv("KB_DIR", _default_kb))
    # STORE_PATH: 向量库持久化（必须可写！打包后存到 APPDATA）
    if _FROZEN:
        STORE_PATH = DATA_DIR / "vectorstore.pkl"
    else:
        STORE_PATH = _resolve(os.getenv("STORE_PATH", "backend/data/vectorstore.pkl"))

    MOCK_MODE = os.getenv("MOCK_MODE", "auto").lower()  # auto|true|false

    FRONTEND_HTML = BASE_DIR / "frontend" / "index.html"

    @property
    def llm_ready(self) -> bool:
        return bool(self.LLM_API_KEY) and self.LLM_API_KEY not in ("your-key-here", "sk-xxx", "")


settings = Settings()
