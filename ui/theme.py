"""huashu-design 设计系统：设计令牌、全局样式表、通用组件工厂。

主题：红白（品牌红 + 纯净白），大字号、大留白、大气排版。

铁律：本模块导出的所有工厂函数一律返回 QWidget（含子类），
      任何 setStyleSheet 只作用于 QWidget，绝不作用于 QLayout。
"""
from PyQt5.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QApplication,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


def screen_metrics() -> dict:
    """获取当前屏幕可用尺寸并计算全局缩放系数（唯一取屏入口）。

    返回字段：
      width / height  当前屏幕可用宽 / 高（不含任务栏）
      scale           全局缩放系数（相对 1080p 基准，clamp 0.82~1.25，步进 0.02）
      wide            是否宽屏（width / height >= 1.6）
      font_delta      字号增量（px）＝ round((scale - 1) * 6)
    """
    try:
        geo = QApplication.primaryScreen().availableGeometry()
        w, h = geo.width(), geo.height()
    except Exception:
        w, h = 1920, 1040
    scale = max(0.82, min(1.25, round(h / 1040 / 0.02) * 0.02))
    return {
        "width": w,
        "height": h,
        "scale": scale,
        "wide": w / max(h, 1) >= 1.6,
        "font_delta": round((scale - 1) * 6),
    }


def _scaled(v) -> int:
    """把某个基准像素值按当前屏幕缩放系数换算。"""
    return int(v * screen_metrics()["scale"] + 0.5)


# ==================== 设计令牌 ====================
class Color:
    # 品牌 / 主色（红白主题）
    PRIMARY = "#dc2626"
    PRIMARY_HOVER = "#b91c1c"
    PRIMARY_PRESSED = "#991b1b"
    PRIMARY_SOFT = "#fef2f2"
    # 语义色
    SUCCESS = "#10b981"
    SUCCESS_SOFT = "#ecfdf5"
    WARNING = "#f59e0b"
    WARNING_SOFT = "#fffbeb"
    DANGER = "#ef4444"
    DANGER_SOFT = "#fef2f2"
    INFO = "#0ea5e9"
    # 中性
    BG = "#faf8f8"
    SURFACE = "#ffffff"
    SIDEBAR = "#8f1414"
    SIDEBAR_DEEP = "#6f0e0e"
    BORDER = "#eadfdf"
    TEXT = "#1f1a1a"
    TEXT_SUB = "#6b7280"
    TEXT_MUTED = "#9ca3af"
    # 排名徽章
    RANK = ["#fbbf24", "#94a3b8", "#d97706", "#e5e7eb"]


class Radius:
    SM = 8
    MD = 12
    LG = 16
    PILL = 999


