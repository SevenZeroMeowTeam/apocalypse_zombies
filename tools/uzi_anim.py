#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uzi 动画生成器 —— 通过 Blockbench MCP 写入 4 个 clip 并导出 GeckoLib 动画文件。

前置：几何生成器已跑过（`tools/uzi_bb_gen.js` 经 risky_eval），项目 uzi / geckolib_model 处于打开状态。
      几何生成器只清 elements+groups，不清 animations，所以本脚本可反复重跑。

用法：
    python tools/uzi_anim.py            # 重置动画 -> 建 8 个 clip -> 全部关键帧设 catmullrom -> 导出
    python tools/uzi_anim.py --dry      # 只打印将写入的关键帧统计，不动 Blockbench

坐标/单位：与几何同一空间（作者空间）。16u = 1 方块；枪口 = -Z；上 = +Y；+X = 射手右侧。
  - bolt 沿 +Z 后退（枪口在 -Z，所以后退就是 +Z），行程 1.05u ≈ 66mm。
  - 弹匣从握把里垂直落出：-Y 5.60u 后弹匣顶(0.58)降到 -5.02，已完全脱出握把底(-2.00)。
  - casing 抛向 +X（作者空间右侧），导出时 x 会被镜像成 -x —— 与几何的镜像契约一致。
  - 三个弹带 mag_r1/r2/r3 用 scale 0/1 表现"空匣/满匣"（与 mosin 的 mag_r1..r5 同一手法）。
  - additional_magazine 绝不参与动画（TaCZ 硬规则）。

命名契约（Java 侧按键名取）：
    static_idle / draw / shoot / bolt / reload_tactical / reload_empty
    + ADS_up / ADS_down（照 crossbow 的插值瞄准过渡）
    本脚本负责全部 8 个。枪焰不在这里：与 AWM/弩 一样由 Java GunAttackGoal 按
    MUZZLE_FORWARD 撒粒子，骨骼树不需要 muzzle 骨。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bbmcp_call as bb  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "src", "main", "resources", "assets", "apocalypse_zombies",
                   "animations", "uzi.animation.json")

RESET = ("(function(){var n=0;if(typeof Animation!=='undefined'){Animation.all.slice().forEach("
         "function(a){try{a.remove();n++;}catch(e){}});}return {removed:n,left:Animation.all.length};})()")

PREFIX_FIX = ("(function(){var r=[];Animation.all.forEach(function(a){"
              "a.name=String(a.name).replace('animation.','');r.push(a.name);});return r;})()")

# Blockbench 的 BoneAnimator 把关键帧直接存在 rotation/position/scale **数组**里
# (不是 .keyframes)。GeckoLib 插件只在插值非 linear 时才写 lerp_mode，
# 而仓库的 m1_garand 导出体每个关键帧都带 "lerp_mode":"catmullrom" —— 所以必须逐个设上。
#
# 例外：shoot_auto 是 2 帧的连发循环，catmullrom 在这么短的区间里会严重过冲
# （枪机会冲过 1.05 的机械止点再弹回来）。枪机本来就是硬止动，线性才是物理正确的，
# 而且 linear 不写 lerp_mode，游戏侧默认就是线性 —— 两头都对。
SETINTERP = ("(function(){var n=0;Animation.all.forEach(function(a){var an=a.animators||{};"
             "var mode=(String(a.name).replace('animation.','')==='shoot_auto')?'linear':'catmullrom';"
             "Object.keys(an).forEach(function(k){var j=an[k];"
             "['rotation','position','scale'].forEach(function(ch){var arr=j[ch];"
             "if(!arr||!arr.length)return;for(var i=0;i<arr.length;i++){if(arr[i]){"
             "arr[i].interpolation=mode;n++;}}});});});return {keys:n};})()")


def b(time, **kw):
    d = {"time": time}
    d.update(kw)
    return d

# ---------------------------------------------------------------- 空间转换层
# 参考文件（m1_garand / crossbow 的 .animation.json）是 **文件空间**，游戏直接读它。
# Blockbench 的 GeckoLib 导出器在 作者空间 -> 文件空间 之间做了一次镜像：
#     position : x 取反，y / z 不变
#     rotation : x 与 y 取反，z 不变
# （实测：把弩 ADS_up 的 move.position / body.rotation 与 uzi 的导出结果逐键比对得出。）
# 因此本脚本全部数值按 **文件空间** 书写 —— 可以直接和 .animation.json 对照，
# 由 pos() / rot() 转成作者空间喂给 Blockbench。
def pos(v):
    return [-v[0], v[1], v[2]]


