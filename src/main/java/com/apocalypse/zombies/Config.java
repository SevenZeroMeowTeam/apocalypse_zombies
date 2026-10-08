package com.apocalypse.zombies;

import net.minecraftforge.common.ForgeConfigSpec;

import java.util.List;

/**
 * All tunables for Apocalypse Zombies. Server-side authoritative: the values are read on the
 * logical server (integrated server included) and synced to clients through gameplay packets.
 */
public final class Config {

    public static final ForgeConfigSpec SPEC;

    // ---- Lunar event probabilities (rolled once per night, weights, not required to sum to 1) ----
    public static final ForgeConfigSpec.DoubleValue BLOOD_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_BLOOD_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue YELLOW_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_YELLOW_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue BLUE_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_BLUE_MOON_CHANCE;

    /** Blood moons (both kinds) make beds unusable for the whole night. */
    public static final ForgeConfigSpec.BooleanValue BLOOD_MOON_BLOCKS_SLEEP;

    // ---- Zombie evolution ----
    /** In-game days required per global evolution level. */
    public static final ForgeConfigSpec.IntValue DAYS_PER_EVOLUTION_LEVEL;
    public static final ForgeConfigSpec.IntValue MAX_EVOLUTION_LEVEL;
    /** Per-tick (1 in N) chance for a single zombie to attempt an evolution step. */
    public static final ForgeConfigSpec.IntValue EVOLUTION_CHECK_INTERVAL;
    public static final ForgeConfigSpec.DoubleValue EVOLUTION_CHANCE;
    /** Extra evolution chance multiplier applied while a blood moon is up. */
    public static final ForgeConfigSpec.DoubleValue BLOOD_MOON_EVOLUTION_MULTIPLIER;
    /** Chance for a freshly spawned zombie to already carry the current global tier. */
    public static final ForgeConfigSpec.DoubleValue SPAWN_WITH_TIER_CHANCE;

    // ---- Hordes ----
    public static final ForgeConfigSpec.BooleanValue HORDES_ENABLED;
    /** A horde always breaks out on these nights (non-super blood moon included). */
    public static final ForgeConfigSpec.BooleanValue HORDE_ON_EVERY_BLOOD_MOON;
    /** Chance of a horde on any other lunar event night. */
    public static final ForgeConfigSpec.DoubleValue HORDE_ON_OTHER_MOON_CHANCE;
    public static final ForgeConfigSpec.IntValue HORDE_WAVES;
    /** 最后一波是否由尸潮之主（三阶段 Boss）领场。 */
    public static final ForgeConfigSpec.BooleanValue HORDE_BOSS_ON_FINAL_WAVE;
    public static final ForgeConfigSpec.IntValue WAVE_MIN_DELAY_TICKS;
    public static final ForgeConfigSpec.IntValue WAVE_MAX_DELAY_TICKS;
    public static final ForgeConfigSpec.IntValue HORDE_MIN_RADIUS;
    public static final ForgeConfigSpec.IntValue HORDE_MAX_RADIUS;
    /** Population multiplier per global evolution level, e.g. 0.15 -> +15% mobs per level. */
    public static final ForgeConfigSpec.DoubleValue HORDE_SCALE_PER_LEVEL;
    /** Head count the first wave rolls (inclusive band, before the growth and evolution multipliers). */
    public static final ForgeConfigSpec.IntValue HORDE_BASE_MIN;
    public static final ForgeConfigSpec.IntValue HORDE_BASE_MAX;
    /** Each wave's population relative to the one before it, e.g. 1.15 -> +15% per wave (compounds). */
    public static final ForgeConfigSpec.DoubleValue HORDE_WAVE_GROWTH;
    public static final ForgeConfigSpec.BooleanValue HORDE_BOSS_BAR;

    // ---- Special hostiles ----
    /** Master switch for the hand-tuned elites' natural overworld spawns. */
    public static final ForgeConfigSpec.BooleanValue ELITE_NATURAL_SPAWN;
    /** Spawn weight of each elite inside the monster category, where vanilla zombie / skeleton / creeper / spider are 100 each. */
    public static final ForgeConfigSpec.IntValue ELITE_SPAWN_WEIGHT;
    /**
     * Spawn weight of the soldier alone. It deliberately does not share {@link #ELITE_SPAWN_WEIGHT}:
     * the zombie soldier is meant to be met while crossing the map, not farmed.
     */
    public static final ForgeConfigSpec.IntValue SOLDIER_SPAWN_WEIGHT;
    /**
     * 精英（尖啸者 / 碎颅者）出厂就配枪的概率。
     *
     * <p>精英配枪是有意给得高的：它们是「值得先处理」的目标，配了枪之后这个定位更明确。</p>
     */
    public static final ForgeConfigSpec.DoubleValue ELITE_GUN_CHANCE;
    /**
     * 普通僵尸出厂配枪的概率。刻意远低于精英 —— 世界里每走几步就撞上一支枪队，
     * 会把「僵尸多但笨」这个基本盘换掉。
     */
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_GUN_CHANCE;
    /**
     * 玩家的生命上限。
     *
     * <p>原版基础值是 20，这里做的是「基础值 + (本值-20)」的 ADDITION 修饰符 ——
     * 别的模组动基础值时两边互不打架，填 20 就等于关掉。</p>
     */
    public static final ForgeConfigSpec.IntValue PLAYER_MAX_HEALTH;
    /** How many soldiers may share a neighbourhood before further spawn attempts are refused. */
    public static final ForgeConfigSpec.IntValue SOLDIER_MAX_NEARBY;
    /** First wave index that brings elites along with the sieges (0 = the very first wave). */
    public static final ForgeConfigSpec.IntValue ELITE_HORDE_FROM_WAVE;
    /** Hard cap on how many elites a single siege wave may bring. */
    public static final ForgeConfigSpec.IntValue ELITE_HORDE_MAX_PER_WAVE;

