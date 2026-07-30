"""交流圈：发帖、帖子列表、点赞、评论对话框。"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QGroupBox,
    QDialog, QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt

from ui.api import BASE_URL
from ui.theme import (
    Color, card, hint_label, loading_label, empty_label,
    primary_button, ghost_button, badge,
)

_ROLE_NAMES = {"admin": "管理员", "master": "师傅", "apprentice": "徒弟"}


class SocialPagesMixin:
    def _build_social_posts(self, layout, container):
        g = QGroupBox("✍️ 发帖")
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        post_input = QTextEdit()
        post_input.setMaximumHeight(84)
        post_input.setPlaceholderText("分享你的想法、学习心得，可 @同事 提醒 TA…")
        gl.addWidget(post_input)
        post_msg = hint_label("")
        gl.addWidget(post_msg)
        post_btn = primary_button("发布")
        gl.addWidget(post_btn, alignment=Qt.AlignRight)

        def do_post():
            content = post_input.toPlainText().strip()
            if not content:
                post_msg.setText("说点什么吧")
                return
            self._api_call("POST", f"{BASE_URL}/api/posts",
                           {"content": content,
                            "author_name": self.user.get("full_name") or self.user.get("username", "")},
                           callback=lambda r: (
                               post_input.clear(),
                               post_msg.setText("✅ 发布成功！" if r.get("success") else r.get("message", "")),
                               self._load_page("social_posts") if r.get("success") else None))
        post_btn.clicked.connect(do_post)
        layout.addWidget(g)

        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            posts = res.get("posts", [])
            if not posts:
                layout.addWidget(empty_label("暂无帖子，来发第一帖吧"))
                return
            for p in posts:
                pf = card(padding=14)
                pl = QVBoxLayout(pf)
                pl.setSpacing(6)

                head = QHBoxLayout()
                author = QLabel(p.get("author_name", ""))
                author.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:15px;")
                head.addWidget(author)
                role = p.get("author_role", "")
                if role:
                    head.addWidget(badge(_ROLE_NAMES.get(role, role),
                                         Color.PRIMARY, Color.PRIMARY_SOFT))
                head.addStretch()
                t = QLabel(str(p.get("created_at", ""))[:19])
                t.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:13px;")
                head.addWidget(t)
                pl.addLayout(head)

                ct = QLabel(p.get("content", ""))
                ct.setWordWrap(True)
                ct.setStyleSheet(f"color:{Color.TEXT};font-size:15.5px;padding:2px 0;")
                pl.addWidget(ct)

                actions = QHBoxLayout()
                like_btn = ghost_button(
                    f'{"❤️" if p.get("liked_by_me") else "🤍"} {p.get("likes_count", 0)}')
                like_btn.clicked.connect(lambda checked, pid=p["id"]: self._api_call(
                    "POST", f"{BASE_URL}/api/posts/{pid}/like", {},
                    callback=lambda r: self._load_page("social_posts")))
                actions.addWidget(like_btn)
                cmt_btn = ghost_button(f'💬 {p.get("comments_count", 0)} 评论')
                cmt_btn.clicked.connect(lambda checked, pid=p["id"]: self._show_comments(pid))
                actions.addWidget(cmt_btn)
                actions.addStretch()
                pl.addLayout(actions)
                layout.addWidget(pf)

        self._api_call("GET", f"{BASE_URL}/api/posts", callback=show)

    # ---------- 评论对话框 ----------
    def _show_comments(self, post_id):
        dlg = QDialog(self)
        dlg.setWindowTitle("评论")
        dlg.resize(440, 460)
        dl = QVBoxLayout(dlg)
        dl.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder.setStyleSheet(f"background:{Color.BG};")
        c_list = QVBoxLayout(holder)
        c_list.setSpacing(8)
        c_list.addStretch()
        scroll.setWidget(holder)
        dl.addWidget(scroll, 1)

        row = QHBoxLayout()
        cmt_in = QLineEdit()
        cmt_in.setPlaceholderText("写评论...")
        row.addWidget(cmt_in, 1)
        send = primary_button("发送")
        row.addWidget(send)
        dl.addLayout(row)

        def render(res):
            while c_list.count() > 1:
                item = c_list.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            comments = res.get("comments", [])
            if not comments:
                c_list.insertWidget(0, empty_label("暂无评论"))
                return
            for c in comments:
                cf = card(padding=10)
                cl = QVBoxLayout(cf)
                cl.setSpacing(2)
                head = QLabel(f'{c.get("author_name") or c.get("author_id", "")}')
                head.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:14px;")
                cl.addWidget(head)
                body = QLabel(c.get("content", ""))
                body.setWordWrap(True)
                body.setStyleSheet(f"color:{Color.TEXT};font-size:14.5px;")
                cl.addWidget(body)
                c_list.insertWidget(c_list.count() - 1, cf)

        def reload():
            self._api_call("GET", f"{BASE_URL}/api/posts/{post_id}/comments", callback=render)

        def do_send():
            content = cmt_in.text().strip()
            if not content:
                return
            cmt_in.clear()
            self._api_call("POST", f"{BASE_URL}/api/posts/{post_id}/comments",
                           {"content": content}, callback=lambda r: reload())

        send.clicked.connect(do_send)
        cmt_in.returnPressed.connect(do_send)
        reload()
        dlg.exec_()