def rot(v):
    return [-v[0], -v[1], v[2]]



CLIPS = {}

# ---------------------------------------------------------------- static_idle
# 静止/复位 clip：不是空的关键帧集合，而是"把每个零件明确写回静止值"，
# 这样上一个 clip 的残留变换（后座、弹匣位移、弹壳 scale）一定会被清掉。
CLIPS["static_idle"] = dict(length=2.0, loop=True, bones={
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.66, position=pos([0, 0.04, 0]), rotation=rot([0.25, 0.12, 0])),
             b(1.33, position=pos([0, -0.02, 0.02]), rotation=rot([-0.15, -0.10, 0])),
             b(2.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])), b(0.66, rotation=rot([-0.20, 0, 0])),
             b(1.33, rotation=rot([0.15, 0, 0])), b(2.0, rotation=rot([0, 0, 0]))],
    "bolt": [b(0.0, position=pos([0, 0, 0])), b(2.0, position=pos([0, 0, 0]))],
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(2.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "casing": [b(0.0, scale=[0, 0, 0]), b(2.0, scale=[0, 0, 0])],
    "mag_r1": [b(0.0, scale=[1, 1, 1]), b(2.0, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[1, 1, 1]), b(2.0, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[1, 1, 1]), b(2.0, scale=[1, 1, 1])],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(2.0, rotation=rot([0, 0, 0]))],
})

# ---------------------------------------------------------------- bolt (拉栓)
# 拉机柄在机匣顶部的槽里后拉 -> 抛壳 -> 松手复进。Uzi 是自由枪机，
# 所谓"拉栓"就是把枪机拉到后方再放，行程短、动作干脆。
CLIPS["bolt"] = dict(length=1.2667, loop=False, bones={
    "bolt": [b(0.0, position=pos([0, 0, 0])),
             b(0.09, position=pos([0, 0, 0.18])),
             b(0.30, position=pos([0, 0, 1.05])),
             b(0.58, position=pos([0, 0, 1.05])),
             b(0.70, position=pos([0, 0, 0.12])),
             b(0.80, position=pos([0, 0, 0.03])),
             b(0.92, position=pos([0, 0, 0])),
             b(1.2667, position=pos([0, 0, 0]))],
    "casing": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0]),
               b(0.20, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0]),
               b(0.29, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[1, 1, 1]),
               b(0.36, position=pos([-0.3, 0.35, 0.10]), rotation=rot([70, 0, -150]), scale=[1, 1, 1]),
               b(0.48, position=pos([-0.95, 1.15, 0.30]), rotation=rot([190, 0, -380]), scale=[1, 1, 1]),
               b(0.62, position=pos([-1.75, 2.05, 0.55]), rotation=rot([260, 0, -520]), scale=[1, 1, 1]),
               b(0.72, position=pos([-2.45, 2.85, 0.80]), rotation=rot([300, 0, -620]), scale=[0, 0, 0]),
               b(1.2667, position=pos([-2.45, 2.85, 0.80]), rotation=rot([300, 0, -620]), scale=[0, 0, 0])],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(0.12, rotation=rot([-4, 0, 0])),
                      b(0.24, rotation=rot([0, 0, 0])), b(1.2667, rotation=rot([0, 0, 0]))],
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.30, position=pos([0.05, -0.04, 0.10]), rotation=rot([1.6, -0.4, 0])),
             b(0.70, position=pos([0, 0, 0]), rotation=rot([-0.5, 0, 0])),
             b(0.95, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(1.2667, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])), b(0.32, rotation=rot([-0.9, 0, 0])),
             b(0.70, rotation=rot([0.5, 0, 0])), b(0.95, rotation=rot([0, 0, 0])),
             b(1.2667, rotation=rot([0, 0, 0]))],
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(1.2667, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
})

