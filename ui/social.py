"""交流圈：发帖（支持图片/文件附件）、帖子列表、点赞、评论对话框。"""
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QGroupBox,
    QDialog, QScrollArea, QWidget, QFileDialog, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ui.api import BASE_URL
from ui.theme import (
    Color, card, hint_label, loading_label, empty_label,
    primary_button, ghost_button, badge, secondary_button, chip,
    screen_metrics, _scaled,
)

_ROLE_NAMES = {"admin": "管理员", "master": "师傅", "apprentice": "徒弟"}


class SocialPagesMixin:
    # 图片扩展名白名单（发帖“上传图片”入口过滤）
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    _MAX_ATTACH = 9  # 单帖附加上限

    def _build_social_posts(self, layout, container):
        g = QGroupBox("✍️ 发帖")
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        post_input = QTextEdit()
        post_input.setMaximumHeight(_scaled(84))
        post_input.setPlaceholderText("分享你的想法、学习心得，可 @同事 提醒 TA…")
        gl.addWidget(post_input)

        # ---- 附件行：上传图片 / 上传文件 + 已选附件 chips ----
        attach_row = QHBoxLayout()
        attach_row.setSpacing(10)
        img_btn = secondary_button("🖼️ 上传图片")
        file_btn = secondary_button("📎 上传文件")
        attach_row.addWidget(img_btn)
        attach_row.addWidget(file_btn)
        self._pending_attach = []          # [{"attachment_id","file_name","mime"}]
        chips_wrap = QWidget()
        chips_lay = QHBoxLayout(chips_wrap)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(6)
        chips_lay.addStretch()
        attach_row.addWidget(chips_wrap, 1)
        gl.addLayout(attach_row)

        post_msg = hint_label("")
        gl.addWidget(post_msg)
        post_btn = primary_button("发布")
        gl.addWidget(post_btn, alignment=Qt.AlignRight)

        def _render_chips():
            """重绘已选附件 chips。"""
            while chips_lay.count() > 1:
                it = chips_lay.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            for i, att in enumerate(self._pending_attach):
                c = chip(f'📎 {att["file_name"]}', Color.INFO, Color.PRIMARY_SOFT)
                c.setToolTip(att["file_name"])
                # 点击 chip 移除该附件（重新绑定 mousePressEvent 无法拦截内部，改用外层删除按钮）
                rem = QPushButton("×")
                rem.setStyleSheet(
                    f"background:transparent;border:none;color:{Color.TEXT_SUB};"
                    "font-size:18px;padding:0 4px;")
                rem.setCursor(Qt.PointingHandCursor)
                rem.setToolTip("移除")
                hc = QWidget()
                hl = QHBoxLayout(hc)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.setSpacing(0)
                hl.addWidget(c)
                hl.addWidget(rem)
                rem.clicked.connect(lambda checked, idx=i: self._remove_pending(idx))
                chips_lay.insertWidget(chips_lay.count() - 1, hc)
            # 空时隐藏整个包装容器
            chips_wrap.setVisible(bool(self._pending_attach))

        def _add_pending(att):
            if len(self._pending_attach) >= self._MAX_ATTACH:
                post_msg.setText(f"附加上限 {self._MAX_ATTACH} 个")
                return
            self._pending_attach.append(att)
            _render_chips()

        def _pick(only_images):
            paths, _ = QFileDialog.getOpenFileNames(
                self, "选择附件", "",
                "图片文件 (*.png *.jpg *.jpeg *.gif *.webp *.bmp)" if only_images
                else "所有文件 (*.*)")
            for p in paths:
                if not p:
                    continue
                if len(self._pending_attach) >= self._MAX_ATTACH:
                    post_msg.setText(f"附加上限 {self._MAX_ATTACH} 个")
                    break
                ext = Path(p).suffix.lower()
                if only_images and ext not in self._IMAGE_EXTS:
                    post_msg.setText(f"不支持的图片格式: {Path(p).name}")
                    continue
                self._upload_file(p, post_msg, _add_pending)
            if not self._pending_attach:
                _render_chips()

        img_btn.clicked.connect(lambda: _pick(True))
        file_btn.clicked.connect(lambda: _pick(False))

        def do_post():
            content = post_input.toPlainText().strip()
            if not content:
                post_msg.setText("说点什么吧")
                return
            if self._pending_attach:
                post_btn.setEnabled(False)
                img_btn.setEnabled(False)
                file_btn.setEnabled(False)
            self._api_call("POST", f"{BASE_URL}/api/posts",
                           {"content": content,
                            "author_name": self.user.get("full_name") or self.user.get("username", ""),
                            "attachment_ids": [a["attachment_id"] for a in self._pending_attach]},
                           callback=lambda r: self._on_posted(
                               r, post_input, post_msg, post_btn, img_btn, file_btn))
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
                pf = card(padding=22)
                pl = QVBoxLayout(pf)
                pl.setSpacing(10)

                head = QHBoxLayout()
                author = QLabel(p.get("author_name", ""))
                author.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:24px;background:transparent;")
                head.addWidget(author)
                role = p.get("author_role", "")
                if role:
                    rb = badge(_ROLE_NAMES.get(role, role),
                               Color.PRIMARY, Color.PRIMARY_SOFT)
                    rb.setStyleSheet(f"background:{Color.PRIMARY_SOFT};color:{Color.PRIMARY};"
                                     "border-radius:999px;padding:4px 16px;font-size:20px;font-weight:600;")
                    head.addWidget(rb)
                head.addStretch()
                t = QLabel(str(p.get("created_at", ""))[:19])
                t.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:20px;background:transparent;")
                head.addWidget(t)
                pl.addLayout(head)

                ct = QLabel(p.get("content", ""))
                ct.setWordWrap(True)
                ct.setStyleSheet(f"color:{Color.TEXT};font-size:25px;padding:4px 0;background:transparent;")
                pl.addWidget(ct)

                # ---- 附件区：图片直接内嵌展示 + 文件 chip(点击下载) ----
                atts = p.get("attachments") or []
                if atts:
                    att_layer = QHBoxLayout()
                    att_layer.setSpacing(8)
                    for att in atts:
                        mime = (att.get("mime") or "").lower()
                        url = att.get("url", "")
                        if mime.startswith("image/") and url:
                            # 图片：直接在界面内嵌显示（缩略图），不弹窗、无点击交互
                            th = QLabel()
                            th.setFixedSize(_scaled(300), _scaled(210))
                            th.setStyleSheet(f"border:1px solid {Color.BORDER};border-radius:10px;"
                                             "background:#f7f2f2;font-size:20px;color:#9ca3af;")
                            th.setAlignment(Qt.AlignCenter)
                            th.setText("加载中…")
                            att_layer.addWidget(th)
                            self._api_call("GET", f"{BASE_URL}{url}", raw=True,
                                           callback=lambda r, lbl=th: self._set_thumb(lbl, r))
                        else:
                            # 非图片文件：chip，点击下载到本地（放大附件名）
                            fchip = chip(f'📎 {att.get("file_name", "附件")}',
                                         Color.PRIMARY, Color.PRIMARY_SOFT)
                            fchip.setStyleSheet(f"background:{Color.PRIMARY_SOFT};color:{Color.PRIMARY};"
                                                "border-radius:999px;padding:10px 20px;font-size:22px;font-weight:500;")
                            fchip.setCursor(Qt.PointingHandCursor)
                            fchip.setToolTip("点击下载")
                            fchip.mousePressEvent = lambda _e, a=att: self._download_attach(a)
                            att_layer.addWidget(fchip)
                    att_layer.addStretch()
                    pl.addLayout(att_layer)

                actions = QHBoxLayout()
                like_btn = ghost_button(
                    f'{"❤️" if p.get("liked_by_me") else "🤍"} {p.get("likes_count", 0)}')
                like_btn.setStyleSheet(f"background:transparent;color:{Color.PRIMARY};border:none;"
                                       "padding:12px 20px;font-size:22px;")
                like_btn.clicked.connect(lambda checked, pid=p["id"]: self._api_call(
                    "POST", f"{BASE_URL}/api/posts/{pid}/like", {},
                    callback=lambda r: self._load_page("social_posts")))
                actions.addWidget(like_btn)
                cmt_btn = ghost_button(f'💬 {p.get("comments_count", 0)} 评论')
                cmt_btn.setStyleSheet(f"background:transparent;color:{Color.PRIMARY};border:none;"
                                      "padding:12px 20px;font-size:22px;")
                cmt_btn.clicked.connect(lambda checked, pid=p["id"]: self._show_comments(pid))
                actions.addWidget(cmt_btn)
                actions.addStretch()
                pl.addLayout(actions)
                layout.addWidget(pf)

        self._api_call("GET", f"{BASE_URL}/api/posts", callback=show)

    # ---------- 附件：上传 / 移除 / 发布回调 ----------
    def _upload_file(self, path, post_msg, on_ok):
        """multipart 上传单个附件到 /api/attachments，成功后回调 on_ok(att_meta)。"""
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            post_msg.setText(f"读取文件失败: {e}")
            return
        import urllib.parse
        fname = os.path.basename(path)
        # multipart 对非 ASCII 文件名会解析乱码，这里对文件名做 percent-encode，
        # 后端 unquote 还原，保证中文文件名在帖子里显示正确。
        safe_fname = urllib.parse.quote(fname)
        # requests multipart: {"file": (filename, bytes, mime)}
        mime = "application/octet-stream"
        ext = Path(path).suffix.lower()
        if ext in self._IMAGE_EXTS:
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}.get(ext[1:], "image/png")
        post_msg.setText(f"上传中 {fname}…")
        self._api_call("POST", f"{BASE_URL}/api/attachments",
                       files={"file": (safe_fname, data, mime)},
                       callback=lambda r: self._on_uploaded(r, post_msg, on_ok))

    def _on_uploaded(self, r, post_msg, on_ok):
        if r.get("success"):
            post_msg.setText("")
            on_ok({
                "attachment_id": r["attachment_id"],
                "file_name": r.get("file_name", "附件"),
                "mime": r.get("mime", ""),
                "url": r.get("url", ""),
            })
        else:
            post_msg.setText(f"上传失败: {r.get('message', '未知错误')}")

    def _remove_pending(self, idx):
        if 0 <= idx < len(self._pending_attach):
            self._pending_attach.pop(idx)
            self._render_chips()

    def _on_posted(self, r, post_input, post_msg, post_btn, img_btn, file_btn):
        post_btn.setEnabled(True)
        img_btn.setEnabled(True)
        file_btn.setEnabled(True)
        if r.get("success"):
            self._pending_attach = []
            post_input.clear()
            post_msg.setText("✅ 发布成功！")
            self._load_page("social_posts")
        else:
            post_msg.setText(r.get("message", "发布失败"))

    # ---------- 附件：图片预览 / 文件下载 ----------
    def _set_thumb(self, lbl, r):
        """把 raw 字节流渲染到缩略图 QLabel。"""
        try:
            if not r.get("success") or not r.get("data"):
                lbl.setText("加载失败")
                return
            pm = QPixmap()
            if pm.loadFromData(r["data"]):
                lbl.setPixmap(pm.scaled(_scaled(300), _scaled(210), Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
            else:
                lbl.setText("无法预览")
        except Exception:
            lbl.setText("无法预览")

    def _download_attach(self, att):
        """点击文件 chip → 下载到桌面并打开。
        文件名优先取前端已知的 att['file_name']（避免依赖后端 Content-Disposition 解析），
        并确保带正确扩展名，让系统能正确识别文件类型。
        """
        self._api_call("GET", f"{BASE_URL}{att.get('url', '')}", raw=True,
                       callback=lambda r: self._save_attach(r, att))

    def _save_attach(self, r, att=None):
        if not r.get("success") or not r.get("data"):
            return
        try:
            desktop = Path.home() / "Desktop"
            desktop.mkdir(exist_ok=True)
            # 文件名来源：优先前端帖子的原始文件名，其次后端解析，再兜底
            fname = ""
            if att and att.get("file_name"):
                fname = Path(att["file_name"]).name
            if not fname:
                fname = Path(r.get("file_name", "attachment")).name
            # 确保扩展名：无扩展名时按 mime 补全
            fpath = desktop / fname
            if not fpath.suffix:
                ext = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                       ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
                       ".pdf": "application/pdf"}.get(r.get("mime", "").lower().strip(),
                                                      ".bin")
                if (r.get("mime", "") or "").startswith("image/"):
                    fpath = desktop / (fname + ".png")
            fpath.write_bytes(r["data"])
            try:
                os.startfile(str(fpath))
            except (OSError, AttributeError):
                pass
        except OSError:
            pass

    # ---------- 评论对话框 ----------
    def _show_comments(self, post_id):
        dlg = QDialog(self)
        dlg.setWindowTitle("评论")
        dlg.resize(_scaled(440), _scaled(460))
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
                head.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:19px;background:transparent;")
                cl.addWidget(head)
                body = QLabel(c.get("content", ""))
                body.setWordWrap(True)
                body.setStyleSheet(f"color:{Color.TEXT};font-size:19.5px;background:transparent;")
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
