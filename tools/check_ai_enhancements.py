#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 增强（1.1.29）静态校验器。

查的是「接线有没有接上」，不是「代码写得对不对」—— 编译管后者，这里管前者。
逐条：配置项被读、Goal 被挂、实体注册 + 渲染器齐、NBT 读写成对、渲染器带缩放回退、
村民走 Brain 而不是 goalSelector、目标调度器不许把「看得见够不着」的东西锁成死锁。

每条都做成「对着源码文本断言」，因此可以 --selftest：在内存里改坏一处，
校验器必须报错。变异测试跑不过，这个校验器就等于不存在。

用法：
    python tools/check_ai_enhancements.py            # 查现场
    python tools/check_ai_enhancements.py --selftest # 查 + 变异测试
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "main" / "java"
PKG = SRC / "com" / "apocalypse" / "zombies"

CONFIG_JAVA = "com/apocalypse/zombies/Config.java"
AI_EVENT_JAVA = "com/apocalypse/zombies/event/MobAiEnhanced.java"
ENTITIES_JAVA = "com/apocalypse/zombies/registry/ModEntities.java"
RENDERERS_JAVA = "com/apocalypse/zombies/client/ClientModBusEvents.java"
GIANT_ARROW_JAVA = "com/apocalypse/zombies/entity/GiantArrow.java"
GIANT_RENDERER_JAVA = "com/apocalypse/zombies/client/renderer/GiantArrowRenderer.java"
MARKSMAN_JAVA = "com/apocalypse/zombies/entity/MarksmanSkeleton.java"
KEEPDISTANCE_JAVA = "com/apocalypse/zombies/entity/KeepDistanceGoal.java"
SURROUND_JAVA = "com/apocalypse/zombies/entity/ai/SurroundGoal.java"
PREY_TARGET_JAVA = "com/apocalypse/zombies/entity/ai/PreyTargetGoal.java"
PREY_JUDGE_JAVA = "com/apocalypse/zombies/entity/ai/PreyJudge.java"
SHARED_AGGRO_JAVA = "com/apocalypse/zombies/entity/ai/SharedAggroGoal.java"
AI_DIR = PKG / "entity" / "ai"

# 原版箭尖在实体位置前方的距离（格）：ArrowRenderer 模型头端 translate(-4,0,0) 之后局部 x=-12，
# 再乘 0.05625 的顶点比例 ⇒ 0.675。放大必须沿视线回退 (scale-1)*0.675，否则箭尖越过命中点。
ARROW_TIP_AHEAD = "0.675"

# 分支开关：关掉任何一个，它那一段就该整体失效（这里只断言开关本身被读）
BRANCH_SWITCHES = [
    "AI_HOSTILE_ENABLED",
    "AI_SKELETON_ENABLED",
    "AI_VILLAGER_ENABLED",
    "AI_GOLEM_ENABLED",
]


