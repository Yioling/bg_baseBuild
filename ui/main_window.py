"""主窗口骨架：侧边栏导航 + 页面路由 + 通知红点。

页面构建逻辑分散在各角色 Mixin（ui/master.py、ui/apprentice.py、ui/admin.py、
ui/social.py、ui/notify.py、ui/progress.py），本文件只负责装配。
"""
import logging
import os
import requests

_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "p5output", "app_debug.log")
try:
    os.makedirs(os.path.dirname(_log_path), exist_ok=True)
    _fh = logging.FileHandler(_log_path, encoding="utf-8")
except OSError:
    _fh = None

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s][%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ui.main_window")
if _fh is not None:
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(name)s: %(message)s",
                                       datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(_fh)

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QStackedWidget, QScrollArea, QButtonGroup, QFrame,
)

from ui.api import ApiMixin, BASE_URL
from ui.theme import GLOBAL_QSS, SIDEBAR_QSS, Color, title_label, subtitle_label
from ui.master import MasterPagesMixin
from ui.apprentice import ApprenticePagesMixin
from ui.admin import AdminPagesMixin
from ui.social import SocialPagesMixin
from ui.notify import NotifyPagesMixin
from ui.progress import ProgressPagesMixin

# pid -> (侧边栏文案, 页面标题, 副标题)
PAGE_META = {
    "admin_overview": ("📊  概览", "管理员概览", "公司整体运行指标一览"),
    "admin_pending": ("🔍  审核注册", "审核注册", "审批新注册的师傅 / 管理员账号"),
    "admin_courses": ("📚  课程库", "课程库管理", "维护公司统一课程资源"),
    "admin_users": ("👥  用户管理", "用户管理", "公司全员列表与师徒关系维护"),
    "admin_departments": ("🏢  部门管理", "部门管理", "维护公司部门结构"),
    "admin_logs": ("🧾  操作日志", "操作日志", "管理员关键操作审计记录"),
    "admin_progress": ("📈  进度视图", "公司进度", "全公司徒弟学习进度排行"),
    "master_overview": ("📊  概览", "师傅概览", "知识库与徒弟培养一览"),
    "master_ingest": ("📥  投喂资料", "投喂资料", "上传本地资料或抓取博客，构建专属知识库"),
    "master_knowledge": ("🧠  知识库", "知识库管理", "AI 精炼生成知识维度与考点树"),
    "master_library": ("📖  公共资料库", "公司公共资料库", "查看管理员维护的公司统一预置课程资源"),
    "master_apprentices": ("👥  徒弟管理", "徒弟管理", "创建徒弟账号并生成学习计划"),
    "master_plans": ("📝  定制计划", "定制培养计划", "从课程库勾选课程，为徒弟定制培养路径"),
    "master_grading": ("✅  批改检测", "批改检测", "查看徒弟检测提交，终评改分与进度判定"),
    "master_dashboard": ("📋  学情看板", "学情看板", "追踪徒弟知识掌握与考核情况"),
    "progress_view": ("📈  进度排名", "进度排名", "公司 / 部门 / 同门三视图"),
    "social_posts": ("💬  交流圈", "交流圈", "发帖、评论、点赞，与同事交流心得"),
    "notifications": ("🔔  通知", "通知中心", "系统通知与提醒"),
    "appr_overview": ("📊  概览", "学习概览", "个人学习进展一览"),
    "appr_assess": ("📝  摸底考试", "摸底考试", "AI 基于师傅知识库评估你的知识水平"),
    "appr_plan": ("📅  学习计划", "今日学习计划", "AI 排课 + PDF 讲义 + 陪练答疑"),
    "appr_review": ("🔄  当日复习", "当日复习", "基于今日所学生成复习题"),
    "appr_mistakes": ("📕  错题本", "错题本", "沉淀所有考试与复习错题"),
    "appr_leaderboard": ("🏆  同门战况", "同门战况", "和师兄弟们比一比"),
    "appr_my_plans": ("📋  我的计划", "我的培养计划", "师傅定制的课程计划与任务检测"),
}

