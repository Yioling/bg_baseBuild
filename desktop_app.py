"""薪火 AI 导师系统 — PyQt5 桌面应用入口（P5）。

UI 已拆分至 `ui/` 包：
- ui.theme        huashu-design 设计系统（令牌 / QSS / 组件工厂）
- ui.api          HTTP 线程层
- ui.login        登录 / 注册对话框
- ui.main_window  主窗口（侧边栏 + 页面路由）
- ui.master / ui.apprentice / ui.admin / ui.social / ui.notify / ui.progress

本文件仅保留：后端服务启动 + 应用启动流程（launch_desktop 供 run_exe.py 复用）。
"""
import os
import sys
import threading
import asyncio

import requests
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QPalette, QColor, QFont

from ui.api import SERVER_PORT, BASE_URL
from ui.login import LoginDialog
from ui.main_window import MainWindow
from ui.theme import Color


# ==================== 启动服务器线程 ====================
def start_server():
    """在后台线程启动 FastAPI。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import uvicorn
    from backend.main import app
    # 服务端监听地址：环境变量 SERVER_HOST 控制（默认 127.0.0.1）
    # 服务端模式设为 0.0.0.0 可让局域网其他电脑连接
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    config = uvicorn.Config(app, host=server_host, port=SERVER_PORT, log_level="warning")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


# ==================== 主入口 ====================
def launch_desktop(start_server_flag=True):
    """启动桌面应用。start_server_flag: 是否同时启动后端服务。"""
    import time

    if start_server_flag:
        t = threading.Thread(target=start_server, daemon=True)
        t.start()
        for _ in range(30):
            try:
                requests.get(f"{BASE_URL}/api/me", timeout=1)
                break
            except requests.RequestException:
                time.sleep(0.3)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 11))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(Color.BG))
    palette.setColor(QPalette.WindowText, QColor(Color.TEXT))
    # 输入控件 placeholder 灰化（与输入色区分，提升表单可读性）
    palette.setColor(QPalette.PlaceholderText, QColor("#9ca3af"))
    app.setPalette(palette)

    login = LoginDialog()
    if login.exec_() == QDialog.Accepted:
        window = MainWindow(login.token, login.user)
        window.showMaximized()
        app.exec_()


if __name__ == "__main__":
    launch_desktop()