    // ---- AI enhancements (hostile mobs / skeleton giant arrow / villagers / iron golems) ----
    public static final ForgeConfigSpec.BooleanValue AI_HOSTILE_ENABLED;
    public static final ForgeConfigSpec.IntValue AI_FOLLOW_RANGE;
    public static final ForgeConfigSpec.DoubleValue AI_AGGRO_RADIUS;
    public static final ForgeConfigSpec.IntValue AI_AGGRO_INTERVAL;
    public static final ForgeConfigSpec.BooleanValue AI_SURROUND_ENABLED;
    public static final ForgeConfigSpec.DoubleValue AI_SURROUND_RANGE;
    public static final ForgeConfigSpec.DoubleValue AI_DOOR_BREAK_CHANCE;
    public static final ForgeConfigSpec.DoubleValue AI_DOOR_BREAK_BLOOD_MOON;
    public static final ForgeConfigSpec.ConfigValue<List<? extends String>> AI_EXCLUDED_MOBS;
    public static final ForgeConfigSpec.BooleanValue AI_SKELETON_ENABLED;
    public static final ForgeConfigSpec.DoubleValue AI_SKELETON_GIANT_CHANCE;
    public static final ForgeConfigSpec.IntValue AI_SKELETON_GIANT_COOLDOWN;
    public static final ForgeConfigSpec.DoubleValue AI_SKELETON_GIANT_DAMAGE;
    public static final ForgeConfigSpec.DoubleValue AI_MARKSMAN_GIANT_CHANCE;
    public static final ForgeConfigSpec.DoubleValue AI_MARKSMAN_GIANT_DAMAGE;
    public static final ForgeConfigSpec.DoubleValue AI_GIANT_ARROW_SPEED;
    public static final ForgeConfigSpec.DoubleValue AI_GIANT_ARROW_TURN;
    public static final ForgeConfigSpec.DoubleValue AI_GIANT_ARROW_SCALE;
    public static final ForgeConfigSpec.IntValue AI_GIANT_ARROW_LIFE;
    public static final ForgeConfigSpec.IntValue AI_GIANT_ARROW_WINDUP;
    // ---- 骸骨射手「骨矢锁定」（骨骼化 + 必中骨矢）----
    public static final ForgeConfigSpec.DoubleValue AI_MARKSMAN_LOCK_RATIO;
    public static final ForgeConfigSpec.IntValue AI_MARKSMAN_LOCK_COOLDOWN;
    public static final ForgeConfigSpec.DoubleValue AI_MARKSMAN_LOCK_TURN;
    public static final ForgeConfigSpec.DoubleValue AI_MARKSMAN_LOCK_SPEED;
    public static final ForgeConfigSpec.IntValue AI_MARKSMAN_LOCK_LIFE;
    /**
     * 僵尸 / 骷髅「必中」的概率：这一下攻击无视目标的受击无敌帧，必定造成伤害。
     *
     * <p>原版近战很少真的打空，被"吃掉"的伤害大多来自受击冷却 —— 目标刚被打过、
     * {@code invulnerableTime > 10}，这一下就白挥了。所以这里的必中做成"攻击前先把目标的冷却清掉"。</p>
     */
    public static final ForgeConfigSpec.DoubleValue AI_SURE_HIT_CHANCE;
    /** 必中判定的间隔（tick）。判定太勤等于无敌帧形同虚设，太疏则几乎撞不上。 */
    public static final ForgeConfigSpec.IntValue AI_SURE_HIT_INTERVAL;
    /** 敌对生物的追击速度倍率（1.0 = 原版）。 */
    public static final ForgeConfigSpec.DoubleValue AI_HOSTILE_SPEED;
    public static final ForgeConfigSpec.BooleanValue AI_VILLAGER_ENABLED;
    public static final ForgeConfigSpec.IntValue AI_VILLAGER_INTERVAL;
    public static final ForgeConfigSpec.DoubleValue AI_VILLAGER_ALERT_RADIUS;
    public static final ForgeConfigSpec.DoubleValue AI_VILLAGER_CALL_RADIUS;
    /** 村民出生时拿起武器的概率。拿了的会反击，且不再一味逃跑。 */
    public static final ForgeConfigSpec.DoubleValue AI_VILLAGER_ARM_CHANCE;
    public static final ForgeConfigSpec.BooleanValue AI_GOLEM_ENABLED;
    public static final ForgeConfigSpec.IntValue AI_GOLEM_FOLLOW_RANGE;
    public static final ForgeConfigSpec.DoubleValue AI_GOLEM_KNOCKBACK;
    public static final ForgeConfigSpec.DoubleValue AI_GOLEM_GUARD_RADIUS;
    /** 铁傀儡的移动速度（原版 0.25）。 */
    public static final ForgeConfigSpec.DoubleValue AI_GOLEM_SPEED;
    /** 铁傀儡的攻击伤害（原版 15）。 */
    public static final ForgeConfigSpec.DoubleValue AI_GOLEM_DAMAGE;
    /**
     * 敌对生物之间不互相攻击（本模组生效档）。
     *
     * <p>任一侧是本模组注册的怪时，双方之间的伤害直接取消：伤害不发生 ⇒ 原版
     * {@code HurtByTargetGoal} 不会记仇 ⇒ 不会互咬。别的模组/原版怪之间照旧。</p>
     */
    public static final ForgeConfigSpec.BooleanValue NO_INFIGHTING;
    /**
     * 敌对生物之间不互相攻击（全局档，默认关）。
     *
     * <p>连原版怪之间也不许互殴。会改到原版行为（凋灵、掠夺者与僵尸之类原本会打起来的
     * 组合也会安静下来），所以默认不开。</p>
     */
    public static final ForgeConfigSpec.BooleanValue NO_INFIGHTING_GLOBAL;

