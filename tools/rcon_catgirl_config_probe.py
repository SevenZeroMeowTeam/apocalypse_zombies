#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.1.79「图形配置界面 + 一键挖掘上限 64」实机探针。

分两段跑，因为**配置文件只在服务端启动时读一次** —— 想验证「手改越界值会被夹回域内」，
必须先改文件再重启，光靠 RCON 是验不出来的。

    --stage default   服务端正跑着（./gradlew runServer）时跑 —— 跑之前**先删掉
                      run/config/apocalypse_zombies-common.toml 再启动服务端**（模拟新装用户，
                      Forge 会把默认值写出来）：默认值是不是 64 / 范围的口子在不在 /
                      枚举器真机数出几项 / 有没有异常

    --stage clamped   把 run/config/apocalypse_zombies-common.toml 里 mine_max_blocks 手改成 999、
                      **重启服务端**之后再跑：文件里写着 999，认**启动日志里运行期真值仍是 64**
                      （Forge 在读取时夹回域内，1.1.78 → 1.1.79 的老用户带着 256 的配置升上来就是这条路）

用法：
    py tools/_deploy_179.py --build && rm -f run/config/apocalypse_zombies-common.toml
    ./gradlew runServer                # 或另开一个窗口
    python tools/rcon_catgirl_config_probe.py --stage default
    # 手改 mine_max_blocks = 999，重启服务端
    python tools/rcon_catgirl_config_probe.py --stage clamped

观察点为什么选这些（都不是「读代码能得出的」结论）：

  1. `Config.values()` 是**反射**实现的枚举器 —— 编译期数源码字段证明不了运行期真数出 151 个。
     主类构造时会往日志打一行 `Config registry: N entries`，探针就钉这个数。
  2. 图形界面那两个类（`ModConfigScreens` / `ApocalypseConfigScreen`）是**纯客户端**的，
     注册走 `DistExecutor.unsafeRunWhenOn(Dist.CLIENT, …)`。专用服务器能不能正常起来，
     就是「分支没被走到 / 客户端类没被加载」最直接的证据（错的话是 NoClassDefFoundError 崩服）。
  3. Forge 的 defineInRange 在**读取时**夹值 —— 所以「上限是多少」只能看运行期：主类启动那行
     `mine_max_blocks=…` 是探针认的唯一口径，文件里写 999 也不算数。