# ==================== 全局样式表（作用于 QMainWindow / QWidget 子类） ====================
GLOBAL_QSS = f"""
QMainWindow, QDialog {{
    background-color: {Color.BG};
}}
QWidget#content {{
    background-color: {Color.BG};
}}
QLabel {{
    font-size: 19px;
    color: {Color.TEXT};
    background: transparent;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #d9cfcf;
    border-radius: 6px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #bfb0b0;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* 主按钮（红框红字白底，与投喂/AI 精炼按钮视觉一致） */
QPushButton {{
    background: {Color.SURFACE};
    color: {Color.PRIMARY};
    border: 1.5px solid {Color.PRIMARY};
    border-radius: {Radius.SM}px;
    padding: 16px 30px;
    font-size: 20px;
    font-weight: 600;
    min-height: 48px;
}}
QPushButton:hover {{ background: {Color.PRIMARY_SOFT}; }}
QPushButton:pressed {{ border-color: {Color.PRIMARY_HOVER}; color: {Color.PRIMARY_HOVER}; }}
QPushButton:disabled {{ color: #c8bcbc; border-color: #e0d4d4; }}

QPushButton#btnSecondary {{
    background-color: {Color.SURFACE};
    color: #4b5563;
    border: 1.5px solid {Color.BORDER};
}}
QPushButton#btnSecondary:hover {{ background-color: {Color.PRIMARY_SOFT}; color: {Color.PRIMARY_HOVER}; border-color: #f3c6c6; }}
QPushButton#btnGhost {{
    background: transparent;
    color: {Color.PRIMARY};
    border: none;
    padding: 10px 16px;
    font-size: 20px;
}}
QPushButton#btnGhost:hover {{ color: {Color.PRIMARY_HOVER}; }}
QPushButton#btnSuccess {{ background-color: {Color.SUCCESS}; color: #ffffff; border: 1.5px solid {Color.SUCCESS}; }}
QPushButton#btnSuccess:hover {{ background-color: #0d9668; }}
QPushButton#btnDanger {{ background-color: {Color.SURFACE}; color: {Color.DANGER}; border: 1.5px solid {Color.DANGER}; }}
QPushButton#btnDanger:hover {{ background-color: {Color.DANGER_SOFT}; }}

/* 输入控件 */
QLineEdit, QTextEdit, QComboBox {{
    border: 1.5px solid #e0d4d4;
    border-radius: {Radius.SM}px;
    padding: 14px 18px;
    font-size: 20px;
    background: white;
    color: {Color.TEXT};
    selection-background-color: {Color.PRIMARY};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 2px solid {Color.PRIMARY};
    background: #fef9f9;
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background: #f5f2f2;
    color: {Color.TEXT_MUTED};
}}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {Color.BORDER};
    background: white;
    font-size: 20px;
    selection-background-color: {Color.PRIMARY_SOFT};
    selection-color: {Color.TEXT};
    outline: none;
}}

/* 文字标题 */
QLabel#pageTitle {{ font-size: 35px; font-weight: 800; color: {Color.TEXT}; background: transparent; }}
QLabel#pageSubtitle {{ font-size: 20.5px; color: {Color.TEXT_SUB}; background: transparent; }}
QLabel#sectionTitle {{ font-size: 23px; font-weight: 700; color: #2b2323; background: transparent; }}

/* 表格 */
QTableWidget {{
    border: 1px solid {Color.BORDER};
    border-radius: {Radius.MD}px;
    gridline-color: #f6efef;
    background: white;
    font-size: 19.5px;
    alternate-background-color: #fdfafa;
}}
QTableWidget::item {{ padding: 14px; }}
QTableWidget::item:hover {{ background: #fdf2f2; }}
QTableWidget::item:selected {{ background: {Color.PRIMARY_SOFT}; color: {Color.PRIMARY}; }}
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #faf5f5, stop:1 #f2e9e9);
    border: none;
    border-bottom: 2px solid {Color.BORDER};
    padding: 14px;
    font-weight: 700;
    font-size: 19px;
    color: {Color.TEXT_SUB};
}}

/* 进度条 */
QProgressBar {{
    border: none;
    border-radius: 7px;
    background: #f0e8e8;
    height: 16px;
    text-align: center;
    font-size: 13px;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {Color.PRIMARY};
    border-radius: 7px;
}}

/* GroupBox 作为卡片容器 */
QGroupBox {{
    font-weight: 700;
    font-size: 21px;
    color: {Color.TEXT};
    border: 1px solid {Color.BORDER};
    border-radius: {Radius.LG}px;
    margin-top: 18px;
    padding: 26px 24px 24px 24px;
    background: white;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    top: 2px;
    padding: 0 8px;
    color: {Color.PRIMARY_HOVER};
}}

/* 单选 / 复选 */
QRadioButton, QCheckBox {{ font-size: 20px; color: {Color.TEXT}; spacing: 12px; padding: 6px 0; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 20px; height: 20px; }}
"""

