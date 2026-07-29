"""资料摄取：读取本地文件 / 抓取博客 URL → 切片 → 嵌入 → 入库。"""
import json
import hashlib
from pathlib import Path
from backend.db import get_conn
from backend.config import settings
from backend.vectorstore import VectorStore


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """简单按字符数分块，带重叠。"""
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
    """读取支持的文件类型。"""
    ext = filepath.suffix.lower()
    try:
        if ext in (".md", ".txt", ".py", ".java", ".js", ".ts", ".cpp", ".c", ".h"):
            return filepath.read_text(encoding="utf-8")
        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(filepath))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                return None
        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(str(filepath))
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                return None
        else:
            return None
    except Exception:
        return None


def ingest_local_path(master_id: int, kb_id: int, path_str: str, store: VectorStore) -> dict:
    """扫描本地文件夹，读取全部支持文件，切片嵌入入库。"""
    root = Path(path_str)
    if not root.exists():
        return {"success": False, "message": f"路径不存在: {path_str}"}

    files = []
    if root.is_file():
        files = [root]
    else:
        for ext in ("*.md", "*.txt", "*.pdf", "*.docx", "*.py", "*.java", "*.js"):
            files.extend(root.rglob(ext))

    if not files:
        return {"success": False, "message": "未找到支持的文件类型（md/txt/pdf/docx/code）"}

    conn = get_conn()
    all_chunks = []
    doc_count = 0

    for fp in files:
        text = _read_file(fp)
        if not text or not text.strip():
            continue
        rel = str(fp)
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

    conn.commit()

    if all_chunks:
        from backend.embeddings import embed
        vectors = embed([c["text"] for c in all_chunks])
        store.add(all_chunks, vectors)
        store.save(settings.STORE_PATH)
        # 同时写入 SQLite 向量块表
        for c in all_chunks:
            conn.execute(
                "INSERT INTO vector_chunks (kb_id, text, meta) VALUES (?, ?, ?)",
                (kb_id, c["text"], c["meta"]),
            )
        conn.commit()

    return {"success": True, "message": f"已摄入 {doc_count} 个文件，共 {len(all_chunks)} 个文本块"}


def ingest_urls(master_id: int, kb_id: int, urls: list[str], store: VectorStore) -> dict:
    """抓取博客/网页 URL，抽取正文后切片嵌入入库。"""
    try:
        import trafilatura
    except ImportError:
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return {"success": False, "message": "需要安装 trafilatura 或 requests+beautifulsoup4，请 pip install trafilatura"}

    conn = get_conn()
    all_chunks = []
    url_count = 0

    for url in urls:
        url = url.strip()
        if not url:
            continue
        text = _fetch_url_text(url)
        if not text or not text.strip():
            continue
        title = url.rsplit("/", 1)[-1] or url
        # 存入 kb_sources
        conn.execute(
            "INSERT INTO kb_sources (kb_id, source_type, location, title) VALUES (?, 'url', ?, ?)",
            (kb_id, url, title),
        )
        # 分块
        for chunk in _chunk_text(text):
            all_chunks.append({
                "text": chunk,
                "source": url,
                "meta": json.dumps({"url": url, "title": title}, ensure_ascii=False),
            })
        url_count += 1

    conn.commit()

    if all_chunks:
        from backend.embeddings import embed
        vectors = embed([c["text"] for c in all_chunks])
        store.add(all_chunks, vectors)
        store.save(settings.STORE_PATH)
        for c in all_chunks:
            conn.execute(
                "INSERT INTO vector_chunks (kb_id, text, meta) VALUES (?, ?, ?)",
                (kb_id, c["text"], c["meta"]),
            )
        conn.commit()

    return {"success": True, "message": f"已摄入 {url_count} 个网址，共 {len(all_chunks)} 个文本块"}


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
        pass

    # 降级为 requests + bs4
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
        return None


def get_kb_texts(kb_id: int) -> str:
    """获取知识库全部文本（用于 Refiner）。"""
    conn = get_conn()
    docs = conn.execute(
        "SELECT raw_text FROM kb_documents WHERE kb_id=?",
        (kb_id,),
    ).fetchall()
    return "\n\n".join(d["raw_text"] for d in docs)


def get_or_create_kb(master_id: int) -> dict:
    """获取或创建师傅的知识库。"""
    conn = get_conn()
    kb = conn.execute(
        "SELECT * FROM knowledge_bases WHERE master_id=? LIMIT 1",
        (master_id,),
    ).fetchone()
    if kb:
        return dict(kb)
    cur = conn.execute(
        "INSERT INTO knowledge_bases (master_id, name) VALUES (?, '默认知识库')",
        (master_id,),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (cur.lastrowid,)).fetchone())
