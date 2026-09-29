# -*- coding: utf-8 -*-
"""美女僵尸「近战 / 远程」两套攻击技能的静态校验。

这一版的坑全在「代码对、编译过、游戏里看不出」的类别里：
  * `EliteAbility` 插在中间 ⇒ `byId` 用 ordinal，别的精英施法状态在网络上错位（旧版看不出来）；
  * `ROTATION` 与 `ROTATION_COOLDOWN` 长度不一致 ⇒ 数组越界或静默用错冷却；
  * 距离条件把轮转卡死 ⇒ 她在远处一站到底，一个技能都不放（本轮专门加了跳过兜底）；
  * 投掷物不小心关掉重力 ⇒ 花束变成直线飞的子弹，「抛物线可躲」的设计前提没了；
  * 少了渲染器注册 / 贴图 / lang ⇒ 客户端一个紫黑方块。

用法：
    python tools/check_bride_combat.py             # 正常校验
    python tools/check_bride_combat.py --selftest  # 变异测试（每条断言都必须抓得住）
"""

import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JAVA = os.path.join(ROOT, "src", "main", "java", "com", "apocalypse", "zombies")
RES = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")
ART = os.path.join(ROOT, "art", "bride")

OVERRIDE = {}
PNG_OVERRIDE = {}

# 已出货的枚举前缀：这些的 ordinal 不许再变（byId 走 ordinal 联网同步）
FROZEN_PREFIX = [
    "NONE", "SCREAM", "SLAM", "SPIT", "SNIPE",
    "DEATH_CHIME", "CONSORT", "SOUL_SHRIEK", "VEIL_SNARE",
    "SACRIFICE", "BOUQUET", "BRIDAL_KISS", "BLOOD_REGEN",
]

CHECKS = [
    ("enum_append_only", "EliteAbility 只在末尾追加"),
    ("rotation_tables", "轮转表与冷却表一一对应"),
    ("rotation_skip", "距离条件不成立会跳过而不是卡死"),
    ("melee_sweep", "近战横扫：扇区、不吃自己人、击退同步"),
    ("ranged_dart", "远程抛掷：抛物线、不关重力、抬瞄"),
    ("registry_chain", "物品 / 实体 / 渲染器 / 贴图 / lang 全链注册"),
    ("clip_wiring", "剪辑常量与动画表对齐"),
    ("move_amplitude", "全身位移复标定（表↔动画逐轴相等 + 语义下限）"),
    ("arm_amplitude", "手臂攻击幅度下限（抬举 / 侧摆 / 肩 / 袖骨）"),
]


def read(rel):
    """java 相对路径 → 文本（通用换行，锚点写 \\n 就能匹配）。"""
    if rel in OVERRIDE:
        return OVERRIDE[rel]
    with io.open(os.path.join(JAVA, rel), encoding="utf-8") as handle:
        return handle.read()


def read_res(rel):
    """resources 相对路径 → 文本。"""
    if rel in OVERRIDE:
        return OVERRIDE[rel]
    with io.open(os.path.join(RES, rel), encoding="utf-8") as handle:
        return handle.read()


def read_any(path):
    """变异测试用：按路径猜到正确的读取根。"""
    if path in OVERRIDE:
        return OVERRIDE[path]
    if path.startswith(("tools/", "art/")):
        with io.open(os.path.join(ROOT, path), encoding="utf-8") as handle:
            return handle.read()
    if path.endswith(".json") and "java" not in path:
        return read_res(path)
    return read(path)


def read_png_size(rel):
    if rel in PNG_OVERRIDE:
        return PNG_OVERRIDE[rel]
    with open(os.path.join(RES, rel), "rb") as handle:
        blob = handle.read()
    return int.from_bytes(blob[16:20], "big"), int.from_bytes(blob[20:24], "big")