# 侧边栏专属样式（作用于 objectName == sidebar 的 QWidget）
SIDEBAR_QSS = f"""
QWidget#sidebar {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {Color.SIDEBAR}, stop:1 {Color.SIDEBAR_DEEP});
    min-width: 378px;
    max-width: 378px;
}}
QWidget#sidebar QPushButton {{
    color: #f3cfcf;
    background: transparent;
    border: none;
    text-align: left;
    padding: 18px 32px;
    min-height: 56px;
    font-size: 20px;
    font-weight: 500;
    border-left: 4px solid transparent;
    border-radius: 0;
}}
QWidget#sidebar QPushButton:hover {{
    background: rgba(255,255,255,0.10);
    color: #ffffff;
}}
QWidget#sidebar QPushButton:checked {{
    background: rgba(255,255,255,0.18);
    color: #ffffff;
    border-left: 4px solid #ffffff;
    font-weight: 700;
}}
QWidget#sidebar QPushButton#logoutBtn {{
    color: #ffd9a8;
}}
QWidget#sidebar QPushButton#logoutBtn:hover {{
    background: rgba(0,0,0,0.18);
    color: #ffe9cc;
}}
QLabel#logo {{
    color: #ffffff;
    font-size: 29px;
    font-weight: 800;
    padding: 28px 32px 8px 32px;
}}
QLabel#logoSub {{
    color: #e8b6b6;
    font-size: 17.5px;
    padding: 0 32px 16px 32px;
}}
QWidget#userinfo {{
    background: transparent;
}}
QLabel#userAvatar {{
    color: #f0c4c4;
    font-size: 26px;
    background: transparent;
}}
QLabel#userName {{
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
    background: transparent;
}}
QLabel#userRole {{
    color: #f0c4c4;
    font-size: 19px;
    font-weight: 500;
    background: transparent;
}}
"""


# ==================== 通用组件工厂 ====================
def apply_shadow(widget: QWidget, blur: int = 24, dy: int = 6, alpha: int = 26):
    """给 QWidget 添加柔和投影（作用于 widget，不作用于 layout）。"""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    eff.setColor(QColor(80, 20, 20, alpha))
    widget.setGraphicsEffect(eff)
    return widget


def _card_qss(accent: str = None, padding: int = None, hover: bool = False) -> str:
    """生成标准卡片 QFrame 样式串（默认/悬停两态），仅作用于 QFrame。"""
    if padding is None:
        padding = _scaled(26)
    else:
        padding = _scaled(padding)
    border = "#f3c6c6" if hover else Color.BORDER
    border_left = f"border-left:4px solid {accent};" if accent else ""
    return (
        f"QFrame#card{{background:{Color.SURFACE};border:1px solid {border};"
        f"border-radius:{Radius.LG}px;padding:{padding}px;{border_left}}}"
    )


def card(accent: str = None, padding: int = None, hoverable: bool = True) -> QFrame:
    """标准白色卡片容器。返回 QFrame（QWidget 子类），可安全 setStyleSheet。

    padding 缺省时按当前屏幕缩放系数自适应（默认基准 26px）。
    hoverable=True 时带统一悬停反馈：边框变粉 + 阴影加深 + 轻微上移（样式仅作用于 QFrame）。
    """
    if padding is None:
        padding = _scaled(26)
    else:
        padding = _scaled(padding)
    f = QFrame()
    f.setObjectName("card")
    f._accent = accent
    f._pad = padding
    f.setStyleSheet(_card_qss(accent, padding, hover=False))
    apply_shadow(f, blur=24, dy=6, alpha=26)

    if hoverable:
        def _hover_enter(_e):
            f.setStyleSheet(_card_qss(accent, padding, hover=True))
            apply_shadow(f, blur=30, dy=10, alpha=34)

        def _hover_leave(_e):
            f.setStyleSheet(_card_qss(accent, padding, hover=False))
            apply_shadow(f, blur=24, dy=6, alpha=26)

        f.enterEvent = _hover_enter
        f.leaveEvent = _hover_leave
    return f


