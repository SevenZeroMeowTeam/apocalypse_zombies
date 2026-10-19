#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天陨终端 / 轨道打击 专用服务器冒烟探针（RCON）。

用途：在 `gradlew runServer` 起的开发专服上，确认 3.10.0 引入的东西真的能落地：
  * 终端方块可以放置，且方块实体 NBT 字段齐全；
  * 终端掉落表能正常掉出物品；
  * `/apocalypse skyfall strikes` 命令已注册，且能报出并发上限。

前置：`run/server.properties` 里 `enable-rcon=true` 且 `rcon.password` 非空；
游戏进程 / 服务端已完全启动（日志出现 `Done (`）。脚本本身不启停服务器。

用法：
    python tools/skyfall_probe.py
    python tools/skyfall_probe.py --host 127.0.0.1 --port 25575 --password skyfall

退出码：0 全过；1 有失败；2 连不上 RCON。
"""
import argparse
import socket
import struct
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 25575
DEFAULT_PASSWORD = "skyfall"

# 探测前先清位（原版 /setblock 对相同状态重复设置会返回失败）。
PREP = [
    "setblock 0 -60 0 minecraft:air",
]

# (名称, 命令, 期望在回复里出现的片段)
CHECKS = [
    ("place-terminal",
     "setblock 0 -60 0 apocalypse_zombies:skyfall_terminal",
     ["Changed the block"]),
    ("block-entity-nbt",
     "data get block 0 -60 0",
     ["apocalypse_zombies:skyfall_terminal", "Selected", "Unlocked"]),
    ("loot-table",
     "loot spawn 2 -60 2 mine 0 -60 0 minecraft:iron_pickaxe",
     ["Skyfall Terminal"]),
    ("command-strikes",
     "apocalypse skyfall strikes",
     ["上限"]),
]


class Rcon:
    def __init__(self, host: str, port: int, password: str, timeout: float = 10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self._next_id = 0
        if not self._auth(password):
            raise ConnectionError("RCON authentication failed")

    def _pack(self, req_type: int, body: str) -> bytes:
        self._next_id += 1
        payload = struct.pack("<ii", self._next_id, req_type) + body.encode("utf-8") + b"\x00\x00"
        return struct.pack("<i", len(payload)) + payload

    def _read(self) -> str:
        raw_len = self.sock.recv(4)
        if len(raw_len) < 4:
            raise ConnectionError("RCON connection closed")
        (length,) = struct.unpack("<i", raw_len)
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        body = data[8:-2]
        return body.decode("utf-8", "replace")

    def _auth(self, password: str) -> bool:
        self.sock.sendall(self._pack(3, password))
        reply = self._read()
        return "Authentication failed" not in reply

    def command(self, command: str) -> str:
        self.sock.sendall(self._pack(2, command))
        return self._read()

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Skyfall RCON smoke probe")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    try:
        rcon = Rcon(args.host, args.port, args.password)
    except (OSError, ConnectionError) as exc:
        print(f"RCON CONNECT FAILED: {exc}")
        return 2

    failures = 0
    try:
        # 原版 /setblock 对「同一方块状态重复设置」返回失败，所以先把探测位清成空气，
        # 保证 place-terminal 这条判据每次都能真正执行一次放置。
        for prep in PREP:
            try:
                rcon.command(prep)
            except (OSError, ConnectionError) as exc:
                print(f"FAIL prep {prep!r}: {exc}")
                failures += 1
        for name, command, expected in CHECKS:
            try:
                reply = rcon.command(command)
            except (OSError, ConnectionError) as exc:
                print(f"FAIL {name:20s} {command!r}: {exc}")
                failures += 1
                continue
            flat = " ".join(reply.split())
            missing = [needle for needle in expected if needle not in flat]
            if missing:
                print(f"FAIL {name:20s} missing={missing}")
                print(f"     reply: {flat[:300]}")
                failures += 1
            else:
                print(f"PASS {name:20s} {flat[:160]}")
    finally:
        rcon.close()

    print("RESULT:", "PASS" if failures == 0 else f"FAIL ({failures})")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
