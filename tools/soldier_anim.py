# -*- coding: utf-8 -*-
"""军装士兵僵尸「残兵」动画生成器（纯标准库，可重复运行）

产物：art/soldier/soldier_zombie.animation.json

── 坐标系与符号（全部来自 GeckoLib 4.8.4 源码，不是猜的）────────────────
模型朝向 −Z（铁律），上 = +Y，角色右手边 = +X。

* `BakedAnimationsAdapter.buildKeyframeStack()`：
      x → Math.toRadians(−rawX)      y → Math.toRadians(−rawY)      z → Math.toRadians(rawZ)
  即 **JSON 里 x/y 取负、z 不取**。位置通道不做任何换算、不取负。
* 位置单位 = u（1 = 1 模型像素 = 1/16 格）：与 .geo.json 的坐标同域
  （两条通道写进的是同一个 bone pos 字段）。已出货枪械动画可印证：
  莫辛枪机行程 2.9u、连发器供弹 14u —— 若当格算是 14 格，荒谬。
* 绕 +X 转 θ 时，被旋转点的 z 位移是 −y·sinθ。所以：
      **肢体（在 pivot 之下，−y 侧）：JSON x 为负 = 向前摆**
      **躯干/头（在 pivot 之上，+y 侧）：JSON x 为正 = 向前俯**
  绕 +Z 转 θ：点的 x 位移是 +y·sinθ ⇒ 右手边肢体 JSON z 为正 = 向 +X 摆
  （即右手外展为正、左手外展为负，成对骨骼异号）。
  绕 +Y 转 θ：朝向 −Z 的向量转向 −X ⇒ JSON y 为正 = 身体向其**右侧**转。

── 铁律（本脚本末尾逐条自检）────────────────────────────────────────
1. 只写 rotation / position，绝不写 scale。
2. 每个通道在 0 与 length 处各有一个键。
3. 循环剪辑：两端数值相等。非循环剪辑：两端都归零。
4. 姿态的可见性不用 scale 表达（弓弦拉/放靠旋转，不靠缩放）。
"""
import io
import json
import os

OUT = os.path.join("art", "soldier", "soldier_zombie.animation.json")

# ── 骨骼名（与 soldier_v2.py / .geo.json 一一对应）────────────────────
ROOT = "root"
SPINE, CHEST, NECK, HEAD, HELMET = "spine", "chest", "neck", "head", "helmet"
LEG_R, SHIN_R, FOOT_R = "leg_r", "shin_r", "foot_r"
LEG_L, SHIN_L, FOOT_L = "leg_l", "shin_l", "foot_l"
ARM_R, FORE_R, HAND_R = "arm_r", "forearm_r", "hand_r"
ARM_L, FORE_L, HAND_L = "arm_l", "forearm_l", "hand_l"
BOW = "bow"
BOW_UP, BOW_DOWN = "bow_string_up", "bow_string_down"
# 引信点燃的 TNT（爆破兵；挂在 hand_r 下，静止时跟着手走，出手时由 throw_tnt 驱动）
TNT, TNT_FUSE = "tnt", "tnt_fuse"

# 僵尸基本站姿（驼背 + 双臂前伸），idle/walk/shoot/throw 都从这里出发
HUNCH_SPINE, HUNCH_CHEST, HEAD_DOWN = 5.0, 6.5, 9.0
ARM_REACH, ELBOW = -52.0, -22.0      # 前伸手臂的臂根/肘
ARM_REACH_L = -60.0                  # 左手略高一点，握弓的手更稳