def _hex_alpha(hex_color: str, ratio: float, base: str = "#ffffff") -> str:
    """把 hex_color 以 ratio 比例混合到 base 上，返回 hex 串（用于淡色选中底）。"""
    try:
        c, b = hex_color.lstrip("#"), base.lstrip("#")
        if len(c) != 6 or len(b) != 6:
            return base
        mix = [
            round(int(b[i:i + 2], 16) * (1 - ratio) + int(c[i:i + 2], 16) * ratio)
            for i in (0, 2, 4)
        ]
        return "#{:02x}{:02x}{:02x}".format(*mix)
    except (ValueError, TypeError):
        return base


def _stat_card_qss(color: str, border_px: int = 4, bg: str = None) -> str:
    """生成指标卡 QFrame 样式串（仅作用于 QFrame，不作用于 QLayout）。"""
    return (
        f"QFrame#card{{background:{bg or Color.SURFACE};"
        f"border:1px solid {Color.BORDER};border-radius:{Radius.LG}px;"
        f"padding:{_scaled(28)}px;border-left:{border_px}px solid {color};}}"
    )


def stat_card(value: str, label: str, color: str = Color.PRIMARY,
              clickable: bool = False, on_click=None) -> QFrame:
    """指标卡：大数字 + 说明文字。

    clickable=True 时卡片可点击：手型光标、右下角 ▸ 提示、悬停/选中态。
    卡片额外挂载 set_selected(bool) 方法供调用方做互斥控制。
    """
    f = card(accent=color)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(_scaled(8), _scaled(8), _scaled(8), _scaled(8))
    lay.setSpacing(_scaled(8))
    v = QLabel(str(value))
    v.setStyleSheet(
        f"font-size:{_scaled(43)}px;font-weight:800;color:{color};background:transparent;"
    )
    v.setAlignment(Qt.AlignCenter)
    lay.addWidget(v)
    l = QLabel(label)
    l.setStyleSheet(
        f"font-size:{_scaled(20)}px;color:{Color.TEXT_SUB};font-weight:500;background:transparent;"
    )
    l.setAlignment(Qt.AlignCenter)
    lay.addWidget(l)
    apply_shadow(f, blur=18, dy=4, alpha=18)

    if not clickable:
        return f

    # ---- 可交互卡片 ----
    hint = QLabel("▸")
    hint.setStyleSheet(
        f"font-size:14px;color:{Color.TEXT_SUB};background:transparent;"
    )
    hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    lay.addWidget(hint)

    f.setCursor(Qt.PointingHandCursor)
    f._selected = False
    sel_bg = _hex_alpha(color, 0.08)

    def _restyle():
        if f._selected:
            f.setStyleSheet(_stat_card_qss(color, 6, sel_bg))
            apply_shadow(f, blur=26, dy=6, alpha=32)
        else:
            f.setStyleSheet(_stat_card_qss(color, 4))
            apply_shadow(f, blur=18, dy=4, alpha=18)

    def set_selected(state: bool):
        f._selected = bool(state)
        _restyle()

    f.set_selected = set_selected

    def _enter(_e):
        if not f._selected:
            f.setStyleSheet(_stat_card_qss(color, 6))
            apply_shadow(f, blur=26, dy=6, alpha=32)

    def _leave(_e):
        if not f._selected:
            _restyle()

    f.enterEvent = _enter
    f.leaveEvent = _leave
    if on_click:
        f.mousePressEvent = lambda _e: on_click()
    return f


def title_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("pageTitle")
    return l


def subtitle_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("pageSubtitle")
    # 用内联样式覆盖随屏字号（QSS 常量不能动态插值）
    l.setStyleSheet(f"font-size:{_scaled(20)}px;background:transparent;")
    l.setWordWrap(True)
    return l


def section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("sectionTitle")
    l.setStyleSheet(f"font-size:{_scaled(23)}px;background:transparent;")
    return l


def hint_label(text: str, color: str = Color.TEXT_SUB) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{color};font-size:{_scaled(19)}px;background:transparent;")
    l.setWordWrap(True)
    return l


