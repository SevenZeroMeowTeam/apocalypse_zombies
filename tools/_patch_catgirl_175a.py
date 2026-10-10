# -*- coding: utf-8 -*-
"""1.1.75 第二批（她的脑子）：自主选题 + 用容器 + 护卫。"""
from pathlib import Path

NL = chr(10)
fails = []


def edit(path, pairs, label):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            fails.append("%s ｜ no anchor: %s" % (label, old.strip().splitlines()[0][:70]))
            continue
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("  [OK] " + label)


ENT = "F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java"

IMPORT_OLD = "import com.apocalypse.zombies.entity.ai.CatGirlBridgeGoal;"
IMPORT_NEW = NL.join([
    "import com.apocalypse.zombies.entity.ai.CatGirlBridgeGoal;",
    "import com.apocalypse.zombies.entity.ai.CatGirlContainerGoal;",
    "import com.apocalypse.zombies.entity.ai.CatGirlEscortGoal;",
    "import com.apocalypse.zombies.entity.ai.CatGirlNeedGoal;",
])

FIELD_OLD = "    // ------------------------------------------------------------ 任务模式"
FIELD_NEW = NL.join([
    "    /** 自主模式：她按背包与周围环境自己挑活干（CatGirlNeedGoal）。玩家手动切过就关。 */",
    "    private boolean autoJob = true;",
    "",
    "    /** 她的储物点（主人绑定的容器）；null = 没绑，她一个容器都不碰。 */",
    "    private BlockPos storage;",
    "",
    "    // ------------------------------------------------------------ 任务模式",
])

ACC_OLD = NL.join([
    "    public void setJob(Job job) {",
    "        this.entityData.set(DATA_JOB, job.ordinal());",
    "    }",
])
ACC_NEW = NL.join([
    "    public void setJob(Job job) {",
    "        this.entityData.set(DATA_JOB, job.ordinal());",
    "    }",
    "",
    "    // ------------------------------------------------------------ 自主 / 储物点",
    "",
    "    /** 自主模式开着时，CatGirlNeedGoal 会按需求替她挑工种。 */",
    "    public boolean isAutoJob() {",
    "        return this.autoJob;",
    "    }",
    "",
    "    public void setAutoJob(boolean auto) {",
    "        this.autoJob = auto;",
    "    }",
    "",
    "    /**",
    "     * 玩家自己切工种（给工具 / 空手右键 / 命令）：自动决策立刻让位。",
    "     *",
    "     * <p>不这么做的话，你刚让它去砍树，两秒后它自己又跑去挖矿了。</p>",
    "     */",
    "    public void applyPlayerJob(Job job) {",
    "        this.autoJob = false;",
    "        this.setJob(job);",
    "    }",
    "",
    "    /** 她的储物点（/apocalypse catgirl chest 绑定）；没绑返回 null。 */",
    "    public BlockPos getStorage() {",
    "        return this.storage;",
    "    }",
    "",
    "    public void setStorage(BlockPos pos) {",
    "        this.storage = pos == null ? null : pos.immutable();",
    "    }",
])

NBT_SAVE_OLD = "        tag.put(\"CatGirlGoods\", this.goods.createTag());"
NBT_SAVE_NEW = NL.join([
    "        tag.put(\"CatGirlGoods\", this.goods.createTag());",
    "        tag.putBoolean(\"CatGirlAutoJob\", this.autoJob);",
    "        if (this.storage != null) {",
    "            tag.putLong(\"CatGirlChest\", this.storage.asLong());",
    "        }",
])

NBT_LOAD_OLD = NL.join([
    "        if (tag.contains(\"CatGirlGoods\")) {",
    "            this.goods.fromTag(tag.getList(\"CatGirlGoods\", 10));",
    "        }",
])
NBT_LOAD_NEW = NL.join([
    "        if (tag.contains(\"CatGirlGoods\")) {",
    "            this.goods.fromTag(tag.getList(\"CatGirlGoods\", 10));",
    "        }",
    "        // 老存档没有这两个键：默认「自动 + 没绑储物点」，正好是安全的那一侧",
    "        this.autoJob = !tag.contains(\"CatGirlAutoJob\") || tag.getBoolean(\"CatGirlAutoJob\");",
    "        this.storage = tag.contains(\"CatGirlChest\")",
    "                ? BlockPos.of(tag.getLong(\"CatGirlChest\")) : null;",
])

GOAL_NEED_OLD = "        this.goalSelector.addGoal(0, new FloatGoal(this));"
GOAL_NEED_NEW = NL.join([
    "        this.goalSelector.addGoal(0, new FloatGoal(this));",
    "        // 只做决策、不占执行权：按需求给她挑工种（可以关，关了就只听玩家的）",
    "        this.goalSelector.addGoal(0, new CatGirlNeedGoal(this));",
])

