#!/usr/bin/env python3
"""M1 加兰德换弹真机化补丁 —— 改的是**真源** art/m1garand/_anim_raw.json。

真源链：tools/m1_garand_bb_anim.js（Blockbench 内写盘）-> _anim_raw.json
        -> tools/m1_anim_export.py -> art/m1garand/m1_garand.animation.json -> 手工拷贝到
           src/main/resources/assets/apocalypse_zombies/animations/m1_garand.animation.json

为什么必须先改 dump：上一次的「压入件纯竖直」补丁只改了导出产物（art/src 两份 JSON）与那个已经
落后的生成器 JS，**dump 里 clip_in 的 z 还留着 0.3 / 1.1 / 1.7**（空夹弹飞与下压两段都带前后分量）。
谁跑一次 m1_anim_export.py，横滑就会被重新导出 —— 本脚本的 ① 把这条漂移关掉。

改动清单（全部按现实 M1 加兰德的装填规程）：
  ① clip_in 的 z 全归 0（压入件只走竖直；空夹弹飞同段一并对齐，避免同一条通道两种口径）
  ② reload_empty：枪机释放推后 2 帧 —— 新漏夹落位(1.2917)后先松压、手撤离(到 1.4583)，
     枪机才自由前冲；掌根拍到位那一下（move 的蹭动）随之后移。手册第 3/4 步的原话是
     「remove your hand and allow the bolt to travel forward freely」，手没撤走枪机不动 ——
     这一拍是 M1 装填最有辨识度的地方（也是 M1 thumb 的由来），原来只有 0.083 s，读不出来。
  ③ reload_tactical：补上**膛内活弹的抛壳**。真机上把导气杆拉到底，膛里那发活弹会先被抛出去
     （手册卸弹程序明写），原来 casing 全程 scale=0，那颗弹是凭空消失的。
  ④ 枪机行程 1.10 -> 1.36 u（0.30-06 全弹长 84.8 mm ≈ 1.36 u）：1.10 u = 69 mm 越不过漏夹末弹
     底缘，半自动自循环在几何上不成立。几何侧由 tools/m1_garand_geo_real.py 同步 trim 尾部方块。
  ⑤ 新增 single_load 段（单发补弹，手册 "To load a single round"）：拉到底 -> 抛掉膛内活弹 ->
     手放一发送进膛 -> 按托弹板 -> 让枪机可控地闭锁（不是自由前冲，手册要求手扶着机柄）。
  ⑥ 新增 shoot_last 段（末发，FM 23-5 "When the last round is fired, the empty clip is automatically
     ejected and the bolt remains to the rear"）：整段沿用 shoot 的后坐/机体/抛壳曲线，只改两处 ——
     导气杆退到底即被挂机爪咬住、整段停在后退位；空漏夹在**末发当场**被抛夹弹簧顶出井口。
     2026-09-30 之前的做法是把「叮」+ 空夹弹飞都塞在按 R 之后（reload_empty 里），
     真机上这两件事都发生在最后一发击发的瞬间，不在换弹时。
  ⑦ reload_empty：起手枪机**已经在后退位**（挂机爪扣住），不再重复拉一次到底（真机此时井里也
     已经没有夹了）—— 新漏夹只走「从井口上方压下」一段；1.2917 落位 -> 手撤离 1.4583 -> 自由前冲
 1.75 闭锁（②的节拍保留），枪机通道从 1.2917 之前恒为全行程。
 ⑧ 删除所有剪辑里的 cover 通道：真机机匣顶部没有"漏夹井盖"这件东西（真机拆件表 + TACOM 手册：
 漏夹是**直接压下去**、靠左侧卡榫扣住的，没有"打开盖"这一步）。几何已由
 tools/m1_cover_removal_geo.py 把 cover 骨（3 方块）删掉；动作为什么必须跟着删：
 那两条轨把井口从 |x| < 0.190 收窄到 |x| < 0.100，而漏夹宽 ±0.167 ⇒ 旧动画只能靠"抬盖
 0.55u"把夹塞进去，且"盖合"时轨的内面正好扎进漏夹里。这一步在本脚本里做（而不是在导出脚本
 里），是为了让 dump 就算被旧数据覆盖一遍也自愈成干净状态。

用法：
  python tools/m1_reload_real.py --dry-run   # 只打印计划，不写盘
  python tools/m1_reload_real.py             # 写盘（幂等）
  python tools/m1_reload_real.py --check     # 断言盘上文件已是目标状态（CI/回归用）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.normpath(os.path.join(HERE, "..", "art", "m1garand", "_anim_raw.json"))

CATA = "catmullrom"
LIN = "linear"
OLD_TRAVEL = 1.10
NEW_TRAVEL = 1.36
K = NEW_TRAVEL / OLD_TRAVEL          # 返程曲线的等比放大（1.2363…）
# 卡榫按入：模型 +X 是射手左侧（导气杆在 −X），dump 里的 x 要取正号才会被导出成"向机匣内收"
PRESS_X = 0.06

# ④ 之后 reload_empty 的枪机通道重写（②：释放推后 2 帧，返程等比）
BOLT_EMPTY = [
    (0.0, [0, 0, NEW_TRAVEL], CATA),             # ⑦ 起手即挂机（末发由 shoot_last 拉到底并挂住）
    (1.2917, [0, 0, NEW_TRAVEL], CATA),          # 一直挂住，直到新漏夹落位
    (1.4583, [0, 0, 0.88 * K], CATA),            # ← 手撤离后的第一帧才有位移（原 1.375）
    (1.5417, [0, 0, 0.50 * K], CATA),
    (1.5833, [0, 0, 0.20 * K], CATA),
    (1.6667, [0, 0, 0.06 * K], CATA),
    (1.75, [0, 0, 0], CATA),                     # 闭锁到位
    (3.0, [0, 0, 0], CATA),
]

MOVE_EMPTY_POS = [
    (0.0, [0, 0, 0], CATA),
    (0.3333, [0.06, -0.10, 0.10], CATA),
    (1.4167, [0, -0.06, 0.06], CATA),
    (1.75, [0, 0.06, -0.08], CATA),              # 掌根拍（原 1.6667）
    (2.0, [0, 0, 0], CATA),
    (3.0, [0, 0, 0], CATA),
]

MOVE_EMPTY_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.3333, [-2.2, 0.6, 0], CATA),
    (1.1667, [-1.2, 0.3, 0], CATA),
    (1.4167, [0.25, 0.15, -0.30], CATA),         # ← 新增：手离开机匣、枪身回正的一丝摆动
    (1.6667, [0.8, 0, 0], CATA),                 # 枪机前冲的反作用（原 1.5833）
    (1.7917, [-0.25, 0, 0], CATA),
    (3.0, [0, 0, 0], CATA),
]

# ③ 膛内活弹：逐帧复用 shoot 的抛壳曲线（+5 帧 = 0.2083 s，落在导气杆到位 0.25 之后）
CASING_EJECT_ROT = [
    (0.2917, [-25, 0, -40], CATA),
    (0.4167, [-70, 0, -160], CATA),
    (0.5417, [-140, 0, -320], CATA),
    (0.6667, [-190, 0, -430], CATA),
]
CASING_EJECT_POS = [
    (0.2917, [0.35, 0.55, 0.10], CATA),
    (0.4167, [0.95, 1.55, 0.50], CATA),
    (0.5417, [1.9, 2.6, 1.3], CATA),
    (0.6667, [2.6, 3.4, 1.9], CATA),
]

# ⑤ 单发补弹：抛旧弹(0.2917-0.6667) -> 手送新弹(0.7083-0.9583) -> 随枪机入膛 -> 闭锁
SINGLE_LEN = 1.5
SINGLE_BOLT = [
    (0.0, [0, 0, 0], CATA),
    (0.0833, [0, 0, 0.12], CATA),
    (0.2917, [0, 0, NEW_TRAVEL], CATA),
    (0.8333, [0, 0, NEW_TRAVEL], CATA),          # 手送弹期间导气杆挂住
    (0.875, [0, 0, 0.88 * K], CATA),             # 手扶着机柄可控闭锁（不是自由前冲）
    (0.9583, [0, 0, 0.50 * K], CATA),
    (1.0, [0, 0, 0.20 * K], CATA),
    (1.0833, [0, 0, 0.06 * K], CATA),
    (1.1667, [0, 0, 0], CATA),
    (SINGLE_LEN, [0, 0, 0], CATA),
]
SINGLE_CASING_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.2917, [-25, 0, -40], CATA),
    (0.4167, [-70, 0, -160], CATA),
    (0.5417, [-140, 0, -320], CATA),
    (0.6667, [-190, 0, -430], CATA),             # 抛掉的膛内活弹
    (0.7083, [-15, 0, 0], CATA),
    (0.8333, [-8, 0, 0], CATA),                  # 手送的新弹（大致顺枪膛轴向）
    (0.9583, [0, 0, 0], CATA),
    (1.1667, [0, 0, 0], CATA),
]
SINGLE_CASING_POS = [
    (0.0, [0, 0, 0], CATA),
    (0.2917, [0.35, 0.55, 0.10], CATA),
    (0.4167, [0.95, 1.55, 0.50], CATA),
    (0.5417, [1.9, 2.6, 1.3], CATA),
    (0.6667, [2.6, 3.4, 1.9], CATA),
    (0.7083, [1.4, 1.2, -1.2], CATA),            # 换件（scale 在这一帧切回 1，跳变被 0 遮住）
    (0.8333, [0.35, 0.75, -1.9], CATA),
    (0.9583, [0.05, 0.12, -2.7], CATA),
    (1.0417, [0, 0, -4.2], CATA),                # 随枪机入膛
    (1.1667, [0, 0, -5.6], CATA),
]
SINGLE_CASING_SCALE = [
    (0.0, [0, 0, 0], LIN),
    (0.2917, [1, 1, 1], LIN),
    (0.6667, [0, 0, 0], LIN),
    (0.7083, [1, 1, 1], LIN),
    (1.1667, [0, 0, 0], LIN),                    # 进了膛就看不见了
]
SINGLE_COVER = [
    (0.0, [0, 0, 0], CATA),
    (0.2917, [0, 0.55, 0], CATA),
    (1.0, [0, 0.55, 0], CATA),
    (1.1667, [0, 0, 0], CATA),
    (SINGLE_LEN, [0, 0, 0], CATA),
]
SINGLE_MOVE_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.3333, [-1.6, 0.5, 0], CATA),
    (0.7917, [-1.0, 0.3, 0], CATA),
    (1.0, [0.6, 0, 0], CATA),
    (1.25, [-0.2, 0, 0], CATA),
    (SINGLE_LEN, [0, 0, 0], CATA),
]
SINGLE_MOVE_POS = [
    (0.0, [0, 0, 0], CATA),
    (0.3333, [0.05, -0.08, 0.08], CATA),
    (0.8333, [0, -0.05, 0.05], CATA),
    (1.0417, [0, 0.05, -0.06], CATA),
    (1.3333, [0, 0, 0], CATA),
    (SINGLE_LEN, [0, 0, 0], CATA),
]


# ⑤ 战术换弹：卡榫按下/松开 + 枪机释放推后（漏夹落位 1.0 -> 手撤离 -> 1.2083 自由前冲）
TACT_LATCH = [
    (0.2917, [PRESS_X, 0, 0], CATA),     # 导气杆到底之后才按得动卡榫
    (0.75, [PRESS_X, 0, 0], CATA),
    (0.7917, [0, 0, 0], CATA),           # 松手（新夹进来之前必须回位）
    (2.5833, [0, 0, 0], CATA),
]
TACT_BOLT = [
    (0.0, [0, 0, 0], CATA),
    (0.0833, [0, 0, 0.12], CATA),
    (0.25, [0, 0, NEW_TRAVEL], CATA),
    (1.2083, [0, 0, NEW_TRAVEL], CATA),
    (1.25, [0, 0, 0.88 * K], CATA),
    (1.2917, [0, 0, 0.50 * K], CATA),
    (1.3333, [0, 0, 0.20 * K], CATA),
    (1.4167, [0, 0, 0.06 * K], CATA),
    (1.5, [0, 0, 0], CATA),
    (2.5833, [0, 0, 0], CATA),
]
# 枪机的蹭动/枪身反作用必须跟着新的释放时刻走（原曲线绑在旧释放时刻 1.0417/1.2917）
TACT_MOVE_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.2917, [-2, 0.55, 0], CATA),
    (1.1667, [-1.1, 0.28, 0], CATA),
    (1.4583, [0.7, 0, 0], CATA),
    (2.5833, [0, 0, 0], CATA),
]
TACT_MOVE_POS = [
    (0.0, [0, 0, 0], CATA),
    (0.2917, [0.06, -0.09, 0.09], CATA),
    (1.2083, [0, -0.05, 0.05], CATA),
    (1.5, [0, 0.05, -0.06], CATA),
    (2.5833, [0, 0, 0], CATA),
]
TACT_BODY_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.4167, [0.65, 0, 0], CATA),
    (1.1667, [-0.85, 0, 0], CATA),
    (1.5417, [0.4, 0, 0], CATA),
    (2.5833, [0, 0, 0], CATA),
]
# reload_empty 的枪身反作用同理（原 1.4167 / 1.7083 绑在旧释放时刻）
EMPTY_BODY_ROT = [
    (0.0, [0, 0, 0], CATA),
    (0.4583, [0.7, 0, 0], CATA),
    (1.5417, [-0.9, 0, 0], CATA),
    (1.8333, [0.45, 0, 0], CATA),
    (3.0, [0, 0, 0], CATA),
]


# ⑥ 末发 shoot_last（1.2 s = 24 t）：导气杆退到底即被挂机爪咬住，整段不回位；空漏夹当场顶出井口
SHOOT_LAST_LEN = 1.2
SHOOT_LAST_BOLT = [
    (0.0, [0, 0, 0], CATA),
    (0.0417, [0, 0, 1.137], CATA),
    (0.0833, [0, 0, NEW_TRAVEL], CATA),
    (SHOOT_LAST_LEN, [0, 0, NEW_TRAVEL], CATA),  # 挂机：停在后退位（shoot 的 0.125 回位键去掉）
]
# 空夹弹飞：沿用 reload_empty 原来那条曲线（0.55 -> 2.2 -> 3.6 u），整段搬到"末发"这一拍
SHOOT_LAST_CLIP_POS = [
    (0.0, [0, 0, 0], CATA),
    (0.1667, [0, 0, 0], CATA),
    (0.2917, [0, 0.55, 0], CATA),
    (0.4583, [0, 2.2, 0], CATA),
    (0.625, [0, 3.6, 0], CATA),
    (SHOOT_LAST_LEN, [0, 3.6, 0], CATA),
]
# 夹在井里全程可见（底下还有一发），飞离画面那一帧收掉（1 帧的 pop-out，同 shoot 的 pop-in 口径）
SHOOT_LAST_CLIP_SCALE = [
    (0.0, [1, 1, 1], LIN),
    (0.5833, [1, 1, 1], LIN),
    (0.625, [0, 0, 0], LIN),
]

# ⑦ reload_empty 的漏夹：井里已经没有夹（末发那拍飞掉了），只走"新夹从井口上方压下"
EMPTY_CLIP_POS = [
    (0.0, [0, 2.6, 0], CATA),
    (1.0, [0, 2.6, 0], CATA),
    (1.1667, [0, 1.1, 0], CATA),
    (1.2917, [0, 0, 0], CATA),                   # 压到位
    (1.3333, [0, 0.06, 0], CATA),
    (1.4167, [0, 0, 0], CATA),
    (3.0, [0, 0, 0], CATA),
]
# 新夹 1.0 s 才出现在井口上方（此前全程不可见；首键非 0 帧 -> 导出时写成 pre+post，1.0 之前恒为 0）
EMPTY_CLIP_SCALE = [
    (0.9583, [0, 0, 0], LIN),
    (1.0, [1, 1, 1], LIN),
]


def keys(rows, first=None):
    """(t, v, i) 列表 -> dump 的键格式；first 给定的通道补一个 0 帧静止键。"""
    out = []
    if first is not None:
        out.append({"t": 0.0, "v": list(first), "i": CATA})
    out += [{"t": t, "v": list(v), "i": i} for t, v, i in rows]
    return out


def stat(v, chan="scale"):
    return [{"t": 0.0, "v": list(v), "i": LIN}]


def clips(doc):
    return {a["name"]: a for a in doc["anims"]}


def bone(clip, name):
    return clip["bones"].setdefault(name, {})


def apply(doc):
    """就地打补丁；返回改动条目列表（用于打印）。"""
    A = clips(doc)
    log = []

    # ④ 枪机行程拉到全行程（按各段自己的峰值等比归一 —— 幂等：归一后再跑系数为 1）
    for name in ("shoot", "bolt"):
        ch = bone(A[name], "bolt").get("position", [])
        peak = max([float(k["v"][2]) for k in ch] or [0.0])
        if peak > 0 and abs(peak - NEW_TRAVEL) > 1e-3:
            f = NEW_TRAVEL / peak
            for k in ch:
                k["v"][2] = round(float(k["v"][2]) * f, 4)
            log.append("④ %s: 枪机行程 %.3f -> %.3f u（×%.4f）" % (name, peak, NEW_TRAVEL, f))
        else:
            log.append("④ %s: 枪机行程已是 %.3f u" % (name, peak))

    # ① clip_in 的 z 归 0
    for name in ("reload_empty", "reload_tactical"):
        n = 0
        for k in bone(A[name], "clip_in").get("position", []):
            if float(k["v"][2]) != 0.0:
                k["v"][2] = 0.0
                n += 1
        log.append("① %s: clip_in z 归 0（%d 帧）" % (name, n))

    # ② reload_empty 的节拍
    bone(A["reload_empty"], "bolt")["position"] = [dict(k) for k in keys(BOLT_EMPTY)]
    bone(A["reload_empty"], "move")["position"] = [dict(k) for k in keys(MOVE_EMPTY_POS)]
    bone(A["reload_empty"], "move")["rotation"] = [dict(k) for k in keys(MOVE_EMPTY_ROT)]
    log.append("② reload_empty: 枪机释放 1.375 -> 1.4583 s，掌根拍 -> 1.75 s")

    # ③ reload_tactical 的膛内活弹
    cas = bone(A["reload_tactical"], "casing")
    cas["rotation"] = keys(CASING_EJECT_ROT, first=[0, 0, 0])
    cas["position"] = keys(CASING_EJECT_POS, first=[0, 0, 0])
    cas["scale"] = keys([(0.2917, [1, 1, 1], LIN), (0.6667, [0, 0, 0], LIN)], first=[0, 0, 0])
    log.append("③ reload_tactical: 膛内活弹 0.2917 s 抛出、0.6667 s 收（复用 shoot 曲线）")

    # ⑤ 卡榫（几何侧由 tools/m1_garand_latch_geo.py 加 bone）：半满漏夹必须按住导气杆 + 按卡榫才脱出；
    #    枪机释放同样推后（与 reload_empty 一个口径：漏夹落位 1.0 -> 手撤离 -> 1.2083 才自由前冲）
    bone(A["reload_tactical"], "clip_latch")["position"] = keys(TACT_LATCH, first=[0, 0, 0])
    bone(A["reload_tactical"], "bolt")["position"] = [dict(k) for k in keys(TACT_BOLT)]
    log.append("⑤ reload_tactical: 卡榫 0.2917 s 按下 / 0.7917 s 松开；枪机释放 1.0417 -> 1.2083 s")
    bone(A["reload_tactical"], "move")["rotation"] = [dict(k) for k in keys(TACT_MOVE_ROT)]
    bone(A["reload_tactical"], "move")["position"] = [dict(k) for k in keys(TACT_MOVE_POS)]
    bone(A["reload_tactical"], "body")["rotation"] = [dict(k) for k in keys(TACT_BODY_ROT)]
    bone(A["reload_empty"], "body")["rotation"] = [dict(k) for k in keys(EMPTY_BODY_ROT)]

    # ⑤ 新增 single_load
    A_by_name = clips(doc)
    if "single_load" in A_by_name:
        one = A_by_name["single_load"]
        one["length"] = SINGLE_LEN
        one["loop"] = "once"
    else:
        one = {"name": "single_load", "length": SINGLE_LEN, "loop": "once", "bones": {}}
        doc["anims"].append(one)
    one["bones"] = {
        "bolt": {"position": keys(SINGLE_BOLT, first=[0, 0, 0])},
        "cover": {"position": keys(SINGLE_COVER, first=[0, 0, 0])},
        "clip_in": {"scale": stat([0, 0, 0])},          # 单发补弹不动漏夹：井里没有夹
        "casing": {"rotation": keys(SINGLE_CASING_ROT, first=[0, 0, 0]),
                   "position": keys(SINGLE_CASING_POS, first=[0, 0, 0]),
                   "scale": keys(SINGLE_CASING_SCALE)},
        "move": {"rotation": keys(SINGLE_MOVE_ROT, first=[0, 0, 0]),
                 "position": keys(SINGLE_MOVE_POS, first=[0, 0, 0])},
    }
    log.append("⑤ single_load: 新增 %.1f s 段（拉到底/抛活弹/送弹/可控闭锁）" % SINGLE_LEN)

    # ⑥ 新增 shoot_last：整段**从 shoot 复制**（后坐/机体/弹壳曲线同源），只换两处 ——
    #    枪机退到底即挂机不复位、空漏夹当场弹出。已存在时按同一位次整段重建，保证与 shoot 始终同源。
    src = json.loads(json.dumps(A["shoot"]))
    src["name"] = "shoot_last"
    src["length"] = SHOOT_LAST_LEN
    src["loop"] = "once"
    src["bones"]["bolt"] = {"position": [dict(k) for k in keys(SHOOT_LAST_BOLT)]}
    src["bones"]["clip_in"] = {"position": [dict(k) for k in keys(SHOOT_LAST_CLIP_POS)],
                               "scale": [dict(k) for k in keys(SHOOT_LAST_CLIP_SCALE)]}
    at = [i for i, a in enumerate(doc["anims"]) if a["name"] == "shoot_last"]
    if at:
        doc["anims"][at[0]] = src
    else:
        doc["anims"].append(src)
    log.append("⑥ shoot_last: %.1f s 段（末发挂机 + 空夹当场弹出；机体/弹壳沿用 shoot）" % SHOOT_LAST_LEN)

    # ⑦ reload_empty 的漏夹通道（枪机"起手即挂机"已在 ② 的 BOLT_EMPTY 表里）
    bone(A["reload_empty"], "clip_in")["position"] = [dict(k) for k in keys(EMPTY_CLIP_POS)]
    bone(A["reload_empty"], "clip_in")["scale"] = [dict(k) for k in keys(EMPTY_CLIP_SCALE)]
    log.append("⑦ reload_empty: 漏夹只走「从井口上方压下」，空夹不再在这里飞第二次")

    # ⑧ 机匣顶部无盖（几何里已删 cover 骨）⇒ 每个剪辑里的 cover 通道一起删掉。
    dropped = [a["name"] for a in doc["anims"] if a["bones"].pop("cover", None) is not None]
    log.append("⑧ cover: 从 %d 段里删掉漏夹井盖通道%s"
               % (len(dropped), ("（" + "、".join(dropped) + "）") if dropped else ""))
    return log


def js_dump_text(obj):
    """与生成器 tools/m1_garand_bb_anim.js 的 JSON.stringify(dump, null, 1) 逐字节同构：
    · 缩进 1 空格            · 数字 round 到 4 位（JS 侧是 +time.toFixed(4)）
    · 整数不写小数点（JS 的 0 不是 0.0）—— 否则每次改写都会产生整文件 diff
    """
    def num(x):
        if isinstance(x, int) and not isinstance(x, bool):
            return str(x)
        r = round(float(x), 4)
        return str(int(r)) if r == int(r) else repr(r)

    def esc(s):
        return json.dumps(s, ensure_ascii=False)

    def rec(o, lvl):
        pad = " " * lvl
        inner = " " * (lvl + 1)
        if isinstance(o, dict):
            if not o:
                return "{}"
            body = ",\n".join("%s%s: %s" % (inner, esc(k), rec(v, lvl + 1)) for k, v in o.items())
            return "{\n%s\n%s}" % (body, pad)
        if isinstance(o, list):
            if not o:
                return "[]"
            body = ",\n".join("%s%s" % (inner, rec(v, lvl + 1)) for v in o)
            return "[\n%s\n%s]" % (body, pad)
        if isinstance(o, bool):
            return "true" if o else "false"
        if o is None:
            return "null"
        if isinstance(o, (int, float)):
            return num(o)
        return esc(o)

    return rec(obj, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只断言盘上已是目标状态")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    args = ap.parse_args()

    raw = open(RAW, "r", encoding="utf-8", newline="").read()
    tail = "\n" if raw.endswith("\n") else ""          # 保持原文件的行尾/结尾约定
    disk = json.loads(raw)

    target = json.loads(json.dumps(disk))
    log = apply(target)

    if args.check:
        same = js_dump_text(disk) + tail == js_dump_text(target) + tail
        print("真源 dump：", "已是目标状态" if same else "★与目标状态不一致（跑一次不带 --check 的）")
        return 0 if same else 1

    for line in log:
        print("  " + line)
    if args.dry_run:
        print("dry-run：未写盘")
        return 0

    with open(RAW, "w", encoding="utf-8", newline="") as fh:
        fh.write(js_dump_text(target) + tail)
    print("wrote %s" % RAW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