    // ---- 持枪怪的贴身行为 + 死亡标记 ----
    /**
     * 枪手与目标贴到这么近时，把移动通道交还出去，由原版近战接手。
     *
     * <p>枪手占着 MOVE 就不可能被近战抢走执行权（原版近战 Goal 也在争同一个标记），
     * 所以「贴脸了还站在原地开枪」只能靠让位来修。填 0 就是关掉这条、退回旧行为。</p>
     */
    public static final ForgeConfigSpec.DoubleValue GUN_MELEE_HANDOFF_RANGE;
    /** 枪手在射程内是否走「游走射击」。false = 站桩开枪（旧行为）。 */
    public static final ForgeConfigSpec.BooleanValue GUN_STRAFE_ENABLED;
    /** 射程内连续看不到目标这么多 tick 就也让位，让它绕过去而不是顶着墙站着。 */
    public static final ForgeConfigSpec.IntValue GUN_BLIND_HANDOFF_TICKS;
    /** 死亡标记总开关。 */
    public static final ForgeConfigSpec.BooleanValue DEATH_MARK_ENABLED;
    /** 每层标记的增伤比例（0.20 = 每层 +20%）。 */
    public static final ForgeConfigSpec.DoubleValue DEATH_MARK_DAMAGE_BONUS;
    /** 标记最多叠几层（层数 = amplifier + 1，填 1 就是不叠）。 */
    public static final ForgeConfigSpec.IntValue DEATH_MARK_MAX_STACKS;
    /** 标记持续时间（tick），每次命中都会刷新。 */
    public static final ForgeConfigSpec.IntValue DEATH_MARK_DURATION;

    /** Q 弹（压扁回弹 + 自转）总开关。纯客户端，服务端不读。 */
    public static final ForgeConfigSpec.BooleanValue SQUASH_ENABLED;
    /**
     * 果冻律动的幅度倍率（1.0 = 曲线原样；调到 0 就只剩受击时弹一下）。
     *
     * <p>键名从 {@code intensity} 改成 {@code sway}：那个名字在语义变之前是"压扁 25%"的**绝对值**，
     * 老配置文件里存着 {@code 0.25}，而 Forge 对**已存在的键会原样保留** —— 于是新语义下它悄悄变成了
     * "只有 1/4 幅度"，实机表现就是"压扁回弹不明显"。换个键名等于让它取回新默认值 1.0。</p>
     */
    public static final ForgeConfigSpec.DoubleValue SQUASH_SWAY;
    /** 绕圈移动的半径（格）。0 = 只在原地压扁自转，身体不挪窝。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_ORBIT;
    /** 压到底时高度缩掉多少（50 = 矮一半）。曲线与幅度照「朋友的酒」的果冻效果。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_COMPRESSION;
    /** 压到底时横向鼓出多少（50 = 宽一半）。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_WIDTH;
    /** 是否一边压扁一边绕竖直轴自转（那个模组叫「逆时针绕圈」）。 */
    public static final ForgeConfigSpec.BooleanValue SQUASH_ROTATE;
    /** 自转速度倍率（1.0 = 一个律动周期正好转一整圈）。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_SPIN_SPEED;
    /** 受击冲击的抖动角频率（弧度/秒）：越大越「弹」。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_FREQUENCY;
    /** 冲击的阻尼系数：越大衰减越快。 */
    public static final ForgeConfigSpec.DoubleValue SQUASH_DAMPING;

