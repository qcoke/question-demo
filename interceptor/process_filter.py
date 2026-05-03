"""按进程名 / PID 过滤本机 TCP 流量。

通过 psutil 周期性快照 (laddr.ip, laddr.port) -> (pid, process_name)，
拦截器只对命中进程的包执行改写，其他包原样放行。
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional, Tuple

LOG = logging.getLogger(__name__)


class ProcessFilter:
    """根据进程名 / PID 决定是否改写当前数据包。

    Args:
        allowed_names: 允许���进程名集合（不区分大小写），如 {"chrome.exe"}。
        allowed_pids: 允许的 PID 集合。
        ttl: 进程映射缓存的 TTL（秒），到期后下次查询会自动刷新。
        snapshot_provider: 可注入的快照源，便于测试。返回可迭代项：
            (laddr_ip, laddr_port, pid, process_name)
    """

    def __init__(
        self,
        allowed_names: Optional[Iterable[str]] = None,
        allowed_pids: Optional[Iterable[int]] = None,
        ttl: float = 1.0,
        snapshot_provider=None,
    ) -> None:
        self._allowed_names = {n.lower() for n in (allowed_names or []) if n}
        self._allowed_pids = {int(p) for p in (allowed_pids or [])}
        self._ttl = ttl
        self._snapshot_provider = snapshot_provider or _default_snapshot
        self._cache: dict[Tuple[str, int], Tuple[int, str]] = {}
        self._cache_ts: float = 0.0

    @property
    def is_active(self) -> bool:
        return bool(self._allowed_names or self._allowed_pids)

    def matches(self, ip: str, port: int) -> bool:
        if not self.is_active:
            return True

        info = self._lookup(ip, port)
        if info is None:
            return False

        pid, name = info
        if pid in self._allowed_pids:
            return True
        if name and name.lower() in self._allowed_names:
            return True
        return False

    def lookup(self, ip: str, port: int) -> Optional[Tuple[int, str]]:
        return self._lookup(ip, port)

    def _lookup(self, ip: str, port: int) -> Optional[Tuple[int, str]]:
        now = time.monotonic()
        if now - self._cache_ts >= self._ttl:
            self._refresh()

        key = (_normalize_ip(ip), port)
        info = self._cache.get(key)
        if info is not None:
            return info

        # 端口冲突（同端口绑定不同 ip）时再尝试 0.0.0.0/:: 兜底
        for fallback in ("0.0.0.0", "::"):
            info = self._cache.get((fallback, port))
            if info is not None:
                return info
        return None

    def _refresh(self) -> None:
        try:
            entries = list(self._snapshot_provider())
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Process snapshot failed: %s", exc)
            return

        new_cache: dict[Tuple[str, int], Tuple[int, str]] = {}
        for ip, port, pid, name in entries:
            if pid is None or port is None:
                continue
            new_cache[(_normalize_ip(ip), int(port))] = (int(pid), name or "")

        self._cache = new_cache
        self._cache_ts = time.monotonic()


def _normalize_ip(ip: Optional[str]) -> str:
    if not ip:
        return ""
    if ip.startswith("::ffff:"):
        return ip[len("::ffff:") :]
    return ip


def _default_snapshot():
    """从 psutil 拉取当前 TCP socket -> (pid, name) 映射。"""
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - psutil 是可选依赖
        raise RuntimeError(
            "进程过滤需要 psutil：pip install psutil"
        ) from exc

    pid_to_name: dict[int, str] = {}

    for conn in psutil.net_connections(kind="tcp"):
        if conn.pid is None or conn.laddr is None:
            continue
        pid = conn.pid
        if pid not in pid_to_name:
            try:
                pid_to_name[pid] = psutil.Process(pid).name()
            except Exception:  # noqa: BLE001
                pid_to_name[pid] = ""
        yield conn.laddr.ip, conn.laddr.port, pid, pid_to_name[pid]

