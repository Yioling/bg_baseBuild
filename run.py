"""桌面应用启动入口：后台启动 FastAPI，然后用 pywebview 打开桌面窗口。"""
import sys
import os
import time
import threading
import socket
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # 数据路径以 backend 为基准

import uvicorn


def _is_port_open(port=8000, host="127.0.0.1"):
    """检测端口是否已监听。"""
    try:
        s = socket.create_connection((host, port), timeout=0.3)
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _wait_for_server(port=8000, timeout=15):
    """轮询等待服务器就绪，返回 True 表示启动成功。"""
    start = time.time()
    while time.time() - start < timeout:
        if _is_port_open(port):
            return True
        time.sleep(0.3)
    return False


def _start_server(port=8000):
    """在 daemon 线程中启动 uvicorn。"""
    config = uvicorn.Config(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_config=None,   # 桌面模式无 TTY，禁用内置日志避免 isatty 崩溃
        access_log=False,
    )
    server = uvicorn.Server(config)

    def _run():
        server.run()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return server


def main():
    port = 8000
    url = f"http://127.0.0.1:{port}"

    print(f"[薪火] 正在启动服务...")
    server = _start_server(port)

    if not _wait_for_server(port, timeout=20):
        print("[薪火] 服务启动超时，请检查控制台错误信息。")
        sys.exit(1)

    print(f"[薪火] 服务就绪 -> {url}")

    try:
        import webview
    except ImportError:
        print("[薪火] pywebview 未安装。请执行: pip install pywebview")
        print(f"[薪火] 请手动打开浏览器访问 {url}")
        input("按回车退出...")
        return

    # 创建桌面窗口
    title = "薪火 · 师傅带徒 AI 导师系统"
    window = webview.create_window(
        title=title,
        url=url,
        width=1100,
        height=740,
        min_size=(860, 600),
        text_select=True,
        confirm_close=True,
    )
    webview.start(debug=False)
    print("[薪火] 窗口已关闭，服务退出。")


if __name__ == "__main__":
    main()
