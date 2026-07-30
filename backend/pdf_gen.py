"""PDF 生成：当日学习讲义包。

降级链（每级独立 try，互不影响）：
  weasyprint(精美 HTML/CSS 排版) -> fpdf2(跨平台 CJK 字体) ->
  reportlab(内置 STSong-Light CID 字体，不依赖外部文件) -> HTML bytes 兜底。

设计要点：
- 跨平台字体：自动搜索 Windows/Linux/macOS 常见中文字体；reportlab 降级使用内置 CID 字体。
- 防 HTML 注入：Markdown 转换前先对原文做 HTML 转义。
- 异常隔离：内容生成 / 渲染各环节失败均不崩溃，最终兜底返回可打印的 HTML bytes。
"""
from __future__ import annotations

import io
import html as html_mod
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.db import get_conn

if TYPE_CHECKING:
    from backend.vectorstore import VectorStore

logger = logging.getLogger(__name__)

# 任务类型 -> 标签颜色
_TAG_COLORS = {"阅读": "#4A90D9", "练习": "#E8853D", "复习": "#5AB799"}

# 跨平台 CJK 字体候选路径（按平台 / 常见度排序，fpdf2 用）
_CJK_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",       # 微软雅黑粗体
    r"C:\Windows\Fonts\simsun.ttc",      # 宋体
    r"C:\Windows\Fonts\simhei.ttf",       # 黑体
    # Linux
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def generate_today_pdf(apprentice_id: int, plan_day_id: int, store: VectorStore) -> bytes:
    """生成当日学习内容 PDF，返回 bytes。"""
    from backend.agents.tutor import generate_lecture_content
    try:
        lecture_data = generate_lecture_content(apprentice_id, plan_day_id, store)
    except Exception:
        logger.error("讲义内容生成失败", exc_info=True)
        return _error_pdf("讲义内容生成失败，请稍后重试")

    if not lecture_data.get("success"):
        return _error_pdf(lecture_data.get("message", "生成失败"))

    # 获取用户信息（确保连接关闭）
    conn = get_conn()
    try:
        user = conn.execute(
            "SELECT username FROM users WHERE id=?", (apprentice_id,)
        ).fetchone()
        username = user["username"] if user else f"学徒{apprentice_id}"
    finally:
        conn.close()

    day = lecture_data["day"]
    lectures = lecture_data["lectures"]

    html = _build_lecture_html(username, day, lectures)
    return _html_to_pdf(html)


def _build_lecture_html(username: str, day: dict, lectures: list) -> str:
    """构建讲义的 HTML 内容，遵循设计系统风格。"""
    date_str = day.get("date", datetime.now().strftime("%Y-%m-%d"))
    note = day.get("note", "认真学习，天天向上")
    total_min = sum(l.get("duration_min", 0) for l in lectures)

    items_html = ""
    for i, lec in enumerate(lectures, 1):
        tag_color = _TAG_COLORS.get(lec.get("task_type"), "#666")
        items_html += f"""
        <div class="lecture-item">
            <div class="lecture-header">
                <span class="lecture-num">第{i}节</span>
                <span class="lecture-tag" style="background:{tag_color}">{html_mod.escape(lec.get('task_type', ''))}</span>
                <span class="lecture-dim">{html_mod.escape(lec.get('dim_name') or '综合')}</span>
                <span class="lecture-dur">{lec.get('duration_min', 0)} 分钟</span>
            </div>
            <h3 class="lecture-title">{html_mod.escape(lec.get('title', ''))}</h3>
            <div class="lecture-content">{_markdown_to_html(lec.get('content', ''))}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 20mm 18mm; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #2c3e50; line-height: 1.8; font-size: 14px; }}
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
  .lecture-content h3 {{ font-size: 15px; color: #1a1a2e; margin: 12px 0 6px; }}
  .lecture-content h4 {{ font-size: 14px; color: #2c3e50; margin: 10px 0 4px; }}
  .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #aaa; font-size: 12px; }}
</style>
</head>
<body>
<div class="cover">
    <h1>📖 薪火 · 每日学习讲义</h1>
    <div class="subtitle">AI 导师系统 · 个性化学习包</div>
    <div class="meta">
        <span>学员：{html_mod.escape(username)}</span>
        <span>日期：{html_mod.escape(str(date_str))}</span>
        <span>总时长：约{total_min}分钟</span>
    </div>
    <p style="margin-top:16px;color:#555;">📝 {html_mod.escape(str(note))}</p>
</div>
{items_html}
<div class="footer">薪火 · 师傅带徒 AI 导师系统 | 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body>
</html>"""