GOAL_ESCORT_OLD = "        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));"
GOAL_ESCORT_NEW = NL.join([
    "        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));",
    "        // 护卫排在近战之后：手里有仇人先打，站位的活等它打完再说",
    "        this.goalSelector.addGoal(2, new CatGirlEscortGoal(this));",
])

GOAL_CHEST_OLD = "        this.goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 1.0D));"
GOAL_CHEST_NEW = NL.join([
    "        // 用容器排在劳作之后：先干活，多余的成品才收进箱子",
    "        this.goalSelector.addGoal(6, new CatGirlContainerGoal(this));",
    "        this.goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 1.0D));",
])

MI_TOOL_OLD = NL.join([
    "                this.setJob(toolJob);",
    "                player.displayClientMessage(Component.translatable(\"cat_girl.job.from_tool\",",
])
MI_TOOL_NEW = NL.join([
    "                this.applyPlayerJob(toolJob);",
    "                player.displayClientMessage(Component.translatable(\"cat_girl.job.from_tool\",",
])

MI_CYCLE_OLD = NL.join([
    "            Job next = this.getJob().next();",
    "            this.setJob(next);",
    "            player.displayClientMessage(Component.translatable(\"cat_girl.job.switched\",",
])
MI_CYCLE_NEW = NL.join([
    "            Job next = this.getJob().next();",
    "            this.applyPlayerJob(next);",
    "            player.displayClientMessage(Component.translatable(\"cat_girl.job.switched\",",
])

edit(ENT, [
    (IMPORT_OLD, IMPORT_NEW),
    (FIELD_OLD, FIELD_NEW),
    (ACC_OLD, ACC_NEW),
    (NBT_SAVE_OLD, NBT_SAVE_NEW),
    (NBT_LOAD_OLD, NBT_LOAD_NEW),
    (GOAL_NEED_OLD, GOAL_NEED_NEW),
    (GOAL_ESCORT_OLD, GOAL_ESCORT_NEW),
    (GOAL_CHEST_OLD, GOAL_CHEST_NEW),
    (MI_TOOL_OLD, MI_TOOL_NEW),
    (MI_CYCLE_OLD, MI_CYCLE_NEW),
], "CatGirlEntity")

# ---------------------------------------------------------------- Config
CFG = "F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java"
CFG_DECL_OLD = "    public static final ForgeConfigSpec.DoubleValue CAT_GIRL_FOLLOW_SPEED;"
CFG_DECL_NEW = NL.join([
    "    public static final ForgeConfigSpec.DoubleValue CAT_GIRL_FOLLOW_SPEED;",
    "    /** 自主模式：她自己按需求挑活干（玩家手动切过工种就关掉）。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_JOB;",
    "    /** 用容器：把多余成品放进主人给她绑定的储物点，缺矿时从那里取。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_CHEST;",
    "    /** 护卫：主人挨打时贴过去站位。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ESCORT;",
])

CFG_DEF_OLD = NL.join([
    "        CAT_GIRL_FOLLOW_SPEED = b.comment(\"她的跟随速度（原版跟班是 1.15，主人冲刺时会被甩掉）。注册期读一次，改完要重进世界。\")",
    "                .defineInRange(\"follow_speed\", 1.3D, 0.5D, 2.0D);",
])
CFG_DEF_NEW = CFG_DEF_OLD + NL + NL.join([
    "        CAT_GIRL_AUTO_JOB = b.comment(\"自主模式：她自己按需求挑活干（缺木→伐木、缺矿→挖矿、有敌人在主人身边→打）。\",",
    "                        \"你一旦手动给她切过工种，自动模式对这个个体就关掉了；/apocalypse catgirl auto 可以再打开。\")",
    "                .define(\"auto_job\", true);",
    "        CAT_GIRL_CHEST = b.comment(\"用容器：把多余成品（工具/武器/盔甲，每种留一件）放进你给她绑定的储物点，\",",
    "                        \"背包里缺矿石时再从那里取一组。储物点用 /apocalypse catgirl chest 绑定；没绑她一个箱子都不碰。\")",
    "                .define(\"chest\", true);",
    "        CAT_GIRL_ESCORT = b.comment(\"护卫：主人被攻击时她会贴到主人与攻击者之间站住（打谁仍由目标选择器决定）。\")",
    "                .define(\"escort\", true);",
])

edit(CFG, [(CFG_DECL_OLD, CFG_DECL_NEW), (CFG_DEF_OLD, CFG_DEF_NEW)], "Config")

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
Path("F:/mcmod/build/p175_note.txt").write_text(NL.join(fails), encoding="utf-8")