class Clip:
    """一个剪辑。键值写法：c.rot(bone, "x", [(t, v), ...])，单位度；位置单位 u。"""

    def __init__(self, name, length, loop=False):
        self.name, self.length, self.loop = name, length, loop
        self.data = {}

    def _key(self, bone, chan, axis, keys):
        keys = sorted((round(float(t), 4), float(v)) for t, v in keys)
        ch = self.data.setdefault(bone, {}).setdefault(chan, {})
        vec = ch.setdefault("_v", [0.0, 0.0, 0.0])
        vec["xyz".index(axis)] = 1  # 占位，真值在 to_json 里按轴装
        ch.setdefault("_k", {}).setdefault(axis, []).extend(keys)

    def rot(self, bone, axis, keys):
        self._key(bone, "rotation", axis, keys)

    def pos(self, bone, axis, keys):
        self._key(bone, "position", axis, keys)

    def to_json(self, v_len=1):
        bones = {}
        for bone, chans in sorted(self.data.items()):
            out = {}
            for chan, ch in chans.items():
                vec_axes, vec = ch["_k"], []
                out[chan] = {}
                # 三个轴各自的键合并到同一个时间轴上；某轴缺键就用相邻键插值
                times = sorted({t for ks in vec_axes.values() for t, _ in ks})
                for t in times:
                    for i, ax in enumerate("xyz"):
                        ks = vec_axes.get(ax)
                        vec.append(at(ks, t) if ks else 0.0)
                    out[chan][fmt_t(t)] = {"post": {"vector": [round(vec[-3], 4),
                                                              round(vec[-2], 4),
                                                              round(vec[-1], 4)]},
                                           "lerp_mode": "catmullrom"}
            bones[bone] = out
        return {"loop": self.loop, "animation_length": self.length, "bones": bones}


def at(keys, t):
    """按 0 键插值取值（缺轴的键点是 0 键，不能当缺省 0 处理）。"""
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return v0
            f = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return keys[-1][1]


def fmt_t(t):
    s = ("%.4f" % t).rstrip("0").rstrip(".")
    return s if s else "0"


# ── idle：3.0s 循环 ───────────────────────────────────────────────────
def clip_idle():
    c = Clip("idle", 3.0, loop=True)
    c.pos(ROOT, "y", [(0, 0), (1.5, 1.2), (3.0, 0)])
    c.rot(SPINE, "x", [(0, HUNCH_SPINE), (1.5, HUNCH_SPINE + 1.6), (3.0, HUNCH_SPINE)])
    c.rot(CHEST, "x", [(0, HUNCH_CHEST), (1.5, HUNCH_CHEST + 1.4), (3.0, HUNCH_CHEST)])
    c.rot(NECK, "x", [(0, 3.0), (1.5, 2.0), (3.0, 3.0)])
    # 头：保持低头，同时缓慢左右扫视（僵尸那种反应迟钝的巡视）
    c.rot(HEAD, "x", [(0, HEAD_DOWN), (1.5, HEAD_DOWN + 2.0), (3.0, HEAD_DOWN)])
    c.rot(HEAD, "y", [(0, -5.0), (1.5, 5.0), (3.0, -5.0)])
    # 握弓的右手：端在身侧前下方，随呼吸微沉
    c.rot(ARM_R, "x", [(0, ARM_REACH + 6), (1.5, ARM_REACH + 2), (3.0, ARM_REACH + 6)])
    c.rot(FORE_R, "x", [(0, ELBOW), (1.5, ELBOW - 3), (3.0, ELBOW)])
    c.rot(ARM_L, "x", [(0, ARM_REACH_L), (1.5, ARM_REACH_L - 3), (3.0, ARM_REACH_L)])
    c.rot(FORE_L, "x", [(0, ELBOW - 4), (1.5, ELBOW - 8), (3.0, ELBOW - 4)])
    c.rot(ARM_R, "z", [(0, 4.0), (1.5, 2.0), (3.0, 4.0)])
    c.rot(ARM_L, "z", [(0, -4.0), (1.5, -2.0), (3.0, -4.0)])
    # 弓是挂在 hand_r 上的，手腕一动它跟着转。持弓臂前抬多少，弓就要反向补多少，
    # 否则抬到水平时这张弓会跟着横躺下去（真实持弓是腕部回正、弓保持竖直）。
    c.rot(BOW, "x", [(0, 46.0), (1.5, 50.0), (3.0, 46.0)])
    c.rot(BOW, "z", [(0, -4.0), (1.5, -2.0), (3.0, -4.0)])
    # 双腿：僵尸站立时重量左偏一点，膝盖不锁死
    c.rot(LEG_R, "x", [(0, -3.0), (1.5, -1.0), (3.0, -3.0)])
    c.rot(LEG_L, "x", [(0, 1.5), (1.5, 3.5), (3.0, 1.5)])
    c.rot(SHIN_R, "x", [(0, 5.0), (1.5, 4.0), (3.0, 5.0)])
    c.rot(SHIN_L, "x", [(0, 3.0), (1.5, 4.5), (3.0, 3.0)])
    return c