# ---------------------------------------------------------------- reload_tactical
# 膛内有弹的换匣：旧匣落出 -> 新匣推入到位 -> 枪机轻拉一次确认闭锁。
MAG_OUT = pos([0, -5.60, 0.42])
CLIPS["reload_tactical"] = dict(length=2.6, loop=False, bones={
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(0.10, position=pos([0, -0.10, 0]), rotation=rot([-1.5, 0, 0])),
                 b(0.48, position=MAG_OUT, rotation=rot([-6, 0, 0])),
                 b(0.92, position=MAG_OUT, rotation=rot([-5, 0, 0])),
                 b(1.30, position=pos([0, 0.30, 0.04]), rotation=rot([2, 0, 0])),
                 b(1.42, position=pos([0, -0.06, 0]), rotation=rot([0, 0, 0])),
                 b(1.55, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(2.6, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "bolt": [b(0.0, position=pos([0, 0, 0])), b(1.50, position=pos([0, 0, 0])),
             b(1.72, position=pos([0, 0, 1.05])), b(1.86, position=pos([0, 0, 1.05])),
             b(1.98, position=pos([0, 0, 0.12])), b(2.10, position=pos([0, 0, 0])),
             b(2.6, position=pos([0, 0, 0]))],
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.42, position=pos([0.1, -0.12, 0.16]), rotation=rot([2.2, -1.0, 0])),
             b(1.20, position=pos([0.05, -0.06, 0.10]), rotation=rot([1.4, -0.6, 0])),
             b(1.80, position=pos([-0.02, 0.03, -0.04]), rotation=rot([-0.8, 0, 0])),
             b(2.35, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(2.6, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])), b(0.44, rotation=rot([-0.8, 0, 0])),
             b(1.28, rotation=rot([0.9, 0, 0])), b(1.80, rotation=rot([-0.6, 0, 0])),
             b(2.40, rotation=rot([0, 0, 0])), b(2.6, rotation=rot([0, 0, 0]))],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(2.6, rotation=rot([0, 0, 0]))],
    "casing": [b(0.0, scale=[0, 0, 0]), b(2.6, scale=[0, 0, 0])],
    "mag_r1": [b(0.0, scale=[1, 1, 1]), b(2.6, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[1, 1, 1]), b(2.6, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[1, 1, 1]), b(2.6, scale=[1, 1, 1])],
})

# ---------------------------------------------------------------- reload_empty
# 空仓换匣：枪机已经挂在后方的位置，旧匣（空）落出 -> 新匣推入 -> 三层弹带逐层亮起 -> 枪机复进上膛。
CLIPS["reload_empty"] = dict(length=3.3, loop=False, bones={
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(0.12, position=pos([0, -0.10, 0]), rotation=rot([-1.8, 0, 0])),
                 b(0.52, position=MAG_OUT, rotation=rot([-7, 0, 0])),
                 b(1.05, position=MAG_OUT, rotation=rot([-6, 0, 0])),
                 b(1.48, position=pos([0, 0.34, 0.04]), rotation=rot([2.2, 0, 0])),
                 b(1.62, position=pos([0, -0.06, 0]), rotation=rot([0, 0, 0])),
                 b(1.76, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(3.3, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "mag_r1": [b(0.0, scale=[0, 0, 0]), b(1.76, scale=[0, 0, 0]),
               b(1.88, scale=[1, 1, 1]), b(3.3, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[0, 0, 0]), b(1.82, scale=[0, 0, 0]),
               b(1.94, scale=[1, 1, 1]), b(3.3, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[0, 0, 0]), b(1.88, scale=[0, 0, 0]),
               b(2.00, scale=[1, 1, 1]), b(3.3, scale=[1, 1, 1])],
    "bolt": [b(0.0, position=pos([0, 0, 0])), b(2.14, position=pos([0, 0, 0])),
             b(2.36, position=pos([0, 0, 1.05])), b(2.50, position=pos([0, 0, 1.05])),
             b(2.62, position=pos([0, 0, 0.12])), b(2.76, position=pos([0, 0, 0])),
             b(3.3, position=pos([0, 0, 0]))],
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.45, position=pos([0.1, -0.13, 0.17]), rotation=rot([2.4, -1.1, 0])),
             b(1.40, position=pos([0.05, -0.06, 0.10]), rotation=rot([1.5, -0.6, 0])),
             b(2.45, position=pos([-0.02, 0.03, -0.04]), rotation=rot([-0.9, 0, 0])),
             b(3.05, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(3.3, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])), b(0.48, rotation=rot([-0.9, 0, 0])),
             b(1.45, rotation=rot([1.0, 0, 0])), b(2.45, rotation=rot([-0.7, 0, 0])),
             b(3.05, rotation=rot([0, 0, 0])), b(3.3, rotation=rot([0, 0, 0]))],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(3.3, rotation=rot([0, 0, 0]))],
    "casing": [b(0.0, scale=[0, 0, 0]), b(3.3, scale=[0, 0, 0])],
})

