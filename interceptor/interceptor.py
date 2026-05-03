"""
WinDivert demo: 拦截发往 Django quiz 服务的 HTTP POST,
把表单中的 selected_option 统一改成 A。

手动验证方式:
    全程都选 B 提交,在结果页应该看到 10 题答案全部被记录为 A;
    停掉拦截器后再做一遍,就会恢复成 B,即可验证拦截生效。

约束:
- 仅用于本人 question-demo 项目的学习/调试
- 仅处理明文 HTTP (端口默认 8000),不解 HTTPS
- 仅处理 IPv4 outbound 流量
- 修改前后字节长度一致,无需调整 Content-Length / TCP seq

运行需要管理员权限 (WinDivert 驱动要求)。
"""

from __future__ import annotations

import argparse
import re
import sys

try:
    import pydivert
except ImportError:
    print("[!] 缺少依赖 pydivert,请先执行: pip install pydivert", file=sys.stderr)
    sys.exit(1)


# 匹配 form-urlencoded 中的 selected_option=A/B/C/D
# 只在选项字符后是 & / \r / \n / 结尾时才替换,降低误伤概率
PATTERN = re.compile(rb"(selected_option=)([ABCD])(?=&|\r|\n|$)")

# 统一替换为 A
FORCED_OPTION = b"A"


def build_filter(host: str, port: int) -> str:
    return f"outbound and tcp and ip.DstAddr == {host} and tcp.DstPort == {port}"


def process_packet(packet: "pydivert.Packet") -> bool:
    """如果改写了 payload 返回 True,否则 False。"""
    payload = packet.payload
    if not payload or b"selected_option=" not in payload:
        return False

    match = PATTERN.search(payload)
    if not match:
        return False

    original = match.group(2)
    if original == FORCED_OPTION:
        # 用户本来就选 A,无需改写
        return False

    new_payload, n = PATTERN.subn(rb"\1" + FORCED_OPTION, payload)
    if n == 0:
        return False

    packet.payload = new_payload  # pydivert 会自动重算 IP/TCP checksum
    print(
        f"[+] {packet.src_addr}:{packet.src_port} -> "
        f"{packet.dst_addr}:{packet.dst_port}  "
        f"selected_option {original.decode()} -> {FORCED_OPTION.decode()}  "
        f"({n} hit)"
    )
    return True


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="拦截 Django quiz 提交,把 selected_option 统一改成 A (WinDivert demo)",
    )
    p.add_argument(
        "--host",
        required=True,
        help="Django 服务器的 IPv4 地址 (例如 Mac 的局域网 IP 192.168.1.10)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Django 服务器端口,默认 8000",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    flt = build_filter(args.host, args.port)

    print(f"[*] WinDivert filter: {flt}")
    print(f"[*] 强制把 selected_option 改成: {FORCED_OPTION.decode()}")
    print("[*] 启动拦截,Ctrl+C 退出。需要管理员权限。")

    try:
        with pydivert.WinDivert(flt) as w:
            for packet in w:
                try:
                    process_packet(packet)
                except Exception as e:  # noqa: BLE001
                    print(f"[!] 处理包出错(已放行): {e}", file=sys.stderr)
                finally:
                    # 无论是否改写,都必须重新发送,否则该包会被丢弃,导致网络中断
                    w.send(packet)
    except KeyboardInterrupt:
        print("\n[*] 已停止。")
        return 0
    except OSError as e:
        print(f"[!] 启动 WinDivert 失败: {e}", file=sys.stderr)
        print(
            "[!] 请确认: 1) 以管理员身份运行  2) 系统已加载 WinDivert64.sys 驱动",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