# ── walk：1.0s 循环（控制器按移动速度缩放）────────────────────────────
def clip_walk():
    c = Clip("walk", 1.0, loop=True)
    # 一个周期两步：t=0 右脚前、t=0.5 左脚前。肢体 JSON x 负 = 向前。
    c.rot(LEG_R, "x", [(0, -22.0), (0.5, 20.0), (1.0, -22.0)])
    c.rot(LEG_L, "x", [(0, 20.0), (0.5, -22.0), (1.0, 20.0)])
    # 膝盖只在腿落后半段收：小腿向后弯（JSON x 正 = 向后）
    c.rot(SHIN_R, "x", [(0, 6.0), (0.3, 4.0), (0.6, 34.0), (0.85, 12.0), (1.0, 6.0)])
    c.rot(SHIN_L, "x", [(0, 34.0), (0.1, 12.0), (0.5, 6.0), (0.8, 4.0), (1.0, 34.0)])
    c.rot(FOOT_R, "x", [(0, 8.0), (0.5, -10.0), (1.0, 8.0)])
    c.rot(FOOT_L, "x", [(0, -10.0), (0.5, 8.0), (1.0, -10.0)])
    # 身体：两步两颠 + 左右轻摇
    c.pos(ROOT, "y", [(0, 0), (0.25, 1.5), (0.5, 0), (0.75, 1.5), (1.0, 0)])
    c.pos(ROOT, "x", [(0, 0.7), (0.5, -0.7), (1.0, 0.7)])
    c.rot(SPINE, "x", [(0, HUNCH_SPINE + 2), (0.5, HUNCH_SPINE), (1.0, HUNCH_SPINE + 2)])
    c.rot(SPINE, "y", [(0, -4.0), (0.5, 4.0), (1.0, -4.0)])
    c.rot(CHEST, "x", [(0, HUNCH_CHEST), (0.5, HUNCH_CHEST + 2), (1.0, HUNCH_CHEST)])
    c.rot(CHEST, "y", [(0, 5.0), (0.5, -5.0), (1.0, 5.0)])
    c.rot(HEAD, "x", [(0, HEAD_DOWN), (0.5, HEAD_DOWN + 1.5), (1.0, HEAD_DOWN)])
    c.rot(HEAD, "y", [(0, -3.0), (0.5, 3.0), (1.0, -3.0)])
    # 双臂：前伸着反向摆（右手握弓，摆幅小一些）
    c.rot(ARM_R, "x", [(0, ARM_REACH + 6), (0.5, ARM_REACH - 8), (1.0, ARM_REACH + 6)])
    c.rot(ARM_L, "x", [(0, ARM_REACH_L - 10), (0.5, ARM_REACH_L + 6), (1.0, ARM_REACH_L - 10)])
    c.rot(FORE_R, "x", [(0, ELBOW), (0.5, ELBOW - 6), (1.0, ELBOW)])
    c.rot(FORE_L, "x", [(0, ELBOW - 6), (0.5, ELBOW), (1.0, ELBOW - 6)])
    c.rot(ARM_R, "z", [(0, 4.0), (0.5, 3.0), (1.0, 4.0)])
    c.rot(ARM_L, "z", [(0, -4.0), (0.5, -3.0), (1.0, -4.0)])
    # 同上：弓随持弓臂同相位反向补偿（walk 的 arm_r 是 -34~-62 之间摆）
    c.rot(BOW, "x", [(0, 46.0), (0.5, 62.0), (1.0, 46.0)])
    c.rot(BOW, "z", [(0, -4.0), (0.5, -3.0), (1.0, -4.0)])
    return c