# ---------------------------------------------------------------- draw (拔枪)
# 与 m1_garand 的 draw 同形：枪从画面下方抬起（move 起始 -2.2u / 前倾 14°），
# 过冲一点再回落；同时手把枪机从后方释放闭锁（上膛）。Uzi 是自由枪机，
# 起始姿态就挂在 0.55u —— 一手抬起、一手放机，是这个叙事的关键。
DRAW_START = pos([0, -2.20, 0.90])
CLIPS["draw"] = dict(length=1.0, loop=False, bones={
    "move": [b(0.0, position=DRAW_START, rotation=rot([14, -3, 4])),
             b(0.3333, position=pos([0, -0.35, 0.12]), rotation=rot([3, -1, 1])),
             b(0.5417, position=pos([0, 0.06, -0.04]), rotation=rot([-1.2, 0.4, 0])),
             b(0.9167, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(1.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([-2.4, 0, 0])), b(0.5, rotation=rot([0.6, 0, 0])),
             b(0.9167, rotation=rot([0, 0, 0])), b(1.0, rotation=rot([0, 0, 0]))],
    "bolt": [b(0.0, position=pos([0, 0, 0.55])),
             b(0.20, position=pos([0, 0, 1.05])),
             b(0.46, position=pos([0, 0, 1.05])),
             b(0.575, position=pos([0, 0, 0.10])),
             b(0.66, position=pos([0, 0, 0])),
             b(1.0, position=pos([0, 0, 0]))],
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(1.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(1.0, rotation=rot([0, 0, 0]))],
    "casing": [b(0.0, scale=[0, 0, 0]), b(1.0, scale=[0, 0, 0])],
    "mag_r1": [b(0.0, scale=[1, 1, 1]), b(1.0, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[1, 1, 1]), b(1.0, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[1, 1, 1]), b(1.0, scale=[1, 1, 1])],
})

# ---------------------------------------------------------------- shoot (开火)
# 单发后座：枪机 0.0833s 冲到 1.05u 行程顶点、0.2083s 复进闭锁（整个循环 0.21s，
# 比手动拉栓快一倍 —— 自由枪机的味道就在这里）；同时抛壳、枪身后座上跳后指数衰减。
# 时序抄 m1_garand.shoot（0.6s），行程换成 Uzi 自己的 1.05u。
CLIPS["shoot"] = dict(length=0.6, loop=False, bones={
    "bolt": [b(0.0, position=pos([0, 0, 0])),
             b(0.0417, position=pos([0, 0, 0.92])),
             b(0.0833, position=pos([0, 0, 1.05])),
             b(0.125, position=pos([0, 0, 0.22])),
             b(0.2083, position=pos([0, 0, 0])),
             b(0.6, position=pos([0, 0, 0]))],
    "casing": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0]),
               b(0.05, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0]),
               b(0.09, position=pos([-0.1, 0.05, 0.05]), rotation=rot([30, 0, -60]), scale=[1, 1, 1]),
               b(0.13, position=pos([-0.3, 0.35, 0.10]), rotation=rot([70, 0, -150]), scale=[1, 1, 1]),
               b(0.22, position=pos([-0.95, 1.15, 0.30]), rotation=rot([190, 0, -380]), scale=[1, 1, 1]),
               b(0.34, position=pos([-1.75, 2.05, 0.55]), rotation=rot([300, 0, -620]), scale=[1, 1, 1]),
               b(0.50, position=pos([-2.45, 2.85, 0.80]), rotation=rot([380, 0, -760]), scale=[0, 0, 0]),
               b(0.6, position=pos([-2.45, 2.85, 0.80]), rotation=rot([380, 0, -760]), scale=[0, 0, 0])],
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.0417, position=pos([0, 0.28, 0.62]), rotation=rot([-2.6, -0.3, 0])),
             b(0.125, position=pos([0, 0.24, 0.44]), rotation=rot([-1.9, 0.2, 0])),
             b(0.2083, position=pos([0, 0.12, 0.20]), rotation=rot([-0.7, -0.1, 0])),
             b(0.3333, position=pos([0, -0.04, -0.06]), rotation=rot([0.25, 0, 0])),
             b(0.5, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.6, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])), b(0.0417, rotation=rot([1.1, 0, 0])),
             b(0.4167, rotation=rot([0, 0, 0])), b(0.6, rotation=rot([0, 0, 0]))],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])), b(0.0417, rotation=rot([-5, 0, 0])),
                      b(0.10, rotation=rot([0, 0, 0])), b(0.6, rotation=rot([0, 0, 0]))],
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(0.6, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "mag_r1": [b(0.0, scale=[1, 1, 1]), b(0.6, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[1, 1, 1]), b(0.6, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[1, 1, 1]), b(0.6, scale=[1, 1, 1])],
})