def _markdown_to_html(text: str) -> str:
    """Markdown -> HTML 转换。先转义防注入，再还原代码块/格式标记。"""
    if not text:
        return ""
    # 先整体 HTML 转义，防止 LLM 输出含 < & 破坏结构
    text = html_mod.escape(text)
    # 代码块（```...```）——转义后再匹配，内容已安全
    text = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", text, flags=re.DOTALL)
    # 行内代码
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # 粗体
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 三级 / 二级标题
    text = re.sub(r"^### (.+)", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    # 无序列表项
    text = re.sub(r"\n- (.+)", r"<br>• \1", text)
    # 段落换行
    text = text.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return text


def _find_cjk_font() -> str | None:
    """跨平台搜索支持中文的字体文件路径。找不到返回 None。"""
    for p in _CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _html_to_pdf(html: str) -> bytes:
    """HTML -> PDF bytes。降级链：weasyprint -> fpdf2 -> reportlab -> HTML bytes。"""
    # 1. weasyprint：最佳 HTML/CSS 排版（可选依赖，未声明于 requirements）
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        pass
    except Exception:
        logger.warning("weasyprint 渲染失败，降级", exc_info=True)

    # 2. fpdf2：注册跨平台 CJK 字体渲染
    try:
        return _fpdf_fallback(html)
    except Exception:
        logger.warning("fpdf2 渲染失败，降级", exc_info=True)

    # 3. reportlab：内置 STSong-Light CID 字体，不依赖外部字体文件
    try:
        return _reportlab_fallback(html)
    except Exception:
        logger.warning("reportlab 渲染失败，降级", exc_info=True)

    # 4. 兜底：返回 HTML bytes（前端可用浏览器打印）
    return html.encode("utf-8")


def _strip_html(html: str) -> str:
    """剥离 HTML 标签为纯文本，并反转义实体。先移除 style/script/head 块，避免 CSS 被当正文。"""
    # 移除 <style>...</style> / <script>...</script> 整块
    html = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 <head>...</head> 整块（含 meta/title 等）
    html = re.sub(r"<head\b[^>]*>.*?</head>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # <br> / <p> / </div> 等块级标签转为换行，保留文本结构
    html = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # 剥离剩余所有标签
    text = re.sub(r"<[^>]+>", "", html)
    text = html_mod.unescape(text)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fpdf_fallback(html: str) -> bytes:
    """fpdf2 降级：注册跨平台 CJK 字体后渲染纯文本。"""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    font_path = _find_cjk_font()
    if font_path:
        # fpdf2 2.7+ 默认 unicode，uni 参数已废弃
        pdf.add_font("CJK", "", font_path)
        pdf.set_font("CJK", "", 12)
    else:
        pdf.set_font("Helvetica", "", 12)

    text = _strip_html(html)
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # fpdf2 的 multi_cell 对无空格的长串可能抛
        # "Not enough horizontal space" 异常，逐行隔离避免整页失败
        try:
            pdf.multi_cell(0, 8, line)
        except Exception:
            # 退化为按字符强制截断写入，保证不崩
            try:
                pdf.multi_cell(0, 8, line, split_only=False)
            except Exception:
                logger.debug("fpdf2 跳过无法换行的行: %s", line[:30], exc_info=True)
    return bytes(pdf.output())


def _reportlab_fallback(html: str) -> bytes:
    """reportlab 降级：使用内置 STSong-Light CID 字体渲染纯文本（不依赖外部字体文件）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    # 注册内置中文 CID 字体（STSong-Light），无需外部字体文件
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    except Exception:
        font_name = "Helvetica"

    styles = {
        "h1": ParagraphStyle("h1", fontName=font_name, fontSize=20, leading=28,
                             alignment=1, spaceAfter=12, textColor="#1a1a2e"),
        "h2": ParagraphStyle("h2", fontName=font_name, fontSize=14, leading=20,
                             spaceBefore=10, spaceAfter=6, textColor="#2c3e50"),
        "normal": ParagraphStyle("normal", fontName=font_name, fontSize=11,
                                leading=18, spaceAfter=4),
        "small": ParagraphStyle("small", fontName=font_name, fontSize=9, leading=14,
                                textColor="#888", alignment=1, spaceBefore=20),
    }

    text = _strip_html(html)
    story = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("📖") or "每日学习讲义" in line:
            story.append(Paragraph(html_mod.escape(line), styles["h1"]))
        elif "生成于" in line or "薪火 · 师傅带徒" in line:
            story.append(Paragraph(html_mod.escape(line), styles["small"]))
        elif line.startswith("第") and "节" in line[:5]:
            story.append(Paragraph(html_mod.escape(line), styles["h2"]))
        else:
            story.append(Paragraph(html_mod.escape(line), styles["normal"]))

    doc.build(story)
    return buf.getvalue()


def _error_pdf(msg: str) -> bytes:
    """生成错误提示 PDF（HTML 兜底，确保即使渲染引擎全失败也能返回 bytes）。"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; text-align: center; padding: 80px; color: #2c3e50; }}
  h1 {{ font-size: 24px; color: #c0392b; }}
  p {{ font-size: 16px; color: #666; }}
</style></head>
<body><h1>⚠ 讲义生成失败</h1><p>{html_mod.escape(msg)}</p></body></html>"""
    return html.encode("utf-8")
