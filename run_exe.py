"""打包后的 exe 入口：启动桌面 PyQt5 应用。

环境变量:
  SERVER_MODE=1    服务端模式（启动本地后端 + 监听 0.0.0.0）
  API_BASE=http://...  客户端模式（直接连接远程后端，不启动本地服务）
"""
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
    # 服务端模式监听 0.0.0.0，允许局域网访问
    config = uvicorn.Config(app, host='0.0.0.0', port=SERVER_PORT, log_level='warning')
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


def ensure_seed_data():
    """预置演示账号（仅服务端需要）"""
    from backend.db import init_db, get_conn
    from backend.auth import hash_password
    init_db()
    conn = get_conn()
    # 确保示例公司存在
    if not conn.execute("SELECT id FROM companies WHERE id=1").fetchone():
        conn.execute("INSERT INTO companies (id, name) VALUES (1, '示例公司（Demo）')")
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
            "VALUES (?, ?, 'master', 1, '张师傅', 'approved', 'M001')",
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


if __name__ == '__main__':
    server_mode = os.getenv('SERVER_MODE', '0') == '1'
    api_base = os.getenv('API_BASE', '')

    # 智能默认：如果设置了远程 API_BASE，一定是客户端模式
    # 如果没有设置任何环境变量，默认服务端模式（单机使用）
    if api_base and not server_mode:
        server_mode = False  # 客户端模式
    elif not api_base and not os.getenv('SERVER_MODE'):
        server_mode = True  # 默认服务端模式
        print('>>> 未设置环境变量，默认使用服务端模式（本地启动后端）')

    if server_mode:
        # ===== 服务端模式：启动后端 + 本地 UI =====
        os.environ['SERVER_HOST'] = '0.0.0.0'
        ensure_seed_data()

        # 启动后端
        t = threading.Thread(target=start_server, daemon=True)
        t.start()

        # 等待就绪
        ready = False
        for i in range(120):
            try:
                requests.get(f'http://127.0.0.1:{SERVER_PORT}/api/me', timeout=2)
                ready = True
                break
            except:
                time.sleep(0.5)
        if not ready:
            try:
                import tkinter.messagebox as mb
                mb.showerror('启动失败', '后端服务未能启动，请检查是否端口被占用或防火墙拦截。')
            except:
                pass
            sys.exit(1)

        # 启动桌面端
        from desktop_app import launch_desktop
        launch_desktop(start_server_flag=False)
    else:
        # ===== 客户端模式：直接连接远程后端 =====
        if not api_base:
            api_base = 'http://127.0.0.1:8000'
            print(f'>>> 客户端模式，连接本地后端: {api_base}')
        else:
            print(f'>>> 客户端模式，连接远程后端: {api_base}')
        from desktop_app import launch_desktop
        launch_desktop(start_server_flag=False)