# ---------------------------------------------------------------- 连发（shoot_auto）
# 逐发触发、2 帧闭合的枪机循环。为什么不能复用 shoot：
#   shoot 的枪机循环是 0.2083s（4.17 tick），而连发的锁是 2 tick —— 每 2 tick 重播一次
#   shoot，枪机在 0.2083s 前就被打断，永远合不上，看起来像卡在后位抽搐。
# 所以连发另给一条 0.0833s（= 2/24s）的紧凑循环：t=0 闭锁 → t=0.0417 后座到底
# → t=0.0833 复进到位，正好在下一次触发落下的瞬间闭合，读起来是连续循环。
#
# 弹壳不在这里出现：2 帧太短，弹壳飞不出去就重置了，挂在枪上比没有更糟。
# 抛壳改由 Java 侧在抛壳窗位置撒粒子（UziItem.fireBullet 的 `port`），10 发/秒读作一道弹壳流。
# 这条 clip 的关键帧是 **linear**（见 SETINTERP），枪机是硬止动，不许过冲。
CLIPS["shoot_auto"] = dict(length=0.0833, loop=False, bones={
    "bolt": [b(0.0, position=pos([0, 0, 0])),
             b(0.0417, position=pos([0, 0, 1.05])),
             b(0.0833, position=pos([0, 0, 0]))],
    "casing": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0]),
               b(0.0833, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]), scale=[0, 0, 0])],
    "move": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
             b(0.0417, position=pos([0, 0.13, 0.28]), rotation=rot([-1.3, 0, 0])),
             b(0.0833, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "body": [b(0.0, rotation=rot([0, 0, 0])),
             b(0.0417, rotation=rot([0.9, 0, 0])),
             b(0.0833, rotation=rot([0, 0, 0]))],
    "trigger_group": [b(0.0, rotation=rot([0, 0, 0])),
                      b(0.0417, rotation=rot([-5, 0, 0])),
                      b(0.0833, rotation=rot([0, 0, 0]))],
    "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0])),
                 b(0.0833, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
    "mag_r1": [b(0.0, scale=[1, 1, 1]), b(0.0833, scale=[1, 1, 1])],
    "mag_r2": [b(0.0, scale=[1, 1, 1]), b(0.0833, scale=[1, 1, 1])],
    "mag_r3": [b(0.0, scale=[1, 1, 1]), b(0.0833, scale=[1, 1, 1])],
})

# ---------------------------------------------------------------- ADS (肩射过渡)
# 照抄 crossbow：0.18s / 步长 1/24s / 共 5 键，move 上抬 0.42u 同时前推 0.26u，
# body 抬头 3.6°。ADS_down 是 ADS_up 关键帧的严格逆序 —— 两条曲线必须互为倒放，
# 否则收枪会有一次跳变。不参与过渡的骨骼一律钉常量，防止混合时被别的 clip 拖走。
ADS_T = [0.0, 0.0417, 0.0833, 0.125, 0.1667]
ADS_LEN = 0.18
_ADS_UP_Y = [0.0, 0.105, 0.210, 0.315, 0.420]
_ADS_UP_Z = [0.0, -0.065, -0.130, -0.195, -0.260]
_ADS_PITCH = [0.0, 0.9, 1.8, 2.7, 3.6]