#: 引导卡（"🚀 带徒五步法" / "🚀 新手上路"）标题样式，供 GroupBox 单独覆写
GUIDE_BOX_TITLE_QSS = (
    f"QGroupBox{{font-size:25px;font-weight:700;color:{Color.TEXT};"
    f"border:1px solid {Color.BORDER};border-radius:{Radius.LG}px;"
    f"margin-top:16px;padding:22px 20px 20px 20px;background:{Color.SURFACE};}}"
    "QGroupBox::title{subcontrol-origin:margin;left:18px;padding:0 8px;}"
)


def guide_item(text: str, color: str = Color.TEXT) -> QLabel:
    """引导卡条目：比 hint_label 更大的字号，专供引导卡使用。"""
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color};font-size:{_scaled(24)}px;font-weight:500;"
        f"padding-left:{_scaled(6)}px;background:transparent;"
    )
    l.setWordWrap(True)
    return l


def badge(text: str, color: str = Color.PRIMARY, bg: str = Color.PRIMARY_SOFT) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"background:{bg};color:{color};border-radius:{Radius.PILL}px;"
        f"padding:{_scaled(3)}px {_scaled(12)}px;font-size:{_scaled(17)}px;font-weight:600;"
    )
    l.setAlignment(Qt.AlignCenter)
    return l


def secondary_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btnSecondary")
    b.setCursor(Qt.PointingHandCursor)
    return b


def primary_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    return b


def ingest_button(text: str) -> QPushButton:
    """投喂动作按钮：白底 + 红框 + 红字（与主按钮红底白字区分）。

    返回 QPushButton（QWidget 子类），样式仅作用于自身，遵守铁律。
    """
    b = QPushButton(text)
    b.setObjectName("btnIngest")
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        "QPushButton#btnIngest{"
        f"background:{Color.SURFACE};"
        f"color:{Color.PRIMARY};"
        f"border:1.5px solid {Color.PRIMARY};"
        f"border-radius:{Radius.SM}px;"
        "padding:16px 30px;"
        "min-height:48px;"
        "font-size:20px;"
        "font-weight:600;"
        "}"
        f"QPushButton#btnIngest:hover{{background:{Color.PRIMARY_SOFT};}}"
        f"QPushButton#btnIngest:pressed{{border-color:{Color.PRIMARY_HOVER};color:{Color.PRIMARY_HOVER};}}"
        "QPushButton#btnIngest:disabled{color:#c8bcbc;border-color:#e0d4d4;}"
    )
    return b


def refine_button(text: str) -> QPushButton:
    """AI 精炼触发按钮：白底 + 红框 + 红字（与投喂按钮视觉一致，强调一次性重要动作）。

    返回 QPushButton（QWidget 子类），样式仅作用于自身，遵守铁律。
    """
    b = QPushButton(text)
    b.setObjectName("btnRefine")
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        "QPushButton#btnRefine{"
        f"background:{Color.SURFACE};"
        f"color:{Color.PRIMARY};"
        f"border:1.5px solid {Color.PRIMARY};"
        f"border-radius:{Radius.SM}px;"
        "padding:16px 30px;"
        "min-height:48px;"
        "font-size:20px;"
        "font-weight:600;"
        "}"
        f"QPushButton#btnRefine:hover{{background:{Color.PRIMARY_SOFT};}}"
        f"QPushButton#btnRefine:pressed{{border-color:{Color.PRIMARY_HOVER};color:{Color.PRIMARY_HOVER};}}"
        "QPushButton#btnRefine:disabled{color:#c8bcbc;border-color:#e0d4d4;}"
    )
    return b


def success_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btnSuccess")
    b.setCursor(Qt.PointingHandCursor)
    return b


def danger_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btnDanger")
    b.setCursor(Qt.PointingHandCursor)
    return b


def ghost_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btnGhost")
    b.setCursor(Qt.PointingHandCursor)
    return b


