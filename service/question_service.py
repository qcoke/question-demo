# -*- coding: utf-8 -*-
"""
question_service.py
~~~~~~~~~~~~~~~~~~~
将 question-demo（Django）封装为 Windows 服务。

使用方式（需管理员权限）：
    python question_service.py install   # 安装服务
    python question_service.py remove    # 卸载服务
    python question_service.py start     # 启动服务
    python question_service.py stop      # 停止服务
    python question_service.py restart   # 重启服务
    python question_service.py debug     # 前台调试模式

依赖：
    pip install pywin32
    python -m pywin32_postinstall -install
"""

import os
import sys
import subprocess
import threading
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

import servicemanager
import win32event
import win32service
import win32serviceutil


# ──────────────────────────────────────────────
# 路径与入口配置
# ──────────────────────────────────────────────

# 仓库根目录（本文件位于 service/ 子目录，故向上一层）
BASE_DIR = Path(__file__).resolve().parent.parent

# 日志目录（仓库根目录下的 logs/）
LOG_DIR = BASE_DIR / "logs"

# 日志文件路径
LOG_FILE = LOG_DIR / "service.log"

# Django 入口脚本
MANAGE_PY = str(BASE_DIR / "manage.py")

# 默认监听地址与端口（可通过环境变量或 service.env 覆盖）
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8000"

# service.env 文件路径（与本脚本同目录）
ENV_FILE = Path(__file__).resolve().parent / "service.env"


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def load_env_file(env_file: Path) -> None:
    """从 service.env 文件加载环境变量（key=value 格式，# 开头为注释）。"""
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def get_logger() -> logging.Logger:
    """构建并返回服务专用的滚动日志记录器。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("QuestionDemoService")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    # 按大小滚动，单个文件最大 10 MB，保留 5 份
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def build_entry_cmd() -> list:
    """根据环境变量（或 service.env）构建 Django runserver 启动命令。"""
    host = os.environ.get("SERVICE_HOST", DEFAULT_HOST)
    port = os.environ.get("SERVICE_PORT", DEFAULT_PORT)
    python = sys.executable
    # ENTRY_CMD 可在此处整体替换，例如改为 gunicorn / waitress
    entry_cmd = [python, MANAGE_PY, "runserver", f"{host}:{port}", "--noreload"]
    return entry_cmd


# Django settings 模块（可通过环境变量或 service.env 中的 DJANGO_SETTINGS_MODULE 覆盖）
DEFAULT_DJANGO_SETTINGS = "config.settings"


# ──────────────────────────────────────────────
# Windows 服务类
# ──────────────────────────────────────────────

class QuestionDemoService(win32serviceutil.ServiceFramework):
    """Question Demo Windows 服务（基于 pywin32 / Windows SCM）。"""

    _svc_name_ = "QuestionDemoService"
    _svc_display_name_ = "Question Demo Service"
    _svc_description_ = "答题站后台服务（用于测试 AI）"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # 用于通知 SCM 服务已停止的事件
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._process = None
        self._log_fd = None  # 子进程的日志文件句柄
        self._log = get_logger()

    # ── 服务启动 ──────────────────────────────

    def SvcDoRun(self):
        """服务主循环：启动 Web 子进程并等待停止信号。"""
        # 加载 service.env（若存在）
        load_env_file(ENV_FILE)

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self._log.info("服务启动，工作目录：%s", BASE_DIR)

        # 确保 DJANGO_SETTINGS_MODULE 已设置（可通过环境变量或 service.env 覆盖）
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", DEFAULT_DJANGO_SETTINGS)

        cmd = build_entry_cmd()
        self._log.info("入口命令：%s", " ".join(cmd))

        try:
            self._start_subprocess(cmd)
            # 阻塞，直到收到停止信号
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
        except Exception as exc:
            self._log.exception("服务运行异常：%s", exc)
            servicemanager.LogErrorMsg(f"{self._svc_name_} 运行异常：{exc}")
        finally:
            self._terminate_subprocess()
            self._log.info("服务已停止")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, ""),
            )

    def _start_subprocess(self, cmd: list) -> None:
        """启动 Web 应用子进程，将 stdout/stderr 重定向到日志文件。"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_fd = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        self._log_fd.write(
            f"\n{'='*60}\n"
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 服务启动\n"
            f"命令：{' '.join(cmd)}\n"
            f"{'='*60}\n"
        )
        self._log_fd.flush()

        self._process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=self._log_fd,
            stderr=self._log_fd,
            # 在 Windows 上不创建新控制台窗口
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._log.info("子进程已启动，PID=%d", self._process.pid)

        # 在后台线程中监控子进程，若意外退出则写日志
        monitor = threading.Thread(target=self._monitor_subprocess, daemon=True)
        monitor.start()

    def _monitor_subprocess(self) -> None:
        """监控子进程：若意外退出则记录日志（服务停止时正常退出不报错）。"""
        if self._process is None:
            return
        ret = self._process.wait()
        # 如果停止事件已触发，说明是正常停止，不记录为异常
        if win32event.WaitForSingleObject(self._stop_event, 0) == win32event.WAIT_OBJECT_0:
            return
        self._log.warning("子进程意外退出，返回码=%d，尝试重启", ret)
        servicemanager.LogErrorMsg(
            f"{self._svc_name_} 子进程意外退出（returncode={ret}）"
        )

    # ── 服务停止 ──────────────────────────────

    def SvcStop(self):
        """接收 SCM 停止请求：通知主循环退出并终止子进程。"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._log.info("收到停止请求")
        win32event.SetEvent(self._stop_event)

    def _terminate_subprocess(self) -> None:
        """优雅终止子进程：先 terminate，超时后 kill；最后关闭日志文件句柄。"""
        if self._process is None:
            return
        if self._process.poll() is not None:
            self._close_log_fd()
            return  # 已退出
        self._log.info("正在终止子进程 PID=%d …", self._process.pid)
        try:
            self._process.terminate()
            self._process.wait(timeout=10)
            self._log.info("子进程已正常终止")
        except subprocess.TimeoutExpired:
            self._log.warning("子进程未在 10s 内退出，强制 kill")
            self._process.kill()
            self._process.wait()
            self._log.info("子进程已强制终止")
        except Exception as exc:
            self._log.exception("终止子进程时发生异常：%s", exc)
        finally:
            self._close_log_fd()

    def _close_log_fd(self) -> None:
        """关闭子进程日志文件句柄（若已打开）。"""
        if self._log_fd is not None and not self._log_fd.closed:
            try:
                self._log_fd.close()
            except Exception:
                pass
            self._log_fd = None


# ──────────────────────────────────────────────
# 脚本入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # 被 SCM 直接调用（无命令行参数）
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(QuestionDemoService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # 命令行管理：install / remove / start / stop / restart / debug
        win32serviceutil.HandleCommandLine(QuestionDemoService)
