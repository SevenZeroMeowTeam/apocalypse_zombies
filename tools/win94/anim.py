# -*- coding: utf-8 -*-
"""win94 动画 —— 7 条 clip，按**真枪机构相位**排关键帧，经 MCP 写入 Blockbench。

时机依据（Winchester M1894 杠杆循环；见 art/win94/README.md 的文献表）
--------------------------------------------------------------------------
把 lever 的全行程记作 bolt 0→100%→0：

| bolt 行程 | 动作 |
|---|---|
| 0–10%   | lever 下扳，闭锁凸榫脱离机匣（**开锁**） |
| 10–35%  | bolt 尾部压下击锤 → **待击**（cock-on-opening，发生在开栓段） |
| 35–65%  | 抽壳钩带壳后退，弹壳脱离弹膛 |
| 60–80%  | 壳尾撞机匣侧 ejector，空壳**向右上方**抛出 |
| 55–75%  | **carrier 这时才下摆**（bolt 行程后半段）——弹仓弹簧把下一发顶到 carrier 顶面 |
| 75–100% | carrier 全下位接弹；carrier 前端兼作 cartridge stop 挡住后面的弹 |
| 回程 0–25%  | lever 凸轮**先抬起 carrier**，把子弹送到膛口高度（抬升略领先 bolt 面） |
| 25–85%  | **bolt 面推弹入膛** |
| 85–100% | bolt 到位、凸榫闭锁、击锤被 sear 扣住 |

⚠ 最容易写错的一条：**carrier 是"先下后上"**。一开栓就抬起 = 把还没出弹仓的子弹抬到膛口，
  门禁 gate.py 会按"最低位时刻必须早于最高位时刻"卡这一条。

装弹是**管状弹仓 + 机匣右侧装填门**逐发压入（不是换弹匣）：每发的节奏与 Java 侧音效表对齐
（Win94Item.BOLT_SOUNDS / RELOAD_EMPTY_SOUNDS 的 tick 锚点）。

时长契约（Java：ceil(length × 20) ticks）：
  static_idle 2.0s(40) draw 0.8s(16) shoot 0.6s(12) bolt 1.1s(22)
  reload_tactical 2.2s(44) reload_empty 4.4s(88) inspect 2.6s(52)

用法：
  python tools/win94/anim.py --dry     # 只打印时间表
  python tools/win94/anim.py           # 写入 Blockbench
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402
import spec as S  # noqa: E402

OUT = ROOT / 'build' / 'win94'

LEVER_OPEN = S.LEVER_OPEN        # 62°：环在转轴后方 ⇒ 绕 X 轴正角度 = 环向前下方摆
BOLT_BACK = S.BOLT_BACK          # 0.98 u = 61 mm（够把 .30-30/.45-70 的壳抽出弹膛）
HAMMER_COCK = S.HAMMER_COCK
TRIGGER_PRESS = S.TRIGGER_PRESS
CARRY_DROP = S.CARRY_DROP        # carrier 下摆接弹的量
LIFT = S.LIFT                    # carrier 抬起送弹的量
GATE_OPEN = S.GATE_OPEN          # 装填门被子弹顶开的位移
CHAMBER_Z = S.CHAMBER_Z          # 子弹"在膛内"相对骨骼原点的 z 偏移
FEED_Z = S.FEED_Z                # 子弹在 carrier 上的 z 偏移
OUT_X = S.OUT_X                  # 子弹在装填门外（右侧）的 x 偏移


def kf(bone, channel, t, v, interp='catmullrom'):
    return {'bone': bone, 'channel': channel, 'time': round(t, 3),
            'value': [round(x, 4) for x in v], 'interpolation': interp}


# =============================================================== 1. static_idle
IDLE = [
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 1.0, (0, -0.014, 0)),
    kf('move', 'position', 2.0, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0.7, 0, 0)),
    kf('body', 'rotation', 1.0, (0, 0.35, 0.4)),
    kf('body', 'rotation', 2.0, (0.7, 0, 0)),
]

# =============================================================== 2. draw
DRAW = [
    kf('body', 'rotation', 0.0, (25, -18, 0)),
    kf('body', 'rotation', 0.5, (-4, 4, 0)),
    kf('body', 'rotation', 0.8, (0, 0, 0)),
    kf('move', 'position', 0.0, (0, -0.55, 0.25)),
    kf('move', 'position', 0.5, (0, 0.05, -0.03)),
    kf('move', 'position', 0.8, (0, 0, 0)),
]

# =============================================================== 3. shoot
# 击锤落下 + 后坐 + 扳机；壳在这一条里不动（退壳属于 bolt 循环，Java 也这么排）。
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

# =============================================================== 4. bolt（杠杆退壳上弹）
# 锚点（Java BOLT_SOUNDS：tick 2 / 7 / 15 / 19 = 0.10 / 0.35 / 0.75 / 0.95 s）
#   0.05–0.40 lever 下扳到底（0.40 时 bolt 全退）
#   0.35      ejector 把空壳甩向右上方
#   0.75      lever 复进（bolt 推弹）
#   0.95      lever 归位、闭锁
BOLT = [
    # lever：0.05 起下扳 → 0.40 到底 → 停 → 0.95 归位
    kf('lever', 'rotation', 0.00, (0, 0, 0)),
    kf('lever', 'rotation', 0.05, (0, 0, 0)),
    kf('lever', 'rotation', 0.40, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 0.50, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 0.95, (0, 0, 0)),
    kf('lever', 'rotation', 1.10, (0, 0, 0)),
    # bolt：先解锁微退 → 0.40 全退（0.98 u）→ 停 → 0.92 到位
    kf('bolt', 'position', 0.00, (0, 0, 0)),
    kf('bolt', 'position', 0.04, (0, 0, 0.06)),
    kf('bolt', 'position', 0.40, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 0.52, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 0.92, (0, 0, 0)),
    kf('bolt', 'position', 1.10, (0, 0, 0)),
    # 击锤：开栓段被 bolt 尾部压下 → 待击（cock on opening），之后一直停在待击
    kf('hammer', 'rotation', 0.06, (0, 0, 0)),
    kf('hammer', 'rotation', 0.34, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', 1.10, (HAMMER_COCK, 0, 0)),
    # carrier：**bolt 行程后半段**才下摆接弹（0.30→0.46），bolt 复进之前抬起送弹（0.66）
    kf('carrier', 'position', 0.00, (0, 0, 0)),
    kf('carrier', 'position', 0.30, (0, 0, 0)),
    kf('carrier', 'position', 0.46, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 0.58, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 0.68, (0, LIFT, 0)),
    kf('carrier', 'position', 0.80, (0, LIFT, 0)),
    kf('carrier', 'position', 0.95, (0, 0, 0)),
    kf('carrier', 'position', 1.10, (0, 0, 0)),
    # 新弹：膛内那发（已打掉）在 0.28 用 step 换成"从弹仓上来的一发"，随 carrier 抬到膛口，
    # 再由闭锁块面推入膛 —— 这就是用户强调的进弹顺序。
    kf('cartridge', 'position', 0.00, (0, 0, CHAMBER_Z)),
    kf('cartridge', 'position', 0.26, (0, 0, CHAMBER_Z)),
    kf('cartridge', 'position', 0.30, (0, -CARRY_DROP, FEED_Z), 'step'),
    kf('cartridge', 'position', 0.48, (0, -CARRY_DROP, FEED_Z)),
    kf('cartridge', 'position', 0.68, (0, LIFT, FEED_Z - 0.06)),
    kf('cartridge', 'position', 0.74, (0, LIFT, FEED_Z - 0.16), 'linear'),
    kf('cartridge', 'position', 0.88, (0, 0.02, CHAMBER_Z + 0.35)),
    kf('cartridge', 'position', 0.94, (0, 0, CHAMBER_Z)),
    kf('cartridge', 'position', 1.10, (0, 0, CHAMBER_Z)),
    # 空壳：随 bolt 后退被抽出 → 0.35 撞 ejector → 向右上方翻滚飞出
    kf('spent_shell', 'position', 0.00, (0, 0, 0)),
    kf('spent_shell', 'position', 0.10, (0, 0, 0.10)),
    kf('spent_shell', 'position', 0.35, (0.02, 0.02, BOLT_BACK * 0.92)),
    kf('spent_shell', 'position', 0.45, (0.20, 0.24, 0.86)),
    kf('spent_shell', 'position', 0.62, (0.62, 0.86, 0.62)),
    kf('spent_shell', 'position', 0.80, (1.20, 1.70, 0.30)),
    kf('spent_shell', 'position', 1.10, (2.10, 2.90, -0.10)),
    kf('spent_shell', 'rotation', 0.35, (0, 0, 0)),
    kf('spent_shell', 'rotation', 0.62, (140, 60, 90)),
    kf('spent_shell', 'rotation', 1.10, (320, 150, 200)),
    kf('spent_shell', 'scale', 0.00, (1, 1, 1)),
    kf('spent_shell', 'scale', 1.10, (1, 1, 1)),
    # 收尾一点自然回弹
    kf('body', 'rotation', 0.00, (0, 0, 0)),
    kf('body', 'rotation', 0.42, (-1.6, 0, 0)),
    kf('body', 'rotation', 0.70, (0.9, 0, 0)),
    kf('body', 'rotation', 1.10, (0, 0, 0)),
]

# =============================================================== 5. reload_tactical
# 膛内有弹、管仓半满 → 从装填门压入 3 发（不循环杠杆）。音效点 0.86 / 1.40 / 1.94 s。
TAC_LEN = 2.2
TAC = [
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.62, (0.02, -0.05, 0.06)),
    kf('move', 'position', 1.35, (-0.01, -0.03, 0.03)),
    kf('move', 'position', 1.95, (0.01, -0.02, 0.02)),
    kf('move', 'position', TAC_LEN, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.62, (3.5, 8, 5)),
    kf('body', 'rotation', 1.35, (2, 6, 4)),
    kf('body', 'rotation', 1.95, (2, 5, 3)),
    kf('body', 'rotation', TAC_LEN, (0, 0, 0)),
]
for i, t0 in enumerate((0.56, 1.10, 1.64)):
    t_push, t_in = t0, t0 + 0.30
    TAC += [
        kf('cartridge', 'position', t0, (OUT_X, 0.10, FEED_Z), 'step'),
        kf('cartridge', 'position', t0 + 0.12, (OUT_X - 0.30, 0.02, FEED_Z), 'linear'),
        kf('cartridge', 'position', t_in, (0.06, -0.10, FEED_Z)),
        kf('cartridge', 'position', t_in + 0.02, (OUT_X, 0.10, FEED_Z), 'step'),
        kf('gate', 'position', t0 + 0.04, (0, 0, 0)),
        kf('gate', 'position', t0 + 0.16, (GATE_OPEN, 0, 0)),
        kf('gate', 'position', t_in, (0, 0, 0)),
        kf('gate', 'rotation', t0 + 0.04, (0, 0, 0)),
        kf('gate', 'rotation', t0 + 0.16, (0, 6, 0)),
        kf('gate', 'rotation', t_in, (0, 0, 0)),
    ]
TAC += [
    kf('cartridge', 'position', TAC_LEN, (OUT_X, 0.10, FEED_Z), 'step'),
    kf('gate', 'position', 0.0, (0, 0, 0)),
    kf('gate', 'position', TAC_LEN, (0, 0, 0)),
]

# =============================================================== 6. reload_empty
# 管仓打空：逐发压入 5 发（音效点 0.95 / 1.50 / 2.05 / 2.60 / 3.15 s），
# 再扳一次杠杆把第一发送进膛（lever down 3.40 s、home 4.20 s）。
EMP_LEN = 4.4
EMP = [
    kf('move', 'position', 0.0, (0, 0, 0)),
    kf('move', 'position', 0.95, (0.03, -0.06, 0.07)),
    kf('move', 'position', 2.05, (-0.02, -0.04, 0.04)),
    kf('move', 'position', 3.15, (0.02, -0.05, 0.05)),
    kf('move', 'position', 3.45, (0, -0.02, 0.02)),
    kf('move', 'position', 3.75, (0, -0.06, 0.10)),
    kf('move', 'position', EMP_LEN, (0, 0, 0)),
    kf('body', 'rotation', 0.0, (0, 0, 0)),
    kf('body', 'rotation', 0.95, (4, 9, 6)),
    kf('body', 'rotation', 2.05, (2, 6, 4)),
    kf('body', 'rotation', 3.15, (3, 7, 5)),
    kf('body', 'rotation', 3.45, (1, 3, 2)),
    kf('body', 'rotation', 3.79, (-2.2, 0, 0)),
    kf('body', 'rotation', 4.05, (1.2, 0, 0)),
    kf('body', 'rotation', EMP_LEN, (0, 0, 0)),
]
for i, t0 in enumerate((0.65, 1.20, 1.75, 2.30, 2.85)):
    t_in = t0 + 0.30
    if i == 4:      # 第 5 发（最后一发）：压进去后不再瞬移回门外
        EMP += [
            kf('cartridge', 'position', t0, (OUT_X, 0.10, FEED_Z), 'step'),
            kf('cartridge', 'position', t0 + 0.12, (OUT_X - 0.30, 0.02, FEED_Z), 'linear'),
            kf('cartridge', 'position', t_in, (0.06, -0.10, FEED_Z)),
            kf('cartridge', 'position', 3.62, (0.06, -CARRY_DROP - 0.02, FEED_Z + 0.20)),
            kf('cartridge', 'position', 3.80, (0.02, -CARRY_DROP, FEED_Z + 0.10)),
            kf('cartridge', 'position', 3.88, (0, 0, CHAMBER_Z), 'step'),
            kf('cartridge', 'position', EMP_LEN, (0, 0, CHAMBER_Z)),
        ]
    else:
        EMP += [
            kf('cartridge', 'position', t0, (OUT_X, 0.10, FEED_Z), 'step'),
            kf('cartridge', 'position', t0 + 0.12, (OUT_X - 0.30, 0.02, FEED_Z), 'linear'),
            kf('cartridge', 'position', t_in, (0.06, -0.10, FEED_Z)),
            kf('cartridge', 'position', t_in + 0.02, (OUT_X, 0.10, FEED_Z), 'step'),
        ]
    EMP += [
        kf('gate', 'position', t0 + 0.04, (0, 0, 0)),
        kf('gate', 'position', t0 + 0.16, (GATE_OPEN, 0, 0)),
        kf('gate', 'position', t_in, (0, 0, 0)),
        kf('gate', 'rotation', t0 + 0.04, (0, 0, 0)),
        kf('gate', 'rotation', t0 + 0.16, (0, 6, 0)),
        kf('gate', 'rotation', t_in, (0, 0, 0)),
    ]
# 收尾：扳一次杠杆，让弹仓里第一发上膛（同 bolt 的相位，只是慢一点）
EMP += [
    kf('gate', 'position', 0.0, (0, 0, 0)),
    kf('gate', 'position', 3.0, (0, 0, 0)),
    kf('gate', 'position', 3.30, (0, 0, 0)),
    kf('gate', 'position', EMP_LEN, (0, 0, 0)),
    kf('lever', 'rotation', 3.36, (0, 0, 0)),
    kf('lever', 'rotation', 3.72, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 3.82, (LEVER_OPEN, 0, 0)),
    kf('lever', 'rotation', 4.22, (0, 0, 0)),
    kf('lever', 'rotation', EMP_LEN, (0, 0, 0)),
    kf('bolt', 'position', 3.36, (0, 0, 0)),
    kf('bolt', 'position', 3.72, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 3.84, (0, 0, BOLT_BACK)),
    kf('bolt', 'position', 4.18, (0, 0, 0)),
    kf('bolt', 'position', EMP_LEN, (0, 0, 0)),
    kf('carrier', 'position', 3.62, (0, 0, 0)),
    kf('carrier', 'position', 3.80, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 3.92, (0, -CARRY_DROP, 0)),
    kf('carrier', 'position', 4.02, (0, LIFT, 0)),
    kf('carrier', 'position', 4.12, (0, LIFT, 0)),
    kf('carrier', 'position', 4.30, (0, 0, 0)),
    kf('carrier', 'position', EMP_LEN, (0, 0, 0)),
    kf('hammer', 'rotation', 3.40, (0, 0, 0)),
    kf('hammer', 'rotation', 3.66, (HAMMER_COCK, 0, 0)),
    kf('hammer', 'rotation', EMP_LEN, (HAMMER_COCK, 0, 0)),
]

# =============================================================== 7. inspect
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
    # 拨一下杠杆：环向前下方摆一点再回位（看机构用）
    kf('lever', 'rotation', 1.62, (0, 0, 0)),
    kf('lever', 'rotation', 1.82, (30, 0, 0)),
    kf('lever', 'rotation', 2.06, (0, 0, 0)),
    kf('carrier', 'position', 1.82, (0, 0, 0)),
    kf('carrier', 'position', 1.94, (0, -CARRY_DROP * 0.7, 0)),
    kf('carrier', 'position', 2.06, (0, 0, 0)),
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
    for name, loop, length, kfs, _close in ANIMS:
        bones = sorted({k['bone'] for k in kfs})
        print(f'{name:18s} {loop:5s} {length:5.1f} {int(length * 20 + 0.999):5d} {len(kfs):4d}  '
              f'{",".join(bones)}')
    # 自检：关键帧不许越过 clip 长度、不许有重复时间
    bad = []
    for name, _loop, length, kfs, _c in ANIMS:
        for k in kfs:
            if k['time'] > length + 1e-6:
                bad.append(f'{name}: {k["bone"]}.{k["channel"]} t={k["time"]} > {length}')
        seen = {}
        for k in kfs:
            key = (k['bone'], k['channel'], k['time'])
            if key in seen:
                bad.append(f'{name}: 重复关键帧 {key}')
            seen[key] = 1
    if bad:
        print('\n自检不通过：')
        for b in bad[:20]:
            print('  [x]', b)
        return 1
    print('自检：关键帧时间全部落在 clip 内，无重复 [ok]')

    if dry:
        return 0

    for name, *_ in ANIMS:
        bbmcp.call('remove_animation', {'animation': name}, timeout=60)

    failures = 0
    for name, loop, length, kfs, close in ANIMS:
        r1 = bbmcp.call('create_animation', {'name': name, 'loop': loop, 'length': length},
                        timeout=120)
        if not r1.get('ok'):
            print(f'[{name}] create FAIL :: {json.dumps(r1, ensure_ascii=False)[:300]}')
            failures += 1
            continue
        payload = {'animation': name, 'keyframes': kfs, 'length': length, 'close_loop': close}
        (OUT / f'anim_{name}.json').write_text(
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