def loading_label(text: str = "加载中...") -> QWidget:
    """加载态容器：不确定进度条（QProgressBar range 0,0 动画）+ 文字。

    返回 QWidget（遵守铁律），内部纵向排布；暴露 setText 转发到文字标签，
    兼容既有 loading.setText(...) / hide() / deleteLater() 调用。
    """
    from PyQt5.QtWidgets import QProgressBar
    wrap = QWidget()
    lay = QVBoxLayout(wrap)
    lay.setContentsMargins(_scaled(24), _scaled(20), _scaled(24), _scaled(20))
    lay.setSpacing(_scaled(10))
    bar = QProgressBar()
    bar.setRange(0, 0)  # 不确定进度，横向动画
    bar.setTextVisible(False)
    bar.setFixedWidth(_scaled(220))
    bar.setStyleSheet(
        f"QProgressBar{{border:none;border-radius:{_scaled(3)}px;"
        f"background:#f0e8e8;height:{_scaled(6)}px;}}"
        f"QProgressBar::chunk{{background:{Color.PRIMARY};border-radius:{_scaled(3)}px;}}"
    )
    lay.addWidget(bar, 0, Qt.AlignCenter)
    lbl = QLabel(f"⏳ {text}")
    lbl.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:{_scaled(20)}px;background:transparent;")
    lbl.setAlignment(Qt.AlignCenter)
    lay.addWidget(lbl, 0, Qt.AlignCenter)
    wrap.setText = lambda t: lbl.setText(t)
    wrap.set_word = lambda t: lbl.setText(t)
    return wrap


def empty_label(text: str = "暂无数据") -> QFrame:
    """空态容器：浅色圆角底卡 + 居中说明，比裸灰字更有"区域感"。"""
    f = QFrame()
    f.setStyleSheet(
        f"QFrame#empty{{background:#f6f1f1;border:1px dashed {Color.BORDER};"
        f"border-radius:{Radius.LG}px;padding:{_scaled(40)}px {_scaled(24)}px;}}"
    )
    el = QVBoxLayout(f)
    el.setContentsMargins(0, 0, 0, 0)
    el.setSpacing(_scaled(8))
    icon = QLabel("🗂")
    icon.setStyleSheet(f"font-size:{_scaled(30)}px;background:transparent;")
    icon.setAlignment(Qt.AlignCenter)
    el.addWidget(icon)
    l = QLabel(text)
    l.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:{_scaled(21)}px;background:transparent;")
    l.setAlignment(Qt.AlignCenter)
    l.setWordWrap(True)
    el.addWidget(l)
    return f


def divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color:{Color.BORDER};background:{Color.BORDER};max-height:1px;")
    return line


def progress_bar(value: int = 0, maximum: int = 100,
                 color: str = Color.PRIMARY, height: int = None) -> "QProgressBar":
    """统一进度条工厂：track/chunk 圆角与高度一致，三处复用。

    height 缺省时按屏幕缩放（基准 14px）。
    """
    from PyQt5.QtWidgets import QProgressBar
    if height is None:
        height = _scaled(14)
    else:
        height = _scaled(height)
    bar = QProgressBar()
    bar.setMaximum(maximum)
    bar.setValue(value)
    bar.setTextVisible(False)
    bar.setStyleSheet(
        f"QProgressBar{{border:none;border-radius:{height // 2}px;"
        f"background:#f0e8e8;height:{height}px;}}"
        f"QProgressBar::chunk{{background:{color};border-radius:{height // 2}px;}}"
    )
    return bar


def chip(text: str, color: str = Color.PRIMARY, bg: str = Color.PRIMARY_SOFT) -> QLabel:
    """附件/标签小圆片：圆角柔和底 + 主色文字，靠 background 着色。

    返回 QLabel（QWidget 子类），样式仅作用于自身，遵守铁律。
    """
    l = QLabel(text)
    l.setStyleSheet(
        f"background:{bg};color:{color};border-radius:{Radius.PILL}px;"
        f"padding:{_scaled(6)}px {_scaled(14)}px;font-size:{_scaled(18)}px;font-weight:500;"
    )
    l.setAlignment(Qt.AlignCenter)
    return l