def body(text, signature):
    """取出某个方法的方法体（按花括号配平），找不到返回 None。"""
    at = text.find(signature)
    if at < 0:
        return None
    depth = 0
    start = text.find("{", at)
    if start < 0:
        return None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def enum_body(text):
    at = text.find("public enum EliteAbility {")
    return None if at < 0 else text[at:]


def check_enum_append_only(fail):
    enum = enum_body(read("entity/EliteAbility.java"))
    if enum is None:
        fail("读不到 EliteAbility 枚举体")
        return
    if "VEIL_SWIPE(" not in enum or "FLOWER_DART(" not in enum or "VEIL_CHOP(" not in enum:
        fail("EliteAbility 里没有 VEIL_SWIPE / FLOWER_DART / VEIL_CHOP")
        return
    # 铁律：只许追加在末尾。byId 用 ordinal，插在中间等于把别的精英的施法状态换掉。
    # 断成两部分：① 已出货的前 13 条冻结不许动；② 新技能必须在末尾。
    order = re.findall(r"^\s*([A-Z][A-Z_]+)\(\d+,", enum, re.M)
    if order[:len(FROZEN_PREFIX)] != FROZEN_PREFIX:
        fail("枚举前 %d 条被动过：实际 %s ⇒ byId 用 ordinal，插在中间会让已有技能错位"
             % (len(FROZEN_PREFIX), order[:len(FROZEN_PREFIX)]))
    tail = ["VEIL_SWIPE", "FLOWER_DART", "VEIL_CHOP"]
    if order[-3:] != tail:
        fail("末尾三条不是 %s，实际 %s ⇒ 新技能只能追加在末尾" % (tail, order[-3:]))
    if not re.search(r"VEIL_CHOP\(42,\s*22\)\s*;", enum):
        fail("VEIL_CHOP 不是枚举里最后一条（必须以 ; 收尾）⇒ 只能追加在末尾")
    for name, dur, imp in (("VEIL_SWIPE", 40, 20), ("FLOWER_DART", 36, 18), ("VEIL_CHOP", 42, 22)):
        if not re.search(r"%s\(%d,\s*%d\)" % (name, dur, imp), enum):
            fail("%s 的 (duration, impactTick) 不是 (%d, %d)" % (name, dur, imp))


def check_rotation_tables(fail):
    bride = read("entity/BrideZombie.java")
    rot = body(bride, "EliteAbility[] ROTATION = {")
    cool = re.search(r"ROTATION_COOLDOWN\s*=\s*\{([^}]*)\}", bride)
    if rot is None or cool is None:
        fail("读不到 ROTATION / ROTATION_COOLDOWN")
        return
    names = re.findall(r"EliteAbility\.([A-Z_]+)", rot)
    if len(names) != len(set(names)):
        fail("ROTATION 里有重复技能：%s" % names)
    for want in ("VEIL_SWIPE", "FLOWER_DART", "VEIL_CHOP"):
        if want not in names:
            fail("ROTATION 里没有 %s ⇒ 这套技能永远不会被轮到" % want)
    nums = [n for n in cool.group(1).replace("\n", " ").split(",") if n.strip()]
    if len(nums) != len(names):
        fail("ROTATION 有 %d 套、ROTATION_COOLDOWN 有 %d 个值 ⇒ 下标错位"
             % (len(names), len(nums)))
    if len(names) != 11:
        fail("轮转应有 11 套（8 + 近战 + 远程 + 下劈），实际 %d 套" % len(names))