# ── shoot：1.0s 非循环（原版 RangedBowAttackGoal 的拉弓时长固定 20 tick）──
# 长度必须钉死 1.0s：原版弓的 draw 时长不对外开放，拉满 20 tick 后立刻 performRangedAttack。
# 剪辑 1.2s 会在箭出膛前被 STOP 掐断，释放段根本看不到。
# 这里**不写腿部通道**：拉弓期间原版目标会让怪边走边瞄，腿部必须留给行走控制器，
# 否则两边抢同一根骨头（后注册的赢，腿就会僵住）。
def clip_shoot():
    c = Clip("shoot", 1.0, loop=False)
    # 角色分工（跟着模型来）：弓挂在右手 hand_r 上
    #   → 右臂 = 持弓臂，抬平指向目标（肢体 JSON x 负 = 向前）
    #   → 左臂 = 拉弦臂，大臂前抬、肘向后折收向脸侧（前臂相对大臂向后 = JSON x 正）
    c.rot(ARM_R, "x", [(0, 0), (0.30, -84.0), (0.70, -86.0), (0.78, -88.0), (1.0, 0)])
    c.rot(FORE_R, "x", [(0, 0), (0.30, -4.0), (0.70, -4.0), (0.78, -2.0), (1.0, 0)])
    c.rot(ARM_R, "z", [(0, 0), (0.30, -8.0), (0.70, -8.0), (1.0, 0)])
    c.rot(ARM_L, "x", [(0, 0), (0.30, -56.0), (0.70, -60.0), (0.78, -48.0), (1.0, 0)])
    c.rot(FORE_L, "x", [(0, 0), (0.30, 58.0), (0.70, 74.0), (0.78, 52.0), (1.0, 0)])
    c.rot(ARM_L, "z", [(0, 0), (0.30, 9.0), (0.70, 11.0), (1.0, 0)])
    c.rot(HAND_L, "x", [(0, 0), (0.30, -8.0), (0.70, -10.0), (1.0, 0)])
    # 弓反向补偿：持弓臂抬到 84~88°，弓补同样角度，抬平后弓仍竖直
    c.rot(BOW, "x", [(0, 0), (0.30, 84.0), (0.70, 86.0), (0.78, 88.0), (1.0, 0)])
    c.rot(BOW, "z", [(0, 0), (0.30, 8.0), (0.70, 8.0), (1.0, 0)])
    # 弓弦：上段绕上梢、下段绕下梢，各往 +Z（贴身侧）拉出同一个角度
    c.rot(BOW_UP, "x", [(0, 0), (0.30, 6.0), (0.70, 30.0), (0.78, 0), (1.0, 0)])
    c.rot(BOW_DOWN, "x", [(0, 0), (0.30, -6.0), (0.70, -30.0), (0.78, 0), (1.0, 0)])
    # 躯干：持弓侧肩转向目标 = 身体向其左侧拧（JSON y 正 = 向右侧转）
    c.rot(SPINE, "x", [(0, 0), (0.30, 6.0), (0.70, 8.5), (0.78, 5.0), (1.0, 0)])
    c.rot(CHEST, "y", [(0, 0), (0.30, -12.0), (0.70, -14.0), (0.78, -9.0), (1.0, 0)])
    c.rot(CHEST, "x", [(0, 0), (0.30, 4.0), (0.70, 5.0), (0.78, 2.0), (1.0, 0)])
    c.rot(HEAD, "y", [(0, 0), (0.30, 12.0), (1.0, 0)])
    c.rot(HEAD, "x", [(0, 0), (0.30, 4.0), (1.0, 0)])
    # 整体：下蹲一点稳住，释放时向后坐 1.6u
    c.pos(ROOT, "y", [(0, 0), (0.30, -1.0), (0.70, -1.4), (0.78, -0.6), (1.0, 0)])
    c.pos(ROOT, "z", [(0, 0), (0.70, 0), (0.78, 1.6), (1.0, 0)])
    return c


