#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""骸骨射手「骨矢锁定」门禁 —— 把「看起来没问题」换成可执行的不变量。

用法:  python tools/check_marksman.py
退出码: 0 = 全部通过（含 SKIP）; 1 = 有条目 FAIL

为什么这些检查必须存在（每一条都对应一种「编译过、日志干净、游戏里却不对」的失效）：
  1. EliteAbility 靠 ordinal 联网同步：新技能插在中间，所有精英的施法状态会静默错位到别的技能上；
     反过来说，动枚举时**误删**一条既有技能同样不会报错 —— 所以既有 22 项要逐项原位比对。
  2. 「伤害 = 目标最大血量 × 比例」一旦退回固定值，「必中 + 无视护甲」就从设计变成瞬秒或挠痒，
     而且两边都能跑、都不报错。
  3. 伤害类型少挂一个标签：护甲会减伤、抗性药水会减半、保护附魔还会再减、盾牌能直接格挡 ——
     全都静默发生。**标签名写错更隐蔽**：1.20.1 里不存在的标签，整个 json 会被当成「不存在的
     标签」丢弃，功能无声失效（初版就把无敌帧标签写成了 1.20.1 没有的 bypasses_cooldown ——
     那是 1.20.5+ 才引入的），所以 c4 直接开原版数据包核对标签名。
  3b. **无敌帧不是标签能解决的**：1.20.1 的 LivingEntity.hurt() 在 invulnerableTime > 10 时
     只结算「本次伤害 − 上次伤害」的差额，而且这个分支没有任何 DamageTypeTags 能跳过
     （bypasses_invulnerability 管的是实体身上的 Invulnerable 标志，不是这个计数器）。
     实测：目标先挨 1 点普通伤害，25 点的骨矢只掉 24.0。所以 c5 盯住弹体侧必须自己把
     invulnerableTime 清零 —— 删掉那一行不会有任何报错，只会少掉「上次伤害」那一点。
  4. Config 五个键少一个，技能要么起不来，要么悄悄跑默认值（改配置的人以为自己改生效了）。
  5. 剪辑名与 Java 的 ANIM_* 常量必须双向一致：GeckoLib 找不到 clip 是**静默**的，
     模型定格在静止姿态，没有任何日志可查。
  6. 几何/动画的硬规则（rest 全零旋转、禁止 scale 通道、UV 不重叠不超界、脚底 0 / 颅顶 32）
     是「真骨骼动画」与「整体缩放假动画」的分界线，也是命中箱不漂移的前提。

