"""师傅视图页面：概览、投喂、知识库、徒弟管理、定制计划、批改检测、学情看板。"""
import logging
import os

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
logger = logging.getLogger("ui.master")
if _fh is not None:
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(name)s: %(message)s",
                                       datefmt="%H:%M:%S"))
    logger.addHandler(_fh)
    logging.getLogger().addHandler(_fh)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QComboBox, QCheckBox, QProgressBar, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDoubleSpinBox,
    QFileDialog, QAbstractItemView, QScrollArea, QApplication,
)
from PyQt5.QtCore import Qt, QMimeData, QUrl

from ui.api import BASE_URL
from ui.theme import (
    Color, card, stat_card, section_label, hint_label, loading_label,
    empty_label, primary_button, success_button, secondary_button, badge, refine_button,
    apply_shadow, ingest_button, guide_item, GUIDE_BOX_TITLE_QSS,
)


class MasterPagesMixin:
    # ==================== 概览 ====================
    def _build_master_overview(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def on_knowledge(res):
            dims = res.get("dimensions", []) if res.get("success") else []
            self._ov_dims = dims
            dim_count = len(dims)
            pt_count = sum(len(d.get("points", [])) for d in dims)
            self._api_call("GET", f"{BASE_URL}/api/master/apprentices",
                           callback=lambda r: on_appr(r, dim_count, pt_count))

        def on_appr(res, dim_count, pt_count):
            loading.hide()
            app_count = len(res.get("apprentices", [])) if res.get("success") else 0
            self._ov_apprs = res.get("apprentices", []) if res.get("success") else []

            # ---- 概览详情区（先建，供卡片回调引用）----
            detail = card()
            detail_lay = QVBoxLayout(detail)
            detail_lay.setContentsMargins(4, 4, 4, 4)
            detail_lay.setSpacing(12)
            detail_scroll = QScrollArea()
            detail_scroll.setWidgetResizable(True)
            detail_scroll.setFrameShape(QFrame.NoFrame)
            detail_scroll.setWidget(detail)
            avail = QApplication.desktop().availableGeometry().height()
            detail_scroll.setFixedHeight(max(300, min(460, int(avail * 0.34))))

            self._ov_cards = {}

            def show_detail(key):
                for k, c in self._ov_cards.items():
                    c.set_selected(k == key)
                while detail_lay.count():
                    item = detail_lay.takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.setParent(None)
                builder = {
                    "dims": self._ov_chart_dimensions,
                    "points": self._ov_chart_points,
                    "apprs": self._ov_chart_apprentices,
                }[key]
                builder(detail_lay)

            grid = QGridLayout()
            grid.setSpacing(14)
            cards = [
                (dim_count, "知识维度", Color.PRIMARY, "dims"),
                (pt_count, "知识点", Color.SUCCESS, "points"),
                (app_count, "徒弟数量", Color.WARNING, "apprs"),
                ("v2.0", "桌面版本", Color.DANGER, None),
            ]
            for i, (val, lbl, color, key) in enumerate(cards):
                if key is None:
                    grid.addWidget(stat_card(val, lbl, color), 0, i)
                else:
                    c = stat_card(val, lbl, color, clickable=True,
                                  on_click=lambda k=key: show_detail(k))
                    self._ov_cards[key] = c
                    grid.addWidget(c, 0, i)
            layout.addLayout(grid)
            layout.addWidget(detail_scroll)

            show_detail("dims")

            guide = QGroupBox("🚀 带徒五步法")
            guide.setStyleSheet(GUIDE_BOX_TITLE_QSS)
            gl = QVBoxLayout(guide)
            gl.setSpacing(14)
            for s in [
                "1. 投喂资料 → 上传本地文档或博客 URL",
                "2. AI 精炼 → 自动生成知识维度与考点树",
                "3. 创建徒弟 → 为学徒注册账号",
                "4. 生成计划 → AI 自动排课或定制培养计划",
                "5. 学情看板 → 追踪徒弟学习进展并批改检测",
            ]:
                gl.addWidget(guide_item(s))
            layout.addWidget(guide)
            layout.addStretch(1)

        self._api_call("GET", f"{BASE_URL}/api/master/knowledge", callback=on_knowledge)

    # ---------- 概览三种图形（均使用首屏缓存，不再发请求） ----------
    def _ov_chart_dimensions(self, lay):
        dims = getattr(self, "_ov_dims", []) or []
        total_pt = sum(len(d.get("points", [])) for d in dims)
        lay.addWidget(section_label(
            f"📚 知识维度分布 (共 {len(dims)} 个维度 / {total_pt} 个知识点)"))
        if not dims:
            lay.addWidget(empty_label("暂无知识维度，前往 📁 投喂资料 添加"))
            return
        ordered = sorted(dims, key=lambda d: len(d.get("points", [])), reverse=True)
        top = ordered[:10]
        max_pt = max(len(d.get("points", [])) for d in top) or 1
        for d in top:
            n = len(d.get("points", []))
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(12)
            name = QLabel(d.get("name", "未命名"))
            name.setStyleSheet(
                f"font-size:19px;color:{Color.TEXT};background:transparent;")
            name.setFixedWidth(220)
            name.setWordWrap(True)
            rl.addWidget(name)
            bar = QProgressBar()
            bar.setMaximum(max_pt)
            bar.setValue(n)
            bar.setTextVisible(False)
            bar.setFixedHeight(20)
            rl.addWidget(bar, 1)
            cnt = QLabel(str(n))
            cnt.setStyleSheet(
                f"font-size:19px;font-weight:700;color:{Color.PRIMARY};"
                "background:transparent;")
            cnt.setFixedWidth(48)
            cnt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rl.addWidget(cnt)
            lay.addWidget(row)
        if len(ordered) > 10:
            lay.addWidget(hint_label(f"其余 {len(ordered) - 10} 个维度未显示"))

    def _ov_chart_points(self, lay):
        dims = getattr(self, "_ov_dims", []) or []
        total_pt = sum(len(d.get("points", [])) for d in dims)
        lay.addWidget(section_label(f"🧩 知识点总览 ({total_pt} 个)"))
        if total_pt == 0:
            lay.addWidget(empty_label("暂无知识点，前往 📁 投喂资料 添加"))
            return
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(10)
        shown = 0
        for d in dims:
            pts = d.get("points", [])
            if not pts or shown >= 60:
                continue
            il.addWidget(hint_label(f"{d.get('name', '未命名')} ({len(pts)})", Color.TEXT))
            wrap = QWidget()
            wl = QGridLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(8)
            col = 0
            row_i = 0
            for p in pts:
                if shown >= 60:
                    break
                pname = p.get("name", str(p)) if isinstance(p, dict) else str(p)
                wl.addWidget(badge(pname, Color.SUCCESS, Color.SUCCESS_SOFT), row_i, col)
                shown += 1
                col += 1
                if col >= 5:
                    col = 0
                    row_i += 1
            il.addWidget(wrap)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(260)
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        if total_pt > shown:
            lay.addWidget(hint_label(f"其余 {total_pt - shown} 个知识点未显示"))

    def _ov_chart_apprentices(self, lay):
        apprs = getattr(self, "_ov_apprs", []) or []
        lay.addWidget(section_label(f"👥 徒弟概览 (共 {len(apprs)} 人)"))
        if not apprs:
            lay.addWidget(empty_label("暂无徒弟，前往 👥 徒弟管理 创建"))
            return
        wrap = QWidget()
        wl = QGridLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(12)
        for i, a in enumerate(apprs):
            name = a.get("full_name") or a.get("username", "未命名")
            status = a.get("status", "")
            c = card(accent=Color.WARNING, padding=18)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(6, 6, 6, 6)
            cl.setSpacing(8)
            n = QLabel(f"👤 {name}")
            n.setStyleSheet(
                f"font-size:20px;font-weight:700;color:{Color.TEXT};"
                "background:transparent;")
            cl.addWidget(n)
            if status == "active":
                cl.addWidget(badge("已激活", Color.SUCCESS, Color.SUCCESS_SOFT))
            else:
                cl.addWidget(badge("待激活", Color.WARNING, Color.WARNING_SOFT))
            wl.addWidget(c, i // 3, i % 3)
        lay.addWidget(wrap)

    # ==================== 投喂资料 ====================
    def _build_master_ingest(self, layout, container):
        logger.debug("=== _build_master_ingest 开始构建投喂资料页 ===")
        g1 = QGroupBox("📁 本地文件夹投喂")
        g1l = QVBoxLayout(g1)
        g1l.addWidget(hint_label("输入包含 md / txt / pdf / docx / 代码 的文件夹路径"))
        path_input = PathDropLineEdit()
        path_input.setPlaceholderText(r"例如: C:\Users\TS\Desktop\入职学习  （可拖拽文件夹/文件到此，或点浏览）")
        g1l.addWidget(path_input)
        row1 = QHBoxLayout()
        browse_btn = secondary_button("📂 浏览…")
        row1.addWidget(browse_btn)
        row1.addStretch()
        g1l.addLayout(row1)
        msg1 = hint_label("")
        g1l.addWidget(msg1)
        btn1 = ingest_button("开始投喂")
        logger.debug("已创建按钮 btn1=[开始投喂] object=%r", btn1)
        g1l.addWidget(btn1, alignment=Qt.AlignLeft)

        def browse():
            # 支持多选文件与目录混合选择（Windows 下 QFileDialog 原生对话框支持）
            dlg = QFileDialog(container)
            dlg.setWindowTitle("选择文件夹或文件")
            dlg.setFileMode(QFileDialog.ExistingFiles)
            dlg.setOption(QFileDialog.DontUseNativeDialog, False)
            dlg.setOption(QFileDialog.ShowDirsOnly, False)
            # 通过 name filter 允许任意类型；目录与文件均可见可选
            if dlg.exec_() == QFileDialog.Accepted:
                paths = dlg.selectedFiles()
                if paths:
                    path_input.setText("; ".join(paths))

        def ingest_path():
            p = path_input.text().strip()
            if not p:
                msg1.setText("请输入路径")
                return
            msg1.setText("⏳ 正在摄入...")
            self._api_call("POST", f"{BASE_URL}/api/master/ingest", {"path": p},
                           callback=lambda r: msg1.setText(
                               f'{"✅" if r.get("success") else "❌"} {r.get("message", "")}'))
        browse_btn.clicked.connect(browse)
        btn1.clicked.connect(ingest_path)
        layout.addWidget(g1)

        g2 = QGroupBox("🌐 博客 URL 投喂")
        g2l = QVBoxLayout(g2)
        g2l.addWidget(hint_label("输入公开网页 URL（每行一个）"))
        url_input = QTextEdit()
        url_input.setPlaceholderText("https://example.com/article1\nhttps://example.com/article2")
        url_input.setMaximumHeight(96)
        g2l.addWidget(url_input)
        msg2 = hint_label("")
        g2l.addWidget(msg2)
        btn2 = ingest_button("抓取并投喂")
        logger.debug("已创建按钮 btn2=[抓取并投喂] object=%r", btn2)
        g2l.addWidget(btn2, alignment=Qt.AlignLeft)

        def ingest_url():
            urls = [u.strip() for u in url_input.toPlainText().split("\n") if u.strip()]
            if not urls:
                msg2.setText("请输入 URL")
                return
            msg2.setText("⏳ 正在抓取网页...")
            self._api_call("POST", f"{BASE_URL}/api/master/ingest/url", {"urls": urls},
                           callback=lambda r: msg2.setText(
                               f'{"✅" if r.get("success") else "❌"} {r.get("message", "")}'))
        btn2.clicked.connect(ingest_url)
        layout.addWidget(g2)

        g3 = QGroupBox("🎯 快速演示")
        g3l = QVBoxLayout(g3)
        g3l.addWidget(hint_label('使用内置的"智能订单交易系统"示例知识库'))
        btn3 = secondary_button("加载示例知识库")
        btn3.clicked.connect(lambda: self._api_call(
            "POST", f"{BASE_URL}/api/master/ingest", {"path": "backend/data/sample_kb"},
            callback=lambda r: QMessageBox.information(self, "结果", r.get("message", ""))))
        g3l.addWidget(btn3, alignment=Qt.AlignLeft)
        layout.addWidget(g3)
        logger.debug("=== _build_master_ingest 完成，g1/g2/g3 均已加入 layout ===")

    # ==================== 知识库 ====================
    def _build_master_knowledge(self, layout, container):
        top = QHBoxLayout()
        refine_btn = refine_button("🧪 触发 AI 精炼")
        top.addWidget(refine_btn)
        top.addWidget(hint_label("投喂资料后点击，AI 自动生成知识维度与考点树"))
        top.addStretch()
        layout.addLayout(top)

        loading = loading_label("加载知识库...")
        layout.addWidget(loading)
        result_area = QVBoxLayout()
        result_area.setSpacing(10)
        layout.addLayout(result_area)

        def show_knowledge(res):
            loading.hide()
            while result_area.count():
                item = result_area.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            if not res.get("success") or not res.get("dimensions"):
                result_area.addWidget(empty_label("暂无知识库内容，请先投喂资料再精炼"))
                return
            for d in res["dimensions"]:
                df = card(accent=Color.PRIMARY, padding=14)
                dl = QVBoxLayout(df)
                dl.setSpacing(6)
                name = QLabel(d.get("name", ""))
                name.setStyleSheet(f"font-weight:700;font-size:21px;color:{Color.TEXT};background:transparent;")
                dl.addWidget(name)
                if d.get("description"):
                    desc = QLabel(d["description"])
                    desc.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;background:transparent;")
                    desc.setWordWrap(True)
                    dl.addWidget(desc)
                for p in d.get("points", []):
                    row = QLabel(f'· {p.get("title", "")}  [{p.get("level", "")}]')
                    row.setStyleSheet(f"color:{Color.TEXT};font-size:19.5px;padding-left:6px;background:transparent;")
                    dl.addWidget(row)
                result_area.addWidget(df)

        self._api_call("GET", f"{BASE_URL}/api/master/knowledge", callback=show_knowledge)

        def do_refine():
            loading.show()
            loading.setText("⏳ AI 精炼中...")
            self._api_call("POST", f"{BASE_URL}/api/master/refine", {}, callback=show_knowledge)
        refine_btn.clicked.connect(do_refine)

    # ==================== 徒弟管理 ====================
    def _build_master_apprentices(self, layout, container):
        g = QGroupBox("➕ 创建徒弟账号")
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        row = QHBoxLayout()
        u = QLineEdit()
        u.setPlaceholderText("徒弟用户名")
        p = QLineEdit()
        p.setPlaceholderText("初始密码")
        p.setEchoMode(QLineEdit.Password)
        row.addWidget(u)
        row.addWidget(p)
        gl.addLayout(row)
        msg = hint_label("")
        gl.addWidget(msg)
        btn = primary_button("创建徒弟")
        gl.addWidget(btn, alignment=Qt.AlignLeft)

        def create():
            if not u.text().strip() or not p.text().strip():
                msg.setText("请填写完整")
                return
            self._api_call("POST", f"{BASE_URL}/api/master/apprentices",
                           {"username": u.text().strip(), "password": p.text().strip()},
                           callback=lambda r: (
                               msg.setText(f'{"✅" if r.get("success") else "❌"} {r.get("message", "")}'),
                               self._load_page("master_apprentices") if r.get("success") else None))
        btn.clicked.connect(create)
        layout.addWidget(g)

        layout.addWidget(section_label("👥 我的徒弟"))
        loading = loading_label()
        layout.addWidget(loading)

        def show_list(res):
            loading.hide()
            apps = res.get("apprentices", [])
            if not apps:
                layout.addWidget(empty_label("暂无徒弟，先创建一个吧"))
                return
            tbl = QTableWidget()
            tbl.setColumnCount(3)
            tbl.setHorizontalHeaderLabels(["用户名", "创建时间", "操作"])
            tbl.setRowCount(len(apps))
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.setAlternatingRowColors(True)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, a in enumerate(apps):
                tbl.setItem(i, 0, QTableWidgetItem(a.get("username", "")))
                tbl.setItem(i, 1, QTableWidgetItem(str(a.get("created_at", "-"))))
                pb = primary_button("生成计划")
                pb.clicked.connect(lambda checked, aid=a["id"]: self._gen_plan(aid))
                tbl.setCellWidget(i, 2, pb)
            tbl.setMinimumHeight(min(320, 60 + len(apps) * 44))
            layout.addWidget(tbl)

        self._api_call("GET", f"{BASE_URL}/api/master/apprentices", callback=show_list)

    def _gen_plan(self, appr_id):
        self._api_call("POST", f"{BASE_URL}/api/master/plan/generate",
                       {"apprentice_id": appr_id},
                       callback=lambda r: QMessageBox.information(self, "结果", r.get("message", "")))

    # ==================== 定制培养计划 ====================
    def _build_master_plans(self, layout, container):
        g = QGroupBox("➕ 为徒弟定制培养计划")
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("选择徒弟:"))
        appr_combo = QComboBox()
        sel_row.addWidget(appr_combo, 1)
        gl.addLayout(sel_row)
        gl.addWidget(hint_label("勾选要加入计划的课程："))
        course_holder = card(padding=12)
        course_area = QVBoxLayout(course_holder)
        course_area.setSpacing(4)
        gl.addWidget(course_holder)
        msg = hint_label("")
        gl.addWidget(msg)
        create_btn = primary_button("创建计划")
        gl.addWidget(create_btn, alignment=Qt.AlignLeft)
        layout.addWidget(g)

        self._course_checks = []

        self._api_call("GET", f"{BASE_URL}/api/master/apprentices", callback=lambda r: [
            appr_combo.addItem(a.get("full_name") or a["username"], a["id"])
            for a in r.get("apprentices", [])])

        def fill_courses(r):
            courses = r.get("courses", [])
            if not courses:
                course_area.addWidget(hint_label("暂无课程，请联系管理员在课程库添加"))
                return
            for c in courses:
                cb = QCheckBox(f'{c["title"]}  [{c.get("type", "")}]')
                self._course_checks.append((c["id"], cb))
                course_area.addWidget(cb)
        # P1 装配修正：原调 /api/admin/courses（需 admin 守卫，师傅会拿到 403），
        # 改为 /api/master/courses（仅需登录 + 同公司隔离）。
        self._api_call("GET", f"{BASE_URL}/api/master/courses", callback=fill_courses)

        def create_plan():
            aid = appr_combo.currentData()
            cids = [cid for cid, cb in self._course_checks if cb.isChecked()]
            if not aid:
                msg.setText("请选择徒弟")
                return
            if not cids:
                msg.setText("请勾选课程")
                return
            msg.setText("创建中...")
            self._api_call("POST", f"{BASE_URL}/api/master/plans",
                           {"apprentice_id": aid, "name": "定制培养计划", "course_ids": cids},
                           callback=lambda r: (
                               msg.setText("✅ 创建成功！" if r.get("success") else r.get("message", "")),
                               self._load_page("master_plans") if r.get("success") else None))
        create_btn.clicked.connect(create_plan)

        layout.addWidget(section_label("📋 已有计划"))
        loading = loading_label()
        layout.addWidget(loading)

        def show_plans(res):
            loading.hide()
            plans = res.get("plans", [])
            if not plans:
                layout.addWidget(empty_label("暂无计划"))
                return
            for p in plans:
                pf = card(padding=12)
                pl = QHBoxLayout(pf)
                name = QLabel(f'{p["name"]}  →  {p.get("apprentice_name", "")}')
                name.setStyleSheet(f"font-weight:600;color:{Color.TEXT};font-size:20px;background:transparent;")
                pl.addWidget(name)
                pl.addStretch()
                t = QLabel(str(p.get("created_at", ""))[:16])
                t.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:18px;background:transparent;")
                pl.addWidget(t)
                layout.addWidget(pf)

        self._api_call("GET", f"{BASE_URL}/api/master/plans", callback=show_plans)

    # ==================== 批改检测 ====================
    def _build_master_grading(self, layout, container):
        layout.addWidget(hint_label("选择徒弟，查看其检测提交记录，进行终评改分与当日进度判定。"))
        sel = QComboBox()
        sel.addItem("-- 选择徒弟 --", 0)
        layout.addWidget(sel)
        area = QVBoxLayout()
        area.setSpacing(10)
        layout.addLayout(area)

        self._api_call("GET", f"{BASE_URL}/api/master/apprentices", callback=lambda r: [
            sel.addItem(a.get("full_name") or a["username"], a["id"])
            for a in r.get("apprentices", [])])

        sel.currentIndexChanged.connect(
            lambda idx: self._load_quizzes(sel.itemData(idx) or 0, area))

    def _load_quizzes(self, appr_id, area):
        self._clear_layout(area)
        if not appr_id:
            return
        loading = loading_label()
        area.addWidget(loading)

        def show(res):
            loading.hide()
            quizzes = res.get("quizzes", [])
            if not res.get("success"):
                area.addWidget(empty_label(res.get("message", "加载失败")))
                return
            if not quizzes:
                area.addWidget(empty_label("该徒弟暂无检测提交"))
                return
            for q in quizzes:
                qf = card(accent=Color.WARNING, padding=12)
                ql = QVBoxLayout(qf)
                ql.setSpacing(6)
                head = QHBoxLayout()
                title = QLabel(q.get("course_title") or f'任务 #{q.get("plan_item_id", "")}')
                title.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:20px;background:transparent;")
                head.addWidget(title)
                head.addWidget(badge(f'第{q.get("attempt", 1)}次',
                                     Color.INFO, "#e0f2fe"))
                status = q.get("status", "")
                st_color = Color.SUCCESS if status == "passed" else Color.WARNING
                head.addWidget(badge(status or "待评", st_color,
                                     Color.SUCCESS_SOFT if status == "passed" else Color.WARNING_SOFT))
                head.addStretch()
                ql.addLayout(head)

                ans = QLabel(f'答案: {q.get("answer", "")[:200]}')
                ans.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;background:transparent;")
                ans.setWordWrap(True)
                ql.addWidget(ans)
                ai = QLabel(f'AI 初评: {q.get("ai_score", "-")}    '
                            f'师傅终评: {q.get("master_score") if q.get("master_score") is not None else "未评"}')
                ai.setStyleSheet(f"color:{Color.TEXT};font-size:19px;font-weight:600;background:transparent;")
                ql.addWidget(ai)

                grade_row = QHBoxLayout()
                grade_row.addWidget(QLabel("终评分数:"))
                spin = QDoubleSpinBox()
                spin.setRange(0, 100)
                spin.setDecimals(0)
                spin.setValue(float(q.get("master_score") or q.get("ai_score") or 0))
                spin.setFixedWidth(90)
                grade_row.addWidget(spin)
                pass_btn = success_button("✅ 通过并保存")
                pass_btn.clicked.connect(
                    lambda checked, qid=q["id"], sp=spin: self._score_quiz(qid, sp.value(), "passed", area))
                grade_row.addWidget(pass_btn)
                fail_btn = secondary_button("需重做")
                fail_btn.clicked.connect(
                    lambda checked, qid=q["id"], sp=spin: self._score_quiz(qid, sp.value(), "redo", area))
                grade_row.addWidget(fail_btn)
                grade_row.addStretch()
                ql.addLayout(grade_row)
                area.addWidget(qf)

        self._api_call("GET", f"{BASE_URL}/api/master/apprentice/{appr_id}/quizzes", callback=show)

    def _score_quiz(self, quiz_id, score, status, area):
        self._api_call("POST", f"{BASE_URL}/api/master/quizzes/{quiz_id}/score",
                       {"master_score": score, "status": status},
                       callback=lambda r: QMessageBox.information(self, "结果", r.get("message", "已保存")))

    # ==================== 学情看板 ====================
    def _build_master_dashboard(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show_apprentices(res):
            loading.hide()
            apps = res.get("apprentices", [])
            if not apps:
                layout.addWidget(empty_label("暂无徒弟"))
                return
            layout.addWidget(hint_label("选择要查看的徒弟："))
            sel = QComboBox()
            sel.addItem("-- 选择徒弟 --", 0)
            for a in apps:
                sel.addItem(a.get("full_name") or a["username"], a["id"])
            layout.addWidget(sel)
            dash_area = QVBoxLayout()
            dash_area.setSpacing(10)
            layout.addLayout(dash_area)
            sel.currentIndexChanged.connect(
                lambda idx: self._show_dashboard(sel.itemData(idx) or 0, dash_area))

        self._api_call("GET", f"{BASE_URL}/api/master/apprentices", callback=show_apprentices)

    def _show_dashboard(self, appr_id, area):
        self._clear_layout(area)
        if not appr_id:
            return
        loading = loading_label()
        area.addWidget(loading)

        def show(res):
            loading.hide()
            if not res.get("success"):
                area.addWidget(empty_label("加载失败"))
                return
            mastery = res.get("mastery", [])
            if not mastery:
                area.addWidget(empty_label("该徒弟暂未完成摸底考试"))
                return
            wrap = QGroupBox("🎯 知识掌握等级")
            wl = QVBoxLayout(wrap)
            wl.setSpacing(10)
            for m in mastery:
                wl.addLayout(_mastery_bar(m))
            area.addWidget(wrap)

        self._api_call("GET", f"{BASE_URL}/api/master/dashboard/{appr_id}", callback=show)

    # ---------- 工具 ----------
    @staticmethod
    def _clear_layout(sub):
        while sub.count():
            item = sub.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                MasterPagesMixin._clear_layout(item.layout())


class PathDropLineEdit(QLineEdit):
    """支持将本地文件夹 / 文件拖拽放入的输入框。

    拖入时高亮边框；drop 时把 mimeData 中的本地路径以 "; " 拼接回填，
    与「📂 浏览…」按钮的回填格式一致，最终统一交给 /api/master/ingest。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "QLineEdit{border:1.5px solid #e6d2d2;border-radius:10px;padding:12px 14px;"
            "font-size:20px;background:#ffffff;color:#1f1a1a;}"
            "QLineEdit[focus]{border-color:#dc2626;}"
            "QLineEdit[dragOver=true]{border:2px solid #dc2626;background:#fef2f2;}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if paths:
                existing = self.text().strip()
                merged = "; ".join([p for p in (existing.split("; ") if existing else []) + paths if p])
                self.setText(merged)
            event.acceptProposedAction()
        self.setProperty("dragOver", False)
        self.style().polish(self)
        super().dropEvent(event)


def _mastery_bar(m: dict) -> QVBoxLayout:
    """知识点掌握进度条（熟练/了解/未知 -> 90/50/20）。"""
    level = m.get("level", "")
    pct = 90 if level == "熟练" else 50 if level == "了解" else 20
    color = Color.SUCCESS if pct >= 90 else Color.WARNING if pct >= 50 else Color.DANGER
    box = QVBoxLayout()
    box.setSpacing(3)
    lbl = QLabel(f'{m.get("dim_name", "")} — {level}')
    lbl.setStyleSheet(f"color:{Color.TEXT};font-size:19.5px;font-weight:600;background:transparent;")
    box.addWidget(lbl)
    bar = QProgressBar()
    bar.setMaximum(100)
    bar.setValue(pct)
    bar.setTextVisible(False)
    bar.setStyleSheet(
        f"QProgressBar{{border:none;border-radius:5px;background:#e9edf3;height:10px;}}"
        f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
    box.addWidget(bar)
    return box
