"""薪火 AI 导师系统 — PyQt5 桌面应用"""
import sys
import os
import json
import threading
import asyncio
import requests
import shutil
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QStackedWidget, QFrame,
    QScrollArea, QTextEdit, QProgressBar, QMessageBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QRadioButton,
    QButtonGroup, QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
    QSplitter, QDialog, QFileDialog, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter

SERVER_PORT = 8000
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"

# ==================== 样式表 ====================
STYLE = """
QMainWindow, QDialog {
    background-color: #f0f2f5;
}
QWidget#sidebar {
    background-color: #1a1a2e;
    min-width: 200px;
    max-width: 200px;
}
QWidget#sidebar QPushButton {
    color: #a0a8c0;
    background: transparent;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
    border-left: 3px solid transparent;
}
QWidget#sidebar QPushButton:hover {
    background: rgba(255,255,255,0.08);
    color: #ffffff;
}
QWidget#sidebar QPushButton:checked {
    background: rgba(37,99,235,0.2);
    color: #ffffff;
    border-left: 3px solid #2563eb;
}
QWidget#sidebar QLabel#logo {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    padding: 20px;
}
QWidget#sidebar QLabel#userinfo {
    color: #6b7280;
    font-size: 12px;
    padding: 10px 20px;
}
QWidget#content {
    background-color: #f7f8fa;
}
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #9ca3af;
}
QPushButton#btnSecondary {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #d1d5db;
}
QPushButton#btnSecondary:hover {
    background-color: #f3f4f6;
}
QPushButton#btnDanger {
    background-color: #ef4444;
}
QPushButton#btnDanger:hover {
    background-color: #dc2626;
}
QLineEdit, QTextEdit, QComboBox {
    border: 1.5px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    background: white;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #2563eb;
}
QLabel#pageTitle {
    font-size: 22px;
    font-weight: bold;
    color: #111827;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: bold;
    color: #1f2937;
    margin-top: 8px;
}
QTableWidget {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    gridline-color: #f3f4f6;
    background: white;
    alternate-background-color: #f9fafb;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background: #f9fafb;
    border: none;
    border-bottom: 2px solid #e5e7eb;
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
    color: #6b7280;
}
QScrollArea {
    border: none;
    background: transparent;
}
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #e5e7eb;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 4px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    background: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}
"""

# ==================== HTTP 线程 ====================
class ApiThread(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, method, url, body=None, token=None):
        super().__init__()
        self.method = method
        self.url = url
        self.body = body
        self.token = token

    def run(self):
        try:
            headers = {'Content-Type': 'application/json'}
            if self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            # 带重试的连接
            r = None
            for attempt in range(5):
                try:
                    if self.method == 'GET':
                        r = requests.get(self.url, headers=headers, timeout=30)
                    elif self.method == 'POST':
                        r = requests.post(self.url, json=self.body, headers=headers, timeout=30)
                    elif self.method == 'PUT':
                        r = requests.put(self.url, json=self.body, headers=headers, timeout=30)
                    else:
                        self.finished.emit({'success': False, 'message': 'Unknown method'})
                        return
                    break
                except requests.exceptions.ConnectionError:
                    if attempt < 4:
                        import time
                        time.sleep(1)
                        continue
                    raise
            if r is None:
                self.finished.emit({'success': False, 'message': '无法连接到服务器，请稍后重试'})
                return
            ct = r.headers.get('content-type', '')
            if 'application/json' in ct:
                self.finished.emit(r.json())
            elif 'application/pdf' in ct:
                # 保存到桌面
                desktop = Path.home() / 'Desktop'
                fname = f'薪火讲义_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                fpath = desktop / fname
                fpath.write_bytes(r.content)
                os.startfile(str(fpath))
                self.finished.emit({'success': True, 'message': f'PDF已保存到桌面: {fname}', 'path': str(fpath)})
            else:
                self.finished.emit({'success': False, 'message': r.text[:200]})
        except Exception as e:
            self.finished.emit({'success': False, 'message': str(e)})


