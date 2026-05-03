"""根据录制的 JSON 文件，把 HTTP 请求重放到指定服务。

用法::

    python -m interceptor.replay path\\to\\record.json --url http://127.0.0.1:8000
    python -m interceptor.replay path\\to\\record.json --url http://127.0.0.1:8000 --rewritten

默认重放“原始 payload”（即被改写之前的真实请求），加 ``--rewritten`` 则重放“改写后 payload”
（即拦截器实际发给后端的内容），便于复现两种场景。
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Tuple

LOG = logging.getLogger("interceptor.replay")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def parse_http_request(raw: bytes) -> Tuple[str, str, dict, bytes]:
    """从 raw HTTP/1.x 请求字节中拆出 method、path、headers、body。"""
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        raise ValueError("payload 中未找到 HTTP 头/体分隔符")

    lines = head.split(b"\r\n")
    if not lines:
        raise ValueError("payload 缺少请求行")

    request_line = lines[0].decode("latin-1")
    parts = request_line.split(" ", 2)
    if len(parts) < 2:
        raise ValueError(f"无法解析请求行: {request_line!r}")
    method = parts[0]
    path = parts[1]

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line or b":" not in line:
            continue
        key, _, value = line.partition(b":")
        headers[key.decode("latin-1").strip()] = value.decode("latin-1").strip()

    return method, path, headers, body


def replay_record(record_path: Path, base_url: str, use_rewritten: bool = False) -> int:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("重放需要 requests：pip install requests") from exc

    data = json.loads(record_path.read_text(encoding="utf-8"))

    field = "rewritten_b64" if use_rewritten else "original_b64"
    if field not in data:
        raise ValueError(f"记录文件缺少字段: {field}")

    raw = base64.b64decode(data[field])
    method, path, headers, body = parse_http_request(raw)

    # 这些字段会被 requests 自行管理，避免重复或错误
    for hop in ("Host", "Content-Length", "Connection", "Transfer-Encoding"):
        headers.pop(hop, None)

    url = base_url.rstrip("/") + path
    LOG.info("Replaying %s %s (body=%d bytes)", method, url, len(body))
    LOG.debug("Headers: %s", headers)
    LOG.debug("Body: %r", body)

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        data=body,
        allow_redirects=False,
        timeout=10,
    )
    LOG.info("Response: %d %s", response.status_code, response.reason)
    if response.text:
        preview = response.text[:500]
        LOG.info("Response body (first 500 bytes): %s", preview)
    return response.status_code


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把拦截器录制的请求重放到目标服务"
    )
    parser.add_argument("record", type=Path, help="录制 JSON 文件路径")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="目标服务 base URL，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--rewritten",
        action="store_true",
        help="重放改写后的 payload；默认为重放原始 payload",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    if not args.record.exists():
        LOG.error("记录文件不存在: %s", args.record)
        return 2

    try:
        replay_record(args.record, args.url, use_rewritten=args.rewritten)
    except Exception as exc:  # noqa: BLE001
        LOG.exception("Replay failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

