# -*- coding: utf-8 -*-
"""win94 动画 v3 —— 杠杆退壳上弹（bolt）+ 侧装填门逐发压弹换弹，全部通过 MCP 写入。

机构依据（Winchester Model 1894 杠杆枪）：
  杠杆循环：lever 绕机匣底部转轴下扳（真枪约 70–90°，取 72°）→ 闭锁块（bolt）后移抽壳
  → 抛壳钩把空壳甩出（右上方翻滚）→ 击锤被压回待击 → 杠杆回位时 carrier 把弹仓里的
  下一发抬起送入弹膛 → 闭锁。
  换弹：**管状弹仓 + 机匣右侧装填门**（不是换弹匣）。左手逐发把子弹压进装填门，
  每发都被弹仓弹簧顶住；空仓补满 5 发后还要扳一次杠杆上膛，这也是"空仓换弹更长"的原因。

时长（与 Java 侧 tick 契约：ceil(length × 20)）：
  static_idle 2.0s(40)  draw 0.8s(16)  shoot 0.6s(12)  bolt 1.1s(22)
  reload_tactical 2.2s(44)  reload_empty 4.4s(88)  inspect 2.6s(52)

用法：
  python tools/win94_anim3.py            # 生成并提交（先删旧 clip）
  python tools/win94_anim3.py --dry      # 只打印时间表，不动 Blockbench
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp  # noqa: E402

OUT = ROOT / 'build' / 'bbmcp'

LEVER_OPEN = 38.0     # 杠杆全开角（度，绕 X 轴**正向** = 环向前下方摆）
                      # 真枪 lever 转轴在机匣前下方、环在后，行程约 60–80 mm；
                      # 38° × 力臂 1.7 u 正好给出 ~58 mm 的环位移，与真枪一致
                      # （早先设 60° 是照"环离转轴很近"的错结构配的，会摆过头）
BOLT_BACK = 0.62      # 闭锁块后退行程（u）＝真枪约 1.5 in
HAMMER_COCK = 32.0    # 击锤待击角（度，绕 X 轴正向 = 锤顶向后倒）
LIFT = 0.13           # carrier 抬起送弹的量（u）
CARRY_DROP = 0.09     # carrier 下摆接弹的量（u）—— 开栓时它是先向下让弹仓出弹的
GATE_OPEN = 22.0      # 装填门被子弹顶开的角度（度，绕 Y 轴向外）
DOOR_X = 0.30         # 装填门在机匣右壁的 x（弹从这里压进去）

# ⚠ 符号约定（对着照片级参考图定的）：
#   模型 +X = 射手右侧、−Z = 枪口。真枪机匣下方**只有一个环** —— lever 的长杆从机匣
#   前下方的转轴向后延伸，末端弯成这个环，环**兼作扳机护圈**、包住扳机。
#   环在转轴后方（Δz = +1.70）⇒ 杠杆绕 X 轴**正向**转，环才会向前下方打开（真枪操作）。
#   trigger 的刀片在扳机轴下方，扣扳机是刀片下端往**后**（+Z）摆 ⇒ 仍是负角度。
TRIGGER_PRESS = -16.0


def kf(bone, channel, t, v, interp='catmullrom'):
    return {'bone': bone, 'channel': channel, 'time': round(t, 3),
            'value': [round(x, 4) for x in v], 'interpolation': interp}


# ---------------------------------------------------------------- 1. static_idle
IDLE = [
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 1.0, (0, -0.014, 0)),
    kf('move', 'position', 2.0, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0.7, 0, 0)),
    kf('body', 'rotation', 1.0, (0, 0.35, 0.4)),
    kf('body', 'rotation', 2.0, (0.7, 0, 0)),
]

# ---------------------------------------------------------------- 2. draw
DRAW = [
    kf('body', 'rotation', 0.0, (25, -18, 0)),
    kf('body', 'rotation', 0.5, (-4, 4, 0)),
    kf('body', 'rotation', 0.8, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, -0.55, 0.25)),
    kf('move', 'position', 0.5, (0, 0.05, -0.03)),
    kf('move', 'position', 0.8, (0, 0, 0)),
]

# ---------------------------------------------------------------- 3. shoot
SHOOT = [
    kf('hammer', 'rotation', 0.0, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', 0.07, (0, 0, 0), 'linear'),
    kf('trigger', 'rotation', 0.0, (0, 0, 0)),
    kf('trigger', 'rotation', 0.05, (TRIGGER_PRESS, 0, 0)),
    kf('trigger', 'rotation', 0.22, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.06, (8.5, 0, 0)),
    kf('body', 'rotation', 0.26, (-2.5, 0, 0)),
    kf('body', 'rotation', 0.6, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.06, (0, 0.03, 0.17)),
    kf('move', 'position', 0.26, (0, -0.01, -0.03)),
    kf('move', 'position', 0.6, (0, 0, 0)),
]

# ---------------------------------------------------------------- 4. bolt（杠杆退壳上弹）
BOLT = [
    # 杠杆：下扳到底 → 停顿（退壳窗口）→ 回位
    kf('lever', 'rotation', 0.0, (0, 0, 0)),
    kf('lever', 'rotation', 0.28, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 0.46, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 0.80, (0, 0, 0)),
    kf('lever', 'rotation', 1.1, (0, 0, 0)),
    # 闭锁块：解锁微退 → 全退抽壳 → 停顿（此时升降器在下位接弹）→ 复进闭锁
    kf('bolt', 'position', 0.0, (0, 0, 0)),
    kf('bolt', 'position', 0.10, (0, 0, 0.06)),
    kf('bolt', 'position', 0.44, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 0.55, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 0.90, (0, 0, 0)),
    kf('bolt', 'position', 1.1, (0, 0, 0)),
    # 击锤被杠杆压回待击位
    kf('hammer', 'rotation', 0.04, (0, 0, 0)),
    kf('hammer', 'rotation', 0.40, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', 0.62, (HAMMER_COCK, 0, 0), 'linear'),   # 停在待击（半待击过渡）
    kf('hammer', 'rotation', 0.74, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', 1.1, (HAMMER_COCK, 0, 0)),
    # 升降器（carrier）：真枪的顺序是 **bolt 后退时下摆接弹**（弹仓弹簧把下一发推上来），
    # bolt 复进之前再**抬到膛口**高度，把子弹交给闭锁块推入膛。最早写成"一开栓就抬起来"，
    # 那是反的 —— 抬早了子弹根本还没从弹仓出来。
    kf('carrier', 'position', 0.10, (0, 0, 0)),
    kf('carrier', 'position', 0.34, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 0.52, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 0.70, (0, LIFT, 0)),
    kf('carrier', 'position', 0.86, (0, LIFT, 0)),
    kf('carrier', 'position', 1.05, (0, 0, 0)),
    kf('carrier', 'position', 1.1, (0, 0, 0)),
    # 新弹：随升降器下摆（从弹仓口滑到位）→ 随它抬起 → 被闭锁块推入膛
    kf('cartridge', 'position', 0.30, (0, 0, 0)),
    kf('cartridge', 'position', 0.46, (0, -CARRY_DROP + 0.01, 0.08)),
    kf('cartridge', 'position', 0.72, (0, LIFT, 0.02)),
    kf('cartridge', 'position', 0.88, (0, 0.02, -0.30)),
    kf('cartridge', 'position', 1.00, (0, 0, -0.34)),
    kf('cartridge', 'position', 1.1, (0, 0, -0.34)),      # 上膛后留在膛内（不再弹回原点）
    kf('cartridge', 'scale', 0.30, (1, 1, 1)),
    kf('cartridge', 'scale', 0.92, (1, 1, 1)),
    kf('cartridge', 'scale', 0.98, (0.05, 0.05, 0.05), 'step'),      # 入膛后隐去
    kf('cartridge', 'scale', 1.1, (0.05, 0.05, 0.05)),
    # 空壳：随闭锁块后退 → 从抛壳口向右上翻滚飞出
    kf('spent_shell', 'position', 0.10, (0, 0, 0)),
    kf('spent_shell', 'position', 0.30, (0.06, 0.16, 0.34)),
    kf('spent_shell', 'position', 0.56, (0.46, 0.82, 0.58)),
    kf('spent_shell', 'position', 0.86, (0.92, 1.60, 0.92)),
    kf('spent_shell', 'position', 1.1, (1.20, 2.30, 1.10)),
    kf('spent_shell', 'rotation', 0.10, (0, 0, 0)),
    kf('spent_shell', 'rotation', 0.30, (150, 40, 20)),
    kf('spent_shell', 'rotation', 0.56, (300, 120, 70)),
    kf('spent_shell', 'rotation', 0.86, (480, 230, 140)),
    kf('spent_shell', 'rotation', 1.1, (600, 300, 190)),
    # 空壳全程保持 scale 1：静止时它躺在机匣内部（被壳体挡住），不必靠缩放藏 ——
    # 之前把它在 0.12 s 缩到 0.05，等于连抛壳动作一起藏掉。
    kf('spent_shell', 'scale', 0.0, (1, 1, 1), 'step'),
    kf('spent_shell', 'scale', 1.1, (1, 1, 1), 'step'),
    # 枪身：杠杆操作时的下压与回位
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.34, (2.6, 0, 0)),
    kf('body', 'rotation', 0.82, (0, 0, 0)),
    kf('body', 'rotation', 1.1, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.32, (0, -0.018, 0.03)),
    kf('move', 'position', 0.86, (0, 0, 0)),
    kf('move', 'position', 1.1, (0, 0, 0)),
]


def load_rounds(t_start, count, step, tilt, vanish=True):
    """逐发从机匣右侧装填门压入：门外 → 对准门口 → 压进去 → 缩小消失（进弹仓）。

    ⚠ 两条硬约束（docs/wiki/05 步骤 2 + 真枪机构）：
      1. **不许有 z 分量**：装填类小件若前后滑动，观感会变成"沿枪身横滑"；
         这里 z 固定，弹只沿 ±X 侧向进出装填门。
      2. 落点必须是**装填门所在的那一段机匣**（loading_gate 在 z≈+0.18），
         不是弹膛口。cartridge 方块静态在 z≈−1.14，所以 Z_OFF = +1.32。
    """
    Z_OFF = 1.58
    out = []
    for i in range(count):
        t0 = t_start + i * step
        out += [
            # 弹簧钢片做的装填门被子弹顶开，弹进仓后弹回
            kf('gate', 'rotation', t0, (0, 0, 0)),
            kf('gate', 'rotation', t0 + step * 0.40, (0, GATE_OPEN, 0)),
            kf('gate', 'rotation', t0 + step * 0.82, (0, GATE_OPEN, 0)),
            kf('gate', 'rotation', t0 + step * 0.94, (0, 0, 0), 'step'),
            kf('cartridge', 'position', t0, (0.95, -0.10, Z_OFF)),
            kf('cartridge', 'position', t0 + step * 0.30, (0.50, -0.11, Z_OFF)),
            kf('cartridge', 'position', t0 + step * 0.58, (0.24, -0.12, Z_OFF)),
            kf('cartridge', 'position', t0 + step * 0.80, (0.02, -0.13, Z_OFF)),
            # 终点必须用 step：否则下一发的起点会被 catmullrom 平滑连上，
            # 看上去就是"同一发弹沿着枪身来回滑"，而不是"又压进去一发新的"。
            kf('cartridge', 'position', t0 + step * 0.92, (0.0, -0.13, Z_OFF), 'step'),
        ]
        if vanish:
            out += [
                kf('cartridge', 'scale', t0, (1, 1, 1), 'step'),
                kf('cartridge', 'scale', t0 + step * 0.90, (1, 1, 1), 'step'),
                kf('cartridge', 'scale', t0 + step * 0.95, (0.04, 0.04, 0.04), 'step'),
                kf('cartridge', 'scale', t0 + step * 1.0, (0.04, 0.04, 0.04), 'step'),
            ]
    return out


# ---------------------------------------------------------------- 5. reload_tactical（补弹 3 发，2.2 s）
TAC_LEN = 2.2
TAC = [
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.35, (-4, 6, 22)),
    kf('body', 'rotation', 1.85, (-4, 6, 22)),
    kf('body', 'rotation', TAC_LEN, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.35, (0.02, -0.05, 0.06)),
    kf('move', 'position', 1.85, (0.02, -0.05, 0.06)),
    kf('move', 'position', TAC_LEN, (0, 0, 0)),
] + load_rounds(0.42, 3, 0.54, 22)

# ---------------------------------------------------------------- 6. reload_empty（空仓 5 发 + 收尾上膛，4.4 s）
EMP_LEN = 4.4
EMP = [
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.45, (-5, 8, 30)),
    kf('body', 'rotation', 3.30, (-5, 8, 30)),
    kf('body', 'rotation', 3.75, (-2, 3, 12)),
    kf('body', 'rotation', EMP_LEN, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.45, (0.03, -0.06, 0.07)),
    kf('move', 'position', 3.30, (0.03, -0.06, 0.07)),
    kf('move', 'position', 3.75, (0.01, -0.02, 0.02)),
    kf('move', 'position', EMP_LEN, (0, 0, 0)),
] + load_rounds(0.50, 5, 0.55, 30)
# 收尾：扳一次杠杆把第一发送进膛（空仓补满后必须上膛）
EMP += [
    kf('lever', 'rotation', 3.30, (0, 0, 0)),
    kf('lever', 'rotation', 3.52, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 3.66, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 3.95, (0, 0, 0)),
    kf('lever', 'rotation', EMP_LEN, (0, 0, 0)),
    kf('bolt', 'position', 3.34, (0, 0, 0)),
    kf('bolt', 'position', 3.58, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 3.68, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 4.00, (0, 0, 0)),
    kf('bolt', 'position', EMP_LEN, (0, 0, 0)),
    # 升降器同 bolt 片段：先下摆接弹，再抬起把子弹交到膛口
    kf('carrier', 'position', 3.34, (0, 0, 0)),
    kf('carrier', 'position', 3.50, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 3.66, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 3.82, (0, LIFT, 0)),
    kf('carrier', 'position', 3.98, (0, LIFT, 0)),
    kf('carrier', 'position', 4.20, (0, 0, 0)),
    kf('carrier', 'position', EMP_LEN, (0, 0, 0)),
    kf('hammer', 'rotation', 3.28, (0, 0, 0)),
    kf('hammer', 'rotation', 3.66, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', EMP_LEN, (HAMMER_COCK, 0, 0)),
    # 最后一发被送上膛（复用 cartridge 骨骼）
    kf('cartridge', 'position', 3.44, (0, 0, 0)),
    kf('cartridge', 'position', 3.58, (0, -CARRY_DROP + 0.01, 0.08)),
    kf('cartridge', 'position', 3.84, (0, LIFT, 0.02)),
    kf('cartridge', 'position', 4.00, (0, 0.02, -0.30)),
    kf('cartridge', 'position', 4.12, (0, 0, -0.34)),
    kf('cartridge', 'position', EMP_LEN, (0, 0, -0.34)),
    kf('cartridge', 'scale', 3.44, (1, 1, 1), 'step'),
    kf('cartridge', 'scale', 4.12, (1, 1, 1), 'step'),
    kf('cartridge', 'scale', 4.18, (0.05, 0.05, 0.05), 'step'),
    kf('cartridge', 'scale', EMP_LEN, (0.05, 0.05, 0.05), 'step'),
]

# ---------------------------------------------------------------- 7. inspect
INS_LEN = 2.6
INSPECT = [
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.55, (0.1, 0.15, 0.25)),
    kf('move', 'position', 1.25, (0, 0.2, 0.3)),
    kf('move', 'position', 1.95, (0.1, 0.15, 0.25)),
    kf('move', 'position', INS_LEN, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.55, (8, 25, 22)),
    kf('body', 'rotation', 1.25, (8, -25, -22)),
    kf('body', 'rotation', 1.95, (8, 25, 22)),
    kf('body', 'rotation', INS_LEN, (0, 0, 0)),
    kf('lever', 'rotation', 1.62, (0, 0, 0)),
    kf('lever', 'rotation', 1.80, (18, 0, 0)),
    kf('lever', 'rotation', 2.00, (0, 0, 0)),
]

ANIMS = [
    ('static_idle', 'loop', 2.0, IDLE, True),
    ('draw', 'once', 0.8, DRAW, False),
    ('shoot', 'once', 0.6, SHOOT, False),
    ('bolt', 'once', 1.1, BOLT, False),
    ('reload_tactical', 'once', TAC_LEN, TAC, False),
    ('reload_empty', 'once', EMP_LEN, EMP, False),
    ('inspect', 'once', INS_LEN, INSPECT, False),
]


def main():
    dry = '--dry' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    print(f'{"clip":18s} {"loop":5s} {"len":>5s} {"ticks":>5s} {"kf":>4s}  bones')
    for name, loop, length, kfs, close in ANIMS:
        bones = sorted({k['bone'] for k in kfs})
        print(f'{name:18s} {loop:5s} {length:5.1f} {int(length * 20 + 0.999):5d} {len(kfs):4d}  {",".join(bones)}')

    if dry:
        return 0

    # 先删同名旧 clip，避免堆叠
    for name, *_ in ANIMS:
        bbmcp.call('remove_animation', {'animation': name}, timeout=60)

    failures = 0
    for name, loop, length, kfs, close in ANIMS:
        r1 = bbmcp.call('create_animation', {'name': name, 'loop': loop, 'length': length}, timeout=120)
        if not r1.get('ok'):
            print(f'[{name}] create FAIL :: {json.dumps(r1, ensure_ascii=False)[:300]}')
            failures += 1
            continue
        payload = {'animation': name, 'keyframes': kfs, 'length': length, 'close_loop': close}
        (OUT / f'win94_anim_{name}.json').write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
        r2 = bbmcp.call('add_keyframes', payload, timeout=300)
        if not r2.get('ok'):
            print(f'[{name}] keyframes FAIL :: {json.dumps(r2, ensure_ascii=False)[:400]}')
            failures += 1
            continue
        res = r2.get('result') or {}
        print(f'[{name}] OK created={res.get("created")} loop_kf={res.get("loop_keyframes_added")} '
              f'len={length}s ticks={int(length * 20 + 0.999)}')

    print('failures =', failures)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