def _ads_holds():
    return {
        "bolt": [b(0.0, position=pos([0, 0, 0]))],
        "magazine": [b(0.0, position=pos([0, 0, 0]), rotation=rot([0, 0, 0]))],
        "trigger_group": [b(0.0, rotation=rot([0, 0, 0]))],
        "casing": [b(0.0, scale=[0, 0, 0])],
        "mag_r1": [b(0.0, scale=[1, 1, 1])],
        "mag_r2": [b(0.0, scale=[1, 1, 1])],
        "mag_r3": [b(0.0, scale=[1, 1, 1])],
    }


def _ads(ys, zs, pitch):
    d = _ads_holds()
    d["move"] = [b(t, position=pos([0, y, z])) for t, y, z in zip(ADS_T, ys, zs)]
    d["body"] = [b(t, rotation=rot([p, 0, 0])) for t, p in zip(ADS_T, pitch)]
    return d


CLIPS["ADS_up"] = dict(length=ADS_LEN, loop=False,
                       bones=_ads(_ADS_UP_Y, _ADS_UP_Z, _ADS_PITCH))
CLIPS["ADS_down"] = dict(length=ADS_LEN, loop=False,
                         bones=_ads(list(reversed(_ADS_UP_Y)),
                                    list(reversed(_ADS_UP_Z)),
                                    list(reversed(_ADS_PITCH))))

# 动画里绝不允许出现的骨骼（TaCZ：additional_magazine 必须为空且不参与动画）
FORBIDDEN = {"additional_magazine"}


def main():
    dry = "--dry" in sys.argv
    # 校验 clip 数据本身
    problems = []
    for name, clip in CLIPS.items():
        for bone, keys in clip["bones"].items():
            if bone in FORBIDDEN:
                problems.append("%s: 动了禁区骨骼 %s" % (name, bone))
            if not keys:
                problems.append("%s: %s 没有关键帧" % (name, bone))
            if max(k["time"] for k in keys) > clip["length"] + 1e-9:
                problems.append("%s: %s 的关键帧超出 clip 长度" % (name, bone))
            if min(k["time"] for k in keys) > 1e-9:
                problems.append("%s: %s 缺少 t=0 的起始关键帧" % (name, bone))
    # 不使用弹壳的 clip 必须全程 scale 0，否则残留弹壳会挂在枪上。
    # 只有会抛壳的两个（bolt 手动拉栓 / shoot 开火）允许弹壳出现。
    for name in ("static_idle", "draw", "reload_tactical", "reload_empty",
                 "ADS_up", "ADS_down", "shoot_auto"):
        for k in CLIPS[name]["bones"]["casing"]:
            if k.get("scale") != [0, 0, 0]:
                problems.append("%s: casing 必须全程 scale 0" % name)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        return 1

    for name, clip in CLIPS.items():
        nb = len(clip["bones"])
        nk = sum(len(v) for v in clip["bones"].values())
        print("%-18s len %-7s %-9s 骨骼 %2d  关键帧 %3d" %
              (name, clip["length"], "loop" if clip["loop"] else "once", nb, nk))
    if dry:
        return 0

    sid = bb.handshake()

    r = bb.text_of(bb.call(sid, "risky_eval", {"code": RESET}))
    print("reset   ->", r[:200])

    for name, clip in CLIPS.items():
        res = bb.text_of(bb.call(sid, "create_animation", {
            "name": name, "loop": clip["loop"],
            "animation_length": clip["length"], "bones": clip["bones"]}))
        print("create  %-18s -> %s" % (name, res[:160]))

    r = bb.text_of(bb.call(sid, "risky_eval", {"code": PREFIX_FIX}))
    print("prefix  ->", r[:200])

    r = bb.text_of(bb.call(sid, "risky_eval", {"code": SETINTERP}))
    print("interp  ->", r[:300])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    res = bb.text_of(bb.call(sid, "geckolib_export_animations",
                             {"mode": "compile", "path": OUT.replace("\\", "/"),
                              "max_content_length": 0}))
    print("export  ->", res[:300])
    if not os.path.isfile(OUT):
        print("FAIL  动画文件没落地：" + OUT)
        return 1
    d = json.load(open(OUT, encoding="utf-8"))
    print("\n落地 %s  (%d bytes, format_version %s)" % (OUT, os.path.getsize(OUT), d.get("format_version")))
    for k, v in d["animations"].items():
        print("  %-18s len %-7s loop %-5s bones %d" %
              (k, v.get("animation_length"), v.get("loop"), len(v.get("bones", {}))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
