"""PDF 生成：当日学习讲义包。使用 reportlab 渲染美观的 PDF。"""
import io
from datetime import datetime
from backend.db import get_conn
from backend.vectorstore import VectorStore, retrieve_context
from backend.config import settings
from backend.llm import chat, use_mock


def generate_today_pdf(apprentice_id: int, plan_day_id: int, store: VectorStore) -> bytes:
    """生成当日学习内容 PDF，返回 bytes。"""
    from backend.agents.tutor import generate_lecture_content
    lecture_data = generate_lecture_content(apprentice_id, plan_day_id, store)

    if not lecture_data.get("success"):
        return _error_pdf(lecture_data.get("message", "生成失败"))

    # 获取用户信息
    conn = get_conn()
    user = conn.execute("SELECT username FROM users WHERE id=?", (apprentice_id,)).fetchone()
    username = user["username"] if user else f"学徒{apprentice_id}"

    day = lecture_data["day"]
    lectures = lecture_data["lectures"]

    # 用 HTML → PDF（weasyprint 最佳，也可用 reportlab）
    html = _build_lecture_html(username, day, lectures)
    return _html_to_pdf(html)


def _build_lecture_html(username: str, day: dict, lectures: list) -> str:
    """构建讲义的 HTML 内容，遵循设计系统风格。"""
    date_str = day.get("date", datetime.now().strftime("%Y-%m-%d"))
    note = day.get("note", "认真学习，天天向上")
    total_min = sum(l.get("duration_min", 0) for l in lectures)

    items_html = ""
    for i, lec in enumerate(lectures, 1):
        tag_color = {"阅读": "#4A90D9", "练习": "#E8853D", "复习": "#5AB799"}.get(lec["task_type"], "#666")
        items_html += f"""
        <div class="lecture-item">
            <div class="lecture-header">
                <span class="lecture-num">第{i}节</span>
                <span class="lecture-tag" style="background:{tag_color}">{lec['task_type']}</span>
                <span class="lecture-dim">{lec['dim_name'] or '综合'}</span>
                <span class="lecture-dur">{lec['duration_min']} 分钟</span>
            </div>
            <h3 class="lecture-title">{lec['title']}</h3>
            <div class="lecture-content">{_markdown_to_html(lec['content'])}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 20mm 18mm; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; color: #2c3e50; line-height: 1.8; font-size: 14px; }}
  .cover {{ text-align: center; padding: 60px 0 40px; border-bottom: 3px solid #2c3e50; margin-bottom: 30px; }}
  .cover h1 {{ font-size: 28px; margin: 0 0 8px; color: #1a1a2e; }}
  .cover .subtitle {{ font-size: 16px; color: #666; }}
  .meta {{ display: flex; justify-content: center; gap: 30px; margin-top: 20px; font-size: 13px; color: #888; }}
  .meta span {{ background: #f0f4f8; padding: 4px 14px; border-radius: 20px; }}
  .lecture-item {{ margin-bottom: 30px; padding: 20px; background: #fafbfc; border-radius: 10px; border-left: 4px solid #4A90D9; }}
  .lecture-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
  .lecture-num {{ font-weight: 700; color: #2c3e50; }}
  .lecture-tag {{ color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 12px; }}
  .lecture-dim {{ color: #888; font-size: 12px; }}
  .lecture-dur {{ margin-left: auto; color: #999; font-size: 12px; }}
  .lecture-title {{ font-size: 18px; margin: 0 0 10px; color: #1a1a2e; }}
  .lecture-content {{ font-size: 14px; }}
  .lecture-content pre {{ background: #1e1e2e; color: #cdd6f4; padding: 14px; border-radius: 8px; overflow-x: auto; font-size: 13px; }}
  .lecture-content code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  .lecture-content pre code {{ background: transparent; padding: 0; }}
  .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #aaa; font-size: 12px; }}
</style>
</head>
<body>
<div class="cover">
    <h1>📖 薪火 · 每日学习讲义</h1>
    <div class="subtitle">AI 导师系统 · 个性化学习包</div>
    <div class="meta">
        <span>学员：{username}</span>
        <span>日期：{date_str}</span>
        <span>总时长：约{total_min}分钟</span>
    </div>
    <p style="margin-top:16px;color:#555;">📝 {note}</p>
</div>
{items_html}
<div class="footer">薪火 · 师傅带徒 AI 导师系统 | 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body>
</html>"""


def _markdown_to_html(text: str) -> str:
    """简单 Markdown → HTML 转换。"""
    import re
    text = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\n- (.+)", r"<br>• \1", text)
    text = text.replace("\n\n", "<br><br>")
    return text


def _html_to_pdf(html: str) -> bytes:
    """将 HTML 转为 PDF bytes。优先 weasyprint，降级为纯文本。"""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        pass
    try:
        # fpdf2 降级方案
        return _fpdf_fallback(html)
    except Exception:
        # 最终降级：返回 HTML 本身（前端可以用浏览器打印）
        return html.encode("utf-8")


def _fpdf_fallback(html: str) -> bytes:
    """fpdf2 纯文本 PDF 降级方案。"""
    from fpdf import FPDF
    import re
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("SimSun", "", r"C:\Windows\Fonts\simsun.ttc", uni=True)
    pdf.set_font("SimSun", "", 12)

    # 纯文本提取
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for line in text.split("\n"):
        line = line.strip()
        if line:
            pdf.multi_cell(0, 8, line)
    return pdf.output()


def _error_pdf(msg: str) -> bytes:
    html = f"<html><body><h1>生成失败</h1><p>{msg}</p></body></html>"
    return html.encode("utf-8")
