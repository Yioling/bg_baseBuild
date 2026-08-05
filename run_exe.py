"""打包后的 exe 入口：启动桌面 PyQt5 应用。"""
import sys
import os
import io
import threading
import asyncio
import time
from pathlib import Path

# PyInstaller --windowed 下重定向 stdout/stderr
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

if getattr(sys, 'frozen', False):
    BASE = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).resolve().parent

os.chdir(BASE)
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'backend'))

# 确保数据目录
if getattr(sys, 'frozen', False):
    import os as _os
    data_dir = Path(_os.getenv('APPDATA', str(Path.home()))) / 'TSForce_MentorAI'
    data_dir.mkdir(parents=True, exist_ok=True)
else:
    (BASE / 'backend' / 'data').mkdir(parents=True, exist_ok=True)

import requests
import uvicorn
from backend.main import app

SERVER_PORT = 8000


def start_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(app, host='127.0.0.1', port=SERVER_PORT, log_level='warning')
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


if __name__ == '__main__':
    # 预置演示账号
    from backend.db import init_db, get_conn
    from backend.auth import hash_password
    init_db()
    conn = get_conn()
    # 管理员（可审核注册）
    if not conn.execute("SELECT id FROM users WHERE username='ts_admin'").fetchone():
        conn.execute(
            "INSERT INTO users (username, password_hash, role, company_id, full_name, status, employee_no) "
            "VALUES (?, ?, 'admin', 1, '管理员', 'approved', 'A001')",
            ('ts_admin', hash_password('admin123')))
    # 师傅
    if not conn.execute("SELECT id FROM users WHERE username='ts_master'").fetchone():
        conn.execute(
            "INSERT INTO users (username, password_hash, role, company_id, full_name, status, employee_no) "
            "VALUES (?, ?, 'master', 1, '" "张师傅', 'approved', 'M001')",
            ('ts_master', hash_password('master123')))
    # 徒弟（绑定到师傅）
    if not conn.execute("SELECT id FROM users WHERE username='ts_apprentice'").fetchone():
        mr = conn.execute("SELECT id FROM users WHERE username='ts_master'").fetchone()
        if mr:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, master_id, company_id, full_name, status, employee_no) "
                "VALUES (?, ?, 'apprentice', ?, 1, '李徒弟', 'approved', ?)",
                ('ts_apprentice', hash_password('appr123'), mr['id'], 'E001'))
    conn.commit()
    conn.close()

    # 启动后端
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 等待就绪（首次启动可能需下载嵌入模型，延长等待）
    ready = False
    for i in range(120):
        try:
            requests.get(f'http://127.0.0.1:{SERVER_PORT}/api/me', timeout=2)
            ready = True
            break
        except:
            time.sleep(0.5)
    if not ready:
        # 服务启动失败，用 tkinter 弹窗提示
        try:
            import tkinter.messagebox as mb
            mb.showerror('启动失败', '后端服务未能启动，请检查是否端口被占用或防火墙拦截。')
        except:
            pass
        sys.exit(1)

    # 启动桌面端（不重复启动服务器）
    from desktop_app import launch_desktop
    launch_desktop(start_server_flag=False)
