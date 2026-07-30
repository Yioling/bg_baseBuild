"""薪火 · 桌面 UI 包（P5）

模块划分：
- theme        huashu-design 设计令牌 / 全局 QSS / 通用组件工厂
- api          HTTP 线程与调用混入（GET/POST/PUT/DELETE + PDF 落盘）
- login        登录 / 注册对话框
- main_window  主窗口骨架（侧边栏 + 页面路由）
- master       师傅视图页面
- apprentice   徒弟视图页面
- admin        管理员视图页面
- social       交流圈
- notify       通知中心
- progress     进度三视图

铁律：任何样式只允许作用于 QWidget 子类，严禁对 QLayout 调 setStyleSheet。
"""
from ui.login import LoginDialog
from ui.main_window import MainWindow

__all__ = ["LoginDialog", "MainWindow"]