def check_rotation_skip(fail):
    bride = read("entity/BrideZombie.java")
    if "ROTATION_SKIP_TICKS" not in bride:
        fail("没有 ROTATION_SKIP_TICKS ⇒ 距离条件会把整条轮转卡死")
        return
    can = body(bride, "boolean canStartAbility()")
    if can is None:
        fail("读不到 canStartAbility")
        return
    if "rotationStallTicks" not in can:
        fail("canStartAbility 里没有用 rotationStallTicks ⇒ 没有跳过兜底")
    if "rotationIndex = (this.rotationIndex + 1) % ROTATION.length" not in can:
        fail("canStartAbility 起不了手时没有把 rotationIndex 推到下一套")
    if "slotInRange" not in can:
        fail("canStartAbility 没有走 slotInRange ⇒ 距离判定与跳过逻辑揉在一起了")
    # 冷却中的槽不许跳过：冷却自己会走完，跳过只会让技能顺序变得不可预测
    if can.find("skillCooldown[index] > 0") > can.find("rotationStallTicks"):
        fail("跳过逻辑排在冷却判定之前 ⇒ 冷却中的技能也会被跳掉，顺序不可预测")
    if body(bride, "boolean slotInRange(int index)") is None:
        fail("没有 slotInRange 方法")


def check_melee_sweep(fail):
    bride = read("entity/BrideZombie.java")
    for const in ("SWIPE_TRIGGER_RANGE", "SWIPE_RADIUS", "SWIPE_HALF_ANGLE",
                  "SWIPE_DAMAGE", "SWIPE_KNOCKBACK"):
        if const not in bride:
            fail("缺少近战常量 %s" % const)
    swipe = body(bride, "private void castVeilSwipe(ServerLevel level)")
    if swipe is None:
        fail("没有 castVeilSwipe 实现")
        return
    for used in ("SWIPE_HALF_ANGLE", "SWIPE_RADIUS", "SWIPE_DAMAGE", "SWIPE_KNOCKBACK"):
        if used not in swipe:
            fail("castVeilSwipe 没用 %s（写死了数字？）" % used)
    if "!(e instanceof Monster)" not in swipe:
        fail("横扫会打到 Monster ⇒ 连她自己的召奬一起清场")
    if "hurtMarked = true" not in swipe:
        fail("击退改了速度却没标 hurtMarked ⇒ 客户端看不到位移")
    if "hasTargetInRange(1.0D, SWIPE_TRIGGER_RANGE)" not in bride:
        fail("近战槽没有距离条件（或条件与常量脱节）")


def check_ranged_dart(fail):
    bride = read("entity/BrideZombie.java")
    for const in ("DART_MIN_RANGE", "DART_MAX_RANGE", "DART_SPEED", "DART_ARC_LIFT"):
        if const not in bride:
            fail("缺少远程常量 %s" % const)
    dart = body(bride, "private void castFlowerDart(ServerLevel level)")
    if dart is None:
        fail("没有 castFlowerDart 实现")
        return
    if "ModEntities.BOUQUET_PROJECTILE.get()" not in dart:
        fail("抛花刺没有生成花束投射物")
    if "shoot(" not in dart or "DART_SPEED" not in dart:
        fail("抛花刺没有按 DART_SPEED 出手")
    if "DART_ARC_LIFT * distance" not in dart:
        fail("抛花刺没有按距离抬瞄 ⇒ 有重力的花会全打在地上")
    if "hasTargetInRange(DART_MIN_RANGE, DART_MAX_RANGE)" not in bride:
        fail("远程槽的距离窗口与常量脱节")

    proj = read("entity/BouquetProjectile.java")
    if "extends ThrowableItemProjectile" not in proj:
        fail("BouquetProjectile 不是投掷物")
    if "ModItems.BOUQUET_DART.get()" not in proj:
        fail("BouquetProjectile 没有用自家的花束道具当贴图")
    # 设计前提：它是被「甩」出来的，保留重力 ⇒ 关掉重力就变成直线飞的子弹
    if "setNoGravity(true)" in proj:
        fail("BouquetProjectile 关掉了重力 ⇒ 抛物线没了，「可躲」这个前提也没了")
    for const in ("IMPACT_DAMAGE", "POISON_TICKS", "SLOW_TICKS"):
        if const not in proj:
            fail("BouquetProjectile 缺少常量 %s" % const)


