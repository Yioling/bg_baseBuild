"""HTTP 层：后台线程调用后端 API（契约见 API_CONTRACT.md）。

- 支持 GET / POST / PUT / DELETE
- PDF 响应自动落盘到桌面并打开
- 连接失败自动重试（后端可能仍在启动中）
"""
import os
from pathlib import Path
from datetime import datetime

import requests
from PyQt5.QtCore import QThread, pyqtSignal

SERVER_PORT = 8000
# 支持环境变量 API_BASE 指定远程服务端地址（默认本机）
# 例如: API_BASE=http://192.168.1.100:8000
BASE_URL = os.getenv("API_BASE", f"http://127.0.0.1:{SERVER_PORT}")


class ApiThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, method, url, body=None, token=None, files=None, raw=False):
        super().__init__()
        self.method = method.upper()
        self.url = url
        self.body = body
        self.token = token
        self.files = files  # multipart 文件字段: {field: (filename, bytes, mime)} 或文件对象列表
        self.raw = raw      # True 时返回原始字节（图片预览/文件下载）

    def run(self):
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            r = None
            for attempt in range(5):
                try:
                    if self.method == "GET":
                        r = requests.get(self.url, headers=headers, timeout=30)
                    elif self.method == "POST":
                        if self.files:
                            # multipart 上传：不设 Content-Type（requests 自动带 boundary）
                            r = requests.post(self.url, files=self.files,
                                              headers=headers, timeout=60)
                        else:
                            headers["Content-Type"] = "application/json"
                            r = requests.post(self.url, json=self.body, headers=headers, timeout=30)
                    elif self.method == "PUT":
                        headers["Content-Type"] = "application/json"
                        r = requests.put(self.url, json=self.body, headers=headers, timeout=30)
                    elif self.method == "DELETE":
                        r = requests.delete(self.url, headers=headers, timeout=30)
                    else:
                        self.finished.emit({"success": False, "message": f"未知方法 {self.method}"})
                        return
                    break
                except requests.exceptions.ConnectionError:
                    if attempt < 4:
                        import time
                        time.sleep(1)
                        continue
                    raise
            if r is None:
                self.finished.emit({"success": False, "message": "无法连接到服务器，请稍后重试"})
                return
            ct = r.headers.get("content-type", "")
            if self.raw:
                # 原始字节流：图片预览 / 文件下载
                self.finished.emit({
                    "success": True,
                    "data": r.content,
                    "mime": ct,
                    "file_name": self._filename_from(r) or "attachment",
                })
            elif "application/json" in ct:
                self.finished.emit(r.json())
            elif "application/pdf" in ct:
                desktop = Path.home() / "Desktop"
                fname = f'薪火讲义_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                fpath = desktop / fname
                fpath.write_bytes(r.content)
                try:
                    os.startfile(str(fpath))
                except OSError:
                    pass
                self.finished.emit({"success": True, "message": f"PDF已保存到桌面: {fname}", "path": str(fpath)})
            else:
                self.finished.emit({"success": False, "message": r.text[:200]})
        except Exception as e:
            self.finished.emit({"success": False, "message": str(e)})

    def _filename_from(self, r) -> str:
        """从 Content-Disposition 头解析文件名，兜底返回空串。"""
        try:
            cd = r.headers.get("content-disposition", "")
            if "filename=" in cd:
                return cd.split("filename=")[1].strip('"').strip("'")
        except Exception:
            pass
        return ""


class ApiMixin:
    """给窗口类提供 `_api_call`，持有线程引用防止提前回收。"""

    token = None

    def _api_call(self, method, url, body=None, callback=None, files=None, raw=False):
        if not hasattr(self, "_api_threads"):
            self._api_threads = []
        thread = ApiThread(method, url, body, self.token, files=files, raw=raw)
        if callback:
            thread.finished.connect(callback)
        thread.finished.connect(lambda _res, t=thread: self._reap_thread(t))
        self._api_threads.append(thread)
        thread.start()
        return thread

    def _reap_thread(self, thread):
        try:
            if thread in self._api_threads and thread.isFinished():
                self._api_threads.remove(thread)
        except (ValueError, RuntimeError):
            pass
