"""登录 / 注册对话框（huashu-design 红白亮色风）。

- 双模式切换：登录 / 注册（师傅、管理员；徒弟由师傅创建）
- 注册字段：用户名、密码、姓名、工号、手机、办公账号、公司（对齐 RegisterReq）
- pending 拦截：后端返回"待审核"提示时高亮展示
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QStackedWidget, QWidget, QFrame,
)
from PyQt5.QtCore import Qt

from ui.api import ApiThread, BASE_URL

_RED_WHITE_QSS = """
QDialog { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ffffff, stop:1 #fdecec); }
QLabel { color: #4b5563; font-size: 14.5px; }
QLabel#loginTitle { color: #b91c1c; font-size: 28px; font-weight: 800; }
QLabel#loginSub { color: #9c8a8a; font-size: 14px; }
QLabel#loginMsg { font-size: 14px; }
QLineEdit, QComboBox {
    background: #ffffff; color: #1f1a1a;
    border: 1.5px solid #e6d2d2; border-radius: 10px;
    padding: 12px 14px; font-size: 15px;
}
QLineEdit:focus, QComboBox:focus { border-color: #dc2626; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: #ffffff; color: #1f1a1a; border: 1px solid #e6d2d2;
    font-size: 15px;
    selection-background-color: #fef2f2; selection-color: #b91c1c;
}
QPushButton#authBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444);
    color: white; border: none; border-radius: 10px;
    padding: 14px; font-size: 17px; font-weight: 700;
}
QPushButton#authBtn:hover { background: #b91c1c; }
QPushButton#authBtn:disabled { background: #d8bcbc; }
QPushButton#tabBtn {
    background: transparent; color: #9c8a8a; border: none;
    padding: 10px 0; font-size: 16px; font-weight: 600;
    border-bottom: 3px solid transparent; border-radius: 0;
}
QPushButton#tabBtn:checked { color: #b91c1c; border-bottom: 3px solid #dc2626; }
QFrame#tabLine { background: #f0dcdc; max-height: 1px; border: none; }
"""


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.token = None
        self.user = None
        self._threads = []
        self.setWindowTitle("薪火 · AI 导师系统 — 登录")
        self.setFixedSize(540, 720)
        self.setStyleSheet(_RED_WHITE_QSS)
        self._init_ui()
        self._load_companies()

    # ---------- UI ----------
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 38, 48, 34)
        root.setSpacing(14)

        title = QLabel("🔥  薪火 · AI 导师系统")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        sub = QLabel("师傅带徒 · 知识传承 · AI 加速成长")
        sub.setObjectName("loginSub")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(8)

        # 模式切换 tab
        tab_row = QHBoxLayout()
        tab_row.setSpacing(24)
        self.tab_login = QPushButton("登 录")
        self.tab_reg = QPushButton("注 册")
        for b in (self.tab_login, self.tab_reg):
            b.setObjectName("tabBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            tab_row.addWidget(b)
        tab_row.addStretch()
        root.addLayout(tab_row)
        line = QFrame()
        line.setObjectName("tabLine")
        line.setFrameShape(QFrame.HLine)
        root.addWidget(line)

        self.tab_login.setChecked(True)
        self.tab_login.clicked.connect(lambda: self._switch_mode(0))
        self.tab_reg.clicked.connect(lambda: self._switch_mode(1))

        # 表单堆栈
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_form())
        self.stack.addWidget(self._build_register_form())
        root.addWidget(self.stack, 1)

        # 消息
        self.msg = QLabel("")
        self.msg.setObjectName("loginMsg")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet("color:#dc2626;")
        root.addWidget(self.msg)

        # 提交按钮
        self.btn = QPushButton("登 录")
        self.btn.setObjectName("authBtn")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self._do_auth)
        root.addWidget(self.btn)

    def _build_login_form(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(QLabel("用户名"))
        self.l_uname = QLineEdit()
        self.l_uname.setPlaceholderText("输入用户名")
        lay.addWidget(self.l_uname)
        lay.addWidget(QLabel("密码"))
        self.l_pwd = QLineEdit()
        self.l_pwd.setEchoMode(QLineEdit.Password)
        self.l_pwd.setPlaceholderText("输入密码")
        self.l_pwd.returnPressed.connect(self._do_auth)
        lay.addWidget(self.l_pwd)
        lay.addStretch()
        return w

    def _build_register_form(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(8)

        row1 = QHBoxLayout()
        col_a = QVBoxLayout()
        col_a.addWidget(QLabel("用户名 *"))
        self.r_uname = QLineEdit()
        self.r_uname.setPlaceholderText("登录用户名")
        col_a.addWidget(self.r_uname)
        col_b = QVBoxLayout()
        col_b.addWidget(QLabel("密码 *"))
        self.r_pwd = QLineEdit()
        self.r_pwd.setEchoMode(QLineEdit.Password)
        self.r_pwd.setPlaceholderText("登录密码")
        col_b.addWidget(self.r_pwd)
        row1.addLayout(col_a)
        row1.addLayout(col_b)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        col_c = QVBoxLayout()
        col_c.addWidget(QLabel("姓名"))
        self.r_name = QLineEdit()
        self.r_name.setPlaceholderText("真实姓名")
        col_c.addWidget(self.r_name)
        col_d = QVBoxLayout()
        col_d.addWidget(QLabel("工号"))
        self.r_empno = QLineEdit()
        self.r_empno.setPlaceholderText("如 M001")
        col_d.addWidget(self.r_empno)
        row2.addLayout(col_c)
        row2.addLayout(col_d)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        col_e = QVBoxLayout()
        col_e.addWidget(QLabel("手机号"))
        self.r_phone = QLineEdit()
        self.r_phone.setPlaceholderText("联系电话")
        col_e.addWidget(self.r_phone)
        col_f = QVBoxLayout()
        col_f.addWidget(QLabel("办公账号"))
        self.r_office = QLineEdit()
        self.r_office.setPlaceholderText("办公软件账号")
        col_f.addWidget(self.r_office)
        row3.addLayout(col_e)
        row3.addLayout(col_f)
        lay.addLayout(row3)

        row4 = QHBoxLayout()
        col_g = QVBoxLayout()
        col_g.addWidget(QLabel("角色 *"))
        self.r_role = QComboBox()
        self.r_role.addItem("师傅", "master")
        self.r_role.addItem("管理员", "admin")
        col_g.addWidget(self.r_role)
        col_h = QVBoxLayout()
        col_h.addWidget(QLabel("公司"))
        self.r_company = QComboBox()
        self.r_company.addItem("加载中...", None)
        col_h.addWidget(self.r_company)
        row4.addLayout(col_g)
        row4.addLayout(col_h)
        lay.addLayout(row4)

        tip = QLabel("💡 徒弟账号由师傅在系统内创建；注册后需管理员审核通过方可登录。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#9c8a8a;font-size:13px;")
        lay.addWidget(tip)
        lay.addStretch()
        return w

    # ---------- 行为 ----------
    def _switch_mode(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.tab_login.setChecked(idx == 0)
        self.tab_reg.setChecked(idx == 1)
        self.btn.setText("登 录" if idx == 0 else "注 册")
        self._set_msg("")

    def _set_msg(self, text: str, ok: bool = False, warn: bool = False):
        color = "#059669" if ok else ("#b45309" if warn else "#dc2626")
        self.msg.setStyleSheet(f"color:{color};")
        self.msg.setText(text)

    def _load_companies(self):
        t = ApiThread("GET", f"{BASE_URL}/api/companies")
        t.finished.connect(self._on_companies)
        self._threads.append(t)
        t.start()

    def _on_companies(self, res):
        self.r_company.clear()
        for c in res.get("companies", []) or []:
            self.r_company.addItem(c.get("name", f'公司{c.get("id")}'), c.get("id"))
        if self.r_company.count() == 0:
            self.r_company.addItem("默认公司", 1)

    def _do_auth(self):
        self._set_msg("")
        if self.stack.currentIndex() == 0:
            uname, pwd = self.l_uname.text().strip(), self.l_pwd.text().strip()
            if not uname or not pwd:
                self._set_msg("请填写用户名和密码")
                return
            self._lock(True, "登录中...")
            t = ApiThread("POST", f"{BASE_URL}/api/login", {"username": uname, "password": pwd})
            t.finished.connect(self._on_login)
        else:
            uname, pwd = self.r_uname.text().strip(), self.r_pwd.text().strip()
            if not uname or not pwd:
                self._set_msg("用户名与密码为必填项")
                return
            body = {
                "username": uname,
                "password": pwd,
                "role": self.r_role.currentData(),
                "company_id": self.r_company.currentData(),
                "employee_no": self.r_empno.text().strip() or None,
                "phone": self.r_phone.text().strip() or None,
                "office_account": self.r_office.text().strip() or None,
                "full_name": self.r_name.text().strip() or None,
            }
            self._lock(True, "注册中...")
            t = ApiThread("POST", f"{BASE_URL}/api/register", body)
            t.finished.connect(self._on_register)
        self._threads.append(t)
        t.start()

    def _lock(self, locked: bool, text: str = None):
        self.btn.setEnabled(not locked)
        if text:
            self.btn.setText(text)

    def _on_login(self, res):
        self._lock(False, "登 录")
        if res.get("success"):
            self.token = res["token"]
            self.user = res["user"]
            self.accept()
            return
        message = res.get("message", "登录失败")
        # pending / rejected 拦截提示
        if "审核" in message or "pending" in message.lower():
            self._set_msg(f"⏳ {message}", warn=True)
        else:
            self._set_msg(message)

    def _on_register(self, res):
        self._lock(False, "注 册")
        if res.get("success"):
            self._set_msg("✅ 注册成功！等待管理员审核后即可登录", ok=True)
            self._switch_mode(0)
            self.l_uname.setText(self.r_uname.text().strip())
            self._set_msg("✅ 注册成功！等待管理员审核后即可登录", ok=True)
        else:
            self._set_msg(res.get("message", "注册失败"))
