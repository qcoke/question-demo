"""把每一次改写事件落盘成 JSON，便于复盘和重放。"""

from __future__ import annotations

import base64
import itertools
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)


class Recorder:
    """把每次 payload 改写事件序列化为 JSON 文件。

    文件命名：``YYYYMMDD-HHMMSS-mmm-<seq>.json``。
    内容包含：原始/改写后 payload 的 base64 与“可读文本”、五元组、进程信息等。
    """

    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._counter = itertools.count(1)

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    def record(
        self,
        *,
        src_addr: str,
        src_port: int,
        dst_addr: str,
        dst_port: int,
        original: bytes,
        rewritten: bytes,
        pid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> Path:
        ts = time.time()
        seq = next(self._counter)
        dt = datetime.fromtimestamp(ts).strftime("%Y%m%d-%H%M%S-%f")[:-3]
        filename = f"{dt}-{seq:04d}.json"
        path = self._log_dir / filename

        record = {
            "timestamp": ts,
            "datetime": datetime.fromtimestamp(ts).isoformat(timespec="milliseconds"),
            "src": {"addr": src_addr, "port": src_port},
            "dst": {"addr": dst_addr, "port": dst_port},
            "pid": pid,
            "process": process_name,
            "original_b64": base64.b64encode(original).decode("ascii"),
            "rewritten_b64": base64.b64encode(rewritten).decode("ascii"),
            "original_text": _safe_text(original),
            "rewritten_text": _safe_text(rewritten),
        }

        try:
            path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            LOG.warning("Recorder failed to write %s: %s", path, exc)
            return path

        LOG.debug("Recorded interception to %s", path)
        return path


def _safe_text(payload: bytes) -> str:
    """尝试用 latin-1 还原文本（HTTP 头是 ASCII，body 是 form-urlencoded）。"""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("latin-1", errors="replace")