报告追加写 run/catgirl_config_probe_report.txt（两段共用一份，中间有分隔）。
"""
import argparse
import glob
import os
import re
import socket
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPERTIES = os.path.join(ROOT, "run", "server.properties")
LOG = os.path.join(ROOT, "run", "logs", "latest.log")
CRASH = os.path.join(ROOT, "run", "crash-reports")
CONFIG = os.path.join(ROOT, "run", "config", "apocalypse_zombies-common.toml")
REPORT = os.path.join(ROOT, "run", "catgirl_config_probe_report.txt")

EXPECTED_ENTRIES = 151          # 源码里 151 个 ConfigValue 字段；运行期必须一样多
# 只认「模组加载阶段」的标记：`Starting minecraft server` 在这之后才打，拿它当界会把我们的启动日志切掉
BOOT_MARKERS = ("Loading Minecraft", "Forge mod loading, version")


def read_properties():
    props = {}
    with open(PROPERTIES, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                props[key.strip()] = value.strip()
    return props


class Rcon:
    def __init__(self, host, port, password, timeout=20.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.next_id = 1
        self._send(3, password)
        pid, _, _ = self._recv()
        if pid == -1:
            raise SystemExit("RCON 鉴权失败（口令不对）")

    def _send(self, ptype, body):
        payload = struct.pack("<ii", self.next_id, ptype) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        self.next_id += 1

    def _recv(self):
        raw = b""
        while len(raw) < 4:
            raw += self.sock.recv(4 - len(raw))
        (length,) = struct.unpack("<i", raw)
        body = b""
        while len(body) < length:
            body += self.sock.recv(length - len(body))
        pid, ptype = struct.unpack("<ii", body[:8])
        return pid, ptype, body[8:-2].decode("utf-8", "replace")

    def cmd(self, command):
        self._send(2, command)
        _, _, text = self._recv()
        return text.strip()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def config_value(key):
    """从 TOML 里抠出某个键的值（只用最朴素的写法，不引第三方 toml）。"""
    try:
        with open(CONFIG, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(key) and "=" in line:
                    return line.split("=", 1)[1].strip()
    except OSError:
        return None
    return None


def boot_log():
    """只取**本次启动**之后的日志行（越界值那次启动的校正告警才作数）。"""
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    last = 0
    for i, line in enumerate(lines):
        if any(marker in line for marker in BOOT_MARKERS):
            last = i
    return lines[last:]


def main():
    ap = argparse.ArgumentParser(description="1.1.79 配置界面 / 上限 64 实机探针")
    ap.add_argument("--stage", choices=("default", "clamped"), default="default")
    args = ap.parse_args()

    props = read_properties()
    host = props.get("rcon.host", "127.0.0.1") or "127.0.0.1"
    port = int(props.get("rcon.port", "25575"))
    password = props.get("rcon.password", "")

    lines = []
    verdicts = []

    def emit(text=""):
        print(text)
        lines.append(text)

    emit("=" * 100)
    emit("1.1.79 配置界面 / 一键挖掘上限 64 —— 实机探针（--stage %s）" % args.stage)
    emit("=" * 100)

    crash_before = set(glob.glob(os.path.join(CRASH, "crash-*.txt")))
    rcon = None
    try:
        rcon = Rcon(host, port, password)
        alive = True
    except OSError as exc:
        alive = False
        emit("  [FAIL] RCON 连不上 %s:%d（%s）—— 服务端起了吗？" % (host, port, exc))

    if args.stage == "default":
        log = boot_log()
        text = "\n".join(log)

        entries = re.findall(r"Config registry:\s*(\d+)\s*entries", text)
        a4 = entries and int(entries[-1]) == EXPECTED_ENTRIES
        runtime = re.findall(r"mine_max_blocks=(\d+)", text)
        runtime = runtime[-1] if runtime else None
        emit("  %s A1 服务端顶着 1.1.79 起得来（纯客户端类没被加载，DistExecutor 分支没被走到）"
             % ("[OK  ]" if alive else "[FAIL]"))
        emit("  %s A2 全新配置里 mine_max_blocks = %s（Forge 按 1.1.79 的默认值写的）"
             % ("[OK  ]" if config_value("mine_max_blocks") == "64" else "[FAIL]",
                config_value("mine_max_blocks")))
        emit("  %s A3 全新配置里 mine_radius = %s（「范围」的口子就这一个）"
             % ("[OK  ]" if config_value("mine_radius") == "24" else "[FAIL]",
                config_value("mine_radius")))
        emit("  %s A4 启动自检日志：Config registry = %s 项（期望 %d —— 图形界面列的就是这些）"
             % ("[OK  ]" if a4 else "[FAIL]", entries[-1] if entries else "没这行", EXPECTED_ENTRIES))
        emit("  %s A6 启动日志里运行期真值：mine_max_blocks = %s"
             % ("[OK  ]" if runtime == "64" else "[FAIL]", runtime or "没这行"))
        client_leak = [ln.strip()[:180] for ln in log
                       if "NoClassDefFoundError" in ln or "net.minecraft.client" in ln]
        a5 = not client_leak
        emit("  %s A5 本次启动没有客户端类泄漏（NoClassDefFoundError / net.minecraft.client 字样）%s"
             % ("[OK  ]" if a5 else "[FAIL]",
                "" if a5 else "：%s" % client_leak[:3]))
        verdicts += [("A1 服务器正常起", alive), ("A2 默认上限 64", config_value("mine_max_blocks") == "64"),
                     ("A3 范围默认 24", config_value("mine_radius") == "24"),
                     ("A4 枚举器数出 151", bool(a4)), ("A5 无客户端类泄漏", a5),
                     ("A6 运行期上限 64", runtime == "64")]
        if alive and rcon is not None:
            emit()
            emit("  —— 控制台跑一遍 mine 命令：两种写法都该**解析通过** ——")
            emit("     （1.1.79 把方块参数换成 ResourceLocationArgument.id()：以前 word()/string() 的"
                 "不带引号形式只认 [A-Za-z0-9_.+-]，`minecraft:stone` 会被 Brigadier 判成 trailing data）")
            emit("     跑完再看它是明确拒掉还是静默失败 —— RCON 没有玩家，静默失败最坑人。")
            raw = rcon.cmd("apocalypse catgirl mine minecraft:stone 999")
            bare = rcon.cmd("apocalypse catgirl mine stone 999")
            emit("     带命名空间：%s" % raw)
            emit("     不带命名空间：%s" % bare)
            a7 = ("要玩家" in raw and "要玩家" in bare
                  and "trailing data" not in raw and "trailing data" not in bare)
            emit("  %s A7 两种写法都能解析、且都被明确拒绝（不是 Brigadier 报错、不是静默失败）"
                 % ("[OK  ]" if a7 else "[FAIL]"))
            verdicts.append(("A7 mine 语法两种写法都通", a7))

    else:
        log = boot_log()
        text = "\n".join(log)
        warn = [ln.strip()[:200] for ln in log
                if "mine_max_blocks" in ln and re.search(r"correct|invalid|range|clamp", ln, re.I)]
        entry = re.findall(r"Config registry:\s*(\d+)\s*entries", text)
        runtime = re.findall(r"mine_max_blocks=(\d+)", text)
        runtime = runtime[-1] if runtime else None
        now = config_value("mine_max_blocks")
        emit("  %s B1 手改越界值（999）之后服务端照样起得来" % ("[OK  ]" if alive else "[FAIL]"))
        emit("  %s B2 日志里 Forge 对越界值的说法：%s"
             % ("[OK  ]" if warn else "[记录]", warn if warn else "（没吭声 —— 夹在读取时，不写回文件）"))
        emit("  %s B3 启动后文件里 mine_max_blocks = %s（Forge 写回就说明校正落到盘上了）"
             % ("[OK  ]" if now in ("64", "999") else "[FAIL]", now))
        emit("  %s B5 运行期真值 = %s —— 文件 999、她实际只认 64（域 1~64 真的在夹）"
             % ("[OK  ]" if runtime == "64" else "[FAIL]", runtime or "没这行"))
        # 防「拿上一次启动的日志糊弄」：只有这次启动真的读到 999，日志里才会出现这个数
        # （Forge 的校正行形如 `Incorrect key cat_girl.mine_max_blocks was corrected from 999 to ...`）。
        tampered = [ln.strip()[:200] for ln in log if "999" in ln]
        emit("  %s B6 日志切片里出现越界值 999%s"
             % ("[OK  ]" if tampered else "[FAIL]",
                "：" + tampered[0] if tampered else "（没读到 —— 这次启动没真的读手改的值，数据不算数）"))
        emit("  %s B4 这次启动枚举器仍然数出 %s 项"
             % ("[OK  ]" if entry and int(entry[-1]) == EXPECTED_ENTRIES else "[FAIL]",
                entry[-1] if entry else "没这行"))
        verdicts += [("B1 越界不崩服", alive), ("B2 Forge 报了校正", bool(warn)),
                     ("B3 文件被写回", now == "64"),
                     ("B5 越界被夹回 64", runtime == "64"), ("B6 确实读到了 999", bool(tampered)),
                     ("B4 枚举器仍 151", bool(entry) and int(entry[-1]) == EXPECTED_ENTRIES)]

    # 日志 / 崩溃
    # D1 只认「我们自己的行」（apocalypse / cat_girl）与 NoClassDefFoundError：裸 Exception 会捞到
    # netty 启动时那句 IllegalAccessException（JDK 模块限制的老噪音，1.1.79 之前就有、不影响启动）。
    bad = [ln.strip()[:180] for ln in boot_log()
           if re.search(r"(NoClassDefFoundError|com\.apocalypse|cat_girl|apocalypse_zombies)", ln)
           and re.search(r"(Exception|Error|Caused by:)", ln)
           and "Config registry" not in ln]
    new_crash = sorted(set(glob.glob(os.path.join(CRASH, "crash-*.txt"))) - crash_before)
    emit("  %s D1 本次启动无异常行%s"
         % ("[OK  ]" if not bad else "[FAIL]", "" if not bad else "：%s" % bad[:3]))
    emit("  %s D2 没有新增 crash-report%s"
         % ("[OK  ]" if not new_crash else "[FAIL]", "" if not new_crash else "：%s" % new_crash))
    verdicts += [("D1 无异常", not bad), ("D2 无崩溃", not new_crash)]

    if rcon is not None:
        rcon.close()

    emit()
    ok = sum(1 for _, v in verdicts if v)
    emit("结论：%d/%d 通过" % (ok, len(verdicts)))
    for name, value in verdicts:
        emit("  %s %s" % ("[OK  ]" if value else "[FAIL]", name))
    emit("=" * 100)

    append = os.path.exists(REPORT) and args.stage != "default"
    with open(REPORT, "a" if append else "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("报告：%s" % REPORT)
    return 0 if ok == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
