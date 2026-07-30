"""资料摄取：读取本地文件 / 抓取博客 URL -> 切片 -> 嵌入 -> 入库。

设计要点：
- 幂等去重：同一文件路径 / URL 重复投喂不会产生重复向量，已存在的源自动跳过。
- 编码鲁棒：本地文本文件自动尝试 utf-8/gbk/gb18030 等多种编码，避免中文乱码。
- 异常隔离：单个文件 / URL 解析失败不影响整批摄取；切片->嵌入->入库链路失败不崩溃。
"""
import json
import hashlib
import logging
from pathlib import Path
from backend.db import get_conn
from backend.config import settings
from backend.vectorstore import VectorStore

logger = logging.getLogger(__name__)

# 支持的文件扩展名
_TEXT_EXTS = (".md", ".txt", ".py", ".java", ".js", ".ts", ".cpp", ".c", ".h", ".go", ".rs", ".sql")
_BINARY_EXTS = (".pdf", ".docx")
_ALL_EXTS = _TEXT_EXTS + _BINARY_EXTS
# 文本文件回退编码（按优先级尝试）
_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1")


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """按字符数分块，带重叠。空文本返回空列表。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _read_file(filepath: Path) -> str | None:
    """读取支持的文件类型，文本文件自动回退多种编码。失败返回 None。"""
    ext = filepath.suffix.lower()
    try:
        if ext in _TEXT_EXTS:
            return _read_text_with_fallback(filepath)
        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(filepath))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                logger.warning("PDF 解析失败: %s", filepath)
                return None
        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(str(filepath))
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                logger.warning("DOCX 解析失败: %s", filepath)
                return None
        else:
            return None
    except Exception:
        logger.warning("文件读取异常: %s", filepath, exc_info=True)
        return None


def _read_text_with_fallback(filepath: Path) -> str | None:
    """依次尝试多种编码读取纯文本文件，解决中文 GBK 等非 UTF-8 文件乱码/失败问题。"""
    raw = filepath.read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _existing_sources(conn, kb_id: int) -> set[str]:
    """获取该知识库已摄取过的源 location 集合（用于幂等去重）。"""
    rows = conn.execute(
        "SELECT location FROM kb_sources WHERE kb_id=?", (kb_id,)
    ).fetchall()
    return {r["location"] for r in rows}


def _ingest_chunks(conn, kb_id: int, all_chunks: list[dict], store: VectorStore) -> bool:
    """对分块执行 嵌入 -> 向量库 -> SQLite 落库。成功返回 True，失败返回 False（不抛异常）。"""
    if not all_chunks:
        return True
    # 嵌入
    try:
        from backend.embeddings import embed
        vectors = embed([c["text"] for c in all_chunks])
    except Exception:
        logger.error("向量化失败", exc_info=True)
        return False
    # 写入内存向量库并持久化
    try:
        store.add(all_chunks, vectors)
        store.save(settings.STORE_PATH)
    except Exception:
        logger.error("向量库写入失败", exc_info=True)
        return False
    # 同步写入 SQLite 向量块表
    try:
        for c in all_chunks:
            conn.execute(
                "INSERT INTO vector_chunks (kb_id, text, meta) VALUES (?, ?, ?)",
                (kb_id, c["text"], c["meta"]),
            )
        conn.commit()
    except Exception:
        logger.error("vector_chunks 落库失败", exc_info=True)
        return False
    return True


def ingest_local_path(master_id: int, kb_id: int, path_str: str, store: VectorStore) -> dict:
    """扫描本地文件夹，读取全部支持文件，切片嵌入入库（幂等去重）。"""
    root = Path(path_str)
    if not root.exists():
        return {"success": False, "message": f"路径不存在: {path_str}"}

    # 收集文件：单文件直接取；文件夹递归遍历按扩展名匹配
    files = []
    if root.is_file():
        files = [root]
    else:
        # 用 rglob("*/**/*") 遍历全部再按后缀过滤，避免 rglob(ext) 传 ".md"
        # 因缺少通配符 "*" 导致匹配为空的问题（中文文件名亦兼容）
        for fp in root.rglob("*"):
            if fp.is_file() and fp.suffix.lower() in _ALL_EXTS:
                files.append(fp)
        # 去重并排序保证顺序确定
        files = sorted({f.resolve() for f in files})

    if not files:
        return {"success": False, "message": "未找到支持的文件类型（md/txt/pdf/docx/代码）"}

    conn = get_conn()
    try:
        existing = _existing_sources(conn, kb_id)
        all_chunks = []
        doc_count = 0
        skipped = 0
        failed = 0

        for fp in files:
            try:
                text = _read_file(fp)
                if not text or not text.strip():
                    failed += 1
                    continue
                rel = str(fp)
                # 幂等去重：同一路径已摄取过则跳过
                if rel in existing:
                    skipped += 1
                    continue
                # 存入 kb_documents
                conn.execute(
                    "INSERT INTO kb_documents (kb_id, filename, raw_text) VALUES (?, ?, ?)",
                    (kb_id, fp.name, text),
                )
                # 存入 kb_sources
                conn.execute(
                    "INSERT INTO kb_sources (kb_id, source_type, location, title) VALUES (?, 'file', ?, ?)",
                    (kb_id, rel, fp.name),
                )
                # 分块
                for chunk in _chunk_text(text):
                    all_chunks.append({
                        "text": chunk,
                        "source": rel,
                        "meta": json.dumps({"filename": fp.name}, ensure_ascii=False),
                    })
                doc_count += 1
                existing.add(rel)
            except Exception:
                failed += 1
                logger.warning("摄取文件异常: %s", fp, exc_info=True)
                continue

        conn.commit()

        embedded = _ingest_chunks(conn, kb_id, all_chunks, store)
        msg = f"已摄入 {doc_count} 个文件，共 {len(all_chunks)} 个文本块"
        if skipped:
            msg += f"；跳过已存在 {skipped} 个"
        if failed:
            msg += f"；失败 {failed} 个"
        if not embedded:
            msg += "（注意：向量化失败，知识库元数据已存但暂不可检索）"
        return {
            "success": True,
            "message": msg,
            "doc_count": doc_count,
            "chunk_count": len(all_chunks),
            "skipped": skipped,
            "failed": failed,
        }
    finally:
        conn.close()


def ingest_urls(master_id: int, kb_id: int, urls: list[str], store: VectorStore) -> dict:
    """抓取博客/网页 URL，抽取正文后切片嵌入入库（幂等去重）。"""
    if not urls:
        return {"success": False, "message": "未提供 URL"}

    # 依赖可用性预检：trafilatura 或 requests+beautifulsoup4 至少一个
    try:
        import trafilatura  # noqa: F401
    except ImportError:
        try:
            import requests  # noqa: F401
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            return {
                "success": False,
                "message": "需要安装 trafilatura 或 requests+beautifulsoup4，请 pip install trafilatura",
            }

    conn = get_conn()
    try:
        existing = _existing_sources(conn, kb_id)
        all_chunks = []
        url_count = 0
        skipped = 0
        failed = 0

        for url in urls:
            url = url.strip()
            if not url:
                continue
            try:
                # 幂等去重：同一 URL 已摄取过则跳过
                if url in existing:
                    skipped += 1
                    continue
                text = _fetch_url_text(url)
                if not text or not text.strip():
                    failed += 1
                    logger.warning("URL 抓取正文为空或失败: %s", url)
                    continue
                # 存入 kb_documents
                conn.execute(
                    "INSERT INTO kb_documents (kb_id, filename, raw_text) VALUES (?, ?, ?)",
                    (kb_id, url, text),
                )
                # 存入 kb_sources
                conn.execute(
                    "INSERT INTO kb_sources (kb_id, source_type, location, title) VALUES (?, 'url', ?, ?)",
                    (kb_id, url, url),
                )
                # 分块
                for chunk in _chunk_text(text):
                    all_chunks.append({
                        "text": chunk,
                        "source": url,
                        "meta": json.dumps({"url": url}, ensure_ascii=False),
                    })
                url_count += 1
                existing.add(url)
            except Exception:
                failed += 1
                logger.warning("摄取 URL 异常: %s", url, exc_info=True)
                continue

        conn.commit()

        embedded = _ingest_chunks(conn, kb_id, all_chunks, store)
        msg = f"已抓取 {url_count} 个 URL，共 {len(all_chunks)} 个文本块"
        if skipped:
            msg += f"；跳过已存在 {skipped} 个"
        if failed:
            msg += f"；失败 {failed} 个"
        if not embedded:
            msg += "（注意：向量化失败，知识库元数据已存但暂不可检索）"
        return {
            "success": True,
            "message": msg,
            "url_count": url_count,
            "chunk_count": len(all_chunks),
            "skipped": skipped,
            "failed": failed,
        }
    finally:
        conn.close()


def _fetch_url_text(url: str) -> str | None:
    """用 trafilatura 或 requests+bs4 抓取网页正文。"""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text:
                return text
    except Exception:
        logger.debug("trafilatura 抓取失败，回退到 requests: %s", url, exc_info=True)
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        logger.warning("URL 正文抓取失败: %s", url, exc_info=True)
        return None


def get_kb_texts(kb_id: int) -> str:
    """获取知识库全部文本（用于 Refiner）。"""
    conn = get_conn()
    try:
        docs = conn.execute(
            "SELECT raw_text FROM kb_documents WHERE kb_id=?", (kb_id,)
        ).fetchall()
        return "\n\n".join(d["raw_text"] for d in docs)
    finally:
        conn.close()


def get_or_create_kb(master_id: int) -> dict:
    """获取或创建师傅的知识库。"""
    conn = get_conn()
    try:
        kb = conn.execute(
            "SELECT * FROM knowledge_bases WHERE master_id=? LIMIT 1", (master_id,)
        ).fetchone()
        if kb:
            return dict(kb)
        cur = conn.execute(
            "INSERT INTO knowledge_bases (master_id, name) VALUES (?, '默认知识库')",
            (master_id,),
        )
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM knowledge_bases WHERE id=?", (cur.lastrowid,)
            ).fetchone()
        )
    finally:
        conn.close()