# ==================== 登录对话框 ====================
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.token = None
        self.user = None
        self.setWindowTitle('薪火 · AI 导师系统 — 登录')
        self.setFixedSize(400, 440)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a2e; }
            QLabel { color: #e5e7eb; font-size: 13px; }
            QLineEdit { background: #16213e; color: white; border: 1px solid #334155; border-radius: 6px; padding: 10px; font-size: 14px; }
            QLineEdit:focus { border-color: #2563eb; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        layout.addWidget(QLabel('🔥  薪火 · AI 导师系统'))
        title = QLabel('🔥  薪火 · AI 导师系统')
        title.setStyleSheet('font-size:22px;font-weight:bold;color:white;')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(10)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['登录', '注册（师傅）'])
        self.mode_combo.setStyleSheet("background:#16213e;color:white;border:1px solid #334155;padding:8px;border-radius:6px;")
        layout.addWidget(self.mode_combo)
        layout.addSpacing(8)

        layout.addWidget(QLabel('用户名'))
        self.uname = QLineEdit()
        self.uname.setPlaceholderText('输入用户名')
        layout.addWidget(self.uname)

        layout.addWidget(QLabel('密码'))
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setPlaceholderText('输入密码')
        layout.addWidget(self.pwd)

        layout.addSpacing(8)

        self.msg = QLabel('')
        self.msg.setStyleSheet('color:#fca5a5;font-size:12px;')
        self.msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.msg)

        self.btn = QPushButton('登录')
        self.btn.setStyleSheet("""
            QPushButton { background: #2563eb; color: white; border-radius: 8px; padding: 12px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #4b5563; }
        """)
        self.btn.clicked.connect(self._do_auth)
        layout.addWidget(self.btn)

    def _do_auth(self):
        self.btn.setEnabled(False)
        self.btn.setText('处理中...')
        self.msg.setText('')
        uname = self.uname.text().strip()
        pwd = self.pwd.text().strip()
        if not uname or not pwd:
            self.msg.setText('请填写用户名和密码')
            self.btn.setEnabled(True)
            self.btn.setText('登录')
            return
        
        if self.mode_combo.currentIndex() == 1:
            url = f'{BASE_URL}/api/register'
            body = {'username': uname, 'password': pwd, 'role': 'master'}
            self.thread = ApiThread('POST', url, body)
            self.thread.finished.connect(self._on_register)
            self.thread.start()
        else:
            url = f'{BASE_URL}/api/login'
            body = {'username': uname, 'password': pwd}
            self.thread = ApiThread('POST', url, body)
            self.thread.finished.connect(self._on_login)
            self.thread.start()

    def _on_login(self, res):
        if res.get('success'):
            self.token = res['token']
            self.user = res['user']
            self.accept()
        else:
            self.msg.setText(res.get('message', '登录失败'))
        self.btn.setEnabled(True)
        self.btn.setText('登录')

    def _on_register(self, res):
        if res.get('success'):
            self.msg.setStyleSheet('color:#6ee7b7;font-size:12px;')
            self.msg.setText('注册成功！请切换到登录模式登录')
            self.mode_combo.setCurrentIndex(0)
        else:
            self.msg.setText(res.get('message', '注册失败'))
        self.btn.setEnabled(True)
        self.btn.setText('注册')


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    def __init__(self, token, user):
        super().__init__()
        self.token = token
        self.user = user
        self._current_threads = []
        self.setWindowTitle('薪火 · 师傅带徒 AI 导师系统')
        self.resize(1100, 720)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        hbox = QHBoxLayout(central)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # ---- 侧边栏 ----
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setStyleSheet("""
            QWidget#sidebar { background: #1a1a2e; min-width: 200px; max-width: 200px; }
            QWidget#sidebar QPushButton { color: #a0a8c0; background: transparent; border: none; text-align: left; padding: 12px 20px; font-size: 13px; border-left: 3px solid transparent; }
            QWidget#sidebar QPushButton:hover { background: rgba(255,255,255,0.08); color: white; }
            QWidget#sidebar QPushButton:checked { background: rgba(37,99,235,0.2); color: white; border-left: 3px solid #2563eb; }
        """)
        slayout = QVBoxLayout(sidebar)
        slayout.setContentsMargins(0, 10, 0, 10)
        slayout.setSpacing(0)

        logo = QLabel('🔥  薪火')
        logo.setObjectName('logo')
        logo.setStyleSheet('color:white;font-size:18px;font-weight:bold;padding:20px 15px;')
        slayout.addWidget(logo)

        slayout.addSpacing(10)

        self.sidebar_btns = []
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        role = self.user['role']
        if role == 'admin':
            pages = [
                ('admin_overview', '📊  概览'),
                ('admin_pending', '🔍  审核注册'),
                ('admin_courses', '📚  课程库'),
                ('admin_users', '👥  用户管理'),
                ('admin_progress', '📈  进度视图'),
                ('social_posts', '💬  交流圈'),
                ('notifications', '🔔  通知'),
            ]
        elif role == 'master':
            pages = [
                ('master_overview', '📊  概览'),
                ('master_ingest', '📥  投喂资料'),
                ('master_knowledge', '🧠  知识库'),
                ('master_apprentices', '👥  徒弟管理'),
                ('master_plans', '📝  定制计划'),
                ('master_dashboard', '📋  学情看板'),
                ('progress_view', '📈  进度排名'),
                ('social_posts', '💬  交流圈'),
                ('notifications', '🔔  通知'),
            ]
        else:
            pages = [
                ('appr_overview', '📊  概览'),
                ('appr_assess', '📝  摸底考试'),
                ('appr_plan', '📅  学习计划'),
                ('appr_review', '🔄  当日复习'),
                ('appr_mistakes', '📕  错题本'),
                ('appr_leaderboard', '🏆  同门战况'),
                ('appr_my_plans', '📋  我的计划'),
                ('progress_view', '📈  进度排名'),
                ('social_posts', '💬  交流圈'),
                ('notifications', '🔔  通知'),
            ]

        for pid, pname in pages:
            btn = QPushButton(pname)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, p=pid: self._switch_page(p))
            self.btn_group.addButton(btn)
            slayout.addWidget(btn)
            self.sidebar_btns.append(btn)

        slayout.addStretch()

        role_names = {'admin': '管理员', 'master': '师傅', 'apprentice': '徒弟'}
        user_info = QLabel(f'👤 {self.user["username"]}\n{role_names.get(role, role)}')
        user_info.setObjectName('userinfo')
        user_info.setStyleSheet('color:#6b7280;font-size:12px;padding:10px 15px;')
        slayout.addWidget(user_info)

        logout_btn = QPushButton('🚪  退出登录')
        logout_btn.setStyleSheet('color:#ef4444!important;')
        logout_btn.clicked.connect(self._logout)
        slayout.addWidget(logout_btn)

        hbox.addWidget(sidebar)

        # ---- 内容区 ----
        self.stack = QStackedWidget()
        self.stack.setObjectName('content')
        self.pages = {}

        for pid, _ in pages:
            page = self._create_page(pid)
            self.pages[pid] = page
            self.stack.addWidget(page)

        hbox.addWidget(self.stack)

        # 默认选中第一个
        if self.sidebar_btns:
            self.sidebar_btns[0].setChecked(True)
            self._switch_page(pages[0][0])

    def _create_page(self, pid):
        """创建页面容器"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f7f8fa; }")
        container = QWidget()
        container.setStyleSheet("background: #f7f8fa;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        # 存储页面ID
        container.setProperty('pageId', pid)
        scroll.setWidget(container)
        return scroll

    def _switch_page(self, pid):
        self.stack.setCurrentWidget(self.pages[pid])
        self._load_page(pid)

    def _load_page(self, pid):
        """加载页面内容"""
        container = self.pages[pid].widget()
        layout = container.layout()
        # 清除旧内容
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        title_map = {
            'admin_overview': '📊 管理员概览', 'admin_pending': '🔍 审核注册',
            'admin_courses': '📚 课程库管理', 'admin_users': '👥 用户管理',
            'admin_progress': '📈 公司进度',
            'master_overview': '📊 师傅概览', 'master_ingest': '📥 投喂资料',
            'master_knowledge': '🧠 知识库管理', 'master_apprentices': '👥 徒弟管理',
            'master_plans': '📝 定制计划', 'master_dashboard': '📋 学情看板',
            'progress_view': '📈 进度排名',
            'social_posts': '💬 交流圈', 'notifications': '🔔 通知中心',
            'appr_overview': '📊 学习概览', 'appr_assess': '📝 摸底考试',
            'appr_plan': '📅 学习计划', 'appr_review': '🔄 当日复习',
            'appr_mistakes': '📕 错题本', 'appr_leaderboard': '🏆 同门战况',
            'appr_my_plans': '📋 我的计划',
        }
        title = QLabel(title_map.get(pid, pid))
        title.setObjectName('pageTitle')
        title.setStyleSheet('font-size:22px;font-weight:bold;color:#111827;margin-bottom:8px;')
        layout.addWidget(title)

        # 根据不同页面调用构建函数
        builders = {
            'admin_overview': self._build_admin_overview,
            'admin_pending': self._build_admin_pending,
            'admin_courses': self._build_admin_courses,
            'admin_users': self._build_admin_users,
            'admin_progress': self._build_progress_view,
            'master_overview': self._build_master_overview,
            'master_ingest': self._build_master_ingest,
            'master_knowledge': self._build_master_knowledge,
            'master_apprentices': self._build_master_apprentices,
            'master_plans': self._build_master_plans,
            'master_dashboard': self._build_master_dashboard,
            'progress_view': self._build_progress_view,
            'social_posts': self._build_social_posts,
            'notifications': self._build_notifications,
            'appr_overview': self._build_appr_overview,
            'appr_assess': self._build_appr_assess,
            'appr_plan': self._build_appr_plan,
            'appr_review': self._build_appr_review,
            'appr_mistakes': self._build_appr_mistakes,
            'appr_leaderboard': self._build_appr_leaderboard,
            'appr_my_plans': self._build_appr_my_plans,
        }
        if pid in builders:
            builders[pid](layout, container)

        layout.addStretch()

    def _api_call(self, method, url, body=None, callback=None):
        """发起 API 调用"""
        thread = ApiThread(method, url, body, self.token)
        if callback:
            thread.finished.connect(callback)
        thread.start()
        self._current_threads.append(thread)
        return thread

    def _show_loading(self, text='加载中...'):
        lbl = QLabel(f'⏳ {text}')
        lbl.setStyleSheet('color:#6b7280;font-size:14px;padding:20px;')
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    # ==================== 师傅页面 ====================
    def _build_master_overview(self, layout, container):
        loading = self._show_loading()
        layout.addWidget(loading)

        def on_knowledge(res):
            loading.hide()
            dim_count = len(res.get('dimensions', [])) if res.get('success') else 0
            pt_count = sum(len(d.get('points', [])) for d in res.get('dimensions', [])) if res.get('success') else 0

            self._api_call('GET', f'{BASE_URL}/api/master/apprentices', callback=lambda r: _on_appr(r, dim_count, pt_count))

        def _on_appr(res, dim_count, pt_count):
            app_count = len(res.get('apprentices', [])) if res.get('success') else 0
            grid = QGridLayout()
            cards = [
                (str(dim_count), '知识维度', '#2563eb', '#eff6ff'),
                (str(pt_count), '知识点', '#10b981', '#ecfdf5'),
                (str(app_count), '徒弟数量', '#f59e0b', '#fffbeb'),
                ('v2.0', '桌面版', '#ef4444', '#fef2f2'),
            ]
            for i, (val, lbl, color, bg) in enumerate(cards):
                card = QFrame()
                card.setStyleSheet(f'background:white;border-radius:10px;padding:16px;border:1px solid #e5e7eb;border-left:3px solid {color};')
                cl = QVBoxLayout(card)
                vl = QLabel(val)
                vl.setStyleSheet(f'font-size:28px;font-weight:800;color:{color};')
                vl.setAlignment(Qt.AlignCenter)
                cl.addWidget(vl)
                ll = QLabel(lbl)
                ll.setStyleSheet('font-size:13px;color:#6b7280;')
                ll.setAlignment(Qt.AlignCenter)
                cl.addWidget(ll)
                grid.addWidget(card, 0, i)
            layout.addLayout(grid)

            # 快速操作
            guide = QGroupBox('🚀 快速操作')
            gl = QVBoxLayout(guide)
            steps = [
                '1. 投喂资料 → 上传本地文档或博客URL',
                '2. AI精炼 → 自动生成知识维度与考点树',
                '3. 创建徒弟 → 为学徒注册账号',
                '4. 生成计划 → AI 自动排课',
                '5. 学情看板 → 追踪徒弟学习进展',
            ]
            for s in steps:
                gl.addWidget(QLabel(s))
            layout.addWidget(guide)

        self._api_call('GET', f'{BASE_URL}/api/master/knowledge', callback=on_knowledge)

    def _build_master_ingest(self, layout, container):
        # 本地路径
        g1 = QGroupBox('📁 本地文件夹投喂')
        g1l = QVBoxLayout(g1)
        g1l.addWidget(QLabel('输入包含 md/txt/pdf/docx/代码的文件夹路径'))
        path_input = QLineEdit()
        path_input.setPlaceholderText('例如: C:\\Users\\TS\\Desktop\\入职学习')
        g1l.addWidget(path_input)
        msg1 = QLabel('')
        g1l.addWidget(msg1)

        def ingest_path():
            p = path_input.text().strip()
            if not p:
                msg1.setText('请输入路径')
                return
            msg1.setText('⏳ 正在摄入...')
            self._api_call('POST', f'{BASE_URL}/api/master/ingest', {'path': p},
                          callback=lambda r: msg1.setText(f'{"✅" if r.get("success") else "❌"} {r.get("message")}'))
        btn1 = QPushButton('开始投喂')
        btn1.clicked.connect(ingest_path)
        g1l.addWidget(btn1)
        layout.addWidget(g1)

        # URL
        g2 = QGroupBox('🌐 博客URL投喂')
        g2l = QVBoxLayout(g2)
        g2l.addWidget(QLabel('输入公开网页URL（每行一个）'))
        url_input = QTextEdit()
        url_input.setPlaceholderText('https://example.com/article1\nhttps://example.com/article2')
        url_input.setMaximumHeight(100)
        g2l.addWidget(url_input)
        msg2 = QLabel('')
        g2l.addWidget(msg2)

        def ingest_url():
            urls = [u.strip() for u in url_input.toPlainText().split('\n') if u.strip()]
            if not urls:
                msg2.setText('请输入URL')
                return
            msg2.setText('⏳ 正在抓取网页...')
            self._api_call('POST', f'{BASE_URL}/api/master/ingest/url', {'urls': urls},
                          callback=lambda r: msg2.setText(f'{"✅" if r.get("success") else "❌"} {r.get("message")}'))
        btn2 = QPushButton('抓取并投喂')
        btn2.clicked.connect(ingest_url)
        g2l.addWidget(btn2)
        layout.addWidget(g2)

        # 示例
        g3 = QGroupBox('🎯 快速演示')
        g3l = QVBoxLayout(g3)
        g3l.addWidget(QLabel('使用内置的"智能订单交易系统"示例知识库'))
        btn3 = QPushButton('加载示例知识库')
        btn3.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/master/ingest', {'path': 'backend/data/sample_kb'},
                          callback=lambda r: QMessageBox.information(self, '结果', r.get('message', ''))))
        g3l.addWidget(btn3)
        layout.addWidget(g3)

    def _build_master_knowledge(self, layout, container):
        loading = self._show_loading('加载知识库...')
        layout.addWidget(loading)

        refine_btn = QPushButton('🧪 触发 AI 精炼')
        refine_btn.setStyleSheet('background:#10b981;font-size:15px;padding:12px;')
        layout.addWidget(refine_btn)
        hint = QLabel('投喂资料后点击此按钮，AI自动生成知识维度与考点树')
        hint.setStyleSheet('color:#6b7280;font-size:12px;')
        layout.addWidget(hint)

        result_area = QVBoxLayout()
        layout.addLayout(result_area)

        def show_knowledge(res):
            loading.hide()
            # 清除旧结果
            while result_area.count():
                item = result_area.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            if not res.get('success') or not res.get('dimensions'):
                result_area.addWidget(QLabel('暂无知识库内容，请先投喂资料再精炼'))
                return
            for d in res['dimensions']:
                df = QFrame()
                df.setStyleSheet('background:white;border-radius:8px;padding:12px;margin:4px 0;border-left:3px solid #2563eb;')
                dl = QVBoxLayout(df)
                dl.addWidget(QLabel(d['name']))
                dl.setStyleSheet('font-weight:bold;')
                dl_desc = QLabel(d.get('description', ''))
                dl_desc.setStyleSheet('color:#6b7280;font-size:12px;')
                dl_desc.setWordWrap(True)
                dl.addWidget(dl_desc)
                for p in d.get('points', []):
                    dl.addWidget(QLabel(f'  • {p["title"]} [{p.get("level","")}]'))
                dl.setStyleSheet('font-size:13px;')
                result_area.addWidget(df)

        self._api_call('GET', f'{BASE_URL}/api/master/knowledge', callback=show_knowledge)

        refine_btn.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/master/refine', {}, callback=show_knowledge))

    def _build_master_apprentices(self, layout, container):
        # 创建
        g = QGroupBox('➕ 创建徒弟账号')
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel('用户名'))
        u = QLineEdit()
        gl.addWidget(u)
        gl.addWidget(QLabel('密码'))
        p = QLineEdit()
        p.setEchoMode(QLineEdit.Password)
        gl.addWidget(p)
        msg = QLabel('')
        gl.addWidget(msg)

        def create():
            if not u.text().strip() or not p.text().strip():
                msg.setText('请填写完整')
                return
            self._api_call('POST', f'{BASE_URL}/api/master/apprentices',
                          {'username': u.text().strip(), 'password': p.text().strip()},
                          callback=lambda r: [msg.setText(f'{"✅" if r.get("success") else "❌"} {r.get("message")}'),
                                             self._load_page('master_apprentices') if r.get('success') else None])
        btn = QPushButton('创建徒弟')
        btn.clicked.connect(create)
        gl.addWidget(btn)
        layout.addWidget(g)

        # 列表
        loading = self._show_loading()
        layout.addWidget(loading)

        def show_list(res):
            loading.hide()
            apps = res.get('apprentices', [])
            if not apps:
                layout.addWidget(QLabel('暂无徒弟'))
                return
            tbl = QTableWidget()
            tbl.setColumnCount(3)
            tbl.setHorizontalHeaderLabels(['用户名', '创建时间', '操作'])
            tbl.setRowCount(len(apps))
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.setAlternatingRowColors(True)
            for i, a in enumerate(apps):
                tbl.setItem(i, 0, QTableWidgetItem(a['username']))
                tbl.setItem(i, 1, QTableWidgetItem(str(a.get('created_at', '-'))))
                pb = QPushButton('生成计划')
                pb.clicked.connect(lambda checked, aid=a['id']: self._gen_plan(aid))
                tbl.setCellWidget(i, 2, pb)
            tbl.setMaximumHeight(300)
            layout.addWidget(tbl)

        self._api_call('GET', f'{BASE_URL}/api/master/apprentices', callback=show_list)

    def _gen_plan(self, appr_id):
        self._api_call('POST', f'{BASE_URL}/api/master/plan/generate', {'apprentice_id': appr_id},
                      callback=lambda r: QMessageBox.information(self, '结果', r.get('message', '')))

    def _build_master_dashboard(self, layout, container):
        loading = self._show_loading()
        layout.addWidget(loading)

        def show_apprentices(res):
            loading.hide()
            apps = res.get('apprentices', [])
            if not apps:
                layout.addWidget(QLabel('暂无徒弟'))
                return
            layout.addWidget(QLabel('选择要查看的徒弟：'))
            sel = QComboBox()
            sel.addItem('-- 选择徒弟 --', 0)
            for a in apps:
                sel.addItem(a['username'], a['id'])
            layout.addWidget(sel)

            dash_area = QVBoxLayout()
            layout.addLayout(dash_area)

            sel.currentIndexChanged.connect(lambda idx: self._show_dashboard(sel.itemData(idx) or 0, dash_area))

        self._api_call('GET', f'{BASE_URL}/api/master/apprentices', callback=show_apprentices)

    def _show_dashboard(self, appr_id, area):
        while area.count():
            item = area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not appr_id:
            return
        loading = self._show_loading()
        area.addWidget(loading)

        def show(res):
            loading.hide()
            if not res.get('success'):
                area.addWidget(QLabel('加载失败'))
                return
            mastery = res.get('mastery', [])
            if mastery:
                tlabel = QLabel('🎯 知识掌握等级')
                tlabel.setStyleSheet('font-weight:bold;')
                area.addWidget(tlabel)
                for m in mastery:
                    pct = 90 if m['level'] == '熟练' else 50 if m['level'] == '了解' else 20
                    bar = QProgressBar()
                    bar.setMaximum(100)
                    bar.setValue(pct)
                    bar.setFormat(f'{m["dim_name"]} — {m["level"]}')
                    ml = QLabel(m.get('dim_name', '') + f' — {m["level"]}')
                    ml.setStyleSheet('color:#1f2937;font-size:13px;')
                    area.addWidget(ml)
                    area.addWidget(bar)
            else:
                el = QLabel('暂未完成摸底考试')
                el.setStyleSheet('color:#6b7280;')
                area.addWidget(el)

        self._api_call('GET', f'{BASE_URL}/api/master/dashboard/{appr_id}', callback=show)

    # ==================== 徒弟页面 ====================
    def _build_appr_overview(self, layout, container):
        guide = QGroupBox('🚀 新手上路')
        gl = QVBoxLayout(guide)
        for s in [
            '1. 摸底考试 → 让AI评估你的知识水平',
            '2. 等待师傅生成学习计划',
            '3. 按计划学习 → 下载每日PDF讲义到桌面',
            '4. 当日复习 → 检验学习成果',
            '5. 同门战况 → 看看师兄弟们的进度',
        ]:
            gl.addWidget(QLabel(s))
        layout.addWidget(guide)

        loading = self._show_loading()
        layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/apprentice/mistakes', callback=lambda r: [
            self._show_mistake_stats(loading, r, layout)
        ])

    def _show_mistake_stats(self, loading, res, layout):
        loading.hide()
        a_count = len(res.get('assess_mistakes', [])) if res.get('success') else 0
        r_count = len(res.get('review_mistakes', [])) if res.get('success') else 0
        g = QGridLayout()
        vals = [(str(a_count + r_count), '错题总数'), (f'{a_count} / {r_count}', '考试/复习错题')]
        for i, (val, lbl) in enumerate(vals):
            f = QFrame()
            f.setStyleSheet('background:white;border-radius:8px;padding:16px;border:1px solid #e5e7eb;')
            fl = QVBoxLayout(f)
            vl = QLabel(val)
            vl.setStyleSheet('font-size:28px;font-weight:800;color:#ef4444;')
            vl.setAlignment(Qt.AlignCenter)
            fl.addWidget(vl)
            ll = QLabel(lbl)
            ll.setStyleSheet('font-size:12px;color:#6b7280;')
            ll.setAlignment(Qt.AlignCenter)
            fl.addWidget(ll)
            g.addWidget(f, 0, i)
        layout.addLayout(g)

    def _build_appr_assess(self, layout, container):
        self._assess_data = getattr(self, '_assess_data', None)
        self._assess_idx = getattr(self, '_assess_idx', 0)
        self._assess_area = QVBoxLayout()
        layout.addLayout(self._assess_area)

        def refresh():
            while self._assess_area.count():
                item = self._assess_area.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            if not self._assess_data:
                layout_desc = QLabel('AI将基于师傅的知识库为你出题，涵盖各知识维度，由易到难逐步评测。')
                layout_desc.setStyleSheet('color:#6b7280;font-size:13px;')
                self._assess_area.addWidget(layout_desc)
                start_btn = QPushButton('开始摸底考试')
                start_btn.setStyleSheet('font-size:15px;padding:12px;')
                start_btn.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/apprentice/assessment/start', {},
                    callback=lambda r: self._on_assess_start(r)))
                self._assess_area.addWidget(start_btn)
            else:
                self._show_assess_question()

        refresh()

    def _on_assess_start(self, res):
        if res.get('success'):
            self._assess_data = res
            self._assess_idx = 0
            self._load_page('appr_assess')
        else:
            QMessageBox.warning(self, '错误', res.get('message', '出题失败'))

    def _show_assess_question(self):
        area = self._assess_area
        questions = self._assess_data['questions']
        if self._assess_idx >= len(questions):
            # 完成
            done_label = QLabel('🎉 摸底考试完成！')
            done_label.setStyleSheet('font-size:18px;color:#10b981;font-weight:bold;')
            area.addWidget(done_label)
            self._api_call('GET', f'{BASE_URL}/api/apprentice/assessment/result/{self._assess_data["assessment_id"]}',
                          callback=lambda r: self._show_assess_result(r, area))
            reset_btn = QPushButton('重新考试')
            reset_btn.clicked.connect(lambda: [setattr(self, '_assess_data', None), setattr(self, '_assess_idx', 0), self._load_page('appr_assess')])
            area.addWidget(reset_btn)
            return

        q = questions[self._assess_idx]
        qf = QFrame()
        qf.setStyleSheet('background:white;border-radius:10px;padding:16px;border:1px solid #e5e7eb;')
        ql = QVBoxLayout(qf)
        ql.addWidget(QLabel(f'题目 {self._assess_idx + 1} / {len(questions)}'))
        ql.addWidget(QLabel(f'[{q["difficulty"]}] [{q["qtype"]}]'))
        qt = QLabel(q['question'])
        qt.setStyleSheet('font-size:15px;font-weight:bold;')
        qt.setWordWrap(True)
        ql.addWidget(qt)

        self._answer_widget = None
        if q.get('qtype') == 'choice' and q.get('options'):
            group = QButtonGroup(self)
            opts = q['options']
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except:
                    opts = [opts]
            for opt in (opts if isinstance(opts, list) else []):
                rb = QRadioButton(opt)
                group.addButton(rb)
                ql.addWidget(rb)
            self._answer_widget = group
        else:
            te = QTextEdit()
            te.setMaximumHeight(80)
            te.setPlaceholderText('请输入你的答案...')
            ql.addWidget(te)
            self._answer_widget = te

        submit = QPushButton('提交答案')
        submit.clicked.connect(lambda: self._submit_assess(q))
        ql.addWidget(submit)
        area.addWidget(qf)

    def _submit_assess(self, q):
        answer = ''
        if isinstance(self._answer_widget, QButtonGroup):
            checked = self._answer_widget.checkedButton()
            if not checked:
                QMessageBox.warning(self, '提示', '请选择一个选项')
                return
            answer = checked.text()[0]
        else:
            answer = self._answer_widget.toPlainText().strip()
            if not answer:
                QMessageBox.warning(self, '提示', '请输入答案')
                return

        self._api_call('POST', f'{BASE_URL}/api/apprentice/assessment/answer',
                      {'question_id': q['id'], 'answer': answer},
                      callback=lambda r: self._on_assess_answer(r))

    def _on_assess_answer(self, res):
        if res.get('success'):
            fb = QLabel(f'得分: {res["score"]} | {res.get("feedback","")}\n正确答案: {res.get("answer_key","")}')
            fb.setStyleSheet(f'padding:12px;border-radius:6px;font-size:13px;')
            fb.setStyleSheet('background:#fef2f2;color:#991b1b;' if res['score'] < 60 else 'background:#ecfdf5;color:#065f46;')
            fb.setWordWrap(True)
            self._assess_area.addWidget(fb)
            self._assess_idx += 1
            next_btn = QPushButton('下一题 →')
            next_btn.clicked.connect(lambda: self._load_page('appr_assess'))
            self._assess_area.addWidget(next_btn)
        else:
            QMessageBox.warning(self, '错误', res.get('message', '提交失败'))

    def _show_assess_result(self, res, area):
        mastery = res.get('mastery', [])
        if mastery:
            tl = QLabel('📊 掌握等级')
            tl.setStyleSheet('font-weight:bold;')
            area.addWidget(tl)
            for m in mastery:
                pct = 90 if m['level'] == '熟练' else 50 if m['level'] == '了解' else 20
                bar = QProgressBar()
                bar.setMaximum(100)
                bar.setValue(pct)
                bar.setFormat(f'{m["dim_name"]} — {m["level"]}')
                ml = QLabel(m['dim_name'] + f' — {m["level"]}')
                ml.setStyleSheet('font-size:13px;')
                area.addWidget(ml)
                area.addWidget(bar)

    def _build_appr_plan(self, layout, container):
        loading = self._show_loading()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            if not res.get('success') or not res.get('today'):
                layout.addWidget(QLabel('暂无学习计划，请联系师傅为您生成。'))
                return
            today = res['today']
            tasks = today.get('tasks', [])
            df = QFrame()
            df.setStyleSheet('background:white;border-radius:10px;padding:16px;border:1px solid #e5e7eb;')
            dl = QVBoxLayout(df)
            hdr = QHBoxLayout()
            plan_label = QLabel(f'📖 今日学习 (Day {today["day_index"]})')
            plan_label.setStyleSheet('font-size:16px;font-weight:bold;')
            hdr.addWidget(plan_label)

            pdf_btn = QPushButton('📄 下载PDF讲义到桌面')
            pdf_btn.clicked.connect(lambda: self._api_call('GET', f'{BASE_URL}/api/apprentice/pdf/today'))
            hdr.addStretch()
            hdr.addWidget(pdf_btn)
            dl.addLayout(hdr)

            if today.get('note'):
                note_label = QLabel(f'📝 {today["note"]}')
                note_label.setStyleSheet('color:#6b7280;')
                dl.addWidget(note_label)
            for t in tasks:
                row = QHBoxLayout()
                row.addWidget(QLabel(f'[{t.get("task_type","")}] {t["title"]}'))
                row.addStretch()
                row.addWidget(QLabel(f'{t.get("duration_min",0)}分钟'))
                dl.addLayout(row)
            total_label = QLabel(f'总时长: {sum(t.get("duration_min",0) for t in tasks)} 分钟')
            total_label.setStyleSheet('color:#6b7280;')
            dl.addWidget(total_label)
            layout.addWidget(df)

            # 陪练
            chat_g = QGroupBox('🤖 AI陪练答疑')
            chat_l = QVBoxLayout(chat_g)
            self._chat_area = QTextEdit()
            self._chat_area.setReadOnly(True)
            self._chat_area.setMaximumHeight(200)
            chat_l.addWidget(self._chat_area)
            chat_in = QHBoxLayout()
            chat_input = QLineEdit()
            chat_input.setPlaceholderText('向AI导师提问...')
            chat_in.addWidget(chat_input)
            chat_btn = QPushButton('发送')
            chat_btn.clicked.connect(lambda: self._do_chat(chat_input))
            chat_in.addWidget(chat_btn)
            chat_l.addLayout(chat_in)
            layout.addWidget(chat_g)

        self._api_call('GET', f'{BASE_URL}/api/apprentice/plan/today', callback=show)

    def _do_chat(self, chat_input):
        q = chat_input.text().strip()
        if not q:
            return
        self._chat_area.append(f'🧑 {q}')
        chat_input.clear()
        self._api_call('POST', f'{BASE_URL}/api/apprentice/ask', {'question': q},
                      callback=lambda r: self._chat_area.append(f'🤖 {r.get("answer", r.get("message",""))}'))

    def _build_appr_review(self, layout, container):
        self._review_data = getattr(self, '_review_data', None)
        self._review_idx = getattr(self, '_review_idx', 0)
        self._review_area = QVBoxLayout()
        layout.addLayout(self._review_area)

        if not self._review_data:
            loading = self._show_loading('获取今日计划...')
            self._review_area.addWidget(loading)
            self._api_call('GET', f'{BASE_URL}/api/apprentice/plan/today', callback=lambda r: self._start_review_check(loading, r))
        else:
            self._show_review_question()

    def _start_review_check(self, loading, res):
        loading.hide()
        if not res.get('success') or not res.get('today'):
            self._review_area.addWidget(QLabel('暂无今日学习计划'))
            return
        day_id = res['today']['id']
        self._review_area.addWidget(QLabel('基于今日学习内容，AI将生成复习题检验掌握程度。'))
        start_btn = QPushButton('开始当日复习')
        start_btn.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/apprentice/review/start',
            {'plan_day_id': day_id}, callback=lambda r: self._on_review_start(r)))
        self._review_area.addWidget(start_btn)

    def _on_review_start(self, res):
        if res.get('success'):
            self._review_data = res
            self._review_idx = 0
            self._load_page('appr_review')
        else:
            QMessageBox.warning(self, '错误', res.get('message', ''))

    def _show_review_question(self):
        area = self._review_area
        questions = self._review_data['questions']
        if self._review_idx >= len(questions):
            done_l = QLabel('🎉 复习完成！')
            done_l.setStyleSheet('font-size:16px;color:#10b981;')
            area.addWidget(done_l)
            reset_btn = QPushButton('再次复习')
            reset_btn.clicked.connect(lambda: [setattr(self, '_review_data', None), setattr(self, '_review_idx', 0), self._load_page('appr_review')])
            area.addWidget(reset_btn)
            return
        q = questions[self._review_idx]
        qf = QFrame()
        qf.setStyleSheet('background:white;border-radius:10px;padding:16px;')
        ql = QVBoxLayout(qf)
        idx_l = QLabel(f'题目 {self._review_idx + 1} / {len(questions)}')
        idx_l.setStyleSheet('font-size:14px;font-weight:bold;')
        ql.addWidget(idx_l)
        q_l = QLabel(q['question'])
        q_l.setStyleSheet('font-size:14px;font-weight:bold;')
        ql.addWidget(q_l)
        if q.get('qtype') == 'choice' and q.get('options'):
            self._r_answer = QButtonGroup(self)
            opts = q['options']
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except:
                    opts = [opts]
            for opt in (opts if isinstance(opts, list) else []):
                self._r_answer.addButton(QRadioButton(opt))
                ql.addWidget(QRadioButton(opt))
        else:
            self._r_answer = QTextEdit()
            self._r_answer.setMaximumHeight(80)
            ql.addWidget(self._r_answer)
        submit = QPushButton('提交')
        submit.clicked.connect(lambda: self._submit_review(q))
        ql.addWidget(submit)
        area.addWidget(qf)

    def _submit_review(self, q):
        answer = ''
        if isinstance(self._r_answer, QButtonGroup):
            checked = self._r_answer.checkedButton()
            if not checked:
                QMessageBox.warning(self, '提示', '请选择')
                return
            answer = checked.text()[0]
        else:
            answer = self._r_answer.toPlainText().strip()
            if not answer:
                QMessageBox.warning(self, '提示', '请输入答案')
                return
        self._api_call('POST', f'{BASE_URL}/api/apprentice/review/answer',
                      {'question_id': q['id'], 'answer': answer, 'review_id': self._review_data['review_id']},
                      callback=lambda r: self._on_review_answered(r))

    def _on_review_answered(self, res):
        fb = QLabel(f'得分: {res.get("score",0)} | {res.get("feedback","")}')
        fb.setStyleSheet('padding:8px;border-radius:6px;' +
                         ('background:#fef2f2;color:#991b1b;' if res.get('score', 0) < 60 else 'background:#ecfdf5;color:#065f46;'))
        fb.setWordWrap(True)
        self._review_area.addWidget(fb)
        self._review_idx += 1
        next_btn = QPushButton('下一题 →')
        next_btn.clicked.connect(lambda: self._load_page('appr_review'))
        self._review_area.addWidget(next_btn)

    def _build_appr_mistakes(self, layout, container):
        loading = self._show_loading()
        layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/apprentice/mistakes', callback=lambda r: self._show_mistakes(loading, r, layout))

    def _show_mistakes(self, loading, res, layout):
        loading.hide()
        all_m = res.get('assess_mistakes', []) + res.get('review_mistakes', [])
        if not res.get('success') or not all_m:
            lbl = QLabel('🎉 太棒了！目前没有错题记录。')
            lbl.setStyleSheet('color:#10b981;font-size:14px;')
            layout.addWidget(lbl)
            return
        for m in all_m:
            df = QFrame()
            df.setStyleSheet('background:white;border-radius:8px;padding:12px;margin:4px 0;border-left:3px solid #ef4444;')
            dl = QVBoxLayout(df)

            ql = QLabel(f'❌ {m.get("question","")}')
            ql.setStyleSheet('font-weight:bold;')
            dl.addWidget(ql)

            a1 = QLabel(f'你的回答: {m.get("apprentice_answer","未作答")}')
            a1.setStyleSheet('color:#6b7280;font-size:12px;')
            dl.addWidget(a1)

            a2 = QLabel(f'正确答案: {m.get("answer_key","-")}')
            a2.setStyleSheet('color:#6b7280;font-size:12px;')
            dl.addWidget(a2)

            a3 = QLabel(f'得分: {m.get("score",0)} | {m.get("feedback","")}')
            a3.setStyleSheet('color:#6b7280;font-size:12px;')
            dl.addWidget(a3)

            layout.addWidget(df)

    def _build_appr_leaderboard(self, layout, container):
        loading = self._show_loading()
        layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/apprentice/leaderboard', callback=lambda r: self._show_leaderboard(loading, r, layout))

    def _show_leaderboard(self, loading, res, layout):
        loading.hide()
        lb = res.get('leaderboard', [])
        if not lb:
            layout.addWidget(QLabel('暂无数据'))
            return
        for i, item in enumerate(lb):
            rank = i + 1
            colors = ['#fbbf24', '#9ca3af', '#d97706', '#e5e7eb']
            color = colors[min(rank - 1, 3)]
            row = QFrame()
            row.setStyleSheet(f'background:white;border-radius:8px;padding:10px;margin:2px 0;border-left:4px solid {color};')
            rl = QHBoxLayout(row)
            rl.addWidget(QLabel(f'#{rank}'))
            is_me = item['apprentice_id'] == res.get('my_id')
            name_label = QLabel(item['username'] + (' (我)' if is_me else ''))
            name_label.setStyleSheet('font-weight:bold;')
            rl.addWidget(name_label)
            rl.addStretch()
            avg_l = QLabel(f'均分: {item["avg_score"]}')
            avg_l.setStyleSheet('color:#6b7280;font-size:12px;')
            rl.addWidget(avg_l)
            mas_l = QLabel(f'熟练: {item["mastery_count"]}维度')
            mas_l.setStyleSheet('color:#6b7280;font-size:12px;')
            rl.addWidget(mas_l)
            err_l = QLabel(f'错题: {item["mistake_count"]}')
            err_l.setStyleSheet('color:#6b7280;font-size:12px;')
            rl.addWidget(err_l)
            layout.addWidget(row)

    # ==================== V2: 交流圈 ====================
    def _build_social_posts(self, layout, container):
        # 发帖区
        g = QGroupBox('✍️ 发帖')
        gl = QVBoxLayout(g)
        post_input = QTextEdit(); post_input.setMaximumHeight(80); post_input.setPlaceholderText('分享你的想法...')
        gl.addWidget(post_input)
        post_msg = QLabel(''); gl.addWidget(post_msg)
        post_btn = QPushButton('发布')
        post_btn.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/posts',
            {'content': post_input.toPlainText().strip(), 'author_name': self.user.get('full_name') or self.user['username']},
            callback=lambda r: [post_input.clear(), post_msg.setText('发布成功！' if r.get('success') else r.get('message','')),
                                self._load_page('social_posts')]))
        gl.addWidget(post_btn)
        layout.addWidget(g)

        # 帖子列表区
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/posts', callback=lambda r: self._show_posts(loading, r, layout))

    def _show_posts(self, loading, res, layout):
        loading.hide()
        posts = res.get('posts', [])
        if not posts: layout.addWidget(QLabel('暂无帖子')); return
        for p in posts:
            pf = QFrame()
            pf.setStyleSheet('background:white;border-radius:8px;padding:12px;margin:4px 0;border:1px solid #e5e7eb;')
            pl = QVBoxLayout(pf)
            hdr = QHBoxLayout()
            hdr.addWidget(QLabel(f'{p.get("author_name","")}  [{p.get("author_role","")}]'))
            hdr.setStyleSheet('font-weight:bold;font-size:13px;')
            hdr.addStretch()
            hdr.addWidget(QLabel(str(p.get('created_at','')[:19])))
            hdr.setStyleSheet('color:#9ca3af;font-size:11px;')
            pl.addLayout(hdr)
            ct = QLabel(p.get('content','')); ct.setWordWrap(True); pl.addWidget(ct)
            # 互动行
            al = QHBoxLayout()
            like_btn = QPushButton(f'{"❤️" if p.get("liked_by_me") else "🤍"} {p.get("likes_count",0)}')
            like_btn.clicked.connect(lambda checked, pid=p['id']: self._api_call('POST', f'{BASE_URL}/api/posts/{pid}/like',
                {}, callback=lambda r: self._load_page('social_posts')))
            al.addWidget(like_btn)
            cmt_btn = QPushButton(f'💬 {p.get("comments_count",0)}')
            cmt_btn.clicked.connect(lambda checked, pid=p['id']: self._show_comments(pid))
            al.addWidget(cmt_btn)
            al.addStretch(); pl.addLayout(al)
            layout.addWidget(pf)

    def _show_comments(self, post_id):
        dlg = QDialog(self); dlg.setWindowTitle('评论'); dlg.resize(400, 400)
        dl = QVBoxLayout(dlg)
        c_area = QTextEdit(); c_area.setReadOnly(True); dl.addWidget(c_area)
        cin = QHBoxLayout()
        cmt_in = QLineEdit(); cmt_in.setPlaceholderText('写评论...'); cin.addWidget(cmt_in)
        cin.addWidget(QPushButton('发送', clicked=lambda: self._api_call('POST', f'{BASE_URL}/api/posts/{post_id}/comments',
            {'content': cmt_in.text().strip()}, callback=lambda r: [cmt_in.clear(), self._api_call('GET', f'{BASE_URL}/api/posts/{post_id}/comments',
                callback=lambda r2: c_area.setText('\n'.join([f'{c.get("author_id","")}: {c.get("content","")}' for c in r2.get('comments',[])])))])))
        dl.addLayout(cin)
        self._api_call('GET', f'{BASE_URL}/api/posts/{post_id}/comments', callback=lambda r: c_area.setText('\n'.join([f'{c.get("author_id","")}: {c.get("content","")}' for c in r.get('comments',[])])))
        dlg.exec_()

    # ==================== V2: 通知 ====================
    def _build_notifications(self, layout, container):
        loading = self._show_loading(); layout.addWidget(loading)
        mark_btn = QPushButton('全部标为已读')
        mark_btn.clicked.connect(lambda: self._api_call('POST', f'{BASE_URL}/api/notifications/read', {},
            callback=lambda r: self._load_page('notifications')))
        layout.addWidget(mark_btn)
        self._api_call('GET', f'{BASE_URL}/api/notifications', callback=lambda r: self._show_notifications(loading, r, layout))

    def _show_notifications(self, loading, res, layout):
        loading.hide()
        unread = res.get('unread_count', 0)
        layout.addWidget(QLabel(f'未读: {unread}'))
        layout.setStyleSheet('font-size:13px;color:#6b7280;')
        for n in res.get('notifications', []):
            nf = QFrame()
            nf.setStyleSheet('background:white;border-radius:6px;padding:10px;margin:2px 0;' +
                            ('border-left:3px solid #2563eb;' if not n.get('read') else 'border:1px solid #e5e7eb;'))
            nl = QHBoxLayout(nf); nl.addWidget(QLabel(f'[{n.get("type","")}] {n.get("content","")}'))
            nl.setStyleSheet('font-size:12px;'); nl.addStretch()
            nl.addWidget(QLabel(str(n.get('created_at','')[:16])))
            nl.setStyleSheet('color:#9ca3af;font-size:10px;')
            layout.addWidget(nf)

    # ==================== V2: 进度视图 ====================
    def _build_progress_view(self, layout, container):
        role = self.user['role']
        tabs = [('公司', 'company'), ('部门', 'department'), ('同门', 'same-master')]
        if role == 'admin': tabs = [('公司', 'company')]
        sel = QComboBox(); [sel.addItem(t[0], t[1]) for t in tabs]; layout.addWidget(sel)
        area = QVBoxLayout(); layout.addLayout(area)
        sel.currentIndexChanged.connect(lambda: self._load_progress(sel.currentData(), area))
        self._load_progress(tabs[0][1], area)

    def _load_progress(self, ptype, area):
        while area.count():
            item = area.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        loading = self._show_loading(); area.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/progress/{ptype}', callback=lambda r: self._show_progress(loading, r, area))

    def _show_progress(self, loading, res, area):
        loading.hide()
        apps = res.get('apprentices', [])
        if not apps: area.addWidget(QLabel('暂无数据')); return
        for a in apps:
            af = QFrame()
            af.setStyleSheet('background:white;border-radius:8px;padding:10px;margin:2px 0;border-left:4px solid #2563eb;')
            al = QHBoxLayout(af)
            al.addWidget(QLabel(f'#{a.get("rank","-")}'))
            al.addWidget(QLabel(f'{a.get("apprentice_name","")} ({a.get("employee_no","")})'))
            al.setStyleSheet('font-weight:bold;font-size:13px;')
            al.addWidget(QLabel(f'师傅: {a.get("master_name","-")}'))
            al.addStretch()
            al.addWidget(QLabel(f'{a.get("progress_pct",0)}%'))
            al.addWidget(QLabel(f'{a.get("avg_score",0)}分'))
            al.setStyleSheet('color:#6b7280;font-size:12px;')
            area.addWidget(af)

    # ==================== V2: 管理员后台 ====================
    def _build_admin_overview(self, layout, container):
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/admin/stats', callback=lambda r: self._show_admin_stats(loading, r, layout))

    def _show_admin_stats(self, loading, res, layout):
        loading.hide()
        grid = QGridLayout()
        cards = [('徒弟数', str(res.get('total_apprentices',0)), '#ef4444'),
                 ('师傅数', str(res.get('total_masters',0)), '#2563eb'),
                 ('待审核', str(res.get('pending_review',0)), '#f59e0b'),
                 ('课程', '管理', '#10b981')]
        for i,(lbl,val,color) in enumerate(cards):
            cf = QFrame()
            cf.setStyleSheet(f'background:white;border-radius:10px;padding:16px;border-left:3px solid {color};')
            cl = QVBoxLayout(cf); vl = QLabel(val); vl.setStyleSheet(f'font-size:24px;font-weight:800;color:{color};'); vl.setAlignment(Qt.AlignCenter)
            cl.addWidget(vl); ll = QLabel(lbl); ll.setStyleSheet('font-size:12px;color:#6b7280;'); ll.setAlignment(Qt.AlignCenter)
            cl.addWidget(ll); grid.addWidget(cf, 0, i)
        layout.addLayout(grid)

    def _build_admin_pending(self, layout, container):
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/admin/pending', callback=lambda r: self._show_pending(loading, r, layout))

    def _show_pending(self, loading, res, layout):
        loading.hide()
        pending = res.get('pending', [])
        if not pending: layout.addWidget(QLabel('无待审核用户')); return
        for u in pending:
            uf = QFrame()
            uf.setStyleSheet('background:white;border-radius:8px;padding:10px;margin:2px 0;border:1px solid #e5e7eb;')
            ul = QVBoxLayout(uf)
            ul.addWidget(QLabel(f'{u.get("full_name","")} ({u["username"]}) - {u["role"]}'))
            ul.addWidget(QLabel(f'工号:{u.get("employee_no","")} 手机:{u.get("phone","")}'))
            ul.setStyleSheet('font-size:12px;color:#6b7280;')
            btns = QHBoxLayout()
            btns.addWidget(QPushButton('✅ 通过', clicked=lambda checked, uid=u['id']: self._api_call('POST', f'{BASE_URL}/api/admin/approve', {'user_id': uid},
                callback=lambda r: self._load_page('admin_pending'))))
            btns.addWidget(QPushButton('❌ 驳回', clicked=lambda checked, uid=u['id']: self._api_call('POST', f'{BASE_URL}/api/admin/reject', {'user_id': uid},
                callback=lambda r: self._load_page('admin_pending'))))
            ul.addLayout(btns); layout.addWidget(uf)

    def _build_admin_courses(self, layout, container):
        # 创建课程
        g = QGroupBox('➕ 创建课程')
        gl = QVBoxLayout(g)
        ct = QLineEdit(); ct.setPlaceholderText('课程名称'); gl.addWidget(ct)
        cty = QComboBox(); cty.addItems(['document','video','link','quiz']); gl.addWidget(cty)
        cc = QTextEdit(); cc.setMaximumHeight(60); cc.setPlaceholderText('内容/描述'); gl.addWidget(cc)
        msg = QLabel(''); gl.addWidget(msg)
        gl.addWidget(QPushButton('创建', clicked=lambda: self._api_call('POST', f'{BASE_URL}/api/admin/courses',
            {'title':ct.text().strip(),'type':cty.currentText(),'content':cc.toPlainText().strip()},
            callback=lambda r: [msg.setText('创建成功！' if r.get('success') else r.get('message','')), self._load_page('admin_courses')])))
        layout.addWidget(g)
        # 列表
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/admin/courses', callback=lambda r: self._show_courses_admin(loading, r, layout))

    def _show_courses_admin(self, loading, res, layout):
        loading.hide()
        courses = res.get('courses', [])
        if not courses: layout.addWidget(QLabel('暂无课程')); return
        for c in courses:
            cf = QFrame()
            cf.setStyleSheet('background:white;border-radius:8px;padding:10px;margin:2px 0;border:1px solid #e5e7eb;')
            cl = QHBoxLayout(cf)
            cl.addWidget(QLabel(f'{c["title"]} [{c.get("type","")}]'))
            cl.addStretch()
            cl.addWidget(QPushButton('🗑️', clicked=lambda checked, cid=c['id']: self._api_call('DELETE', f'{BASE_URL}/api/admin/courses/{cid}',
                {}, callback=lambda r: self._load_page('admin_courses'))))
            layout.addWidget(cf)

    def _build_admin_users(self, layout, container):
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/admin/users', callback=lambda r: self._show_admin_users(loading, r, layout))

    def _show_admin_users(self, loading, res, layout):
        loading.hide()
        users = res.get('users', [])
        if not users: layout.addWidget(QLabel('暂无用户')); return
        for u in users:
            uf = QFrame()
            uf.setStyleSheet('background:white;border-radius:8px;padding:8px;margin:2px 0;border:1px solid #e5e7eb;')
            ul = QHBoxLayout(uf)
            ul.addWidget(QLabel(f'{u.get("full_name","") or u["username"]}'))
            ul.addWidget(QLabel(f'[{u["role"]}] [{u.get("status","")}]'))
            ul.setStyleSheet('font-size:12px;'); ul.addStretch()
            ul.addWidget(QLabel(f'师傅: {u.get("master_name","-")}'))
            ul.setStyleSheet('color:#6b7280;font-size:11px;')
            layout.addWidget(uf)

    # ==================== V2: 师傅定制计划 ====================
    def _build_master_plans(self, layout, container):
        # 创建计划
        g = QGroupBox('➕ 为徒弟定制培养计划')
        gl = QVBoxLayout(g)
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel('选择徒弟:'))
        appr_combo = QComboBox(); sel_row.addWidget(appr_combo); gl.addLayout(sel_row)
        gl.addWidget(QLabel('课程列表（勾选加入计划）:'))
        course_area = QVBoxLayout(); gl.addLayout(course_area)
        msg = QLabel(''); gl.addWidget(msg)
        create_btn = QPushButton('创建计划'); gl.addWidget(create_btn)
        layout.addWidget(g)

        self._course_checks = []  # (course_id, checkbox)
        # 加载徒弟和课程
        self._api_call('GET', f'{BASE_URL}/api/master/apprentices', callback=lambda r: [
            appr_combo.addItem(a.get('full_name') or a['username'], a['id']) for a in r.get('apprentices', [])])
        self._api_call('GET', f'{BASE_URL}/api/admin/courses', callback=lambda r: [
            (self._course_checks.append((c['id'], QCheckBox(c['title']))),
             course_area.addWidget(self._course_checks[-1][1])) for c in r.get('courses', [])
        ])

        def create_plan():
            aid = appr_combo.currentData()
            cids = [cid for cid, cb in self._course_checks if cb.isChecked()]
            if not aid: msg.setText('请选择徒弟'); return
            if not cids: msg.setText('请勾选课程'); return
            msg.setText('创建中...')
            self._api_call('POST', f'{BASE_URL}/api/master/plans',
                {'apprentice_id': aid, 'name': '定制培养计划', 'course_ids': cids},
                callback=lambda r: [msg.setText('创建成功！' if r.get('success') else r.get('message','')),
                                    self._load_page('master_plans')])
        create_btn.clicked.connect(create_plan)

        # 已有计划列表
        layout.addWidget(QLabel('📋 已有计划'))
        layout.setStyleSheet('font-weight:bold;margin-top:12px;')
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/master/plans', callback=lambda r: self._show_master_plans(loading, r, layout))

    def _show_master_plans(self, loading, res, layout):
        loading.hide()
        plans = res.get('plans', [])
        if not plans: layout.addWidget(QLabel('暂无计划')); return
        for p in plans:
            pf = QFrame()
            pf.setStyleSheet('background:white;border-radius:8px;padding:10px;margin:2px 0;border:1px solid #e5e7eb;')
            pl = QHBoxLayout(pf)
            pl.addWidget(QLabel(f'{p["name"]} → {p.get("apprentice_name","")}'))
            pl.addStretch()
            pl.addWidget(QLabel(str(p.get('created_at','')[:16])))
            pl.setStyleSheet('color:#9ca3af;font-size:11px;')
            layout.addWidget(pf)

    # ==================== V2: 徒弟我的计划 ====================
    def _build_appr_my_plans(self, layout, container):
        loading = self._show_loading(); layout.addWidget(loading)
        self._api_call('GET', f'{BASE_URL}/api/apprentice/plans', callback=lambda r: self._show_appr_plans(loading, r, layout))

    def _show_appr_plans(self, loading, res, layout):
        loading.hide()
        plans = res.get('plans', [])
        if not plans: layout.addWidget(QLabel('暂无学习计划')); return
        for p in plans:
            pf = QFrame()
            pf.setStyleSheet('background:white;border-radius:10px;padding:12px;margin:4px 0;border:1px solid #e5e7eb;')
            pl = QVBoxLayout(pf)
            pl.addWidget(QLabel(f'📋 {p["name"]}'))
            pl.setStyleSheet('font-size:15px;font-weight:bold;')
            for item in p.get('items', []):
                row = QHBoxLayout()
                row.addWidget(QLabel(f'• {item.get("course_title","")} [{item.get("course_type","")}]'))
                row.addStretch()
                done = item.get('done', 0)
                row.addWidget(QLabel('✅ 已完成' if done else '⏳ 待学习'))
                row.setStyleSheet('color:#10b981;font-size:12px;' if done else 'color:#f59e0b;font-size:12px;')
                pl.addLayout(row)
            layout.addWidget(pf)

    # ==================== 登出 ====================
    def _logout(self):
        try:
            requests.post(f'{BASE_URL}/api/logout', headers={'Authorization': f'Bearer {self.token}'})
        except:
            pass
        self.close()


# ==================== 启动服务器线程 ====================
def start_server():
    """在后台线程启动 FastAPI"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import uvicorn
    from backend.main import app
    config = uvicorn.Config(app, host='127.0.0.1', port=SERVER_PORT, log_level='warning')
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


# ==================== 主入口 ====================
def launch_desktop(start_server_flag=True):
    """启动桌面应用。start_server_flag: 是否同时启动后端服务。"""
    import time

    if start_server_flag:
        t = threading.Thread(target=start_server, daemon=True)
        t.start()
        # 等待服务器就绪
        for _ in range(30):
            try:
                requests.get(f'{BASE_URL}/api/me', timeout=1)
                break
            except:
                time.sleep(0.3)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor('#f7f8fa'))
    palette.setColor(QPalette.WindowText, QColor('#111827'))
    app.setPalette(palette)

    login = LoginDialog()
    if login.exec_() == QDialog.Accepted:
        window = MainWindow(login.token, login.user)
        window.show()
        app.exec_()


if __name__ == '__main__':
    launch_desktop()
