"""徒弟视图页面：概览、摸底考试、学习计划、当日复习、错题本、同门战况、我的培养计划。"""
import json

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QRadioButton, QButtonGroup, QProgressBar,
    QMessageBox, QDialog,
)
from PyQt5.QtCore import Qt

from ui.api import BASE_URL
from ui.theme import (
    Color, card, stat_card, section_label, hint_label, loading_label,
    empty_label, primary_button, success_button, secondary_button, badge,
    guide_item, GUIDE_BOX_TITLE_QSS,
)
from ui.master import _mastery_bar


def _parse_options(opts):
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except (ValueError, TypeError):
            opts = [opts]
    return opts if isinstance(opts, list) else []


class ApprenticePagesMixin:
    # ==================== 概览 ====================
    def _build_appr_overview(self, layout, container):
        guide = QGroupBox("🚀 新手上路")
        guide.setStyleSheet(GUIDE_BOX_TITLE_QSS)
        gl = QVBoxLayout(guide)
        gl.setSpacing(14)
        for s in [
            "1. 摸底考试 → 让 AI 评估你的知识水平",
            "2. 等待师傅生成学习计划",
            "3. 按计划学习 → 下载每日 PDF 讲义到桌面",
            "4. 当日复习 → 检验学习成果",
            "5. 同门战况 → 看看师兄弟们的进度",
        ]:
            gl.addWidget(guide_item(s))
        layout.addWidget(guide)

        loading = loading_label()
        layout.addWidget(loading)

        def show_stats(res):
            loading.hide()
            a_count = len(res.get("assess_mistakes", [])) if res.get("success") else 0
            r_count = len(res.get("review_mistakes", [])) if res.get("success") else 0
            grid = QGridLayout()
            grid.setSpacing(14)
            grid.addWidget(stat_card(a_count + r_count, "错题总数", Color.DANGER), 0, 0)
            grid.addWidget(stat_card(f"{a_count} / {r_count}", "考试 / 复习错题", Color.WARNING), 0, 1)
            layout.addLayout(grid)

        self._api_call("GET", f"{BASE_URL}/api/apprentice/mistakes", callback=show_stats)

    # ==================== 摸底考试 ====================
    def _build_appr_assess(self, layout, container):
        self._assess_data = getattr(self, "_assess_data", None)
        self._assess_idx = getattr(self, "_assess_idx", 0)
        self._assess_area = QVBoxLayout()
        self._assess_area.setSpacing(10)
        layout.addLayout(self._assess_area)

        if not self._assess_data:
            self._assess_area.addWidget(hint_label(
                "AI 将基于师傅的知识库为你出题，涵盖各知识维度，由易到难逐步评测。"))
            start_btn = primary_button("🚀 开始摸底考试")
            start_btn.clicked.connect(lambda: self._api_call(
                "POST", f"{BASE_URL}/api/apprentice/assessment/start", {},
                callback=self._on_assess_start))
            self._assess_area.addWidget(start_btn, alignment=Qt.AlignLeft)
        else:
            self._show_assess_question()

    def _on_assess_start(self, res):
        if res.get("success"):
            self._assess_data = res
            self._assess_idx = 0
            self._load_page("appr_assess")
        else:
            QMessageBox.warning(self, "错误", res.get("message", "出题失败"))

    def _show_assess_question(self):
        area = self._assess_area
        questions = self._assess_data["questions"]
        if self._assess_idx >= len(questions):
            done = QLabel("🎉 摸底考试完成！")
            done.setStyleSheet(f"font-size:25px;color:{Color.SUCCESS};font-weight:800;background:transparent;")
            area.addWidget(done)
            self._api_call(
                "GET",
                f'{BASE_URL}/api/apprentice/assessment/result/{self._assess_data["assessment_id"]}',
                callback=lambda r: self._show_assess_result(r, area))
            reset_btn = secondary_button("重新考试")
            reset_btn.clicked.connect(lambda: (
                setattr(self, "_assess_data", None),
                setattr(self, "_assess_idx", 0),
                self._load_page("appr_assess")))
            area.addWidget(reset_btn, alignment=Qt.AlignLeft)
            return

        q = questions[self._assess_idx]
        qf = card(padding=16)
        ql = QVBoxLayout(qf)
        ql.setSpacing(8)
        head = QHBoxLayout()
        idx = QLabel(f"题目 {self._assess_idx + 1} / {len(questions)}")
        idx.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;font-weight:600;background:transparent;")
        head.addWidget(idx)
        head.addWidget(badge(q.get("difficulty", ""), Color.WARNING, Color.WARNING_SOFT))
        head.addWidget(badge(q.get("qtype", ""), Color.INFO, "#e0f2fe"))
        head.addStretch()
        ql.addLayout(head)

        qt = QLabel(q.get("question", ""))
        qt.setStyleSheet(f"font-size:22px;font-weight:700;color:{Color.TEXT};background:transparent;")
        qt.setWordWrap(True)
        ql.addWidget(qt)

        self._answer_widget = None
        if q.get("qtype") == "choice" and q.get("options"):
            group = QButtonGroup(self)
            for opt in _parse_options(q["options"]):
                rb = QRadioButton(str(opt))
                group.addButton(rb)
                ql.addWidget(rb)
            self._answer_widget = group
        else:
            te = QTextEdit()
            te.setMaximumHeight(90)
            te.setPlaceholderText("请输入你的答案...")
            ql.addWidget(te)
            self._answer_widget = te

        submit = primary_button("提交答案")
        submit.clicked.connect(lambda: self._submit_assess(q))
        ql.addWidget(submit, alignment=Qt.AlignLeft)
        area.addWidget(qf)

    def _submit_assess(self, q):
        answer = self._collect_answer(self._answer_widget)
        if answer is None:
            return
        self._api_call("POST", f"{BASE_URL}/api/apprentice/assessment/answer",
                       {"question_id": q["id"], "answer": answer},
                       callback=self._on_assess_answer)

    def _collect_answer(self, widget):
        """从选择题按钮组或文本框收集答案；不合法时弹提示并返回 None。"""
        if isinstance(widget, QButtonGroup):
            checked = widget.checkedButton()
            if not checked:
                QMessageBox.warning(self, "提示", "请选择一个选项")
                return None
            return checked.text()[0]
        answer = widget.toPlainText().strip()
        if not answer:
            QMessageBox.warning(self, "提示", "请输入答案")
            return None
        return answer

    def _on_assess_answer(self, res):
        if not res.get("success"):
            QMessageBox.warning(self, "错误", res.get("message", "提交失败"))
            return
        ok = res.get("score", 0) >= 60
        fb = QLabel(f'得分: {res.get("score", 0)} | {res.get("feedback", "")}\n'
                    f'正确答案: {res.get("answer_key", "")}')
        fb.setStyleSheet(
            f'background:{Color.SUCCESS_SOFT if ok else Color.DANGER_SOFT};'
            f'color:{"#065f46" if ok else "#991b1b"};'
            f'padding:12px;border-radius:8px;font-size:25px;')
        fb.setWordWrap(True)
        self._assess_area.addWidget(fb)
        self._assess_idx += 1
        next_btn = primary_button("下一题 →")
        next_btn.clicked.connect(lambda: self._load_page("appr_assess"))
        self._assess_area.addWidget(next_btn, alignment=Qt.AlignLeft)

    def _show_assess_result(self, res, area):
        mastery = res.get("mastery", [])
        if not mastery:
            return
        wrap = QGroupBox("📊 掌握等级")
        wl = QVBoxLayout(wrap)
        wl.setSpacing(10)
        for m in mastery:
            wl.addLayout(_mastery_bar(m))
        area.addWidget(wrap)

    # ==================== 学习计划 ====================
    def _build_appr_plan(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            if not res.get("success") or not res.get("today"):
                layout.addWidget(empty_label("暂无学习计划，请联系师傅为您生成"))
                return
            today = res["today"]
            tasks = today.get("tasks", [])

            df = card(accent=Color.PRIMARY, padding=16)
            dl = QVBoxLayout(df)
            dl.setSpacing(8)
            hdr = QHBoxLayout()
            plan_label = QLabel(f'📖 今日学习 (Day {today.get("day_index", "")})')
            plan_label.setStyleSheet(f"font-size:23px;font-weight:800;color:{Color.TEXT};background:transparent;")
            hdr.addWidget(plan_label)
            hdr.addStretch()
            pdf_btn = success_button("📄 下载 PDF 讲义到桌面")
            pdf_btn.clicked.connect(lambda: self._api_call(
                "GET", f"{BASE_URL}/api/apprentice/pdf/today",
                callback=lambda r: QMessageBox.information(self, "PDF", r.get("message", ""))))
            hdr.addWidget(pdf_btn)
            dl.addLayout(hdr)

            if today.get("note"):
                dl.addWidget(hint_label(f'📝 {today["note"]}'))

            for t in tasks:
                row = QHBoxLayout()
                tl = QLabel(f'[{t.get("task_type", "")}] {t.get("title", "")}')
                tl.setStyleSheet(f"color:{Color.TEXT};font-size:25px;background:transparent;")
                row.addWidget(tl)
                row.addStretch()
                dur = QLabel(f'{t.get("duration_min", 0)} 分钟')
                dur.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;background:transparent;")
                row.addWidget(dur)
                dl.addLayout(row)

            total = QLabel(f'总时长: {sum(t.get("duration_min", 0) for t in tasks)} 分钟')
            total.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;font-weight:600;background:transparent;")
            dl.addWidget(total)
            layout.addWidget(df)

            chat_g = QGroupBox("🤖 AI 陪练答疑")
            chat_l = QVBoxLayout(chat_g)
            chat_l.setSpacing(8)
            self._chat_area = QTextEdit()
            self._chat_area.setReadOnly(True)
            self._chat_area.setMaximumHeight(220)
            chat_l.addWidget(self._chat_area)
            chat_row = QHBoxLayout()
            chat_input = QLineEdit()
            chat_input.setPlaceholderText("向 AI 导师提问...")
            chat_input.returnPressed.connect(lambda: self._do_chat(chat_input))
            chat_row.addWidget(chat_input, 1)
            chat_btn = primary_button("发送")
            chat_btn.clicked.connect(lambda: self._do_chat(chat_input))
            chat_row.addWidget(chat_btn)
            chat_l.addLayout(chat_row)
            layout.addWidget(chat_g)

        self._api_call("GET", f"{BASE_URL}/api/apprentice/plan/today", callback=show)

    def _do_chat(self, chat_input):
        q = chat_input.text().strip()
        if not q:
            return
        self._chat_area.append(f"🧑 {q}")
        chat_input.clear()
        self._api_call("POST", f"{BASE_URL}/api/apprentice/ask", {"question": q},
                       callback=lambda r: self._chat_area.append(
                           f'🤖 {r.get("answer", r.get("message", ""))}\n'))

    # ==================== 当日复习 ====================
    def _build_appr_review(self, layout, container):
        self._review_data = getattr(self, "_review_data", None)
        self._review_idx = getattr(self, "_review_idx", 0)
        self._review_area = QVBoxLayout()
        self._review_area.setSpacing(10)
        layout.addLayout(self._review_area)

        if not self._review_data:
            loading = loading_label("获取今日计划...")
            self._review_area.addWidget(loading)
            self._api_call("GET", f"{BASE_URL}/api/apprentice/plan/today",
                           callback=lambda r: self._start_review_check(loading, r))
        else:
            self._show_review_question()

    def _start_review_check(self, loading, res):
        loading.hide()
        if not res.get("success") or not res.get("today"):
            self._review_area.addWidget(empty_label("暂无今日学习计划"))
            return
        day_id = res["today"]["id"]
        self._review_area.addWidget(hint_label("基于今日学习内容，AI 将生成复习题检验掌握程度。"))
        start_btn = primary_button("🔄 开始当日复习")
        start_btn.clicked.connect(lambda: self._api_call(
            "POST", f"{BASE_URL}/api/apprentice/review/start",
            {"plan_day_id": day_id}, callback=self._on_review_start))
        self._review_area.addWidget(start_btn, alignment=Qt.AlignLeft)

    def _on_review_start(self, res):
        if res.get("success"):
            self._review_data = res
            self._review_idx = 0
            self._load_page("appr_review")
        else:
            QMessageBox.warning(self, "错误", res.get("message", ""))

    def _show_review_question(self):
        area = self._review_area
        questions = self._review_data["questions"]
        if self._review_idx >= len(questions):
            done = QLabel("🎉 复习完成！")
            done.setStyleSheet(f"font-size:23px;color:{Color.SUCCESS};font-weight:800;background:transparent;")
            area.addWidget(done)
            reset_btn = secondary_button("再次复习")
            reset_btn.clicked.connect(lambda: (
                setattr(self, "_review_data", None),
                setattr(self, "_review_idx", 0),
                self._load_page("appr_review")))
            area.addWidget(reset_btn, alignment=Qt.AlignLeft)
            return

        q = questions[self._review_idx]
        qf = card(padding=16)
        ql = QVBoxLayout(qf)
        ql.setSpacing(8)
        idx_l = QLabel(f"题目 {self._review_idx + 1} / {len(questions)}")
        idx_l.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;font-weight:600;background:transparent;")
        ql.addWidget(idx_l)
        q_l = QLabel(q.get("question", ""))
        q_l.setStyleSheet(f"font-size:21px;font-weight:700;color:{Color.TEXT};background:transparent;")
        q_l.setWordWrap(True)
        ql.addWidget(q_l)

        if q.get("qtype") == "choice" and q.get("options"):
            self._r_answer = QButtonGroup(self)
            for opt in _parse_options(q["options"]):
                rb = QRadioButton(str(opt))
                self._r_answer.addButton(rb)
                ql.addWidget(rb)
        else:
            self._r_answer = QTextEdit()
            self._r_answer.setMaximumHeight(90)
            self._r_answer.setPlaceholderText("请输入你的答案...")
            ql.addWidget(self._r_answer)

        submit = primary_button("提交")
        submit.clicked.connect(lambda: self._submit_review(q))
        ql.addWidget(submit, alignment=Qt.AlignLeft)
        area.addWidget(qf)

    def _submit_review(self, q):
        answer = self._collect_answer(self._r_answer)
        if answer is None:
            return
        self._api_call("POST", f"{BASE_URL}/api/apprentice/review/answer",
                       {"question_id": q["id"], "answer": answer,
                        "review_id": self._review_data["review_id"]},
                       callback=self._on_review_answered)

    def _on_review_answered(self, res):
        ok = res.get("score", 0) >= 60
        fb = QLabel(f'得分: {res.get("score", 0)} | {res.get("feedback", "")}')
        fb.setStyleSheet(
            f'background:{Color.SUCCESS_SOFT if ok else Color.DANGER_SOFT};'
            f'color:{"#065f46" if ok else "#991b1b"};'
            f'padding:10px;border-radius:8px;font-size:25px;')
        fb.setWordWrap(True)
        self._review_area.addWidget(fb)
        self._review_idx += 1
        next_btn = primary_button("下一题 →")
        next_btn.clicked.connect(lambda: self._load_page("appr_review"))
        self._review_area.addWidget(next_btn, alignment=Qt.AlignLeft)

    # ==================== 错题本 ====================
    def _build_appr_mistakes(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            all_m = res.get("assess_mistakes", []) + res.get("review_mistakes", [])
            if not res.get("success") or not all_m:
                lbl = QLabel("🎉 太棒了！目前没有错题记录。")
                lbl.setStyleSheet(f"color:{Color.SUCCESS};font-size:21px;font-weight:600;padding:20px;background:transparent;")
                layout.addWidget(lbl)
                return
            for m in all_m:
                df = card(accent=Color.DANGER, padding=12)
                dl = QVBoxLayout(df)
                dl.setSpacing(4)
                ql = QLabel(f'❌ {m.get("question", "")}')
                ql.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:25px;background:transparent;")
                ql.setWordWrap(True)
                dl.addWidget(ql)
                for text in [
                    f'你的回答: {m.get("apprentice_answer", "未作答")}',
                    f'正确答案: {m.get("answer_key", "-")}',
                    f'得分: {m.get("score", 0)} | {m.get("feedback", "")}',
                ]:
                    dl.addWidget(hint_label(text))
                layout.addWidget(df)

        self._api_call("GET", f"{BASE_URL}/api/apprentice/mistakes", callback=show)

    # ==================== 同门战况 ====================
    def _build_appr_leaderboard(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            lb = res.get("leaderboard", [])
            if not lb:
                layout.addWidget(empty_label("暂无数据"))
                return
            for i, item in enumerate(lb):
                rank = i + 1
                color = Color.RANK[min(rank - 1, 3)]
                row = card(accent=color, padding=10)
                rl = QHBoxLayout(row)
                rk = QLabel(f"#{rank}")
                rk.setStyleSheet(f"font-size:23px;font-weight:800;color:{color};min-width:36px;background:transparent;")
                rl.addWidget(rk)
                is_me = item.get("apprentice_id") == res.get("my_id")
                name = QLabel(item.get("username", "") + ("  (我)" if is_me else ""))
                name.setStyleSheet(
                    f'font-weight:700;color:{Color.PRIMARY if is_me else Color.TEXT};font-size:25px;')
                rl.addWidget(name)
                rl.addStretch()
                for txt in [f'均分: {item.get("avg_score", 0)}',
                            f'熟练: {item.get("mastery_count", 0)} 维度',
                            f'错题: {item.get("mistake_count", 0)}']:
                    t = QLabel(txt)
                    t.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;padding:0 6px;background:transparent;")
                    rl.addWidget(t)
                layout.addWidget(row)

        self._api_call("GET", f"{BASE_URL}/api/apprentice/leaderboard", callback=show)

    # ==================== 我的培养计划（含任务检测） ====================
    def _build_appr_my_plans(self, layout, container):
        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            plans = res.get("plans", [])
            if not plans:
                layout.addWidget(empty_label("暂无培养计划，请等待师傅定制"))
            for p in plans:
                pf = card(accent=Color.PRIMARY, padding=14)
                pl = QVBoxLayout(pf)
                pl.setSpacing(6)
                head = QHBoxLayout()
                name = QLabel(f'📋 {p.get("name", "")}')
                name.setStyleSheet(f"font-size:22px;font-weight:800;color:{Color.TEXT};background:transparent;")
                head.addWidget(name)
                if p.get("completed_at"):
                    head.addWidget(badge("已完成", Color.SUCCESS, Color.SUCCESS_SOFT))
                head.addStretch()
                pl.addLayout(head)
                for item in p.get("items", []):
                    row = QHBoxLayout()
                    it = QLabel(f'· {item.get("course_title", "")}  [{item.get("course_type", "")}]')
                    it.setStyleSheet(f"color:{Color.TEXT};font-size:25px;background:transparent;")
                    row.addWidget(it)
                    row.addStretch()
                    quiz_btn = secondary_button("✍ 提交检测")
                    quiz_btn.clicked.connect(
                        lambda checked, iid=item["id"], title=item.get("course_title", ""):
                        self._open_quiz_dialog(iid, title))
                    row.addWidget(quiz_btn)
                    pl.addLayout(row)
                layout.addWidget(pf)

            layout.addWidget(section_label("🧾 我的检测历史"))
            hist_loading = loading_label()
            layout.addWidget(hist_loading)
            self._api_call("GET", f"{BASE_URL}/api/apprentice/quizzes",
                           callback=lambda r: show_quizzes(hist_loading, r))

        def show_quizzes(hist_loading, res):
            hist_loading.hide()
            quizzes = res.get("quizzes", [])
            if not quizzes:
                layout.addWidget(empty_label("暂无检测记录"))
                return
            for q in quizzes:
                qf = card(padding=10)
                ql = QHBoxLayout(qf)
                t = QLabel(f'{q.get("course_title") or "任务"}  · 第{q.get("attempt", 1)}次')
                t.setStyleSheet(f"font-weight:600;color:{Color.TEXT};font-size:25px;background:transparent;")
                ql.addWidget(t)
                status = q.get("status", "")
                passed = status == "passed"
                ql.addWidget(badge("已通过" if passed else "待师傅终评",
                                   Color.SUCCESS if passed else Color.WARNING,
                                   Color.SUCCESS_SOFT if passed else Color.WARNING_SOFT))
                ql.addStretch()
                sc = QLabel(f'AI: {q.get("ai_score", "-")} | 终评: '
                            f'{q.get("master_score") if q.get("master_score") is not None else "—"}')
                sc.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:19px;background:transparent;")
                ql.addWidget(sc)
                layout.addWidget(qf)

        self._api_call("GET", f"{BASE_URL}/api/apprentice/plans", callback=show)

    def _open_quiz_dialog(self, plan_item_id, title):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"任务检测 — {title}")
        dlg.resize(460, 340)
        dl = QVBoxLayout(dlg)
        dl.setSpacing(10)
        dl.addWidget(hint_label("写下你对本课程的学习总结 / 答题内容，提交后 AI 初评，师傅终评。"))
        answer = QTextEdit()
        answer.setPlaceholderText("输入你的答案...")
        dl.addWidget(answer, 1)
        msg = hint_label("")
        dl.addWidget(msg)
        btn = primary_button("提交检测")
        dl.addWidget(btn, alignment=Qt.AlignRight)

        def submit():
            text = answer.toPlainText().strip()
            if not text:
                msg.setText("请输入答案")
                return
            btn.setEnabled(False)
            self._api_call("POST", f"{BASE_URL}/api/apprentice/quiz/submit",
                           {"plan_item_id": plan_item_id, "answer": text},
                           callback=lambda r: (
                               msg.setText(f'{"✅" if r.get("success") else "❌"} '
                                           f'{r.get("message", "")} AI初评: {r.get("ai_score", "-")}'),
                               btn.setEnabled(True)))
        btn.clicked.connect(submit)
        dlg.exec_()