def check_registry_chain(fail):
    items = read("registry/ModItems.java")
    if 'ITEMS.register("bouquet_dart"' not in items:
        fail("ModItems 没有注册 bouquet_dart")
    if "public static final RegistryObject<Item> BOUQUET_DART" not in items:
        fail("ModItems.BOUQUET_DART 常量声明被改名 ⇒ 出货门禁没有可钉的标识符")

    entities = read("registry/ModEntities.java")
    if 'ENTITY_TYPES.register("bouquet_projectile"' not in entities:
        fail("ModEntities 没有注册 bouquet_projectile")
    if "public static final RegistryObject<EntityType<BouquetProjectile>> BOUQUET_PROJECTILE" not in entities:
        fail("ModEntities.BOUQUET_PROJECTILE 常量声明被改名")

    client = read("client/ClientModBusEvents.java")
    if "ModEntities.BOUQUET_PROJECTILE.get()" not in client:
        fail("客户端没注册花束渲染器 ⇒ 游戏里看不到它飞")
    if "ThrownItemRenderer<BouquetProjectile>" not in client:
        fail("花束渲染器不是 ThrownItemRenderer")

    model = read_res("models/item/bouquet_dart.json")
    if "apocalypse_zombies:item/bouquet_dart" not in model:
        fail("物品模型没有指向自家贴图")
    size = read_png_size("textures/item/bouquet_dart.png")
    if size != (16, 16):
        fail("花束贴图尺寸 %sx%s，应为 16x16" % size)

    for lang in ("lang/zh_cn.json", "lang/en_us.json"):
        text = read_res(lang)
        match = re.search(r'"item\.apocalypse_zombies\.bouquet_dart"\s*:\s*"([^"]*)"', text)
        if not match or not match.group(1).strip():
            fail("%s 里没有 bouquet_dart 的显示名" % lang)


