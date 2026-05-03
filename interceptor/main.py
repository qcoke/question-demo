"""
答题站请求拦截器 (WinDivert / PyDivert)

功能：
- 监听本机出站 TCP 流量，匹配指定 Django 服务端口（默认 8000）
- 在表单 POST 体中把 `selected_option=A|B|C|D` 改写为 `selected_option=E`
- 替换是同长度（1 字符 → 1 字符），不需要重算 TCP seq 或 Content-Length
- 校验和由 WinDivert 在 send 时自动重算

要求：
- Windows + 管理员权限（驱动加载需要）
- 已安装 pydivert (`pip install pydivert`)

运行：
    python -m interceptor.main --port 8000 --verbose

停止：
    Ctrl+C

注意：
- 仅作为本地观察工具，请勿在生产环境使用
- 避免与浏览器自动重试/HTTP/2 同时使用，简单场景下用 HTTP/1.1
"""

from __future__ import annotations

import argparse
import logging
import re
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from .process_filter import ProcessFilter
from .recorder import Recorder

LOG = logging.getLogger("interceptor")

# 表单参数 selected_option=X，X 紧跟 & 或字符串结尾。
# 用 \b 做单词边界匹配，避免误改类似字段。
PATTERN = re.compile(rb"(selected_option=)([ABCD])\b")
REPLACEMENT_CHAR = b"E"


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def rewrite_payload(payload: bytes) -> Optional[bytes]:
    """如果检测到 selected_option=A/B/C/D，返回改写后的 payload，否则返回 None。"""
    if b"selected_option=" not in payload:
        return None

    matches = PATTERN.findall(payload)
    if not matches:
        return None

    new_payload = PATTERN.sub(rb"\1" + REPLACEMENT_CHAR, payload)
    return new_payload


def build_filter(port: int) -> str:
    # 仅捕获出站、目的端口为 Django 服务端口的 TCP 包。
    # WinDivert 2 默认会包含 loopback 流量，无需额外配置。
    return f"outbound and tcp.DstPort == {port}"


def run(
    filter_expr: str,
    process_filter: Optional[ProcessFilter] = None,
    recorder: Optional[Recorder] = None,
) -> None:
    import pydivert  # 延迟导入，避免无 pydivert 时 import 阶段报错

    LOG.info("Loading WinDivert with filter: %s", filter_expr)
    if process_filter and process_filter.is_active:
        LOG.info("Process filter is ACTIVE.")
    if recorder is not None:
        LOG.info("Recorder enabled, log dir: %s", recorder.log_dir)

    stop_event = threading.Event()

    def _stop(signum, _frame):
        LOG.info("Signal %s received, shutting down...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    try:
        signal.signal(signal.SIGTERM, _stop)
    except (AttributeError, ValueError):
        # Windows 上 SIGTERM 注册可能受限，忽略即可
        pass

    with pydivert.WinDivert(filter_expr) as w:
        LOG.info("Interceptor started. Press Ctrl+C to stop.")
        for packet in w:
            if stop_event.is_set():
                # 把当前已收到的包发出去再退出
                try:
                    w.send(packet)
                except Exception:
                    pass
                break

            try:
                _process_packet(packet, process_filter=process_filter, recorder=recorder)
                w.send(packet)
            except Exception as exc:  # 任何错误都尽量放行，避免把网卡“锁住”
                LOG.exception("Error processing packet: %s", exc)
                try:
                    w.send(packet)
                except Exception:
                    LOG.exception("Failed to forward packet after error")


def _process_packet(
    packet,
    process_filter: Optional[ProcessFilter] = None,
    recorder: Optional[Recorder] = None,
) -> None:
    if packet.tcp is None:
        return
    raw = packet.payload
    if not raw:
        return

    raw_bytes = bytes(raw)
    new_payload = rewrite_payload(raw_bytes)
    if new_payload is None:
        return

    pid: Optional[int] = None
    process_name: Optional[str] = None
    if process_filter is not None and process_filter.is_active:
        info = process_filter.lookup(packet.src_addr, packet.src_port)
        if info is None:
            LOG.debug(
                "Skip rewrite (process unknown) %s:%d -> %s:%d",
                packet.src_addr, packet.src_port,
                packet.dst_addr, packet.dst_port,
            )
            return
        pid, process_name = info
        if not process_filter.matches(packet.src_addr, packet.src_port):
            LOG.debug(
                "Skip rewrite (process not allowed) pid=%s name=%s",
                pid, process_name,
            )
            return

    LOG.info(
        "Rewriting selected_option -> %s | %s:%d -> %s:%d (len=%d)%s",
        REPLACEMENT_CHAR.decode(),
        packet.src_addr, packet.src_port,
        packet.dst_addr, packet.dst_port,
        len(new_payload),
        f" pid={pid} name={process_name}" if pid else "",
    )
    LOG.debug("Original payload: %r", raw_bytes)
    LOG.debug("Rewritten payload: %r", new_payload)

    if recorder is not None:
        try:
            recorder.record(
                src_addr=packet.src_addr,
                src_port=packet.src_port,
                dst_addr=packet.dst_addr,
                dst_port=packet.dst_port,
                original=raw_bytes,
                rewritten=new_payload,
                pid=pid,
                process_name=process_name,
            )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Recorder error: %s", exc)

    packet.payload = new_payload  # WinDivert 会在 send 时重算 IP/TCP 校验和


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WinDivert 拦截器：把答题接口的 selected_option 改写为 E"
    )
    parser.add_argument("--port", type=int, default=8000, help="Django 服务监听端口（默认 8000）")
    parser.add_argument(
        "--filter",
        default=None,
        help="自定义 WinDivert 过滤表达式，覆盖 --port",
    )
    parser.add_argument(
        "--process-name",
        action="append",
        default=[],
        metavar="NAME",
        help="只拦截指定进程名（不区分大小写），可重复指定，例如 --process-name chrome.exe",
    )
    parser.add_argument(
        "--pid",
        type=int,
        action="append",
        default=[],
        metavar="PID",
        help="只拦截指定 PID 的进程，可重复指定",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="把每次改写事件录制为 JSON 文件",
    )
    parser.add_argument(
        "--log-dir",
        default=str(Path(__file__).resolve().parent / "logs"),
        help="录制 JSON 的存放目录（默认 interceptor/logs）",
    )
    parser.add_argument("--verbose", action="store_true", help="输出更详细的调试日志")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    filter_expr = args.filter or build_filter(args.port)

    process_filter = ProcessFilter(
        allowed_names=args.process_name,
        allowed_pids=args.pid,
    )
    if process_filter.is_active:
        LOG.info(
            "Process filter armed: names=%s pids=%s",
            args.process_name, args.pid,
        )

    recorder: Optional[Recorder] = None
    if args.record:
        recorder = Recorder(args.log_dir)

    try:
        run(filter_expr, process_filter=process_filter, recorder=recorder)
    except ImportError as exc:
        LOG.error("pydivert 未安装：%s。请先执行 `pip install pydivert`。", exc)
        return 2
    except PermissionError:
        LOG.error("权限不足：请在“以管理员身份运行”的 PowerShell 中执行。")
        return 2
    except OSError as exc:
        LOG.error("WinDivert 初始化失败：%s", exc)
        return 2
    except KeyboardInterrupt:
        LOG.info("Interrupted by user.")
    except Exception as exc:  # noqa: BLE001
        LOG.exception("Fatal error: %s", exc)
        return 1

    LOG.info("Interceptor stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

