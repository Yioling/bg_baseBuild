"""进度三视图：公司 / 部门 / 同门 排行（契约：/api/progress/*）。"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QComboBox

from ui.api import BASE_URL
from ui.theme import Color, card, loading_label, empty_label, _scaled, progress_bar


class ProgressPagesMixin:
    def _build_progress_view(self, layout, container):
        role = self.user.get("role")
        tabs = [("公司", "company"), ("部门", "department"), ("同门", "same-master")]
        if role == "admin":
            tabs = [("公司", "company")]
        sel = QComboBox()
        for name, key in tabs:
            sel.addItem(f"视图：{name}", key)
        layout.addWidget(sel)
        area = QVBoxLayout()
        area.setSpacing(8)
        layout.addLayout(area)
        sel.currentIndexChanged.connect(lambda: self._load_progress(sel.currentData(), area))
        self._load_progress(tabs[0][1], area)

    def _load_progress(self, ptype, area):
        while area.count():
            item = area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        loading = loading_label()
        area.addWidget(loading)
        self._api_call("GET", f"{BASE_URL}/api/progress/{ptype}",
                       callback=lambda r: self._show_progress(loading, r, area))

    def _show_progress(self, loading, res, area):
        loading.hide()
        apps = res.get("apprentices", [])
        if not apps:
            area.addWidget(empty_label("暂无数据"))
            return
        for a in apps:
            rank = a.get("rank", "-")
            color = Color.RANK[min((rank if isinstance(rank, int) else 4) - 1, 3)] \
                if rank != "-" else Color.BORDER
            af = card(accent=color, padding=10)
            al = QHBoxLayout(af)
            rk = QLabel(f"#{rank}")
            rk.setStyleSheet(f"font-size:22px;font-weight:800;color:{color};min-width:34px;background:transparent;")
            al.addWidget(rk)

            info = QVBoxLayout()
            info.setSpacing(2)
            name = QLabel(f'{a.get("apprentice_name", "")}  ({a.get("employee_no") or "-"})')
            name.setStyleSheet(f"font-weight:700;color:{Color.TEXT};font-size:20px;background:transparent;")
            info.addWidget(name)
            master = QLabel(f'师傅: {a.get("master_name") or "-"}')
            master.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:18.5px;background:transparent;")
            info.addWidget(master)
            al.addLayout(info)
            al.addStretch()

            pct = a.get("progress_pct", 0) or 0
            bar = progress_bar(value=int(pct), maximum=100, color=Color.PRIMARY, height=14)
            bar.setFixedWidth(_scaled(140))
            al.addWidget(bar)
            pl = QLabel(f"{pct}%")
            pl.setStyleSheet(f"color:{Color.PRIMARY};font-size:{_scaled(19)}px;font-weight:700;min-width:{_scaled(42)}px;background:transparent;")
            al.addWidget(pl)
            sc = QLabel(f'{a.get("avg_score", 0)} 分')
            sc.setStyleSheet(f"color:{Color.TEXT_SUB};font-size:{_scaled(19)}px;min-width:{_scaled(44)}px;background:transparent;")
            al.addWidget(sc)
            area.addWidget(af)