def check_move_amplitude(fail):
    """全身位移复标定：MOVE_AMP 表 ↔ 动画表逐轴对上，且不许低于语义下限。

    这张表是「她整个人移了多少」的唯一出处。**表里写了幅度、剪辑里却没有该轴通道时会静默空转**
    （本轮真踩过：`skill_bouquet` 的 z、`summon` 的 y 都只写在表里，剪出来一点没动），
    所以这里要求逐轴相等 —— 只断「幅度不等于 0」抓不住这类事。
    """
    src = read_any("tools/bride_v2.py")
    at = src.find("MOVE_AMP = {")
    if at < 0:
        fail("bride_v2.py 里找不到 MOVE_AMP 表")
        return
    open_at = src.find("{", at)
    depth, end = 0, None
    for i in range(open_at, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        fail("MOVE_AMP 的花括号不配平")
        return
    try:
        table = ast.literal_eval(src[open_at:end])
    except (ValueError, SyntaxError) as exc:
        fail("MOVE_AMP 不是纯字面量，读不出来：%s" % exc)
        return

    doc = json.loads(read_res("animations/bride_zombie.animation.json"))
    anims = doc.get("animations", {})
    axis_index = {"x": 0, "y": 1, "z": 2}
    for clip in sorted(table):
        clip_data = anims.get(clip)
        if clip_data is None:
            fail("动画表里没有剪辑 %s（可 MOVE_AMP 里写了它的位移幅度）" % clip)
            continue
        pos = (clip_data.get("bones") or {}).get("move", {}).get("position", {})
        for axis in sorted(table[clip]):
            target = table[clip][axis]
            j = axis_index[axis]
            # 注意：position 是按**时间**索引的，每帧一个 3 维 vector。
            # 「剪辑里没有这条通道」在文件里的实际形态是「该轴全程为 0」。
            peak = 0.0
            for frame in pos.values():
                vec = (frame.get("post") or frame.get("pre") or {}).get("vector") or []
                if len(vec) > j and isinstance(vec[j], (int, float)):
                    peak = max(peak, abs(vec[j]))
            if peak <= 1e-9:
                fail("%s 的 move.%s 全程为 0 ⇒ MOVE_AMP 里写的 %.2fu 是静默空转"
                     % (clip, axis, target))
                continue
            if abs(peak - target) > 1e-3:
                fail("%s 的 move.%s 振幅 %.3fu，表里写的是 %.3fu（幅度与形状脱节了）"
                     % (clip, axis, peak, target))

    # 语义下限：表本身可以调，但「该有位移」的地方不许再缩回看不见的量级
    floors = (("skill_veil_swipe", "z", 6.0),   # 近战垫步进身至少 0.37 格
              ("skill_bridal_kiss", "z", 4.0),
              ("skill_sacrifice", "y", 3.0),    # 跪下去至少 19cm
              ("skill_consort", "y", 2.5),
              ("idle", "y", 0.5),
              ("walk", "y", 0.6))
    for clip, axis, floor in floors:
        value = (table.get(clip) or {}).get(axis, 0.0)
        if value < floor:
            fail("%s 的 move.%s 振幅 %.2fu < 下限 %.2fu（她整个人又在原地打转了）"
                 % (clip, axis, value, floor))


def check_arm_amplitude(fail):
    """「手臂攻击要明显」的量化下限：抬举 / 侧摆 / 肩膀 / 袖子，四条都钉死。

    1.1.32 之前的实测：三套攻击的 `arm_r` 前举 x 全程只有 Δ18~20°，而肩膀的 y/z **恒为 0** ——
    手臂垂在髋部高度横着抹，第三人称侧后方看成一条线，还不如一个送花动作（Δ76°）显眼。
    所以这里按**平面**定下限：横扫必须走出 z（水平面）、下劈必须走出 x（垂直面）、
    抛花刺两条都要；肩膀每套攻击至少三轴参与；重档的袖骨每套都得真的甩起来。
    """
    doc = json.loads(read_res("animations/bride_zombie.animation.json"))
    anims = doc.get("animations", {})
    axis_index = {"x": 0, "y": 1, "z": 2}

    def swing(clip, bone, axis):
        """某剪辑某骨某轴的角位移幅度（度）。通道不存在 / 全 0 时返回 0.0。"""
        chan = ((anims.get(clip) or {}).get("bones", {}).get(bone, {}) or {}).get("rotation") or {}
        j = axis_index[axis]
        lo = hi = 0.0
        for frame in chan.values():
            vec = (frame.get("post") or frame.get("pre") or {}).get("vector") or []
            if len(vec) > j and isinstance(vec[j], (int, float)):
                lo, hi = min(lo, vec[j]), max(hi, vec[j])
        return hi - lo

    # 手臂本体：横扫「先抬后扫」、下劈「过顶到劈下」、抛花刺「后引→前送」
    for clip, axis, floor in (("skill_veil_swipe", "x", 80.0),
                              ("skill_veil_swipe", "z", 95.0),
                              ("skill_veil_chop", "x", 150.0),
                              ("skill_flower_dart", "x", 60.0),
                              ("skill_flower_dart", "z", 70.0)):
        got = swing(clip, "arm_r", axis)
        if got < floor:
            fail("%s 的 arm_r.%s 只有 %.1f°，下限 %.1f° ⇒ 手臂又回到「垂着抹」了"
                 % (clip, axis, got, floor))

    # 肩膀：原来是全程 0（y/z 两个通道根本没写）。三轴都要参与，主抬举还得够大。
    for clip, axis, floor in (("skill_veil_swipe", "x", 30.0),
                              ("skill_veil_swipe", "y", 25.0),
                              ("skill_veil_swipe", "z", 25.0),
                              ("skill_veil_chop", "x", 35.0),
                              ("skill_veil_chop", "y", 15.0),
                              ("skill_veil_chop", "z", 20.0),
                              ("skill_flower_dart", "x", 30.0),
                              ("skill_flower_dart", "y", 18.0)):
        got = swing(clip, "shoulder_r", axis)
        if got < floor:
            fail("%s 的 shoulder_r.%s 只有 %.1f°，下限 %.1f° ⇒ 肩膀又不参与了"
                 % (clip, axis, got, floor))

    # 重档的袖骨：三套攻击都得甩袖子，且**两节袖骨都要动**（子段配比 0.55，断了就说明没链上）
    for clip, floor in (("skill_veil_swipe", 90.0),
                        ("skill_veil_chop", 120.0),
                        ("skill_flower_dart", 90.0)):
        root = max(swing(clip, "sleeve_r", "x"), swing(clip, "sleeve_r", "z"))
        if root < floor:
            fail("%s 的袖骨（sleeve_r）最大摆幅只有 %.1f°，下限 %.1f° ⇒ 袖骨装了没甩"
                 % (clip, root, floor))
            continue
        child = max(swing(clip, "sleeve_r2", "x"), swing(clip, "sleeve_r2", "z"))
        if child < root * 0.4:
            fail("%s 的袖口（sleeve_r2）只跟着走了 %.1f°、根段 %.1f° ⇒ 两节袖骨的主从配比断了"
                 % (clip, child, root))


def check_clip_wiring(fail):
    bride = read("entity/BrideZombie.java")
    for const, clip in (("ANIM_VEIL_SWIPE", "skill_veil_swipe"),
                        ("ANIM_FLOWER_DART", "skill_flower_dart"),
                        ("ANIM_VEIL_CHOP", "skill_veil_chop")):
        if '"%s"' % clip not in bride:
            fail("BrideZombie 里没有剪辑常量 %s" % clip)
        if const not in bride:
            fail("BrideZombie 里没有 %s" % const)

    cast = body(bride, "private static PlayState castAnimation")
    if cast is None:
        fail("读不到 castAnimation")
    else:
        for want in ("VEIL_SWIPE -> ANIM_VEIL_SWIPE", "FLOWER_DART -> ANIM_FLOWER_DART",
                     "VEIL_CHOP -> ANIM_VEIL_CHOP"):
            if want not in cast:
                fail("castAnimation 没把 %s 接到剪辑上" % want.split(" -> ")[0])

    impact = body(bride, "protected void onAbilityImpact()")
    if impact is None or "castVeilSwipe" not in impact or "castFlowerDart" not in impact \
            or "castVeilChop" not in impact:
        fail("onAbilityImpact 没有接上三套技能的结算（横扫 / 抛花刺 / 下劈）")

    aura = body(bride, "private SimpleParticleType auraParticle()")
    if aura is None:
        fail("读不到 auraParticle")
        return
    # 只查「名字出现过」会被 `-> null;` 骗过：钉住 case 的整行形状
    for ability in ("VEIL_SWIPE", "FLOWER_DART", "VEIL_CHOP"):
        if not re.search(r"case %s -> ParticleTypes\.[A-Z_]+;" % ability, aura):
            fail("auraParticle 的 %s 没有配一个真的粒子（写成 null 骗不过这条）" % ability)

    with io.open(os.path.join(ART, "bride_zombie.animation.json"), encoding="utf-8") as handle:
        anim = handle.read()
    for clip, length in (("skill_veil_swipe", 2.0), ("skill_flower_dart", 1.8),
                         ("skill_veil_chop", 2.1)):
        match = re.search(r'"%s"\s*:\s*\{[^}]*?"animation_length"\s*:\s*([0-9.]+)' % clip, anim)
        if not match:
            fail("动画表里没有剪辑 %s" % clip)
        elif abs(float(match.group(1)) - length) > 1e-6:
            fail("%s 的 animation_length=%s，应是 %.1f（= EliteAbility 的 %d tick）"
                 % (clip, match.group(1), length, int(length * 20)))
    # 时长必须与枚举一致：剪辑 2.1s ⇒ 42 tick
    enum = read("entity/EliteAbility.java")
    for clip, enum_name in (("skill_veil_swipe", "VEIL_SWIPE"), ("skill_flower_dart", "FLOWER_DART"),
                            ("skill_veil_chop", "VEIL_CHOP")):
        match = re.search(r"%s\((\d+)," % enum_name, enum)
        if not match:
            fail("枚举里没有 %s" % enum_name)


# ------------------------------------------------------------------ 变异测试
MUTATIONS = [
    ("enum_append_only", "entity/EliteAbility.java",
     "    BLOOD_REGEN(52, 18),", "    VEIL_SWIPE(40, 20),"),
    ("enum_append_only", "entity/EliteAbility.java",
     "VEIL_CHOP(42, 22);", "VEIL_CHOP(42, 22),\n    EXTRA(1, 1);"),
    ("rotation_tables", "entity/BrideZombie.java",
     "EliteAbility.SACRIFICE, EliteAbility.BLOOD_REGEN,\n            EliteAbility.VEIL_SWIPE, EliteAbility.FLOWER_DART,\n            EliteAbility.VEIL_CHOP};",
     "EliteAbility.SACRIFICE, EliteAbility.BLOOD_REGEN,\n            EliteAbility.VEIL_SWIPE, EliteAbility.FLOWER_DART};"),
    ("rotation_tables", "entity/BrideZombie.java",
     "= {400, 300, 240, 260, 220, 200, 500, 320, 180, 220, 260};",
     "= {400, 300, 240, 260, 220, 200, 500, 320, 180, 220};"),
    ("rotation_skip", "entity/BrideZombie.java",
     "            this.rotationStallTicks = 0;\n            this.rotationIndex = (this.rotationIndex + 1) % ROTATION.length;",
     "            this.rotationStallTicks = 0;"),
    ("melee_sweep", "entity/BrideZombie.java",
     "e -> e != this && e.isAlive() && (e == target || !(e instanceof Monster))",
     "e -> e != this && e.isAlive()"),
    ("melee_sweep", "entity/BrideZombie.java",
     "            // 击退是服务端改的速度：不标脏，客户端那具尸体还会站在原地\n            victim.hurtMarked = true;",
     "            // 击退不标脏（变异）"),
    ("ranged_dart", "entity/BrideZombie.java",
     "double dy = target.getEyeY() - this.getEyeY() + DART_ARC_LIFT * distance;",
     "double dy = target.getEyeY() - this.getEyeY();"),
    ("ranged_dart", "entity/BouquetProjectile.java",
     "    public BouquetProjectile(EntityType<? extends BouquetProjectile> type, Level level) {\n        super(type, level);\n    }",
     "    public BouquetProjectile(EntityType<? extends BouquetProjectile> type, Level level) {\n        super(type, level);\n        this.setNoGravity(true);\n    }"),
    ("registry_chain", "client/ClientModBusEvents.java",
     "        event.registerEntityRenderer(ModEntities.BOUQUET_PROJECTILE.get(),\n                context -> new ThrownItemRenderer<BouquetProjectile>(context, 1.0F, true));",
     "        // 渲染器被删（变异）"),
    ("registry_chain", "lang/zh_cn.json",
     '"item.apocalypse_zombies.bouquet_dart": "花束飞刺",',
     '"item.apocalypse_zombies.bouquet_dart_typo": "花束飞刺",'),
    ("clip_wiring", "entity/BrideZombie.java",
     "    public static final String ANIM_VEIL_SWIPE = \"skill_veil_swipe\";",
     "    public static final String ANIM_VEIL_SWIPE = \"skill_veil_swipe_x\";"),
    ("clip_wiring", "entity/BrideZombie.java",
     "            case FLOWER_DART -> ANIM_FLOWER_DART;",
     "            case FLOWER_DART -> ANIM_BOUQUET;"),
    ("clip_wiring", "entity/BrideZombie.java",
     "            case FLOWER_DART -> this.castFlowerDart(level);",
     "            // 结算没接（变异）"),
    ("clip_wiring", "entity/BrideZombie.java",
     "            case FLOWER_DART -> ParticleTypes.SPORE_BLOSSOM_AIR;",
     "            case FLOWER_DART -> null;"),
    ("registry_chain", "textures/item/bouquet_dart.png", "", "8,8"),
    ("move_amplitude", "tools/bride_v2.py",
     '{"y": 1.2, "z": 8.0, "x": 2.5}', '{"y": 1.2, "z": 0.9, "x": 2.5}'),
    ("move_amplitude", "tools/bride_v2.py",
     '{"y": 2.0},', '{"y": 2.0, "z": 1.5},'),
    ("move_amplitude", "animations/bride_zombie.animation.json",
     '"idle": {', '"idle_x": {'),
    ("arm_amplitude", "animations/bride_zombie.animation.json",
     "145.0", "14.0"),
    ("arm_amplitude", "animations/bride_zombie.animation.json",
     '"skill_flower_dart": {', '"skill_flower_dart_x": {'),
    ("arm_amplitude", "animations/bride_zombie.animation.json",
     '"skill_veil_chop": {', '"skill_veil_chop_x": {'),
]


def run_checks():
    """跑一遍全部断言，返回 [(检查名, 失败说明), ...]。"""
    failures = []
    for name, _label in CHECKS:
        CHECK_FUNCS[name](lambda msg, n=name: failures.append((n, msg)))
    return failures


CHECK_FUNCS = {
    "enum_append_only": check_enum_append_only,
    "rotation_tables": check_rotation_tables,
    "rotation_skip": check_rotation_skip,
    "melee_sweep": check_melee_sweep,
    "ranged_dart": check_ranged_dart,
    "registry_chain": check_registry_chain,
    "clip_wiring": check_clip_wiring,
    "move_amplitude": check_move_amplitude,
    "arm_amplitude": check_arm_amplitude,
}


def selftest():
    base = run_checks()
    if base:
        print("!! 未变异时就有失败项，先修代码：")
        for name, msg in base:
            print("   - [%s] %s" % (name, msg))
        return 1
    caught = 0
    missed = 0
    for expected, path, old, new in MUTATIONS:
        if path.endswith(".png"):
            # 贴图类变异：直接改「读到的尺寸」，不动磁盘
            PNG_OVERRIDE[path] = tuple(int(v) for v in new.split(","))
            hits = [n for n, _ in run_checks()]
            PNG_OVERRIDE.clear()
            if expected in hits:
                caught += 1
                print("  OK   %-16s 抓住 <- %s 尺寸改成 %s" % (expected, path, new))
            else:
                missed += 1
                print("  MISS %-16s 漏检 <- %s" % (expected, path))
                print("       实际报警: %s" % (hits or "无"))
            continue
        text = read_any(path)
        if old not in text:
            print("  !! 变异点找不到（校验器与代码脱节，这条变异等于没跑）: %s @ %s"
                  % (old[:48].replace("\n", "\\n"), path))
            missed += 1
            continue
        OVERRIDE[path] = text.replace(old, new, 1)
        hits = [n for n, _ in run_checks()]
        OVERRIDE.clear()
        if expected in hits:
            caught += 1
            print("  OK   %-16s 抓住 <- %s" % (expected, old[:42].replace("\n", "\\n")))
        else:
            missed += 1
            print("  MISS %-16s 漏检 <- %s" % (expected, old[:42].replace("\n", "\\n")))
            print("       实际报警: %s" % (hits or "无"))
    if missed:
        print("  !! 有 %d 条变异没被消化，变异测试不算通过" % missed)
    print("变异测试：%d/%d 被抓" % (caught, len(MUTATIONS)))
    return 0 if caught == len(MUTATIONS) else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    failures = run_checks()
    if failures:
        for name, msg in failures:
            print("FAIL [%s] %s" % (name, msg))
        return 1
    print("全部通过：" + "、".join(label for _n, label in CHECKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