    /** 「朋友的酒」常驻背景音乐总开关。纯客户端，服务端不读。 */
    public static final ForgeConfigSpec.BooleanValue FRIENDS_WINE_MUSIC;
    /** 音乐音量乘子（0~1）。最终音量还要乘玩家自己的「音乐」滑块，两者是相乘关系。 */
    public static final ForgeConfigSpec.DoubleValue FRIENDS_WINE_VOLUME;
    /** 是否在原版背景音乐要开播时把它压下去（不压就会两首歌重叠）。 */
    public static final ForgeConfigSpec.BooleanValue FRIENDS_WINE_SUPPRESS_VANILLA;

    static {
        ForgeConfigSpec.Builder b = new ForgeConfigSpec.Builder();

        b.comment("Chances rolled once per night when dusk starts. 0.10 = 10%.",
                        "Whatever is left over after all six rolls is an ordinary night.")
                .push("lunar_events");
        BLOOD_MOON_CHANCE = b.comment("Red moon, sky washed dark red, beds unusable.")
                .defineInRange("blood_moon_chance", 0.10D, 0.0D, 1.0D);
        SUPER_BLOOD_MOON_CHANCE = b.comment("Bigger, deeper red blood moon; harsher night.")
                .defineInRange("super_blood_moon_chance", 0.035D, 0.0D, 1.0D);
        YELLOW_MOON_CHANCE = b.comment("Bright yellow moon; crops grow all night long.")
                .defineInRange("yellow_moon_chance", 0.09D, 0.0D, 1.0D);
        SUPER_YELLOW_MOON_CHANCE = b.comment("Bigger yellow moon; crops grow much faster.")
                .defineInRange("super_yellow_moon_chance", 0.025D, 0.0D, 1.0D);
        BLUE_MOON_CHANCE = b.comment("Pale blue moon; grants Luck until dawn.")
                .defineInRange("blue_moon_chance", 0.08D, 0.0D, 1.0D);
        SUPER_BLUE_MOON_CHANCE = b.comment("Bigger pale blue moon; stronger Luck until dawn.")
                .defineInRange("super_blue_moon_chance", 0.02D, 0.0D, 1.0D);
        BLOOD_MOON_BLOCKS_SLEEP = b.comment("Players cannot sleep while a blood moon is up.")
                .define("blood_moon_blocks_sleep", true);
        b.pop();

        b.comment("Zombies level up over the in-game days and can evolve on the fly.")
                .push("evolution");
        DAYS_PER_EVOLUTION_LEVEL = b.comment("In-game days per global evolution level.")
                .defineInRange("days_per_evolution_level", 3, 1, 1000);
        MAX_EVOLUTION_LEVEL = b.comment("Global evolution level cap (0 = only plain zombies).")
                .defineInRange("max_evolution_level", 5, 0, 10);
        EVOLUTION_CHECK_INTERVAL = b.comment("A zombie rolls for evolution every N ticks.")
                .defineInRange("evolution_check_interval", 200, 20, 24000);
        EVOLUTION_CHANCE = b.comment("Chance per roll that the zombie evolves one tier.")
                .defineInRange("evolution_chance", 0.06D, 0.0D, 1.0D);
        BLOOD_MOON_EVOLUTION_MULTIPLIER = b.comment("Evolution chance multiplier during blood moons.")
                .defineInRange("blood_moon_evolution_multiplier", 3.0D, 1.0D, 100.0D);
        SPAWN_WITH_TIER_CHANCE = b.comment("Chance a newly spawned zombie already matches the global tier.")
                .defineInRange("spawn_with_tier_chance", 0.55D, 0.0D, 1.0D);
        b.pop();

        b.comment("Five-wave siege events that break out at night.",
                        "The last wave is led by the Horde Overlord (a three-phase, 2500 HP boss)")
                .push("hordes");
        HORDES_ENABLED = b.define("hordes_enabled", true);
        HORDE_ON_EVERY_BLOOD_MOON = b.comment("Guarantee a horde whenever a blood moon rises.")
                .define("horde_on_every_blood_moon", true);
        HORDE_ON_OTHER_MOON_CHANCE = b.comment("Chance of a horde on yellow / blue moon nights.")
                .defineInRange("horde_on_other_moon_chance", 0.35D, 0.0D, 1.0D);
        HORDE_WAVES = b.comment("How many waves a single horde consists of.")
                .defineInRange("horde_waves", 5, 1, 12);
        WAVE_MIN_DELAY_TICKS = b.comment("Shortest gap between waves, in ticks (20 = 1s).")
                .defineInRange("wave_min_delay_ticks", 600, 20, 72000);
        WAVE_MAX_DELAY_TICKS = b.comment("Longest gap between waves, in ticks.")
                .defineInRange("wave_max_delay_ticks", 1800, 20, 72000);
        HORDE_MIN_RADIUS = b.comment("Closest a horde mob may spawn to a player, in blocks.")
                .defineInRange("horde_min_radius", 24, 8, 128);
        HORDE_MAX_RADIUS = b.comment("Furthest a horde mob may spawn from a player, in blocks.")
                .defineInRange("horde_max_radius", 48, 16, 256);
        HORDE_SCALE_PER_LEVEL = b.comment("Extra horde population per global evolution level.")
                .defineInRange("horde_scale_per_level", 0.15D, 0.0D, 10.0D);
        HORDE_BASE_MIN = b.comment("Smallest head count the first wave rolls (before the per-wave growth",
                        "and the evolution multiplier).")
                .defineInRange("horde_base_min", 10, 1, 90);
        HORDE_BASE_MAX = b.comment("Largest head count the first wave rolls.")
                .defineInRange("horde_base_max", 16, 1, 200);
        HORDE_WAVE_GROWTH = b.comment("Each wave's population relative to the previous one.",
                        "1.15 = every wave is 15% bigger than the one before it.",
                        "It compounds: with 5 waves, wave 5 is 1.15^4 = 1.75x wave 1; with 12 waves,",
                        "wave 12 is 1.15^11 = 4.65x. Applied before the evolution multiplier, and the",
                        "usual +/-15% jitter is rolled on top.")
                .defineInRange("horde_wave_growth", 1.15D, 1.0D, 3.0D);
        HORDE_BOSS_BAR = b.comment("Show a boss bar tracking the current wave and remaining mobs.")
                .define("horde_boss_bar", true);
        HORDE_BOSS_ON_FINAL_WAVE = b.comment("Let the Horde Overlord lead the last wave.",
                        "It counts towards that wave's head count, so the siege only ends once it is dead.",
                        "Turn off to keep the sieges boss-free (the spawn egg and the command still work).")
                .define("horde_boss_on_final_wave", true);
        b.pop();

        b.comment("Hand-tuned special hostiles. They stay outside the evolution ladder.")
                .push("specials");
        ELITE_NATURAL_SPAWN = b.comment("Allow the special hostiles to spawn naturally in the overworld.")
                .define("elite_natural_spawn", true);
        ELITE_SPAWN_WEIGHT = b.comment("Spawn weight of each special hostile inside the monster category.",
                        "Vanilla zombie / skeleton / creeper / spider are 100 each, so 3 is roughly",
                        "one elite per 170 natural monster spawns. 0 removes them from the spawn pool entirely.",
                        "Takes effect on world load; reload the world after changing it.")
                .defineInRange("elite_spawn_weight", 3, 0, 100);
        SOLDIER_SPAWN_WEIGHT = b.comment("Spawn weight of the soldier inside the monster category.",
                        "It has its own knob instead of sharing elite_spawn_weight: it is the one variant",
                        "meant to turn up on a normal walk, so it is tuned lower than the rest.",
                        "0 keeps it out of natural spawns; siege waves and the spawn egg still work.")
                .defineInRange("soldier_spawn_weight", 2, 0, 100);
        ELITE_GUN_CHANCE = b.comment("Chance for an elite (screamer / crusher) to spawn carrying a gun.",
                        "An armed mob keeps its distance and fires visible bullets instead of closing to melee;",
                        "the gun never drops, so this is not a source of free weapons for the player.",
                        "0 turns armed spawns off entirely. Takes effect on world load.")
                .defineInRange("elite_gun_chance", 0.35D, 0.0D, 1.0D);
        ZOMBIE_GUN_CHANCE = b.comment("Chance for an ordinary zombie to spawn carrying a gun.",
                        "Kept far below the elite figure on purpose: a gun behind every second zombie",
                        "trades away the whole 'many but dumb' baseline the horde is built on.")
                .defineInRange("zombie_gun_chance", 0.05D, 0.0D, 1.0D);
        PLAYER_MAX_HEALTH = b.comment("Maximum health for players.",
                        "Applied as an ADDITION modifier on top of the vanilla base of 20, so it coexists",
                        "with other mods that touch the base value; 20 disables the change.",
                        "Health is scaled proportionally the first time the new value takes effect.",
                        "Takes effect on world load.")
                .defineInRange("player_max_health", 100, 20, 1024);
        SOLDIER_MAX_NEARBY = b.comment("Cap on how many soldiers may stand within 48 blocks of a spawn attempt.",
                        "Keeps a lucky streak of spawn rolls from stacking a firing squad in one chunk.")
                .defineInRange("soldier_max_nearby", 2, 1, 16);
        ELITE_HORDE_FROM_WAVE = b.comment("First wave index that sends elites along with a siege (0 = the first wave).")
                .defineInRange("elite_horde_from_wave", 2, 0, 12);
        ELITE_HORDE_MAX_PER_WAVE = b.comment("Cap on elites per wave; later waves bring more until this caps out.")
                .defineInRange("elite_horde_max_per_wave", 3, 0, 12);
        b.pop();

        b.comment("AI enhancements. Every value here is read by event/MobAiEnhanced.java.",
                        "Set hostile_enabled / skeleton_enabled / villager_enabled / golem_enabled to false",
                        "to turn each branch off without touching the others.")
                .push("ai_enhance");
        AI_HOSTILE_ENABLED = b.comment("Auto-targeting, shared aggro and flanking for every ground-based Monster.",
                        "Applies to vanilla and modded hostiles alike; flying mobs are skipped by design.")
                .define("hostile_enabled", true);
        AI_FOLLOW_RANGE = b.comment("Follow range hostiles are raised to (vanilla zombie / skeleton = 35).",
                        "This is what lets them keep coming when the player breaks line of sight.")
                .defineInRange("follow_range", 48, 16, 128);
        AI_AGGRO_RADIUS = b.comment("How far a hostile shares an ally's target (metres). Aggro propagation.")
                .defineInRange("aggro_radius", 16.0D, 1.0D, 64.0D);
        AI_AGGRO_INTERVAL = b.comment("Ticks between aggro scans. The scan is the expensive part; keep it above 10.")
                .defineInRange("aggro_interval", 20, 5, 200);
        AI_SURROUND_ENABLED = b.comment("Hostiles fan out around the target instead of queueing up in a line.")
                .define("surround_enabled", true);
        AI_SURROUND_RANGE = b.comment("Distance at which the fan-out starts; melee takes over inside it.")
                .defineInRange("surround_range", 6.0D, 2.0D, 24.0D);
        AI_DOOR_BREAK_CHANCE = b.comment("Chance a newly spawned zombie can break wooden doors (vanilla is ~0.025).")
                .defineInRange("door_break_chance", 0.15D, 0.0D, 1.0D);
        AI_DOOR_BREAK_BLOOD_MOON = b.comment("Same roll on a blood moon night.")
                .defineInRange("door_break_blood_moon", 0.30D, 0.0D, 1.0D);
        AI_EXCLUDED_MOBS = b.comment("Entity ids that must never receive the hostile enhancements.",
                        "Flying mobs and no-AI mobs are skipped automatically; this is for special cases.",
                        "Example: [\"minecraft:wither\", \"othermod:boss\"]")
                .defineList("excluded_mobs", List.of("minecraft:wither"),
                        value -> value instanceof String);
        AI_SKELETON_ENABLED = b.comment("Skeleton skirmishing (back off when rushed) and the giant tracking arrow.")
                .define("skeleton_enabled", true);
        AI_SKELETON_GIANT_CHANCE = b.comment("Per attack roll: chance an ordinary skeleton fires the giant arrow.")
                .defineInRange("skeleton_giant_chance", 0.08D, 0.0D, 1.0D);
        AI_SKELETON_GIANT_COOLDOWN = b.comment("Ticks between giant-arrow attempts for ordinary skeletons.")
                .defineInRange("skeleton_giant_cooldown", 200, 20, 6000);
        AI_SKELETON_GIANT_DAMAGE = b.comment("Giant arrow base damage (a normal arrow is about 2).")
                .defineInRange("skeleton_giant_damage", 10.0D, 1.0D, 100.0D);
        AI_MARKSMAN_GIANT_CHANCE = b.comment("Same roll for the elite marksman skeleton; it is meant to be the threat.")
                .defineInRange("marksman_giant_chance", 0.20D, 0.0D, 1.0D);
        AI_MARKSMAN_GIANT_DAMAGE = b.comment("Giant arrow base damage for the elite marksman.")
                .defineInRange("marksman_giant_damage", 14.0D, 1.0D, 100.0D);
        AI_GIANT_ARROW_SPEED = b.comment("Giant arrow launch speed (blocks / tick).")
                .defineInRange("giant_arrow_speed", 3.0D, 0.5D, 10.0D);
        AI_GIANT_ARROW_TURN = b.comment("Homing rate in degrees per tick.",
                        "6 deg/tick tracks a straight runner but can be shaken by hard strafing or cover;",
                        "15 is near-unavoidable and 3 only catches people who run in a straight line.")
                .defineInRange("giant_arrow_turn", 6.0D, 0.0D, 30.0D);
        AI_GIANT_ARROW_SCALE = b.comment("Render size multiplier (client side only, 1 = vanilla arrow size).")
                .defineInRange("giant_arrow_scale", 2.5D, 1.0D, 6.0D);
        AI_GIANT_ARROW_LIFE = b.comment("Ticks before an arrow that never hit gives up and vanishes.")
                .defineInRange("giant_arrow_life", 120, 20, 1200);
        AI_GIANT_ARROW_WINDUP = b.comment("Ticks the skeleton stands still and draws before loosing it.",
                        "This is the telegraph: 0 makes the hit feel like it came out of nowhere.")
                .defineInRange("giant_arrow_windup", 20, 0, 100);
        AI_MARKSMAN_LOCK_RATIO = b.comment("Bone lock damage = target max health x this ratio.",
                        "0.25 = a quarter of the bar whoever it lands on; armour, resistance potions",
                        "and i-frames are bypassed by the damage type, so this number is the hit.",
                        "伤害 = 目标最大血量 × 该比例。")
                .defineInRange("marksman_lock_ratio", 0.25D, 0.0D, 1.0D);
        AI_MARKSMAN_LOCK_COOLDOWN = b.comment("Ticks the elite marksman waits between bone lock casts.",
                        "The shot is unavoidable, so the cooldown IS the counter-play window.",
                        "技能冷却（tick）：必中所以冷却就是玩家的操作窗口。")
                .defineInRange("marksman_lock_cooldown", 160, 20, 6000);
        AI_MARKSMAN_LOCK_TURN = b.comment("Bone lock homing rate in degrees per tick.",
                        "60 deg/tick is 3600 deg/s: strafing, pillar hugging and doorways do not shake it,",
                        "which is the point of a guaranteed hit. Lower it only to soften the fantasy.",
                        "转向速率（度 / tick）：默认 60 ≈ 每秒转 10 圈，甩不掉。")
                .defineInRange("marksman_lock_turn", 60.0D, 5.0D, 180.0D);
        AI_MARKSMAN_LOCK_SPEED = b.comment("Bone lock flight speed (blocks / tick).")
                .defineInRange("marksman_lock_speed", 1.6D, 0.5D, 4.0D);
        AI_MARKSMAN_LOCK_LIFE = b.comment("Ticks a bone lock arrow lives before it gives up.",
                        "Keep it long enough to cross the arena but short enough that a missing arrow",
                        "does not keep circling behind the player.")
                .defineInRange("marksman_lock_life", 100, 20, 400);
        AI_VILLAGER_ENABLED = b.comment("Villagers panic when hostiles close in, and call the nearest golem.")
                .define("villager_enabled", true);
        AI_VILLAGER_INTERVAL = b.comment("Ticks between villager threat scans.")
                .defineInRange("villager_interval", 20, 5, 200);
        AI_VILLAGER_ALERT_RADIUS = b.comment("A hostile inside this radius sends the villager into panic.")
                .defineInRange("villager_alert_radius", 16.0D, 4.0D, 48.0D);
        AI_VILLAGER_CALL_RADIUS = b.comment("How far a villager calls for an iron golem (needs line of sight).")
                .defineInRange("villager_call_radius", 16.0D, 4.0D, 64.0D);
        AI_VILLAGER_ARM_CHANCE = b.comment("Chance a villager spawns armed with an iron sword.",
                        "An armed villager stops fleeing and fights back instead: it gets a melee goal",
                        "and a monster target goal, and the panic branch is skipped for it.",
                        "0 disables the whole feature (and unarmed villagers behave as before).")
                .defineInRange("villager_arm_chance", 0.15D, 0.0D, 1.0D);
        AI_SURE_HIT_CHANCE = b.comment("Chance that a zombie's or skeleton's attack counts as a sure hit:",
                        "the target's hurt cooldown is cleared first, so the blow cannot be eaten by",
                        "invulnerability frames. 0 restores vanilla behaviour.")
                .defineInRange("sure_hit_chance", 0.35D, 0.0D, 1.0D);
        AI_SURE_HIT_INTERVAL = b.comment("Ticks between sure-hit rolls. Rolling every tick would make",
                        "invulnerability frames meaningless.")
                .defineInRange("sure_hit_interval", 10, 1, 200);
        AI_HOSTILE_SPEED = b.comment("Chase speed multiplier for hostile mobs (1.0 = vanilla).",
                        "Applies to this mod's mobs and vanilla zombies/skeletons alike.")
                .defineInRange("hostile_speed", 1.1D, 0.5D, 3.0D);
        AI_GOLEM_ENABLED = b.comment("Iron golems prioritise whatever is threatening a villager, and hit harder.")
                .define("golem_enabled", true);
        AI_GOLEM_FOLLOW_RANGE = b.comment("Follow range iron golems are raised to (vanilla is 35).")
                .defineInRange("golem_follow_range", 48, 16, 128);
        AI_GOLEM_KNOCKBACK = b.comment("Attack knockback added to iron golems (vanilla is 1.0).")
                .defineInRange("golem_knockback", 2.0D, 0.0D, 10.0D);
        AI_GOLEM_GUARD_RADIUS = b.comment("Radius in which golems look for monsters threatening villagers.")
                .defineInRange("golem_guard_radius", 24.0D, 4.0D, 64.0D);
        AI_GOLEM_SPEED = b.comment("Iron golem movement speed (vanilla is 0.25).")
                .defineInRange("golem_speed", 0.28D, 0.1D, 1.0D);
        AI_GOLEM_DAMAGE = b.comment("Iron golem attack damage (vanilla is 15).")
                .defineInRange("golem_damage", 18.0D, 1.0D, 100.0D);
        NO_INFIGHTING = b.comment("Hostile mobs do not hurt or fight each other. Any exchange where one",
                        "side is one of this mod's mobs is cancelled outright, so the vanilla",
                        "retaliation goal never records a grudge. Other mods' and vanilla mobs",
                        "still behave normally.",
                        "Charmed minions of the bride are exempt: they exist to fight zombies.")
                .define("no_infighting", true);
        NO_INFIGHTING_GLOBAL = b.comment("Extends no_infighting to vanilla mobs too. Off by default:",
                        "it changes vanilla behaviour (a wither, pillagers and zombies that would",
                        "normally tear into each other go quiet as well).")
                .define("no_infighting_global", false);
        b.pop();

        b.comment("Gun-armed mobs up close, and the mark they leave on you.")
                .push("gun_and_mark");
        GUN_MELEE_HANDOFF_RANGE = b.comment("Distance at which a gunner hands the movement channel back to melee.",
                        "Inside this the vanilla melee goal takes over, so a gunner stops firing into your face",
                        "and starts swinging. 0 disables the hand-off (the gunner never switches to melee).")
                .defineInRange("melee_handoff_range", 3.0D, 0.0D, 12.0D);
        GUN_STRAFE_ENABLED = b.comment("Gunners walk sideways while firing instead of standing still.",
                        "They still hold the firing distance, they just stop being statues.")
                .define("mobile_fire", true);
        GUN_BLIND_HANDOFF_TICKS = b.comment("In range but without line of sight for this many ticks, the gunner",
                        "hands the channel over so vanilla pathing can walk it around the obstacle.")
                .defineInRange("blind_handoff_ticks", 40, 5, 400);
        DEATH_MARK_ENABLED = b.comment("Ranged monsters mark whoever they hit; a marked target takes extra",
                        "damage from every monster while the mark lasts.")
                .define("death_mark_enabled", true);
        DEATH_MARK_DAMAGE_BONUS = b.comment("Damage bonus per mark stack (0.20 = +20% per stack).")
                .defineInRange("death_mark_damage_bonus", 0.20D, 0.0D, 2.0D);
        DEATH_MARK_MAX_STACKS = b.comment("How many times the mark stacks; 1 turns stacking off.")
                .defineInRange("death_mark_max_stacks", 3, 1, 10);
        DEATH_MARK_DURATION = b.comment("Mark duration in ticks (200 = 10 seconds). Every hit refreshes it.")
                .defineInRange("death_mark_duration", 200, 20, 6000);
        b.pop();

        // 纯客户端效果：像 AI_GIANT_ARROW_SCALE 一样只被渲染代码读取，不参与任何服务端判定，
        // 所以不需要同步包，也不会在专用服务器上被求值。
        b.comment("Squash & stretch: mobs compress and wobble back like jelly, and can spin.",
                        "Q 弹：生物压扁、回弹、绕竖直轴自转。曲线与幅度照「朋友的酒」的果冻效果",
                        "（周期 0.91667 s，一个周期 0→1→0→1→0，只压宽度与高度，Z 轴不动）。纯客户端。")
                .push("squash_stretch");
        SQUASH_ENABLED = b.comment("Master switch for the client-side squash & stretch effect.")
                .define("enabled", true);
        SQUASH_SWAY = b.comment("Amplitude multiplier on the idle jelly wobble (1.0 = the curve as authored).",
                        "0 turns the idle wobble off and leaves only the impact kick.",
                        "Renamed from 'intensity': that key meant '25% flatter' in an earlier take, and Forge",
                        "keeps an existing key's old value, which quietly quartered the wobble.")
                .defineInRange("sway", 1.0D, 0.0D, 1.5D);
        SQUASH_ORBIT = b.comment("Radius, in blocks, of the little circle a mob walks while it wobbles.",
                        "0 keeps it in place; 0.25 is a visible orbit that still reads as 'roughly here'.",
                        "It laps once per wobble period, same rate as the spin.")
                .defineInRange("orbit_radius", 0.25D, 0.0D, 2.0D);
        SQUASH_COMPRESSION = b.comment("How much shorter the body gets at full squash (50 = half height).")
                .defineInRange("compression", 50.0D, 0.0D, 90.0D);
        SQUASH_WIDTH = b.comment("How much wider it gets at full squash (50 = half again as wide).",
                        "Z (thickness) is never scaled — this is a face-on squash, not a volume-preserving one.")
                .defineInRange("width", 50.0D, 0.0D, 90.0D);
        SQUASH_ROTATE = b.comment("Spin about the vertical axis while squashing.")
                .define("rotate", true);
        SQUASH_SPIN_SPEED = b.comment("Spin speed multiplier (1.0 = one full turn per wobble period).")
                .defineInRange("spin_speed", 1.0D, 0.0D, 5.0D);
        SQUASH_FREQUENCY = b.comment("Impact kick: wobble frequency in radians per second; higher = snappier.")
                .defineInRange("wobble_frequency", 13.0D, 4.0D, 40.0D);
        SQUASH_DAMPING = b.comment("Impact kick: how fast it dies out. 3 = about three visible bounces.")
                .defineInRange("damping", 3.0D, 0.5D, 12.0D);
        b.pop();

        // 同样是纯客户端表现：只有客户端的音乐控制器读它，专用服务器上不会被求值。
        b.comment("The player's own background track (\"朋友的酒\"), looped for as long as you are in a world.",
                        "玩家自备的背景音乐，进世界就一直循环放；离开世界或关掉开关即停。纯客户端。")
                .push("friends_wine_music");
        FRIENDS_WINE_MUSIC = b.comment("Play it at all.")
                .define("enabled", true);
        FRIENDS_WINE_VOLUME = b.comment("Volume multiplier (0~1). Multiplied with your own Music slider, not replacing it.")
                .defineInRange("volume", 1.0D, 0.0D, 1.0D);
        FRIENDS_WINE_SUPPRESS_VANILLA = b.comment("Keep vanilla background music from starting underneath it.",
                        "Off means you may hear both at once.")
                .define("suppress_vanilla", true);
        b.pop();

        SPEC = b.build();
    }

    private Config() {
    }
}
