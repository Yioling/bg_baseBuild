"""通知中心：列表、未读红点、全部已读。"""
from PyQt5.QtWidgets import QHBoxLayout, QLabel
from PyQt5.QtCore import Qt

from ui.api import BASE_URL
from ui.theme import (
    Color, card, loading_label, empty_label, secondary_button, badge,
)


class NotifyPagesMixin:
    def _build_notifications(self, layout, container):
        head = QHBoxLayout()
        self._unread_lbl = QLabel("")
        self._unread_lbl.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:15px;font-weight:600;")
        head.addWidget(self._unread_lbl)
        head.addStretch()
        mark_btn = secondary_button("全部标为已读")
        mark_btn.clicked.connect(lambda: self._api_call(
            "POST", f"{BASE_URL}/api/notifications/read", {},
            callback=lambda r: (self._load_page("notifications"),
                                self._refresh_notify_badge())))
        head.addWidget(mark_btn)
        layout.addLayout(head)

        loading = loading_label()
        layout.addWidget(loading)

        def show(res):
            loading.hide()
            unread = res.get("unread_count", 0)
            self._unread_lbl.setText(f"未读 {unread} 条" if unread else "全部已读 ✅")
            notes = res.get("notifications", [])
            if not notes:
                layout.addWidget(empty_label("暂无通知"))
                return
            for n in notes:
                is_unread = not n.get("read")
                nf = card(accent=Color.PRIMARY if is_unread else None, padding=10)
                nl = QHBoxLayout(nf)
                if is_unread:
                    dot = QLabel("●")
                    dot.setStyleSheet(f"color:{Color.PRIMARY};font-size:12px;")
                    nl.addWidget(dot)
                nl.addWidget(badge(n.get("type", "系统"), Color.INFO, "#e0f2fe"))
                content = QLabel(n.get("content", ""))
                content.setWordWrap(True)
                content.setStyleSheet(
                    f'color:{Color.TEXT};font-size:14.5px;'
                    f'font-weight:{"600" if is_unread else "400"};')
                nl.addWidget(content, 1)
                t = QLabel(str(n.get("created_at", ""))[:16])
                t.setStyleSheet(f"color:{Color.TEXT_MUTED};font-size:13px;")
                nl.addWidget(t)
                layout.addWidget(nf)

        self._api_call("GET", f"{BASE_URL}/api/notifications", callback=show)