class Sources:
    """源码读取层。独立成类是为了变异测试能替换它而不碰磁盘。"""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self._cache: dict[str, str] = {}

    def text(self, rel: str) -> str:
        if rel not in self._cache:
            path = self.root / "src" / "main" / "java" / rel
            self._cache[rel] = path.read_text(encoding="utf-8", errors="replace")
        return self._cache[rel]

    def all_java(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in (self.root / "src" / "main" / "java").rglob("*.java"):
            rel = path.relative_to(self.root / "src" / "main" / "java").as_posix()
            out[rel] = self.text(rel)
        return out


def parse_ai_config(sources: Sources) -> dict[str, str]:
    """从 Config.java 的 ai_enhance 段解析 {字段名: 配置键}。

    不按 ';' 切语句：注释文本里出现过分号（"…hostiles alike; flying mobs…"），
    按分号切会把一条 define 拦腰截断。改为「字段名到下一个字段名之间」当一个体。
    """
    text = sources.text(CONFIG_JAVA)
    start = text.find('push("ai_enhance")')
    if start < 0:
        raise AssertionError("Config.java 里找不到 ai_enhance 段")
    end = text.find("SPEC = b.build();", start)
    if end < 0:
        raise AssertionError("ai_enhance 段没有在 SPEC = b.build() 前收尾")
    section = text[start:end]

    fields = list(re.finditer(r"\b(AI_[A-Z0-9_]+)\s*=", section))
    if not fields:
        raise AssertionError("ai_enhance 段里一个 AI_* 字段都没解析到")

    pairs: dict[str, str] = {}
    for index, field in enumerate(fields):
        stop = fields[index + 1].start() if index + 1 < len(fields) else len(section)
        body = section[field.end():stop]
        key = re.search(r'\.define(?:InRange|List)?\(\s*"([a-z0-9_]+)"', body)
        if not key:
            raise AssertionError("ai_enhance 段里 %s 的体里没有 define* 键名" % field.group(1))
        pairs[field.group(1)] = key.group(1)
    return pairs


def check_config_is_read(sources: Sources, failures: list[str]) -> None:
    pairs = parse_ai_config(sources)
    if len(pairs) < 20:
        failures.append("ai_enhance 配置项只有 %d 个，比预期少（是不是漏了 define）" % len(pairs))
    others = {rel: txt for rel, txt in sources.all_java().items() if rel != CONFIG_JAVA}
    blob = "\n".join(others.values())
    for field, key in sorted(pairs.items()):
        if ("Config." + field) not in blob:
            failures.append("配置项 ai_enhance.%s（字段 %s）没有任何 Java 读它" % (key, field))
    for switch in BRANCH_SWITCHES:
        if switch not in pairs:
            failures.append("缺少分支开关 %s（关不掉的分支等于永远开着的分支）" % switch)


def check_goals_are_attached(sources: Sources, failures: list[str]) -> None:
    # 只把真正的 Goal 算进来：entity/ai/ 下允许放非 Goal 的判据类（如 PreyJudge），
    # 但它们必须被别处用到 —— 写了没人用的判据类同样是静默失效。
    goals = sorted(path.stem for path in AI_DIR.glob("*.java")
                   if re.search(r"\bextends\s+Goal\b",
                                path.read_text(encoding="utf-8", errors="replace")))
    if len(goals) < 5:
        failures.append("entity/ai/ 下只有 %d 个 Goal，比预期少" % len(goals))
    others = {rel: txt for rel, txt in sources.all_java().items()
              if not rel.startswith("com/apocalypse/zombies/entity/ai/")}
    blob = "\n".join(others.values())
    for goal in goals:
        if goal not in blob:
            failures.append("Goal %s 在 entity/ai/ 之外没有任何引用 ⇒ 写了但没挂上" % goal)
    for path in sorted(AI_DIR.glob("*.java")):
        if path.stem in goals:
            continue
        # 非 Goal 的判据类（如 PreyJudge）：允许只被同目录的 Goal 用，但不能是死代码 ——
        # 类名在整棵源码树里只出现一次（就是它自己的声明）= 写了没人用。
        hits = len(re.findall(r"\b%s\b" % re.escape(path.stem),
                              "\n".join(sources.all_java().values())))
        if hits <= 1:
            failures.append("entity/ai/%s 不是 Goal、也没有第二个文件引用它 ⇒ 写了没人用（死代码）"
                            % path.stem)

    event = sources.text(AI_EVENT_JAVA)
    # 每个 Goal 都必须在事件层接线：贴在别的文件里（比如某个实体自己 registerGoals）
    # 不算数 —— 那样普通骷髅就漏掉了，而且是静默漏掉。
    for goal in goals:
        if ("%s.class" % goal) not in event:
            failures.append("Goal %s 没有在 event/MobAiEnhanced 里挂上（写了但没接线）" % goal)
    if len(re.findall(r"\.addGoal\(", event)) != 1:
        failures.append("MobAiEnhanced 里的 addGoal( 出现次数不是 1 ⇒ 有 Goal 绕过 addOnce 挂上去了"
                        "（区块反复加载会越挂越多）")


def check_entity_wiring(sources: Sources, failures: list[str]) -> None:
    entities = sources.text(ENTITIES_JAVA)
    if '"giant_arrow"' not in entities or "EntityType<GiantArrow>" not in entities:
        failures.append("ModEntities 里没有注册 giant_arrow")
    renderers = sources.text(RENDERERS_JAVA)
    if "ModEntities.GIANT_ARROW.get()" not in renderers:
        failures.append("ClientModBusEvents 里没有给 GIANT_ARROW 注册渲染器 ⇒ 客户端会崩")
    if "GiantArrowRenderer" not in renderers:
        failures.append("ClientModBusEvents 里没有引用 GiantArrowRenderer")


def check_nbt_paired(sources: Sources, failures: list[str]) -> None:
    text = sources.text(GIANT_ARROW_JAVA)
    written = set(re.findall(r'\b\w+\.put\w+\(\s*"([A-Za-z0-9_]+)"', text))
    read = set(re.findall(r'\b\w+\.get\w+\(\s*"([A-Za-z0-9_]+)"', text))
    if not written or not read:
        failures.append("GiantArrow 的 NBT 键一个都没抓到 ⇒ 匹配方式过期了")
        return
    for key in sorted(written - read):
        failures.append("GiantArrow 写了 NBT 键 %s 但从不读它（存档里是死数据）" % key)
    for key in sorted(read - written):
        failures.append("GiantArrow 读 NBT 键 %s 但从不写它（读出来永远是默认值）" % key)


def check_event_listener_registered(sources: Sources, failures: list[str]) -> None:
    """整类必须真的挂在事件总线上。

    这是最阴的一种失效：代码全对、编译全过、检查全绿，只因为漏了一个类注解，
    游戏里一点反应都没有 —— 而且没有任何日志。
    """
    text = sources.text(AI_EVENT_JAVA)
    # 行首锚定：注释掉的 // @Mod.EventBusSubscriber( 不能算数（变异测试抓过这个洞）
    if not re.search(r"^\s*@Mod\.EventBusSubscriber\(", text, re.M):
        failures.append("MobAiEnhanced 没有 @Mod.EventBusSubscriber ⇒ 整类不会被调用，AI 增强全静默失效")
    n = len(re.findall(r"^\s*@SubscribeEvent", text, re.M))
    if n < 3:
        failures.append("MobAiEnhanced 只订阅了 %d 个事件（期望 ≥3：加入世界 / 刷怪 / 每 tick）" % n)
    for ev in ("EntityJoinLevelEvent", "FinalizeSpawn", "LivingTickEvent"):
        if ev not in text:
            failures.append("MobAiEnhanced 没有订阅 %s" % ev)


def check_move_goals_hand_off(sources: Sources, failures: list[str]) -> None:
    """站位/包抄类 Goal 必须把 MOVE 交还出去。

    这条是踩出来的：只要 canUse 写成「有目标就为真」，该 Goal 就永久占着 MOVE，
    同一只怪身上优先级更低的攻击 Goal（弓箭 Goal 也要 MOVE）一箭都放不出来 —— 而且是静默的，
    编译过、日志干净、看上去只是「怪不射箭」。
    """
    text = sources.text(KEEPDISTANCE_JAVA)
    body = re.search(r"public boolean canUse\(\)\s*\{(.*?)\n    \}", text, re.S)
    if not body or "outOfBand" not in body.group(1):
        failures.append("KeepDistanceGoal.canUse 不是按距离判定 ⇒ 会永久霸占 MOVE，"
                        "同实体上优先级更低的弓箭 Goal 一箭都放不出来")

    surround = sources.text(SURROUND_JAVA)
    body = re.search(r"public boolean canUse\(\)\s*\{(.*?)\n    \}", surround, re.S)
    flat = re.sub(r"\s+", " ", body.group(1)) if body else ""
    if "distance > this.engage" not in flat:
        failures.append("SurroundGoal.canUse 没有要求「还没贴身」⇒ 它跟近战 Goal 抢不到 MOVE，等于死代码")
    if not re.search(r"addOnce\(monster\.goalSelector,\s*1,\s*SurroundGoal\.class",
                     sources.text(AI_EVENT_JAVA)):
        failures.append("SurroundGoal 的优先级不是 1 ⇒ 会被原版近战 Goal（僵尸 2 / 蜘蛛 3）永久挡住 MOVE")


def check_renderer_backoff(sources: Sources, failures: list[str]) -> None:
    text = sources.text(GIANT_RENDERER_JAVA)
    # 钉在常量声明上，不是钉在「文件里出现过 0.675」上 —— 注释里也写着这个数，
    # 只查字符串的话，把代码里的值改成 0 也能过（变异测试就是这么抓出来的）。
    if not re.search(r"TIP_AHEAD\s*=\s*" + re.escape(ARROW_TIP_AHEAD) + r"D?\s*;", text):
        failures.append("GiantArrowRenderer 的 TIP_AHEAD 不是 %s ⇒ 放大后箭尖会越过命中点"
                        % ARROW_TIP_AHEAD)
    for need in ("pushPose", "popPose", "scale", "AI_GIANT_ARROW_SCALE"):
        if need not in text:
            failures.append("GiantArrowRenderer 缺少 %s" % need)


def check_villager_uses_brain(sources: Sources, failures: list[str]) -> None:
    """村民走 Brain：给它加 goalSelector 的 Goal 等于没加。"""
    event = sources.text(AI_EVENT_JAVA)
    if "getBrain()" not in event:
        failures.append("MobAiEnhanced 没有通过 getBrain() 影响村民 ⇒ 村民那一支是无效的")
    if "Activity.PANIC" not in event:
        failures.append("MobAiEnhanced 没有把村民切进 PANIC 活动")
    if re.search(r"Villager[^\n]{0,80}goalSelector", event) or \
            re.search(r"villager\.goalSelector", event):
        failures.append("MobAiEnhanced 用 goalSelector 改村民 ⇒ 村民是 Brain 驱动的，这条永远不会生效")
    villager_owned = []
    for path in sorted(AI_DIR.glob("*.java")):
        body = path.read_text(encoding="utf-8", errors="replace")
        # 只看构造函数签名：Goal 的宿主必须是个 Mob；拿 Villager 当宿主 = 永远不会被 AI 调度
        for ctor in re.finditer(r"public\s+%s\s*\(([^)]*)\)" % re.escape(path.stem), body):
            if re.search(r"\bVillager\b", ctor.group(1)):
                villager_owned.append(path.stem)
    if villager_owned:
        failures.append("entity/ai/ 下有以 Villager 为宿主的 Goal %s ⇒ 村民不吃 Goal，这段不会跑"
                        % villager_owned)


def check_marksman_elite(sources: Sources, failures: list[str]) -> None:
    text = sources.text(MARKSMAN_JAVA)
    if "new GiantArrowGoal(" not in text:
        failures.append("MarksmanSkeleton 没有挂重箭 Goal ⇒ 精英那一档没落地")
    event = sources.text(AI_EVENT_JAVA)
    if "MarksmanSkeleton" not in event:
        failures.append("MobAiEnhanced 没排除 MarksmanSkeleton ⇒ 精英会同时挂两段重箭逻辑")


def check_prey_director(sources: Sources, failures: list[str]) -> None:
    """目标死锁（1.1.34 修的缺陷）的护栏。

    缺陷现场：她锁上「看得见但走不到」的东西（柱顶村民 / 飞在天上的玩家）之后，TARGET
    标志位被占死 —— 技能起手要视线、近战要距离、原版那三条目标（玩家 / 村民 / 铁傀儡）
    全都起不来 ⇒ 她站在村民/铁傀儡旁边一动不动，一下都不打。运行时判据：
    `tools/bride_aggro_probe.py --scenario perch`（修前冻结期 0.0 伤害，修后正常打死）。

    三条要点，任何一条退回原样死锁就会复活：
    """
    judge = sources.text(PREY_JUDGE_JAVA)
    if not re.search(r"\bboolean usable\(", judge):
        failures.append("PreyJudge 里没有 usable 判据 ⇒ 谁来判断「用得上」")
    if "hasLineOfSight" in judge:
        failures.append("PreyJudge 的判据里出现了视线 ——「看得见就算用得上」正是那个死锁"
                        "（柱顶村民看得见却走不到），判据只能是「走得到」")
    if "createPath" not in judge:
        failures.append("PreyJudge 没做路径判定 ⇒ 够不着的目标又会被当成可用")
    if "Math.abs(dy)" not in judge:
        failures.append("PreyJudge 的路径判据没比高度：原版 canReachTarget 只比 x/z，"
                        "柱子底部与柱顶 x/z 相同 ⇒「要爬 5 格」的目标会被判成走得到")

    director = sources.text(PREY_TARGET_JAVA)
    if not re.search(r"if \(this\.anyPrey\) \{\s*this\.mob\.setTarget\(null\);\s*return true;",
                     director):
        failures.append("PreyTargetGoal 没有「空转」分支（没有可用猎物时占着 TARGET 但目标置空）"
                        "⇒ 一放手，原版村民目标就会把够不着的锁回去，死锁复活")
    if not re.search(r"addOnce\(monster\.targetSelector,\s*1,\s*PreyTargetGoal\.class",
                     sources.text(AI_EVENT_JAVA)):
        failures.append("PreyTargetGoal 的优先级不是 1（要在同伴传仇恨 0 之下、原版玩家 2 之上）"
                        "⇒ 要么抢不掉原版那三条目标，要么挡住同伴传仇恨")
    if "judge.usable(this.shared)" not in sources.text(SHARED_AGGRO_JAVA):
        failures.append("SharedAggroGoal 没有用同一套「用得上」判据复核目标 ⇒ 同伴传过来的"
                        "够不着目标照样会把 TARGET 占死")
    if (AI_DIR / "ScentTargetGoal.java").exists():
        failures.append("ScentTargetGoal 还在：它就是 mustSee / mustReach 全 false 的死锁源，"
                        "应已被 PreyTargetGoal 取代")


def run(sources: Sources) -> list[str]:
    failures: list[str] = []
    for check in (check_config_is_read, check_goals_are_attached, check_entity_wiring,
                  check_nbt_paired, check_renderer_backoff, check_villager_uses_brain,
                  check_event_listener_registered, check_prey_director,
                  check_move_goals_hand_off, check_marksman_elite):
        check(sources, failures)
    return failures


class MutatedSource(Sources):
    def __init__(self, rel: str, old: str, new: str, count: int = 1):
        super().__init__()
        self._rel = rel
        self._old = old
        self._new = new
        self._count = count

    def text(self, rel: str) -> str:
        text = super().text(rel)
        if rel != self._rel:
            return text
        if self._old not in text:
            raise AssertionError("变异测试的靶子找不到：%s 里没有 %r" % (rel, self._old))
        return text.replace(self._old, self._new, self._count)


MUTATIONS = [
    ("删掉重箭渲染器注册",
     MutatedSource(RENDERERS_JAVA,
                   "event.registerEntityRenderer(ModEntities.GIANT_ARROW.get(), GiantArrowRenderer::new);",
                   "")),
    ("把普通骷髅的重箭 Goal 名字改坏",
     MutatedSource(AI_EVENT_JAVA, "GiantArrowGoal.class", "SomethingElse.class")),
    ("删掉重箭 NBT 的写入",
     MutatedSource(GIANT_ARROW_JAVA, 'putInt("GiantSeeker"', 'putInt("GiantSeekerXXX"')),
    ("去掉箭尖回退常量（改代码里的值，不是注释）",
     MutatedSource(GIANT_RENDERER_JAVA, "TIP_AHEAD = %sD" % ARROW_TIP_AHEAD,
                   "TIP_AHEAD = 0.0D")),
    ("给村民改成挂 goalSelector（村民不吃这一套）",
     MutatedSource(AI_EVENT_JAVA, "villager.getBrain()", "villager.goalSelector")),
    ("KeepDistanceGoal 退回成「只看有没有目标」",
     MutatedSource(KEEPDISTANCE_JAVA, "return this.outOfBand();",
                   "return this.mob.getTarget() != null;", 1)),
    ("SurroundGoal 的 canUse 反回「贴身时才跑」",
     MutatedSource(SURROUND_JAVA, "distance > this.engage && distance <=",
                   "distance < this.engage && distance <=")),
    ("包抄 Goal 挂到近战之后（拿不到 MOVE）",
     MutatedSource(AI_EVENT_JAVA, "addOnce(monster.goalSelector, 1, SurroundGoal.class",
                   "addOnce(monster.goalSelector, 5, SurroundGoal.class")),
    ("把事件订阅类的类注解注释掉（整类静默失效）",
     MutatedSource(AI_EVENT_JAVA, "@Mod.EventBusSubscriber(", "// @Mod.EventBusSubscriber(")),
    ("目标判据退回成「看得见就算用得上」（死锁本尊）",
     MutatedSource(PREY_JUDGE_JAVA,
                   "|| this.reachable(candidate);",
                   "|| this.mob.getSensing().hasLineOfSight(candidate);")),
    ("目标判据的路径检查丢掉高度比较（柱顶村民会被判成走得到）",
     MutatedSource(PREY_JUDGE_JAVA, "&& Math.abs(dy) <= 1", "")),
    ("调度器挂到原版那三条目标之后（抢不掉死锁）",
     MutatedSource(AI_EVENT_JAVA, "targetSelector, 1, PreyTargetGoal.class",
                   "targetSelector, 3, PreyTargetGoal.class")),
    ("去掉空转分支（没可用猎物就放手，死锁立刻复活）",
     MutatedSource(PREY_TARGET_JAVA,
                   "        if (this.anyPrey) {\n"
                   "            this.mob.setTarget(null);\n"
                   "            return true;\n"
                   "        }\n"
                   "        return false;",
                   "        return false;")),
    ("同伴传仇恨不再复核「用得上」",
     MutatedSource(SHARED_AGGRO_JAVA, "\n                && this.judge.usable(this.shared)", "")),
]


def selftest() -> int:
    bad = 0
    for name, sources in MUTATIONS:
        try:
            failures = run(sources)
        except AssertionError as exc:
            print("  [变异测试] %-38s 靶子失效：%s" % (name, exc))
            bad += 1
            continue
        if failures:
            print("  [变异测试] %-38s 被抓住（%s）" % (name, failures[0][:60]))
        else:
            print("  [变异测试] %-38s 没抓住 ⇒ 校验器有洞" % name)
            bad += 1
    return bad


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true", help="额外跑变异测试")
    args = parser.parse_args()

    if not SRC.is_dir():
        print("找不到源码目录：%s" % SRC)
        return 2

    failures = run(Sources())
    if failures:
        print("AI 增强接线检查未通过（%d 条）：" % len(failures))
        for item in failures:
            print("  - " + item)
        return 1
    print("AI 增强接线检查通过：配置项 %d 个全部被读、Goal %d 个全部挂上、实体与渲染器齐、"
          "NBT 读写成对" % (len(parse_ai_config(Sources())), len(list(AI_DIR.glob('*.java')))))

    if args.selftest:
        print("变异测试：")
        bad = selftest()
        if bad:
            print("变异测试有 %d 条没通过" % bad)
            return 1
        print("变异测试 %d 条全部通过" % len(MUTATIONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
