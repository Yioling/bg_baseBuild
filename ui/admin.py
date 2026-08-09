"""管理员视图页面：概览、审核注册、课程库、用户管理（含师徒重绑）、部门管理、操作日志。"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QTextEdit,
    QComboBox, QGroupBox, QMessageBox, QDialog,
)
from PyQt5.QtCore import Qt

from ui.api import BASE_URL
from ui.theme import (
    Color, card, stat_card, section_label, hint_label, loading_label,
    empty_label, primary_button, success_button, secondary_button,
    danger_button, badge,
)

_ROLE_NAMES = {"admin": "管理员", "master": "师傅", "apprentice": "徒弟"}
_STATUS_META = {
    "approved": ("已通过", Color.SUCCESS, Color.SUCCESS_SOFT),
    "pending": ("待审核", Color.WARNING, Color.WARNING_SOFT),
    "rejected": ("已驳回", Color.DANGER, Color.DANGER_SOFT),
}


class AdminPagesMixin:
    # ==================== 概览 ====================
    def _build_admin_overview(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            grid = QGridLayout()
            grid.setSpacing(14)
            cards = [
                (res.get("total_apprentices", 0), "徒弟数", Color.DANGER),
                (res.get("total_masters", 0), "师傅数", Color.PRIMARY),
                (res.get("pending_review", 0), "待审核", Color.WARNING),
                ("正常", "系统状态", Color.SUCCESS),
            ]
            for i, (val, lbl, color) in enumerate(cards):
                grid.addWidget(stat_card(val, lbl, color), 0, i)
            layout.addLayout(grid)

            if res.get("pending_review", 0):
                warn = card(accent=Color.WARNING, padding=12)
                wl = QHBoxLayout(warn)
                wt = QLabel(f'⚠️ 有 {res["pending_review"]} 个注册申请待审核')
                wt.setStyleSheet(f"color:{Color.TEXT};font-size:20px;font-weight:600;background:transparent;")
                wl.addWidget(wt)
                wl.addStretch()
                go = primary_button("去审核")
                go.clicked.connect(lambda: self._switch_page("admin_pending"))
                wl.addWidget(go)
                layout.addWidget(warn)

        self._api_call("GET", f"{BASE_URL}/api/admin/stats", callback=show)

    # ==================== 审核注册 ====================
    def _build_admin_pending(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            pending = res.get("pending", [])
            if not pending:
                layout.addWidget(empty_label("无待审核用户"))
                return
            for u in pending:
                uf = card(accent=Color.WARNING, padding=12)
                ul = QVBoxLayout(uf)
                ul.setSpacing(6)
                head = QHBoxLayout()
                name = QLabel(f'{u.get("full_name") or u.get("username", "")}  ({u.get("username", "")})')
                name.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:21px;background:transparent;")
                head.addWidget(name)
                head.addWidget(badge(_ROLE_NAMES.get(u.get("role"), u.get("role", "")),
                                     Color.PRIMARY, Color.PRIMARY_SOFT))
                head.addStretch()
                ul.addLayout(head)
                ul.addWidget(hint_label(
                    f'工号: {u.get("employee_no") or "-"}    手机: {u.get("phone") or "-"}    '
                    f'办公账号: {u.get("office_account") or "-"}'))
                btns = QHBoxLayout()
                ok_btn = success_button("✅ 通过")
                ok_btn.clicked.connect(lambda checked, uid=u["id"]: self._api_call(
                    "POST", f"{BASE_URL}/api/admin/approve", {"user_id": uid},
                    callback=lambda r: self._load_page("admin_pending")))
                btns.addWidget(ok_btn)
                no_btn = danger_button("❌ 驳回")
                no_btn.clicked.connect(lambda checked, uid=u["id"]: self._api_call(
                    "POST", f"{BASE_URL}/api/admin/reject", {"user_id": uid},
                    callback=lambda r: self._load_page("admin_pending")))
                btns.addWidget(no_btn)
                btns.addStretch()
                ul.addLayout(btns)
                layout.addWidget(uf)

        self._api_call("GET", f"{BASE_URL}/api/admin/pending", callback=show)

    # ==================== 课程库 ====================
    def _build_admin_courses(self, layout, container):
        g = QGroupBox("➕ 创建课程")
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        row = QHBoxLayout()
        ct = QLineEdit()
        ct.setPlaceholderText("课程名称")
        row.addWidget(ct, 1)
        cty = QComboBox()
        cty.addItems(["document", "video", "link", "quiz"])
        row.addWidget(cty)
        gl.addLayout(row)
        cc = QTextEdit()
        cc.setMaximumHeight(70)
        cc.setPlaceholderText("内容 / 描述")
        gl.addWidget(cc)
        msg = hint_label("")
        gl.addWidget(msg)
        create = primary_button("创建课程")
        gl.addWidget(create, alignment=Qt.AlignLeft)

        def do_create():
            if not ct.text().strip():
                msg.setText("请输入课程名称")
                return
            self._api_call("POST", f"{BASE_URL}/api/admin/courses",
                           {"title": ct.text().strip(), "type": cty.currentText(),
                            "content": cc.toPlainText().strip()},
                           callback=lambda r: (
                               msg.setText("✅ 创建成功！" if r.get("success") else r.get("message", "")),
                               self._load_page("admin_courses") if r.get("success") else None))
        create.clicked.connect(do_create)
        layout.addWidget(g)

        layout.addWidget(section_label("📚 课程列表"))
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            courses = res.get("courses", [])
            if not courses:
                layout.addWidget(empty_label("暂无课程"))
                return
            for c in courses:
                cf = card(padding=10)
                cl = QHBoxLayout(cf)
                t = QLabel(c.get("title", ""))
                t.setStyleSheet(f"font-weight:600;color:{Color.TEXT};font-size:20px;background:transparent;")
                cl.addWidget(t)
                cl.addWidget(badge(c.get("type", ""), Color.INFO, "#e0f2fe"))
                cl.addStretch()
                del_btn = danger_button("删除")
                del_btn.clicked.connect(lambda checked, cid=c["id"]: self._api_call(
                    "DELETE", f"{BASE_URL}/api/admin/courses/{cid}",
                    callback=lambda r: self._load_page("admin_courses")))
                cl.addWidget(del_btn)
                layout.addWidget(cf)

        self._api_call("GET", f"{BASE_URL}/api/admin/courses", callback=show)

    # ==================== 用户管理 ====================
    def _build_admin_users(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            users = res.get("users", [])
            if not users:
                layout.addWidget(empty_label("暂无用户"))
                return
            masters = [u for u in users if u.get("role") == "master"]
            for u in users:
                uf = card(padding=10)
                ul = QHBoxLayout(uf)
                name = QLabel(u.get("full_name") or u.get("username", ""))
                name.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:20px;min-width:110px;background:transparent;")
                ul.addWidget(name)
                ul.addWidget(badge(_ROLE_NAMES.get(u.get("role"), u.get("role", "")),
                                   Color.PRIMARY, Color.PRIMARY_SOFT))
                st_text, st_c, st_bg = _STATUS_META.get(
                    u.get("status", ""), (u.get("status", ""), Color.TEXT_SUB, "#f3f4f6"))
                ul.addWidget(badge(st_text, st_c, st_bg))
                ul.addStretch()
                info = QLabel(f'工号: {u.get("employee_no") or "-"}   师傅: {u.get("master_name") or "-"}')
                info.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;background:transparent;")
                ul.addWidget(info)
                if u.get("role") == "apprentice":
                    rebind = secondary_button("重绑师傅")
                    rebind.clicked.connect(
                        lambda checked, uid=u["id"], uname=u.get("full_name") or u.get("username", ""):
                        self._open_rebind_dialog(uid, uname, masters))
                    ul.addWidget(rebind)
                layout.addWidget(uf)

        self._api_call("GET", f"{BASE_URL}/api/admin/users", callback=show)

    def _open_rebind_dialog(self, apprentice_id, name, masters):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"重绑师傅 — {name}")
        dlg.resize(360, 160)
        dl = QVBoxLayout(dlg)
        dl.setSpacing(10)
        dl.addWidget(hint_label("为该徒弟选择新的师傅："))
        combo = QComboBox()
        for m in masters:
            combo.addItem(m.get("full_name") or m.get("username", ""), m["id"])
        dl.addWidget(combo)
        btn = primary_button("确认重绑")

        def do_rebind():
            mid = combo.currentData()
            if not mid:
                return
            self._api_call("POST", f"{BASE_URL}/api/admin/rebind-master",
                           {"apprentice_id": apprentice_id, "master_id": mid},
                           callback=lambda r: (
                               QMessageBox.information(self, "结果", r.get("message", "")),
                               dlg.accept(),
                               self._load_page("admin_users")))
        btn.clicked.connect(do_rebind)
        dl.addWidget(btn, alignment=Qt.AlignRight)
        dlg.exec_()

    # ==================== 部门管理 ====================
    def _build_admin_departments(self, layout, container):
        g = QGroupBox("➕ 新增部门")
        gl = QHBoxLayout(g)
        name_input = QLineEdit()
        name_input.setPlaceholderText("部门名称")
        gl.addWidget(name_input, 1)
        add_btn = primary_button("添加")
        gl.addWidget(add_btn)
        layout.addWidget(g)

        layout.addWidget(section_label("🏢 部门列表"))
        loading = loading_label()
        layout.addWidget(loading)
        area = QVBoxLayout()
        area.setSpacing(8)
        layout.addLayout(area)

        def show(res):
            loading.hide()
            while area.count():
                item = area.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            depts = res.get("departments", [])
            if not depts:
                area.addWidget(empty_label("暂无部门"))
                return
            for d in depts:
                df = card(padding=10)
                dl = QHBoxLayout(df)
                t = QLabel(f'🏢 {d.get("name", "")}')
                t.setStyleSheet(f"font-weight:600;color:{Color.TEXT};font-size:20px;background:transparent;")
                dl.addWidget(t)
                dl.addStretch()
                area.addWidget(df)

        def do_add():
            n = name_input.text().strip()
            if not n:
                return
            name_input.clear()
            self._api_call("POST", f"{BASE_URL}/api/admin/departments", {"name": n}, callback=show)

        add_btn.clicked.connect(do_add)
        self._api_call("GET", f"{BASE_URL}/api/admin/departments", callback=show)

    # ==================== 操作日志 ====================
    def _build_admin_logs(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            logs = res.get("logs", [])
            if not logs:
                layout.addWidget(empty_label("暂无操作日志"))
                return
            for lg in logs:
                lf = card(padding=8)
                ll = QHBoxLayout(lf)
                act = QLabel(f'[{lg.get("action", "")}]')
                act.setStyleSheet(f"color:{Color.PRIMARY};font-size:19px;font-weight:700;min-width:110px;background:transparent;")
                ll.addWidget(act)
                detail = QLabel(
                    f'{lg.get("target_type", "")} #{lg.get("target_id", "")}  {lg.get("detail", "")}')
                detail.setStyleSheet(f"color:{Color.TEXT};font-size:19px;background:transparent;")
                ll.addWidget(detail)
                ll.addStretch()
                t = QLabel(str(lg.get("created_at", ""))[:19])
                t.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:18px;background:transparent;")
                ll.addWidget(t)
                layout.addWidget(lf)

        self._api_call("GET", f"{BASE_URL}/api/admin/logs", callback=show)
