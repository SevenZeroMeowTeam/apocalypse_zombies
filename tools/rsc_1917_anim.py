#!/usr/bin/env python3
"""RSC M1917 动画：把 tools/rsc_1917_bb_anim.js 送进 Blockbench 跑，落 raw dump，再转 GeckoLib。

用法：
  py tools/rsc_1917_anim.py            # 跑 Blockbench → 写 art/rsc_1917/_anim_raw.json → 写 .animation.json
  py tools/rsc_1917_anim.py --from-raw # 只用已有 raw dump 重转（不连 Blockbench）
  py tools/rsc_1917_anim.py --check    # 与 art/rsc_1917/rsc_1917.animation.json 逐条比对，不写盘

转换规则（从出厂文件 art/m1garand/m1_garand.animation.json 逆向核对过，与 m1_anim_export.py 同一套）：
  * 时间按 24fps 吸附（半点进位）；键名至少一位小数
  * 左手/右手系变换（与 geo.json 的 X 翻转一致）：
      position -> [-x,  y, z]     rotation -> [-x, -y, z]     scale -> 不变
  * catmullrom/smooth/bezier/easeinout -> {"post": {"vector": v}, "lerp_mode": "catmullrom"}
    step -> {... "lerp_mode": "step"}；linear -> {"vector": v}
  * 单键通道写成静态缩写；首键落在非 0 帧的插值通道写 pre+post
  * 通道顺序 rotation -> position -> scale；loop 只在循环动画上写；geckolib_format_version = 2
"""
import argparse
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ARC = os.path.join(ROOT, "art", "rsc_1917")
RAW = os.path.join(ARC, "_anim_raw.json")
OUT = os.path.join(ARC, "rsc_1917.animation.json")
JS = os.path.join(HERE, "rsc_1917_bb_anim.js")

MCP_URL = "http://localhost:3000/bb-mcp"
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
FPS = 24.0
LERP = {"catmullrom": "catmullrom", "smooth": "catmullrom", "bezier": "catmullrom",
        "easeinout": "catmullrom", "step": "step"}


# ---------------------------------------------------------------- MCP
def _post(payload, sid=None):
    h = dict(HDRS)
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        sid_out = r.headers.get("mcp-session-id")
        raw = r.read().decode("utf-8", "replace")
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:]), sid_out
    return (json.loads(raw) if raw.strip() else {}), sid_out


def mcp_run_anim_js():
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "hermes", "version": "1.0"}}}
    _, sid = _post(init)
    if not sid:
        _, sid = _post(init)
    if not sid:
        raise SystemExit("拿不到 mcp-session-id（Blockbench MCP 没起来？）")
    code = ("(function(){var fs=require('fs');"
            "return (0,eval)(fs.readFileSync(%s,'utf8'));})()" % json.dumps(JS))
    res, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "risky_eval", "arguments": {"code": code}}}, sid)
    if "error" in res:
        raise SystemExit("risky_eval 报错: " + json.dumps(res["error"], ensure_ascii=False))
    texts = [c.get("text", "") for c in (res.get("result", {}) or {}).get("content", []) or []]
    blob = "\n".join(texts)
    return blob


def extract_dump(blob):
    """risky_eval 的返回里带一坨 JSON；把最外层对象切出来。"""
    i = blob.find("{")
    if i < 0:
        raise SystemExit("返回里没有 JSON：" + blob[:400])
    depth = 0
    for j in range(i, len(blob)):
        if blob[j] == "{":
            depth += 1
        elif blob[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(blob[i:j + 1])
    raise SystemExit("JSON 括号不闭合：" + blob[:400])


# ---------------------------------------------------------------- 转换
def flip(chan, vals):
    x, y, z = (float(v) for v in vals)
    if chan == "position":
        return [-x, y, z]
    if chan == "rotation":
        return [-x, -y, z]
    return [x, y, z]


def fmt_time(t):
    s = f"{float(t):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def num(v):
    f = float(v)
    return int(f) if f.is_integer() else round(f, 4)


def vec(vals):
    return [num(v) for v in vals]


def build(raw):
    animations = {}
    for a in raw["anims"]:
        bones = {}
        for bone, chans in a["bones"].items():
            out_bone = {}
            for chan in ("rotation", "position", "scale"):
                arr = chans.get(chan)
                if not arr:
                    continue
                snapped = {}
                for k in sorted(arr, key=lambda k: float(k["t"])):
                    t = math.floor(float(k["t"]) * FPS + 0.5) / FPS
                    snapped[fmt_time(t)] = k          # 同帧取后者
                times = sorted(snapped.keys(), key=float)
                if len(times) == 1:
                    out_bone[chan] = {"vector": vec(flip(chan, snapped[times[0]]["v"]))}
                    continue
                ochan = {}
                for i, t in enumerate(times):
                    v = vec(flip(chan, snapped[t]["v"]))
                    mode = LERP.get(snapped[t].get("i") or "")
                    if not mode:
                        ochan[t] = {"vector": v}
                    elif i == 0 and float(t) != 0.0:
                        ochan[t] = {"pre": {"vector": v}, "post": {"vector": v}, "lerp_mode": mode}
                    else:
                        ochan[t] = {"post": {"vector": v}, "lerp_mode": mode}
                out_bone[chan] = ochan
            if out_bone:
                bones[bone] = out_bone
        entry = {}
        if a["loop"] == "loop":
            entry["loop"] = True
        entry["animation_length"] = num(a["length"])
        entry["bones"] = bones
        animations[a["name"]] = entry
    return {"format_version": "1.8.0", "animations": animations, "geckolib_format_version": 2}


EXPECTED = ["static_idle", "draw", "shoot", "bolt", "reload_tactical", "reload_empty",
            "single_load", "shoot_last"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-raw", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    os.makedirs(ARC, exist_ok=True)
    if not args.from_raw:
        blob = mcp_run_anim_js()
        dump = extract_dump(blob)
        warn = dump.get("warnings") or []
        for w in warn:
            print("  ! " + w)
        raw = dump.get("animation_dump")
        if not raw:
            raise SystemExit("Blockbench 没回 animation_dump（前置步骤失败？）：" + blob[:600])
        with open(RAW, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=1)
        print(f"wrote {RAW}  ({len(raw['anims'])} anims)")
        got = [x["name"] for x in raw["anims"]]
        miss = [n for n in EXPECTED if n not in got]
        extra = [n for n in got if n not in EXPECTED]
        if miss or extra:
            print(f"  ! 片段表不符：缺 {miss} 多 {extra}")
    else:
        with open(RAW, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

    doc = build(raw)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        with open(OUT, "r", encoding="utf-8") as fh:
            old = json.load(fh)
        bad = 0
        for name in sorted(set(list(old.get("animations", {})) + list(doc["animations"]))):
            same = json.dumps(old["animations"].get(name, {}), sort_keys=True) == \
                   json.dumps(doc["animations"].get(name, {}), sort_keys=True)
            print(f"  {name:16s} {'一致' if same else '不一致'}")
            bad += 0 if same else 1
        print("逐条对比：", "全部一致" if not bad else f"{bad} 个动画不同")
        return 1 if bad else 0

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {OUT}")
    for name, a in doc["animations"].items():
        keys = sum(len(k) for b in a["bones"].values() for k in b.values())
        print(f"  {name:16s} len={a['animation_length']:<5} loop={str(a.get('loop', False)):5s} "
              f"bones={len(a['bones']):2d} keys={keys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