几何（geo）与动画（animations）由武器线那套 Blockbench 生成器产出（见 art/marksman/DESIGN.md 开场表）：
文件还不存在时，相关项打 SKIP + WARN，不算 FAIL；文件一旦进仓库，就按下面的硬规则逐一校验。
"""
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAVA = os.path.join(ROOT, "src", "main", "java", "com", "apocalypse", "zombies")
ASSETS = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")
DATA = os.path.join(ROOT, "src", "main", "resources", "data")

ABILITY_JAVA = os.path.join(JAVA, "entity", "EliteAbility.java")
ARROW_JAVA = os.path.join(JAVA, "entity", "BoneLockArrow.java")
MARKSMAN_JAVA = os.path.join(JAVA, "entity", "MarksmanSkeleton.java")
CONFIG_JAVA = os.path.join(JAVA, "Config.java")
ENTITIES_JAVA = os.path.join(JAVA, "registry", "ModEntities.java")
EVENT_JAVA = os.path.join(JAVA, "client", "ClientModBusEvents.java")
GEOMODEL_JAVA = os.path.join(JAVA, "client", "model", "MarksmanGeoModel.java")
GEORENDERER_JAVA = os.path.join(JAVA, "client", "renderer", "MarksmanGeoRenderer.java")
OLD_MODEL_JAVA = os.path.join(JAVA, "client", "model", "MarksmanModel.java")
OLD_RENDERER_JAVA = os.path.join(JAVA, "client", "renderer", "MarksmanRenderer.java")

DAMAGE_TYPE_JSON = os.path.join(DATA, "apocalypse_zombies", "damage_type", "bone_lock.json")
TAG_DIR = os.path.join(DATA, "minecraft", "tags", "damage_type")
DESIGN = os.path.join(ROOT, "art", "marksman", "DESIGN.md")

GEO = os.path.join(ASSETS, "geo", "marksman_skeleton.geo.json")
ANIM = os.path.join(ASSETS, "animations", "marksman_skeleton.animation.json")

BONE_LOCK = "apocalypse_zombies:bone_lock"
GEO_ID = "geometry.marksman_skeleton"
TEXTURE_SIZE = 128
MODEL_HEIGHT = 32.0          # 颅顶（u）；脚底一律 0

# 设计规格「骨架树」的 27 根骨头：多一根少一根都说明几何与契约脱钩了。
DESIGN_BONES = ["root", "move", "hip", "spine", "chest", "neck", "head", "jaw",
                "cape_a", "cape_b", "cape_c", "quiver",
                "shoulder_r", "arm_r", "forearm_r", "hand_r",
                "shoulder_l", "arm_l", "forearm_l", "hand_l", "bow",
                "leg_r", "shin_r", "foot_r", "leg_l", "shin_l", "foot_l"]

# 新增技能之前必须原样存在、且保持相对顺序的 22 条既有技能（byId 靠 ordinal 联网）。
LEGACY_ABILITIES = ["NONE", "SCREAM", "SLAM", "SPIT", "SNIPE", "DEATH_CHIME", "CONSORT",
                    "SOUL_SHRIEK", "VEIL_SNARE", "SACRIFICE", "BOUQUET", "BRIDAL_KISS",
                    "BLOOD_REGEN", "VEIL_SWIPE", "FLOWER_DART", "VEIL_CHOP",
                    "BOSS_SWEEP", "BONE_VOLLEY", "RAISE_HORDE", "GROUND_QUAKE",
                    "BLOOD_RAGE", "DEATH_WAIL"]

# 五个必须挂上 bone_lock 的伤害标签（bypasses_armor 里还有既有的 awm_bullet，必须保留）：
# 护甲 / 无敌帧 / 抗性 / 保护附魔 / 盾牌。1.20.1 的无敌帧标签是 bypasses_invulnerability，
# **没有** bypasses_cooldown（1.20.5+ 才有）：写错不报错，整个标签文件被静默丢弃。
TAGS = ["bypasses_armor", "bypasses_invulnerability", "bypasses_resistance",
        "bypasses_enchantments", "bypasses_shield"]

rows = []      # (键, 名称, 状态, 说明)
fails = []     # FAIL 明细
warns = []


def load(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def flat(text):
    """压掉所有空白：Java 代码的换行/缩进不该影响字符串匹配。"""
    return re.sub(r"\s+", " ", text)


def record(key, name, ok, detail, warn=False):
    status = "WARN" if (ok and warn) else ("PASS" if ok else "FAIL")
    rows.append((key, name, status, detail))
    if not ok:
        fails.append("%s %s —— %s" % (key, name, detail))
    elif warn:
        warns.append("%s %s —— %s" % (key, name, detail))
    return ok


def skip(key, name, detail):
    rows.append((key, name, "SKIP", detail))
    warns.append("%s %s —— %s" % (key, name, detail))


def missing(path):
    record("!!", "文件缺失", False, "%s 不存在" % os.path.relpath(path, ROOT))
    return False


# ---------------------------------------------------------------------------- (a) 技能枚举
def check_ability_enum():
    """(a) BONE_LOCK 必须是**最后一条**枚举常量，且既有 22 条一个不少、相对顺序不变。

    byId(ordinal) 联网同步：插在中间会让别的精英的技能错位；误删一条既有技能同样静默出事
    （施法状态整体前移一位）。
    """
    if not os.path.isfile(ABILITY_JAVA):
        return missing(ABILITY_JAVA)
    text = load(ABILITY_JAVA)
    head = text.split("private static final EliteAbility[] BY_ID")[0]
    consts = re.findall(r"^\s{4}([A-Z][A-Z0-9_]*)\s*\(\s*-?\d", head, re.M)

    ok_legacy = consts[:len(LEGACY_ABILITIES)] == LEGACY_ABILITIES
    if ok_legacy:
        record("a2", "既有技能原位保留", True, "前 %d 条既有技能顺序与数量一致" % len(LEGACY_ABILITIES))
    else:
        record("a2", "既有技能原位保留", False,
               "既有技能被改动/删除/重排：%s" % consts[:len(LEGACY_ABILITIES) + 1])

    last_ok = bool(consts) and consts[-1] == "BONE_LOCK" and len(consts) == len(LEGACY_ABILITIES) + 1
    tail = re.search(r"BONE_LOCK\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
    if last_ok and tail and (tail.group(1), tail.group(2)) == ("42", "34"):
        record("a", "BONE_LOCK 位于枚举末尾", True, "枚举共 %d 条，最后一条 BONE_LOCK(42, 34)"
               % len(consts))
    else:
        record("a", "BONE_LOCK 位于枚举末尾", False,
               "期望 BONE_LOCK(42, 34) 是最后一条常量（当前末尾 %s，共 %d 条，匹配 %s）"
               % (consts[-1] if consts else "?", len(consts), bool(tail)))
    return last_ok


# ---------------------------------------------------------------------------- (b) 伤害公式
def check_damage_formula():
    """(b) 伤害必须是「目标最大血量 × 配置比例」，并且命中即 discard（不穿透、不调 super）。

    固定值伤害不会报错，但它会让「必中 + 无视护甲」从设计变成瞬秒或挠痒；
    super.onHitEntity 会再叠一层原版箭伤害并判穿透，与「命中即碎」矛盾。
    """
    if not os.path.isfile(ARROW_JAVA):
        return missing(ARROW_JAVA)
    text = load(ARROW_JAVA)
    flat_text = flat(text)
    formula = re.search(r"getMaxHealth\(\)\s*\*\s*(?:\(float\)\s*)?"
                        r"Config\.AI_MARKSMAN_LOCK_RATIO\.get\(\)(?:\.floatValue\(\))?",
                        text)
    problems = []
    if not formula:
        problems.append("没找到 maxHealth × Config.AI_MARKSMAN_LOCK_RATIO 形式的伤害")
    if "extends GiantArrow" not in text:
        problems.append("没有继承 GiantArrow（追踪物理不会生效）")
    if "protected void onHitEntity(EntityHitResult" not in text:
        problems.append("没有覆写 onHitEntity")
    if "super.onHitEntity" in text:
        problems.append("调用了 super.onHitEntity（会再叠一层原版箭伤害/穿透判定）")
    if "this.discard()" not in text:
        problems.append("命中后没有 discard()（会穿透）")
    if '"bone_lock"' not in text:
        problems.append("没有使用伤害类型路径 bone_lock")
    if "target.hurt(" not in flat_text:
        problems.append("没有调用 target.hurt(...)")
    if problems:
        return record("b", "骨矢伤害公式 = 最大血量 × 比例", False, "；".join(problems))
    return record("b", "骨矢伤害公式 = 最大血量 × 比例", True,
                  "maxHealth × AI_MARKSMAN_LOCK_RATIO → target.hurt(自定义伤害类型)，命中即 discard")


# ---------------------------------------------------------------------------- (c) 伤害类型与标签
def check_damage_tags():
    """(c) 伤害类型 JSON + 五个标签齐全。

    少一个标签就会被无敌帧 / 护甲 / 抗性 / 保护附魔 / 盾牌静默吃掉一部分伤害。
    盾牌那条靠 bypasses_shield 明说 —— 不能指望「不挂 is_projectile」，
    盾牌格挡并不只看 is_projectile（1.20.1 有专门的 bypasses_shield）。
    """
    if not os.path.isfile(DAMAGE_TYPE_JSON):
        return missing(DAMAGE_TYPE_JSON)
    try:
        payload = json.loads(load(DAMAGE_TYPE_JSON))
    except ValueError as exc:
        return record("c1", "伤害类型 JSON", False, "解析失败：%s" % exc)

    problems = []
    if payload.get("message_id") != "bone_lock":
        problems.append("message_id 不是 bone_lock（死亡消息会找不到键）")
    if "exhaustion" not in payload or "scaling" not in payload:
        problems.append("缺少 exhaustion / scaling（与 awm_bullet.json 的三字段格式不一致）")
    if problems:
        record("c1", "伤害类型 JSON", False, "；".join(problems))
    else:
        record("c1", "伤害类型 JSON", True,
               "message_id=bone_lock，exhaustion/scaling 与 awm_bullet 同格式")

    tag_problems = []
    for tag in TAGS:
        path = os.path.join(TAG_DIR, tag + ".json")
        if not os.path.isfile(path):
            tag_problems.append("%s.json 不存在" % tag)
            continue
        try:
            data = json.loads(load(path))
        except ValueError as exc:
            tag_problems.append("%s.json 解析失败：%s" % (tag, exc))
            continue
        values = data.get("values") or []
        if BONE_LOCK not in values:
            tag_problems.append("%s.json 里没有 %s" % (tag, BONE_LOCK))
        if data.get("replace") is not False:
            tag_problems.append("%s.json 的 replace 不是 false（会顶掉原版同标签内容）" % tag)
    armor = os.path.join(TAG_DIR, "bypasses_armor.json")
    if os.path.isfile(armor) and "apocalypse_zombies:awm_bullet" not in load(armor):
        tag_problems.append("bypasses_armor.json 丢了既有的 awm_bullet")
    if tag_problems:
        record("c2", "五个伤害标签", False, "；".join(tag_problems))
    else:
        record("c2", "五个伤害标签", True,
               "armor / invulnerability / resistance / enchantments / shield 均含 %s 且 replace:false" % BONE_LOCK)

    projectile = os.path.join(TAG_DIR, "is_projectile.json")
    if os.path.isfile(projectile) and BONE_LOCK in load(projectile):
        record("c3", "不挂 is_projectile", False,
               "bone_lock 出现在 is_projectile ⇒ 会被保护附魔等「按投射物判定」的原版逻辑重新接住")
    else:
        record("c3", "不挂 is_projectile", True, "不被当成普通箭处理；盾牌由 bypasses_shield 明确绕开")
    return not (problems or tag_problems)


def vanilla_damage_type_tags():
    """原版 1.20.1 究竟有哪些 damage_type 标签 —— 直接从 gradle 缓存里的 client.jar 读。

    返回 (标签名集合, jar 路径)；找不到 jar 返回 (None, None)。
    这个检查存在的理由：标签名写错（例如 1.20.1 根本没有的 bypasses_cooldown）**不会报任何错**，
    整个 json 被当成「不存在的标签」丢弃，护甲 / 无敌帧照旧生效，而日志干净、闸门全绿。
    """
    import glob
    import zipfile

    version_dir = os.path.expanduser(
        "~/.gradle/caches/forge_gradle/minecraft_repo/versions/1.20.1")
    candidates = sorted(glob.glob(os.path.join(version_dir, "*.jar")))
    candidates.sort(key=lambda p: 0 if "client.jar" in p else 1)
    for path in candidates:
        try:
            with zipfile.ZipFile(path) as zf:
                names = {os.path.basename(n)[:-5] for n in zf.namelist()
                         if n.startswith("data/minecraft/tags/damage_type/") and n.endswith(".json")}
        except (OSError, zipfile.BadZipFile):
            continue
        if names:
            return names, path
    return None, None


def check_tag_names():
    """(c4) 本模组发出的每个 damage_type 标签文件，名字必须真的存在于原版 1.20.1 数据包里。"""
    if not os.path.isdir(TAG_DIR):
        return record("c4", "标签名存在于原版", False, "%s 目录不存在" % os.path.relpath(TAG_DIR, ROOT))
    shipped = sorted(os.path.basename(f)[:-5] for f in os.listdir(TAG_DIR) if f.endswith(".json"))
    known, source = vanilla_damage_type_tags()
    if known is None or source is None:
        return record("c4", "标签名存在于原版", True,
                      "找不到原版 1.20.1 数据包 jar，跳过（%d 个标签未核对）" % len(shipped), warn=True)
    unknown = [t for t in shipped if t not in known]
    if unknown:
        return record("c4", "标签名存在于原版", False,
                      "1.20.1 没有这些标签：%s ⇒ 文件会被静默丢弃，减伤 / 无敌帧照旧生效"
                      % "、".join(unknown))
    return record("c4", "标签名存在于原版", True,
                  "本模组发出的 %d 个标签在原版数据包里都存在（核对源：%s）"
                  % (len(shipped), os.path.basename(source)))


def check_iframe_reset():
    """(c5) 骨矢必须自己清零目标的无敌帧计数器 —— 1.20.1 没有能跳过差额结算的标签。

    判据：`BoneLockArrow.onHitEntity` 的方法体里，`invulnerableTime = 0` 必须出现在 `hurt(`
    之前。删掉那一行既不会编译报错、也不会留下日志，只是每发少掉「上次伤害」那一点
    （实测：先挨 1 点普通伤害，25 点的骨矢只掉 24.0）—— 属于必须由闸门盯住的静默失效。
    """
    if not os.path.isfile(ARROW_JAVA):
        return missing(ARROW_JAVA)
    text = load(ARROW_JAVA)
    match = re.search(r"protected void onHitEntity\([^)]*\)\s*\{(.*?)\n    \}", text, re.S)
    if not match:
        return record("c5", "骨矢清零无敌帧计数器", False, "找不到 onHitEntity 的方法体")
    body = match.group(1)
    # 先剥注释：方法体的说明注释里就会写到 hurt(，不剥的话判序会误报（本条闸门第一次跑就是这么红的）
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    reset = body.find("invulnerableTime = 0")
    hurt = body.find("hurt(")
    if reset < 0:
        return record("c5", "骨矢清零无敌帧计数器", False,
                      "onHitEntity 里没有 invulnerableTime = 0 ⇒ 目标带着无敌帧时这一发只结算差额")
    if hurt >= 0 and reset > hurt:
        return record("c5", "骨矢清零无敌帧计数器", False,
                      "invulnerableTime = 0 写在 hurt(...) 之后 ⇒ 这一发仍然走差额结算")
    return record("c5", "骨矢清零无敌帧计数器", True,
                  "onHitEntity 先清零 invulnerableTime 再 hurt ⇒ 无敌帧不会吃掉这一发的伤害")


def check_sight_firing():
    """(c6) 「看得见就能打」这条放宽必须**存在、必须 opt-in、必须与武器射程同源**。

    射手原来是「看得见但走不到就不开火」：3 格石柱顶上的靶子（有视线、而 createPath 的终点
    永远只到地面）会占死它的目标表，45 秒一箭不放（实测）。修法是给目标调度加一条由实体
    自己声明的例外。三件事都得盯住，因为三件都会**静默**失效：

    * 删掉例外 ⇒ 退回死锁（一箭不放，日志干净）；
    * 去掉 instanceof 守卫 ⇒ 放宽变成对全体怪生效，「看得见却走不到的村民」那次死锁原样搬回来
      （近战怪重新站着发呆）；
    * sightFiringRange() 与三件武器的入参脱钩（例如手写 20，而骨矢锁定上限是 26）⇒ 调度器会把
      技能明明够得着的目标判成走不到，又退回死锁。
    """
    judge_path = os.path.join(JAVA, "entity", "ai", "PreyJudge.java")
    sight_path = os.path.join(JAVA, "entity", "ai", "SightFiring.java")
    if not os.path.isfile(MARKSMAN_JAVA):
        return missing(MARKSMAN_JAVA)
    if not os.path.isfile(judge_path):
        return missing(judge_path)
    mob = load(MARKSMAN_JAVA)
    flat_mob = flat(mob)
    judge = load(judge_path)
    problems = []

    if "implements EliteMob, GeoEntity, SightFiring" not in flat_mob:
        problems.append("MarksmanSkeleton 没有实现 SightFiring（调度器不会把它当远程怪）")
    if not os.path.isfile(sight_path):
        problems.append("entity/ai/SightFiring.java 不存在")
    elif "double sightFiringRange();" not in flat(load(sight_path)):
        problems.append("SightFiring 的契约方法不是 double sightFiringRange()")

    # 判序：「看得见就能打」必须排在「走得到」之前，否则永远轮不到它。
    # 先剥注释再判序 —— c5 第一次跑就是被方法体注释里的 hurt( 误报的。
    body = re.search(r"public boolean usable\(LivingEntity candidate\)\s*\{(.*?)\n    \}", judge, re.S)
    if not body:
        problems.append("PreyJudge.usable 的方法体没找到")
    else:
        code = re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", body.group(1)), flags=re.S)
        i_sight, i_reach = code.find("sightFiring("), code.find("reachable(")
        if i_sight < 0:
            problems.append("usable() 不再走 sightFiring() ⇒ 例外被删（退回「走不到就不打」）")
        elif i_reach >= 0 and i_sight > i_reach:
            problems.append("usable() 里 sightFiring() 排在 reachable() 之后 ⇒ 永远轮不到这条例外")

    # opt-in 守卫：缺了它，放宽会对全体怪生效。
    if "private boolean sightFiring(LivingEntity" not in flat(judge):
        problems.append("PreyJudge 里没有 sightFiring 方法")
    if "instanceof SightFiring" not in judge:
        problems.append("没有 instanceof SightFiring 守卫 ⇒ 放宽对全体怪生效（死锁会回来）")
    if "getSensing().hasLineOfSight(" not in flat(judge):
        problems.append("放宽里没有视线判定（这是这条判据的另一半）")

    # 同源：sightFiringRange() 的取值必须来自与三件武器入参**同一批常量**，且不小于骨矢锁定上限。
    consts = dict(re.findall(
        r"double\s+(BOW_RANGE|LOCK_MIN_RANGE|LOCK_MAX_RANGE|GIANT_ARROW_MIN_RANGE|GIANT_ARROW_MAX_RANGE)"
        r"\s*=\s*([0-9.]+)D", mob))
    if len(consts) != 5:
        problems.append("射程常量不全（应有 5 个）：%s" % sorted(consts))
    else:
        values = {k: float(v) for k, v in consts.items()}
        if values["GIANT_ARROW_MAX_RANGE"] < values["LOCK_MAX_RANGE"]:
            problems.append("「看得见就能打」的上限 %sD < 骨矢锁定上限 %sD ⇒ 技能够得着的目标会被判成走不到"
                            % (consts["GIANT_ARROW_MAX_RANGE"], consts["LOCK_MAX_RANGE"]))
        if values["LOCK_MIN_RANGE"] <= 0 or values["LOCK_MAX_RANGE"] <= values["LOCK_MIN_RANGE"]:
            problems.append("骨矢锁定的距离区间不合法（%sD ~ %sD）"
                            % (consts["LOCK_MIN_RANGE"], consts["LOCK_MAX_RANGE"]))
    ret = re.search(r"double sightFiringRange\(\)\s*\{\s*return ([^;]+);", mob)
    if not ret:
        problems.append("找不到 sightFiringRange() 的返回表达式")
    else:
        for name in ("GIANT_ARROW_MAX_RANGE", "LOCK_MAX_RANGE", "BOW_RANGE"):
            if name not in ret.group(1):
                problems.append("sightFiringRange() 没把 %s 算进去 ⇒ 与武器入参脱钩" % name)
    for call, msg in (("new GiantArrowGoal(this, GIANT_ARROW_MIN_RANGE, GIANT_ARROW_MAX_RANGE",
                       "重箭 Goal 的射程改回字面量了（与 sightFiringRange 脱钩）"),
                      ("new RangedBowAttackGoal<>(this, 1.0D, 20, (float) BOW_RANGE)",
                       "弓 Goal 的射程改回字面量了（与 sightFiringRange 脱钩）"),
                      ("EliteMob.hasTargetInRange(MarksmanSkeleton.this, LOCK_MIN_RANGE, LOCK_MAX_RANGE)",
                       "骨矢锁定的起手距离改回字面量了（与 sightFiringRange 脱钩）")):
        if call not in flat(mob):
            problems.append(msg)

    if problems:
        return record("c6", "看得见就能打（远程 opt-in）", False, "；".join(problems))
    return record("c6", "看得见就能打（远程 opt-in）", True,
                  "射手实现 SightFiring，射程 = max(重箭 %s / 骨矢 %s / 弓 %s)、与三件武器入参同源；"
                  "判序 贴脸→看得见就能打→走得到，且带 instanceof 守卫（近战怪不受影响）"
                  % (consts["GIANT_ARROW_MAX_RANGE"], consts["LOCK_MAX_RANGE"], consts["BOW_RANGE"]))


def check_config():
    """(d) Config 五个键：少一个要么起不来，要么悄悄跑默认值。"""
    if not os.path.isfile(CONFIG_JAVA):
        return missing(CONFIG_JAVA)
    text = flat(load(CONFIG_JAVA))
    spec = [("AI_MARKSMAN_LOCK_RATIO", "DoubleValue",
             'defineInRange("marksman_lock_ratio", 0.25D, 0.0D, 1.0D)'),
            ("AI_MARKSMAN_LOCK_COOLDOWN", "IntValue",
             'defineInRange("marksman_lock_cooldown", 160, 20, 6000)'),
            ("AI_MARKSMAN_LOCK_TURN", "DoubleValue",
             'defineInRange("marksman_lock_turn", 60.0D, 5.0D, 180.0D)'),
            ("AI_MARKSMAN_LOCK_SPEED", "DoubleValue",
             'defineInRange("marksman_lock_speed", 1.6D, 0.5D, 4.0D)'),
            ("AI_MARKSMAN_LOCK_LIFE", "IntValue",
             'defineInRange("marksman_lock_life", 100, 20, 400)')]
    problems = []
    for name, kind, define in spec:
        if ("ForgeConfigSpec.%s %s;" % (kind, name)) not in text:
            problems.append("缺少字段声明 %s（%s）" % (name, kind))
        if define not in text:
            problems.append("缺少/改动了定义 %s" % define)
    if problems:
        return record("d", "Config 五个键", False, "；".join(problems))
    return record("d", "Config 五个键", True,
                  "ratio 0.25 / cooldown 160 / turn 60° / speed 1.6 / life 100，范围与默认值一致")


# ---------------------------------------------------------------------------- (e) Java 侧接线
def check_java_wiring():
    """(e) 剪辑名、GeckoLib 接线、渲染器换绑、旧文件清理。

    剪辑名与 DESIGN.md / animation.json 不一致时 GeckoLib 静默不播（模型定格）；
    旧的原版模型/渲染器残留会让「骨骼化」变成两份模型同时存在。
    """
    problems = []
    for path in (MARKSMAN_JAVA, GEOMODEL_JAVA, GEORENDERER_JAVA, EVENT_JAVA, ENTITIES_JAVA):
        if not os.path.isfile(path):
            problems.append("%s 不存在" % os.path.relpath(path, ROOT))
    if problems:
        return record("e", "Java 接线", False, "；".join(problems))

    mob = load(MARKSMAN_JAVA)
    flat_mob = flat(mob)
    expect_anims = {"ANIM_IDLE": "idle", "ANIM_WALK": "walk",
                    "ANIM_SHOOT": "shoot", "ANIM_LOCK": "skill_bone_lock"}
    for const, value in expect_anims.items():
        if not re.search(r"String\s+%s\s*=\s*\"%s\"" % (const, value), mob):
            problems.append("%s 不是 \"%s\"" % (const, value))
    checks = [("implements EliteMob, GeoEntity" in flat_mob, "类声明不是 implements EliteMob, GeoEntity"),
              ("GeckoLibUtil.createInstanceCache(this)" in mob, "没有 GeckoLibUtil.createInstanceCache(this)"),
              (re.search(r'new AnimationController<>\(this, "movement"', mob) is not None,
               "movement 控制器缺失/改名"),
              (re.search(r'new AnimationController<>\(this, "cast"', mob) is not None,
               "cast 控制器缺失/改名"),
              ("RawAnimation.begin().thenPlay(ANIM_LOCK)" in mob, "cast 控制器没有播 ANIM_LOCK"),
              ("RawAnimation.begin().thenPlay(ANIM_SHOOT)" in mob, "cast 控制器没有播 ANIM_SHOOT（弓射动作）"),
              ("EliteAbility.BONE_LOCK" in mob, "没有引用 EliteAbility.BONE_LOCK"),
              ("EliteAbility.BONE_LOCK.getImpactTick()" in mob, "前摇粒子没有按 impactTick 截断"),
              ("Config.AI_MARKSMAN_LOCK_COOLDOWN.get()" in mob, "cooldownTicks 没读 AI_MARKSMAN_LOCK_COOLDOWN"),
              ("ParticleTypes.SOUL_FIRE_FLAME" in mob, "前摇粒子不是 SOUL_FIRE_FLAME"),
              ("BoneLockArrow.launch(" in mob, "onImpact 没有调用 BoneLockArrow.launch"),
              ("new GiantArrowGoal(" in mob, "既有重箭 Goal 被删了（check_ai_enhancements.py 会红）"),
              (".is(Items.BOW)" in mob and "setItemSlot(EquipmentSlot.MAINHAND, new ItemStack(Items.BOW))" in mob,
               "主手弓装备被改成别的（RangedBowAttackGoal 依赖它）")]
    for ok, msg in checks:
        if not ok:
            problems.append(msg)

    # 粒子必须是具名常量，不许散落内联字面量。
    if not re.search(r"ParticleOptions\s+WINDUP_PARTICLE\s*=\s*ParticleTypes\.SOUL_FIRE_FLAME", mob):
        problems.append("前摇粒子不是具名常量（照 DeathMarkEffect.MARK_PARTICLE 的写法）")

    geo_model = load(GEOMODEL_JAVA)
    for need, msg in ((r"geo/marksman_skeleton\.geo\.json", "模型资源路径不对"),
                      (r"textures/entity/marksman_skeleton\.png", "贴图资源路径不对"),
                      (r"animations/marksman_skeleton\.animation\.json", "动画资源路径不对"),
                      (r"RenderType\.entityCutoutNoCull", "RenderType 不是 entityCutoutNoCull")):
        if not re.search(need, geo_model):
            problems.append(msg)
    if not re.search(r"MODEL_HEIGHT\s*=\s*%sF" % MODEL_HEIGHT, geo_model):
        problems.append("MarksmanGeoModel.MODEL_HEIGHT 不是 %s（应与几何颅顶一致）" % MODEL_HEIGHT)

    if not re.search(r"shadowRadius\s*=\s*0\.5F", load(GEORENDERER_JAVA)):
        problems.append("MarksmanGeoRenderer.shadowRadius 不是 0.5")

    event = load(EVENT_JAVA)
    if "MarksmanGeoRenderer::new" not in event:
        problems.append("ClientModBusEvents 没有换绑 MarksmanGeoRenderer")
    if "MarksmanModel" in event or "MarksmanRenderer" in event:
        problems.append("ClientModBusEvents 还引用着已删除的 MarksmanModel / MarksmanRenderer")
    if "ModEntities.BONE_LOCK_ARROW.get()" not in event:
        problems.append("ClientModBusEvents 没有给 BONE_LOCK_ARROW 注册渲染器（客户端会崩）")
    if "ModEntities.GIANT_ARROW.get(), GiantArrowRenderer::new" not in event:
        problems.append("重箭渲染注册被改动了（check_ai_enhancements.py 会红）")

    entities = load(ENTITIES_JAVA)
    if '"bone_lock_arrow"' not in entities or "EntityType<BoneLockArrow>" not in entities:
        problems.append("ModEntities 没有注册 bone_lock_arrow / EntityType<BoneLockArrow>")

    for old in (OLD_MODEL_JAVA, OLD_RENDERER_JAVA):
        if os.path.isfile(old):
            problems.append("%s 还在（应删除）" % os.path.relpath(old, ROOT))

    if problems:
        return record("e", "Java 接线（剪辑名 / 渲染 / 弹体）", False, "；".join(problems))
    record("e", "Java 接线（剪辑名 / 渲染 / 弹体）", True,
           "ANIM_* ↔ 控制器 ↔ 资源路径 ↔ 渲染换绑 一致，旧模型/渲染器已删")
    if os.path.isfile(DESIGN):
        design = load(DESIGN)
        bad = [v for v in expect_anims.values() if v not in design]
        record("e2", "剪辑名 ↔ DESIGN.md", not bad,
               "四个 clip 名都在设计规格里" if not bad else "设计规格里找不到 %s" % bad)
    else:
        skip("e2", "剪辑名 ↔ DESIGN.md", "art/marksman/DESIGN.md 不存在，跳过双向核对")
    return not problems


# ---------------------------------------------------------------------------- (f) 几何 / 动画
def cube_bounds(origin, size):
    lo = [origin[i] if size[i] >= 0 else origin[i] + size[i] for i in range(3)]
    hi = [origin[i] + size[i] if size[i] >= 0 else origin[i] for i in range(3)]
    return lo, hi


def check_geo(bones):
    """几何硬规则：rest 全零旋转 / 禁 scale / UV 不超界不重叠 / 脚底 0 / 颅顶 32 / 27 骨齐全。

    这几条是「真骨骼」与「整体缩放假动画」的分界，也是命中箱不漂移的前提
    （模型总高 32u = 2.0 格，与原版骷髅同级，所以 ModEntities 的 sized() 不用动）。
    """
    names = [b.get("name") for b in bones]
    problems = []
    absent = [n for n in DESIGN_BONES if n not in names]
    if absent:
        problems.append("缺少设计规格里的骨头 %s" % absent)
    if len(names) != len(DESIGN_BONES):
        problems.append("骨头数 %d ≠ 设计规格的 %d" % (len(names), len(DESIGN_BONES)))

    for b in bones:
        rot = b.get("rotation") or (0, 0, 0)
        if any(abs(float(v)) > 1e-9 for v in rot):
            problems.append("骨头 %s 带静态旋转（rest 必须全零）" % b.get("name"))
        if "scale" in b:
            problems.append("骨头 %s 带 scale 通道（禁止）" % b.get("name"))
        for c in b.get("cubes", []):
            if "scale" in c:
                problems.append("骨头 %s 的体块带 scale（禁止）" % b.get("name"))
            if any(float(s) <= 0 for s in c.get("size", [])):
                problems.append("骨头 %s 的体块 size 出现非正数" % b.get("name"))

    ymin, ymax = 1e9, -1e9
    rects = []
    for b in bones:
        for idx, c in enumerate(b.get("cubes", [])):
            lo, hi = cube_bounds(c["origin"], c["size"])
            ymin, ymax = min(ymin, lo[1]), max(ymax, hi[1])
            uv = c.get("uv")
            if isinstance(uv, dict):
                for face, spec in uv.items():
                    u, v = spec["uv"]
                    du, dv = spec["uv_size"]
                    rects.append((b["name"], idx, face, float(u), float(v),
                                  float(u) + float(du), float(v) + float(dv)))
            elif isinstance(uv, list):
                problems.append("骨头 %s 的体块用 box_uv（设计规格要求逐面 UV 图集）" % b["name"])
    if abs(ymin) > 1e-9:
        problems.append("脚底 minY = %s（必须 0）" % ymin)
    if abs(ymax - MODEL_HEIGHT) > 1e-9:
        problems.append("颅顶 maxY = %s（必须 %s）" % (ymax, MODEL_HEIGHT))

    for name, idx, face, u0, v0, u1, v1 in rects:
        if u0 < 0 or v0 < 0 or u1 > TEXTURE_SIZE or v1 > TEXTURE_SIZE:
            problems.append("UV 超界：%s 体块%d %s 面 (%s,%s)-(%s,%s)"
                            % (name, idx, face, u0, v0, u1, v1))
    for a, b in itertools.combinations(rects, 2):
        if a[3] < b[5] and b[3] < a[5] and a[4] < b[6] and b[4] < a[6]:
            problems.append("UV 重叠：%s/%s 与 %s/%s"
                            % (a[0], a[2], b[0], b[2]))

    return problems, len(rects)


def check_geo_file():
    """(f) geo 存在就必须过硬规则；不存在则 SKIP（生成器在另一条线上）。"""
    if not os.path.isfile(GEO):
        skip("f1", "几何契约（geo）", "geo/marksman_skeleton.geo.json 还不存在（生成器由主线另一位同事做）")
        return True
    try:
        payload = json.loads(load(GEO))
    except ValueError as exc:
        return record("f1", "几何契约（geo）", False, "geo 解析失败：%s" % exc)
    geometry = payload["minecraft:geometry"][0]
    desc = geometry.get("description", {})
    problems = []
    if desc.get("identifier") != GEO_ID:
        problems.append("identifier 不是 %s" % GEO_ID)
    if (desc.get("texture_width"), desc.get("texture_height")) != (TEXTURE_SIZE, TEXTURE_SIZE):
        problems.append("贴图尺寸不是 %d×%d" % (TEXTURE_SIZE, TEXTURE_SIZE))
    geo_problems, faces = check_geo(geometry.get("bones", []))
    problems.extend(geo_problems)
    if problems:
        return record("f1", "几何契约（geo）", False, "；".join(problems))
    return record("f1", "几何契约（geo）", True,
                  "27 骨 / %d 个面：rest 全零旋转、无 scale、UV 不重叠不超界、脚底 0 颅顶 %g"
                  % (faces, MODEL_HEIGHT))


def keyframe_times(anim):
    """把一段 clip 里所有通道的时间戳抽出来（值里存的是秒，字典键就是时间）。"""
    stamps = []
    for channels in (anim.get("bones") or {}).values():
        for channel in channels.values():
            if isinstance(channel, dict):
                for stamp in channel:
                    try:
                        stamps.append(float(stamp))
                    except (TypeError, ValueError):
                        pass
    return sorted(set(stamps))


def check_anim_file(bones):
    """(f2) 动画存在就必须：无 scale 通道、四个 clip 齐全、clip 里的骨头都在几何里、
    skill_bone_lock 的关键帧落在 1.7s（impactTick=34）。"""
    if not os.path.isfile(ANIM):
        skip("f2", "动画契约（anim）",
             "animations/marksman_skeleton.animation.json 还不存在 —— 需要 tools/marksman_bb_anim.js "
             "+ tools/marksman_anim.py 那一线产出；在它进仓库前，模型会以静止姿态渲染（GeckoLib 静默降级）")
        return True
    try:
        payload = json.loads(load(ANIM))
    except ValueError as exc:
        return record("f2", "动画契约（anim）", False, "动画解析失败：%s" % exc)

    clips = {}
    for key, anim in (payload.get("animations") or {}).items():
        if isinstance(anim, dict):
            # clip 名就是字典的键（Blockbench 导出 'idle' 或 'animation.<模型>.<clip>'）。
            # 故意不用 next(iter(...)) 兜底：那会给每个 clip 安上「第一个 clip 的名字」，
            # 于是四个 clip 一起报错，真正错的那个反而看不出来。
            clips[anim.get("name") or key.split(".")[-1]] = anim
    expected = {"idle": 3.0, "walk": 1.0, "shoot": 0.9, "skill_bone_lock": 2.1}
    problems = []
    if not bones:
        problems.append("几何骨头列表为空 ⇒ 无法核对 clip 里的骨头名")
    for name, length in expected.items():
        anim = clips.get(name)
        if anim is None:
            problems.append("缺少 clip %s" % name)
            continue
        if abs(float(anim.get("animation_length", 0)) - length) > 0.05:
            problems.append("clip %s 时长 %s ≠ %s s" % (name, anim.get("animation_length"), length))
        for bone, channels in (anim.get("bones") or {}).items():
            if bones and bone not in bones:
                problems.append("clip %s 里的骨头 %s 不在几何里（GeckoLib 会静默忽略）" % (name, bone))
            if channels.get("scale"):
                problems.append("clip %s 的骨头 %s 带 scale 通道（禁止）" % (name, bone))
    lock = clips.get("skill_bone_lock")
    if lock:
        lock_bones = set((lock.get("bones") or {}).keys())
        need = {"arm_l", "forearm_r", "jaw", "head"}
        if not need <= lock_bones:
            problems.append("skill_bone_lock 没有驱动 %s" % sorted(need - lock_bones))
        if "bow" not in lock_bones:
            problems.append("skill_bone_lock 没有驱动 bow（举弓前摇看不出是这一招）")
        stamps = keyframe_times(lock)
        if not any(abs(t - 1.7) <= 0.01 for t in stamps):
            problems.append("skill_bone_lock 没有 1.7s 那一帧（与 impactTick=34 对不上）")
        latest = max(stamps) if stamps else 0.0
        if abs(latest - 2.1) > 0.05:
            problems.append("skill_bone_lock 的最晚关键帧 %s ≠ 2.1s（收招没落完）" % latest)
    if problems:
        return record("f2", "动画契约（anim）", False, "；".join(problems))
    return record("f2", "动画契约（anim）", True,
                  "四个 clip 齐全、无 scale 通道、骨头全在几何里、命中点落 1.7s")


# ---------------------------------------------------------------------------- 输出
def dwidth(text):
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def pad(text, width):
    return text + " " * max(1, width - dwidth(text))


def report():
    print("=" * 92)
    print("骸骨射手「骨矢锁定」门禁 · tools/check_marksman.py")
    print("=" * 92)
    print("%-5s %-34s %-6s %s" % ("检查", "项目", "结论", "说明"))
    print("-" * 92)
    for key, name, status, detail in rows:
        print("%-5s %s %-6s %s" % (key, pad(name, 34), status, detail))
    print("-" * 92)
    counted = {}
    for _, _, status, _ in rows:
        counted[status] = counted.get(status, 0) + 1
    print("合计：PASS %d / FAIL %d / SKIP %d" %
          (counted.get("PASS", 0) + counted.get("WARN", 0), counted.get("FAIL", 0),
           counted.get("SKIP", 0)))
    for w in warns:
        print("WARN  " + w)
    if fails:
        for f in fails:
            print("FAIL  " + f)
        print("\nCHECK FAIL：%d 项" % len(fails))
        return 1
    print("\nCHECK PASS：骸骨射手骨骼化 + 骨矢锁定契约成立（伤害 = 目标最大血量 × 比例，"
          "命中即碎并绕过护甲 / 无敌帧 / 抗性 / 保护附魔）")
    return 0


def main():
    check_ability_enum()
    check_damage_formula()
    check_damage_tags()
    check_tag_names()
    check_iframe_reset()
    check_sight_firing()
    check_config()
    check_java_wiring()
    check_geo_file()
    bones = []
    if os.path.isfile(GEO):
        try:
            bones = [b.get("name") for b in
                     json.loads(load(GEO))["minecraft:geometry"][0].get("bones", [])]
        except (ValueError, KeyError, TypeError):
            bones = []
    check_anim_file(bones)
    return report()


if __name__ == "__main__":
    sys.exit(main())