# ── throw_tnt：1.5s 非循环（引信点燃的 TNT，0.62s 出手）───────────────
THROW_RELEASE = 0.62


def clip_throw():
    c = Clip("throw_tnt", 1.5, loop=False)
    # 0.00-0.45 引臂：左臂抡到身后举起（JSON x 正 = 向后），身体向左拧
    c.rot(ARM_L, "x", [(0, 0), (0.45, 98.0), (0.62, -104.0), (0.85, -26.0), (1.5, 0)])
    c.rot(FORE_L, "x", [(0, 0), (0.45, 44.0), (0.62, -6.0), (0.85, -14.0), (1.5, 0)])
    c.rot(HAND_L, "x", [(0, 0), (0.45, 16.0), (0.62, -18.0), (1.5, 0)])
    c.rot(ARM_L, "z", [(0, 0), (0.45, -18.0), (0.62, 4.0), (0.85, 0), (1.5, 0)])
    # 躯干：拧腰蓄力 → 反拧甩出 → 前倾跟上
    c.rot(CHEST, "y", [(0, 0), (0.30, -8.0), (0.45, -16.0), (0.62, 12.0), (0.85, 6.0), (1.5, 0)])
    c.rot(SPINE, "y", [(0, 0), (0.45, -9.0), (0.62, 7.0), (0.85, 3.0), (1.5, 0)])
    c.rot(SPINE, "x", [(0, HUNCH_SPINE - 5), (0.45, HUNCH_SPINE - 2), (0.62, HUNCH_SPINE + 9), (0.85, HUNCH_SPINE + 4), (1.5, 0)])
    c.rot(CHEST, "x", [(0, HUNCH_CHEST - 4), (0.45, HUNCH_CHEST - 1), (0.62, HUNCH_CHEST + 8), (0.85, HUNCH_CHEST + 3), (1.5, 0)])
    c.rot(HEAD, "x", [(0, HEAD_DOWN), (0.45, HEAD_DOWN - 6), (0.62, HEAD_DOWN + 5), (0.85, HEAD_DOWN + 2), (1.5, 0)])
    c.rot(HEAD, "y", [(0, 0), (0.45, -10.0), (0.62, 6.0), (1.5, 0)])
    # 整体：先起身蓄力，出手瞬间下沉 + 向前扑 3u（出手点在代码里对齐 0.62s）
    c.pos(ROOT, "y", [(0, 0), (0.45, 1.5), (0.62, -2.5), (0.85, -1.0), (1.5, 0)])
    c.pos(ROOT, "z", [(0, 0), (0.45, 1.2), (0.62, -3.0), (0.85, -1.2), (1.5, 0)])
    # 撑弓的右臂保持低位平衡
    c.rot(ARM_R, "x", [(0, ARM_REACH), (0.45, ARM_REACH + 10), (0.62, ARM_REACH - 14), (1.5, 0)])
    c.rot(FORE_R, "x", [(0, ELBOW), (0.62, ELBOW - 10), (1.5, 0)])
    # 手里的 TNT：引臂时往后压、出手瞬间往前翻出去；引信自己再抖一抖（点燃的不是静态贴图）
    c.rot(TNT, "x", [(0, 0), (0.45, -30.0), (0.62, 46.0), (0.85, 14.0), (1.5, 0)])
    c.rot(TNT, "z", [(0, 0), (0.45, 6.0), (0.62, -12.0), (0.85, -4.0), (1.5, 0)])
    c.rot(TNT_FUSE, "x", [(0, 0), (0.30, 9.0), (0.45, -7.0), (0.62, 11.0), (1.5, 0)])
    c.rot(TNT_FUSE, "z", [(0, 0), (0.38, -6.0), (0.55, 6.0), (1.5, 0)])
    # 腿：后腿蹬地
    c.rot(LEG_R, "x", [(0, 0), (0.45, 8.0), (0.62, -12.0), (1.5, 0)])
    c.rot(LEG_L, "x", [(0, 0), (0.45, -4.0), (0.62, 6.0), (1.5, 0)])
    c.rot(SHIN_R, "x", [(0, 0), (0.45, 6.0), (0.62, 16.0), (1.5, 0)])
    c.rot(SHIN_L, "x", [(0, 0), (0.45, 10.0), (0.62, 4.0), (1.5, 0)])
    return c