ROLE_PAGES = {
    "admin": [
        "admin_overview", "admin_pending", "admin_courses", "admin_users",
        "admin_departments", "admin_logs", "admin_progress",
        "social_posts", "notifications",
    ],
    "master": [
        "master_overview", "master_ingest", "master_knowledge", "master_library",
        "master_apprentices", "master_plans", "master_grading",
        "master_dashboard", "progress_view", "social_posts", "notifications",
    ],
    "apprentice": [
        "appr_overview", "appr_assess", "appr_plan", "appr_review",
        "appr_mistakes", "appr_leaderboard", "appr_my_plans",
        "progress_view", "social_posts", "notifications",
    ],
}


class MainWindow(
    ApiMixin,
    MasterPagesMixin, ApprenticePagesMixin, AdminPagesMixin,
    SocialPagesMixin, NotifyPagesMixin, ProgressPagesMixin,
    QMainWindow,
):
    def __init__(self, token, user):
        super().__init__()
        self.token = token
        self.user = user
        self.setWindowTitle("薪火 · 师傅带徒 AI 导师系统")
        self.resize(1520, 940)
        self.setMinimumSize(1200, 780)
        self.setStyleSheet(GLOBAL_QSS)
        self._init_ui()
        self._refresh_notify_badge()

    # ---------- 装配 ----------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        hbox = QHBoxLayout(central)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        role = self.user.get("role", "apprentice")
        page_ids = ROLE_PAGES.get(role, ROLE_PAGES["apprentice"])

        hbox.addWidget(self._build_sidebar(page_ids))

        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        self.pages = {}
        self._page_inners = {}
        for pid in page_ids:
            page = self._create_page(pid)
            self.pages[pid] = page
            self.stack.addWidget(page)
        hbox.addWidget(self.stack, 1)

        if self.sidebar_btns:
            self.sidebar_btns[0].setChecked(True)
            self._switch_page(page_ids[0])

    def _build_sidebar(self, page_ids) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(SIDEBAR_QSS)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        logo = QLabel("🔥  薪火")
        logo.setObjectName("logo")
        lay.addWidget(logo)
        logo_sub = QLabel("师傅带徒 · AI 导师系统")
        logo_sub.setObjectName("logoSub")
        lay.addWidget(logo_sub)

        self.sidebar_btns = []
        self.nav_btn_map = {}
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        for pid in page_ids:
            btn = QPushButton(PAGE_META[pid][0])
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, p=pid: self._switch_page(p))
            self.btn_group.addButton(btn)
            lay.addWidget(btn)
            self.sidebar_btns.append(btn)
            self.nav_btn_map[pid] = btn

        lay.addStretch()

        role_names = {"admin": "管理员", "master": "师傅", "apprentice": "徒弟"}
        display = self.user.get("full_name") or self.user.get("username", "")
        role_text = role_names.get(self.user.get("role"), self.user.get("role") or "")

        info = QWidget()
        info.setObjectName("userinfo")
        info_lay = QHBoxLayout(info)
        info_lay.setContentsMargins(32, 10, 32, 10)
        info_lay.setSpacing(12)

        avatar = QLabel("👤")
        avatar.setObjectName("userAvatar")
        avatar.setFixedWidth(34)
        avatar.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        info_lay.addWidget(avatar, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        name_lbl = QLabel(display)
        name_lbl.setObjectName("userName")
        name_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        role_lbl = QLabel(role_text)
        role_lbl.setObjectName("userRole")
        role_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_col.addWidget(name_lbl)
        text_col.addWidget(role_lbl)
        info_lay.addLayout(text_col, 1)

        lay.addWidget(info)

        logout = QPushButton("🚪  退出登录")
        logout.setObjectName("logoutBtn")
        logout.clicked.connect(self._logout)
        lay.addWidget(logout)
        return sidebar

    # ---------- 页面路由 ----------
    def _create_page(self, pid):
        """构建单页：固定头部(标题+副标题) + 紧贴其下的可滚动画布(pageInner)。

        副标题(15.5px/灰)常驻顶部不随滚动；QScrollArea 无边框透明、紧贴副标题下沿；
        pageInner 内 QVBoxLayout 从上向下排布，底部 addStretch(1) 贴顶。
        """
        page = QWidget()
        page.setStyleSheet(f"background: {Color.BG};")
        v = QVBoxLayout(page)
        v.setContentsMargins(52, 28, 52, 20)
        v.setSpacing(8)

        _, page_title, page_sub = PAGE_META[pid]
        v.addWidget(title_label(page_title))
        v.addWidget(subtitle_label(page_sub))

        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")

        inner = QWidget()
        inner.setObjectName("pageInner")
        inner.setProperty("pageId", pid)
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 14, 0, 0)
        il.setSpacing(20)
        scroll.setWidget(inner)

        v.addWidget(scroll, 1)
        self._page_inners[pid] = inner
        return page

    def _switch_page(self, pid):
        self.stack.setCurrentWidget(self.pages[pid])
        if pid in self.nav_btn_map:
            self.nav_btn_map[pid].setChecked(True)
        self._load_page(pid)

    def _load_page(self, pid):
        inner = self._page_inners[pid]
        layout = inner.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

        builders = {
            "admin_overview": self._build_admin_overview,
            "admin_pending": self._build_admin_pending,
            "admin_courses": self._build_admin_courses,
            "admin_users": self._build_admin_users,
            "admin_departments": self._build_admin_departments,
            "admin_logs": self._build_admin_logs,
            "admin_progress": self._build_progress_view,
            "master_overview": self._build_master_overview,
            "master_ingest": self._build_master_ingest,
            "master_knowledge": self._build_master_knowledge,
            "master_library": self._build_master_library,
            "master_apprentices": self._build_master_apprentices,
            "master_plans": self._build_master_plans,
            "master_grading": self._build_master_grading,
            "master_dashboard": self._build_master_dashboard,
            "progress_view": self._build_progress_view,
            "social_posts": self._build_social_posts,
            "notifications": self._build_notifications,
            "appr_overview": self._build_appr_overview,
            "appr_assess": self._build_appr_assess,
            "appr_plan": self._build_appr_plan,
            "appr_review": self._build_appr_review,
            "appr_mistakes": self._build_appr_mistakes,
            "appr_leaderboard": self._build_appr_leaderboard,
            "appr_my_plans": self._build_appr_my_plans,
        }
        if pid in builders:
            logger.debug("开始构建页面 pid=%s", pid)
            try:
                builders[pid](layout, inner)
                logger.debug("页面构建完成 pid=%s", pid)
            except Exception as e:
                logger.exception("构建页面 pid=%s 时抛出异常: %r", pid, e)
                layout.addWidget(QLabel(f"⚠ 页面构建异常: {e}"))
        else:
            logger.warning("无对应构建器 pid=%s", pid)
        layout.addStretch()

    @staticmethod
    def _clear_sub_layout(sub):
        while sub.count():
            item = sub.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                MainWindow._clear_sub_layout(item.layout())

    # ---------- 通知红点 ----------
    def _refresh_notify_badge(self):
        def on_res(res):
            btn = self.nav_btn_map.get("notifications")
            if not btn:
                return
            unread = res.get("unread_count", 0) if res.get("success") else 0
            btn.setText(f"🔔  通知  ({unread})" if unread else "🔔  通知")

        self._api_call("GET", f"{BASE_URL}/api/notifications", callback=on_res)

    # ---------- 登出 ----------
    def _logout(self):
        try:
            requests.post(f"{BASE_URL}/api/logout",
                          headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
        except requests.RequestException:
            pass
        self.close()
