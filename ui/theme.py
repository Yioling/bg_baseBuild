"""huashu-design 设计系统：设计令牌、全局样式表、通用组件工厂。

主题：红白（品牌红 + 纯净白），大字号、大留白、大气排版。

铁律：本模块导出的所有工厂函数一律返回 QWidget（含子类），
      任何 setStyleSheet 只作用于 QWidget，绝不作用于 QLayout。
"""
from PyQt5.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


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

/* 主按钮 */
QPushButton {{
    background-color: {Color.PRIMARY};
    color: white;
    border: none;
    border-radius: {Radius.SM}px;
    padding: 12px 24px;
    font-size: 15px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {Color.PRIMARY_HOVER}; }}
QPushButton:pressed {{ background-color: {Color.PRIMARY_PRESSED}; }}
QPushButton:disabled {{ background-color: #c8bcbc; }}

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
    padding: 8px 12px;
}}
QPushButton#btnGhost:hover {{ color: {Color.PRIMARY_HOVER}; }}
QPushButton#btnSuccess {{ background-color: {Color.SUCCESS}; }}
QPushButton#btnSuccess:hover {{ background-color: #059669; }}
QPushButton#btnDanger {{ background-color: #991b1b; }}
QPushButton#btnDanger:hover {{ background-color: #7f1616; }}

/* 输入控件 */
QLineEdit, QTextEdit, QComboBox {{
    border: 1.5px solid #e0d4d4;
    border-radius: {Radius.SM}px;
    padding: 11px 14px;
    font-size: 15px;
    background: white;
    color: {Color.TEXT};
    selection-background-color: {Color.PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {Color.PRIMARY};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {Color.BORDER};
    background: white;
    font-size: 15px;
    selection-background-color: {Color.PRIMARY_SOFT};
    selection-color: {Color.TEXT};
    outline: none;
}}

/* 文字标题 */
QLabel#pageTitle {{ font-size: 30px; font-weight: 800; color: {Color.TEXT}; }}
QLabel#pageSubtitle {{ font-size: 15.5px; color: {Color.TEXT_SUB}; }}
QLabel#sectionTitle {{ font-size: 18px; font-weight: 700; color: #2b2323; }}

/* 表格 */
QTableWidget {{
    border: 1px solid {Color.BORDER};
    border-radius: {Radius.MD}px;
    gridline-color: #f6efef;
    background: white;
    font-size: 14.5px;
    alternate-background-color: #fdfafa;
}}
QTableWidget::item {{ padding: 11px; }}
QHeaderView::section {{
    background: #faf5f5;
    border: none;
    border-bottom: 2px solid {Color.BORDER};
    padding: 12px;
    font-weight: 700;
    font-size: 14px;
    color: {Color.TEXT_SUB};
}}

/* 进度条 */
QProgressBar {{
    border: none;
    border-radius: 6px;
    background: #f0e8e8;
    height: 12px;
    text-align: center;
    font-size: 11px;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {Color.PRIMARY};
    border-radius: 6px;
}}

/* GroupBox 作为卡片容器 */
QGroupBox {{
    font-weight: 700;
    font-size: 16px;
    color: {Color.TEXT};
    border: 1px solid {Color.BORDER};
    border-radius: {Radius.LG}px;
    margin-top: 16px;
    padding: 22px 20px 20px 20px;
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
QRadioButton, QCheckBox {{ font-size: 15px; color: {Color.TEXT}; spacing: 10px; padding: 4px 0; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
"""

# 侧边栏专属样式（作用于 objectName == sidebar 的 QWidget）
SIDEBAR_QSS = f"""
QWidget#sidebar {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {Color.SIDEBAR}, stop:1 {Color.SIDEBAR_DEEP});
    min-width: 252px;
    max-width: 252px;
}}
QWidget#sidebar QPushButton {{
    color: #f3cfcf;
    background: transparent;
    border: none;
    text-align: left;
    padding: 14px 26px;
    font-size: 15px;
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
    font-size: 24px;
    font-weight: 800;
    padding: 28px 26px 8px 26px;
}}
QLabel#logoSub {{
    color: #e8b6b6;
    font-size: 12.5px;
    padding: 0 26px 16px 26px;
}}
QLabel#userinfo {{
    color: #f0c4c4;
    font-size: 13.5px;
    padding: 12px 26px;
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


def card(accent: str = None, padding: int = 20) -> QFrame:
    """标准白色卡片容器。返回 QFrame（QWidget 子类），可安全 setStyleSheet。"""
    f = QFrame()
    f.setObjectName("card")
    border_left = f"border-left:4px solid {accent};" if accent else ""
    f.setStyleSheet(
        f"QFrame#card{{background:{Color.SURFACE};border:1px solid {Color.BORDER};"
        f"border-radius:{Radius.LG}px;padding:{padding}px;{border_left}}}"
    )
    return f


def stat_card(value: str, label: str, color: str = Color.PRIMARY) -> QFrame:
    """指标卡：大数字 + 说明文字。"""
    f = card(accent=color, padding=22)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(8, 8, 8, 8)
    lay.setSpacing(8)
    v = QLabel(str(value))
    v.setStyleSheet(f"font-size:38px;font-weight:800;color:{color};")
    v.setAlignment(Qt.AlignCenter)
    lay.addWidget(v)
    l = QLabel(label)
    l.setStyleSheet(f"font-size:15px;color:{Color.TEXT_SUB};font-weight:500;")
    l.setAlignment(Qt.AlignCenter)
    lay.addWidget(l)
    apply_shadow(f, blur=18, dy=4, alpha=18)
    return f


def title_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("pageTitle")
    return l


def subtitle_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("pageSubtitle")
    l.setWordWrap(True)
    return l


def section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("sectionTitle")
    return l


def hint_label(text: str, color: str = Color.TEXT_SUB) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{color};font-size:14px;")
    l.setWordWrap(True)
    return l


def badge(text: str, color: str = Color.PRIMARY, bg: str = Color.PRIMARY_SOFT) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"background:{bg};color:{color};border-radius:{Radius.PILL}px;"
        f"padding:3px 12px;font-size:12.5px;font-weight:600;"
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
        "padding:12px 24px;"
        "font-size:15px;"
        "font-weight:600;"
        "}"
        f"QPushButton#btnIngest:hover{{background:{Color.PRIMARY_SOFT};}}"
        f"QPushButton#btnIngest:pressed{{border-color:{Color.PRIMARY_HOVER};color:{Color.PRIMARY_HOVER};}}"
        "QPushButton#btnIngest:disabled{color:#c8bcbc;border-color:#e0d4d4;}"
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


def loading_label(text: str = "加载中...") -> QLabel:
    l = QLabel(f"⏳ {text}")
    l.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:16px;padding:28px;")
    l.setAlignment(Qt.AlignCenter)
    return l


def empty_label(text: str = "暂无数据") -> QLabel:
    l = QLabel(f"🗂  {text}")
    l.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:16px;padding:32px;")
    l.setAlignment(Qt.AlignCenter)
    return l


def divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color:{Color.BORDER};background:{Color.BORDER};max-height:1px;")
    return line