CLIPS = [clip_idle, clip_walk, clip_shoot, clip_throw]


def build():
    anims = {}
    for f in CLIPS:
        c = f()
        anims[c.name] = c.to_json()
    return {"format_version": "1.8.0", "animations": anims}


# ── 铁律自检 ─────────────────────────────────────────────────────────
def verify(doc):
    bad = []
    LOOPS = {"idle", "walk"}
    for name, clip in doc["animations"].items():
        ln = clip["animation_length"]
        for bone, chans in clip["bones"].items():
            for chan, keys in chans.items():
                if chan not in ("rotation", "position"):
                    bad.append("%s.%s 出现通道 %s" % (name, bone, chan))
                if chan == "scale":
                    bad.append("%s.%s 写了 scale（铁律禁止）" % (name, bone))
                ts = sorted(float(t) for t in keys)
                if ts[0] != 0.0:
                    bad.append("%s.%s.%s 缺少 t=0 键" % (name, bone, chan))
                if abs(ts[-1] - ln) > 1e-6:
                    bad.append("%s.%s.%s 缺少 t=length 键（末键 %.3f ≠ %.3f）"
                               % (name, bone, chan, ts[-1], ln))
                v0 = keys[fmt_t(0.0)]["post"]["vector"]
                v1 = keys[fmt_t(ln)]["post"]["vector"] if fmt_t(ln) in keys else None
                if v1 is None:
                    continue
                if name in LOOPS:
                    if v0 != v1:
                        bad.append("%s.%s.%s 循环剪辑两端不等 %s / %s" % (name, bone, chan, v0, v1))
                else:
                    if any(abs(x) > 1e-6 for x in v1):
                        bad.append("%s.%s.%s 非循环剪辑末帧未归零 %s" % (name, bone, chan, v1))
    return bad


if __name__ == "__main__":
    doc = build()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    bad = verify(doc)
    nb = sum(len(c["bones"]) for c in doc["animations"].values())
    print("剪辑 %d 个：%s" % (len(doc["animations"]),
                             ", ".join("%s(%.1fs%s)" % (k, v["animation_length"],
                                                        "/循环" if v["loop"] else "/单次")
                                       for k, v in doc["animations"].items())))
    print("涉及骨骼键 %d 条；输出 %s" % (nb, OUT))
    # 位置量级体检：u 为单位的通道，绝对值 <1 的"位移"在游戏里是看不见的
    tiny = []
    for name, clip in doc["animations"].items():
        for bone, chans in clip["bones"].items():
            for chan, keys in chans.items():
                if chan != "position":
                    continue
                m = max(max(abs(x) for x in k["post"]["vector"]) for k in keys.values())
                if 0 < m < 1.0:
                    tiny.append("%s.%s 最大位移仅 %.2fu" % (name, bone, m))
    if bad:
        print("自检失败 %d 项：" % len(bad))
        for b in bad:
            print("   ✗", b)
        raise SystemExit(1)
    print("自检通过：通道仅 rotation/position、两端键齐、循环等值、非循环归零")
    if tiny:
        print("提示：以下位移小于 1u，游戏内几乎不可见 → " + "; ".join(tiny))
