package com.apocalypse.zombies;

import net.minecraftforge.common.ForgeConfigSpec;

import java.util.List;

/**
 * All tunables for Apocalypse Zombies. Server-side authoritative: the values are read on the
 * logical server (integrated server included) and synced to clients through gameplay packets.
 */
public final class Config {

    public static final ForgeConfigSpec SPEC;

    /**
     * 声明顺序里的全部配置项（客户端配置界面照着它列）。
     *
     * <p>用反射取静态字段而不是 {@code SPEC.getValues()}：后者是 nightconfig 的
     * {@code UnmodifiableConfig}，叶子到底是不是 {@code ConfigValue} 实例要看 Forge 内部实现，
     * 而这里要的就是「源码里的字段，按声明顺序」，反射是唯一确定拿得到的。</p>
     *
     * <p>顺序 = 源码声明顺序（HotSpot 返回 {@code getDeclaredFields()} 就是声明序），
     * 所以界面上 {@code mine_radius} 与 {@code mine_max_blocks} 会挨在一起，
     * 不用再排一遍。</p>
     */
    public static java.util.List<ForgeConfigSpec.ConfigValue<?>> values() {
        java.util.List<ForgeConfigSpec.ConfigValue<?>> out = new java.util.ArrayList<>();
        for (java.lang.reflect.Field field : Config.class.getDeclaredFields()) {
            if (!java.lang.reflect.Modifier.isStatic(field.getModifiers())) {
                continue;
            }
            if (!ForgeConfigSpec.ConfigValue.class.isAssignableFrom(field.getType())) {
                continue;
            }
            try {
                out.add((ForgeConfigSpec.ConfigValue<?>) field.get(null));
            } catch (IllegalAccessException ignored) {
                // 公开静态字段，取不到就不列它 —— 不值得为一行配置把界面整个搞崩。
            }
        }
        return out;
    }

    /**
     * 月亮事件的触发方式。
     *
     * <p>{@code true}（默认）= 按 <b>Crafting Dead 的 28 天日历</b>触发（第 6/7 蓝月、13 血月、
     * 20/21 黄月、27 超级血月），玩家可以数着日子等；{@code false} = 每晚按下面那组权重独立掷骰。</p>
     */
    public static final ForgeConfigSpec.BooleanValue LUNAR_SCHEDULE_ENABLED;

    // ---- Lunar event probabilities (random mode only: rolled once per night, weights not required to sum to 1) ----
    public static final ForgeConfigSpec.DoubleValue BLOOD_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_BLOOD_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue YELLOW_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_YELLOW_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue BLUE_MOON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue SUPER_BLUE_MOON_CHANCE;

    /** Blood moons (both kinds) make beds unusable for the whole night. */
    public static final ForgeConfigSpec.BooleanValue BLOOD_MOON_BLOCKS_SLEEP;
    /** 血月期间禁止苦力怕 / 蜘蛛 / 洞穴蜘蛛 / 女巫生成（与 Crafting Dead 同步：血月之夜只留僵尸潮）。 */
    public static final ForgeConfigSpec.BooleanValue BLOOD_MOON_BLOCKS_OTHER_MOBS;

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

    // ---- 僵尸掉落 ----
    /** 僵尸掉落整段的开关。 */
    public static final ForgeConfigSpec.BooleanValue ZOMBIE_LOOT_ENABLED;
    /** crafting-dead 的僵尸保留自身掉落物的概率（它原本必掉）。 */
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_CRAFTINGDEAD_CHANCE;
    /** 是否额外补一套原版掉落（食物 / 工具 / 武器 / 装备 / 稀有枪械）。 */
    public static final ForgeConfigSpec.BooleanValue ZOMBIE_LOOT_EXTRA_ENABLED;
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_FOOD_CHANCE;
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_TOOL_CHANCE;
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_WEAPON_CHANCE;
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_GEAR_CHANCE;
    public static final ForgeConfigSpec.DoubleValue ZOMBIE_LOOT_RARE_CHANCE;

    // ---- 相同物品一键采集 ----
    public static final ForgeConfigSpec.BooleanValue COLLECT_ENABLED;
    /** 采集半径（格）。 */
    public static final ForgeConfigSpec.DoubleValue COLLECT_RADIUS;
    /** 一次最多收多少个物品实体。 */
    public static final ForgeConfigSpec.IntValue COLLECT_MAX;
    /** 只收与手上相同的物品；手上为空时一律收全部。 */
    public static final ForgeConfigSpec.BooleanValue COLLECT_MATCH_HAND;

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

    // ---- 猫耳娘随从 ----
    /** 伐木 / 挖矿的搜索半径（格）。 */
    /** 订做一件成品的手续费（爱心币）。0 = 不收。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_CRAFT_FEE;

    /** 她有个内部熔炉：有矿石 + 燃料就把矿石烧成锭。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_SMELT;

    /** 她的盔甲在模型上画出来（关掉只影响画面，装备本身照样生效）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ARMOR_RENDER;

    /** 血月期间主动在她/玩家附近刷怪。 */
    public static final ForgeConfigSpec.BooleanValue BLOOD_MOON_SPAWN_ENABLED;

    /** 血月刷怪间隔（tick）。 */
    public static final ForgeConfigSpec.IntValue BLOOD_MOON_SPAWN_INTERVAL;

    /** 血月每次刷怪数量（每名玩家）。 */
    public static final ForgeConfigSpec.IntValue BLOOD_MOON_SPAWN_COUNT;

    /** 她会捡地上的东西塞进自己库存（捡到的东西就是她的货架）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_PICKUP;

    /** 她按工种自己换主手：伐木拿斧、挖矿拿镐、战斗拿剑（没剑就弓弩），并把库存里更好的盔甲穿上。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_EQUIP;

    /** 她自己动手把库存材料做成装备（工具 / 武器 / 盔甲 / 箭）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_CRAFT;

    /** 她的装备不吃耐久（主手、盔甲、库存里的可损物品一律修满）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_NO_DURABILITY;

    /** 无视原版工具等级限制：她砸的方块一律有产物（用最高等级工具兜底取掉落）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ALWAYS_DROPS;

    /** 全功能工具：按方块「该用的工具类型」取掉落 —— 斧砍树、锹挖土、剪刀剪叶，一律有产物。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_UNIVERSAL_TOOL;

    /** 什么都能挖：挖矿目标从「只有矿石」放开到所有非保护方块（基岩等仍不碰）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_MINE_ALL;

    /** 挖矿保护名单（方块 id）：名单内一律不砸，默认是基岩 / 屏障 / 命令方块 / 传送门框这类。 */
    public static final ForgeConfigSpec.ConfigValue<List<? extends String>> CAT_GIRL_MINE_PROTECTED;

    /** 挖矿时以她为中心的搜索半径（格）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_MINE_RADIUS;

    /** 一条 {@code /apocalypse catgirl mine} 指令最多挖多少块（一键挖掘的上限）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_MINE_MAX_BLOCKS;

    /** 自主挖矿：目标最多比她的脚层低几格（0 = 只在脚下那层及以上找）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_MINE_DEPTH;

    /** 一键挖掘订单：目标最多比她的脚层低几格（订单是主人点名的活）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_MINE_ORDER_DEPTH;

    /** 探矿：附近一时找不到矿石时，她主动走到附近没探过的位置转一圈。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_PROSPECT;

    /** 一趟探矿最多连走几个探点。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_PROSPECT_TRIES;

    /** 每个探点大概走多远（格）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_PROSPECT_STEP;

    /**
     * 她手里那件东西要不要按镜像摆（默认 false = 原版右手拿法）。
     *
     * <p>只影响贴图的左右朝向（镐 / 斧的头朝里还是朝外），倾角与摆位两者相同。</p>
     */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_HELD_ITEM_MIRROR;

    /** 干活去找工作方块：合成去合成台、熔炼去熔炉（走过去再动手）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_STATION_USE;

    /** 找工作方块的半径（格）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_STATION_RADIUS;

    /** 就近没有工作方块时，她自己做出来并放在脚边（只限合成台 / 熔炉，只放在可替换的位置）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_STATION_SELF_CRAFT;

    /** 全无敌：任何来源都不掉血、也不会死（敌对生物、玩家、爆炸、虚空都免）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_INVULNERABLE;
    public static final ForgeConfigSpec.IntValue CAT_GIRL_WORK_RADIUS;
    /** 她能自己走出去找目标的半径（格）：比 work_radius 大，够她绕过一栋房子。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_AUTONOMY_RADIUS;
    /** 开路：导航走不通时砸掉挡路的自然方块。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_CLEAR_WAY;
    /** 搭桥：前方是坑时用她自己背包里的实心方块铺落脚点。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_BRIDGE;
    /** 她的跟随速度（原版跟班 1.15；主人冲刺时会被甩掉）。 */
    public static final ForgeConfigSpec.DoubleValue CAT_GIRL_FOLLOW_SPEED;
    /** 自主模式：她自己按需求挑活干（玩家手动切过工种就关掉）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_JOB;
    /** 用容器：把多余成品放进主人给她绑定的储物点，缺矿时从那里取。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_CHEST;
    /** 护卫：主人挨打时贴过去站位。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ESCORT;

    /** 本地 AI 助理：用本机的 Ollama 给她一张嘴（默认 qwen2 1.5B）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AI_ENABLED;
    /** 允许她把模型的话落地（切工种 / 下单做东西）。关掉就只剩聊天。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AI_ACTIONS;
    /** Ollama 的地址（默认本机）。 */
    public static final ForgeConfigSpec.ConfigValue<String> CAT_GIRL_AI_ENDPOINT;
    /** 模型名，写 `ollama list` 里那个全名。 */
    public static final ForgeConfigSpec.ConfigValue<String> CAT_GIRL_AI_MODEL;
    /** 一轮最多等多久（毫秒）；超时不会崩游戏，只当她没听懂。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_AI_TIMEOUT_MS;
    /** 上下文长度：KV 缓存越大越吃显存，4096 够她记住你说过的话和现状。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_AI_NUM_CTX;
    /** 破坏一根原木的基础耗时（tick），拿着斧头打折。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_CHOP_TICKS;
    /** 破坏一块矿石的基础耗时（tick），拿着镐打折。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_MINE_TICKS;
    /** 拿对工具时的耗时折扣（0.5 = 减半）。 */
    public static final ForgeConfigSpec.DoubleValue CAT_GIRL_TOOL_SPEEDUP;
    /** 交易价值表：没有单独指定的物品一律按这个价收（模组物品也走这条）。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_TRADE_DEFAULT;
    /** 工具 / 武器（含带攻击力属性的模组装备）的收购价。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_TRADE_TOOL_VALUE;
    /** 覆盖价目表，形如 {@code "minecraft:diamond=8"}；命中即用该值，不再走默认与工具价。 */
    public static final ForgeConfigSpec.ConfigValue<List<? extends String>> CAT_GIRL_TRADE_VALUES;
    /** 附魔一次的爱心币价格：在她的界面里给装备附魔时扣这么多。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_ENCHANT_COST;

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
        LUNAR_SCHEDULE_ENABLED = b.comment("月亮事件按 Crafting Dead 的 28 天日历触发：",
                        "第 6/7 天蓝月、第 13 天血月、第 20/21 天黄月、第 27 天超级血月。",
                        "关掉则退回「每晚独立掷骰」的随机模式（用下面那组概率）。")
                .define("lunar_schedule", true);
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
        BLOOD_MOON_BLOCKS_OTHER_MOBS = b.comment("血月期间禁止苦力怕 / 蜘蛛 / 洞穴蜘蛛 / 女巫生成。",
                        "与 Crafting Dead 同一条规则：血月之夜只留僵尸潮。")
                .define("blood_moon_blocks_other_mobs", true);
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

        b.comment("僵尸掉落：压制 crafting-dead 那份掉落，并按档次补上食物 / 武器 / 装备 / 工具。")
                .push("zombie_loot");
        ZOMBIE_LOOT_ENABLED = b.comment("Master switch for everything in this section.")
                .define("enabled", true);
        ZOMBIE_LOOT_CRAFTINGDEAD_CHANCE = b.comment("crafting-dead 的僵尸（craftingdeadsurvival:*）保留自身掉落物的概率。",
                        "它原本是必掉，0.02 就是「只有 2% 的僵尸会掉东西」。")
                .defineInRange("craftingdead_drop_chance", 0.02D, 0.0D, 1.0D);
        ZOMBIE_LOOT_EXTRA_ENABLED = b.comment("是否给僵尸额外补掉落（下面五档的总开关）。",
                        "补的都是原版物品，各档概率独立判定：一只僵尸可能同时掉好几样，也可能什么都不掉。")
                .define("extra_drops_enabled", true);
        ZOMBIE_LOOT_FOOD_CHANCE = b.comment("掉食物的概率（面包 / 熟肉 / 苹果这类原版食物）。")
                .defineInRange("food_chance", 0.12D, 0.0D, 1.0D);
        ZOMBIE_LOOT_TOOL_CHANCE = b.comment("掉工具的概率（铁锹 / 镐 / 斧 / 锄）。")
                .defineInRange("tool_chance", 0.05D, 0.0D, 1.0D);
        ZOMBIE_LOOT_WEAPON_CHANCE = b.comment("掉武器的概率（剑 / 弓 / 弩）。")
                .defineInRange("weapon_chance", 0.04D, 0.0D, 1.0D);
        ZOMBIE_LOOT_GEAR_CHANCE = b.comment("掉装备的概率（皮革 / 锁链护甲的一个部件）。")
                .defineInRange("gear_chance", 0.06D, 0.0D, 1.0D);
        ZOMBIE_LOOT_RARE_CHANCE = b.comment("掉本模组枪械的概率。默认极低 —— 枪是稀罕物，",
                        "不该变成打僵尸的常规产出。")
                .defineInRange("rare_gun_chance", 0.002D, 0.0D, 1.0D);
        b.pop();

        b.comment("相同物品一键采集。")
                .push("collect");
        COLLECT_ENABLED = b.comment("Master switch.")
                .define("enabled", true);
        COLLECT_RADIUS = b.comment("采集半径（格）。")
                .defineInRange("radius", 6.0D, 1.0D, 32.0D);
        COLLECT_MAX = b.comment("一次最多收多少个物品实体。")
                .defineInRange("max_items", 64, 1, 512);
        COLLECT_MATCH_HAND = b.comment("true = 只收与手上物品相同的；false = 收范围内所有掉落物。",
                        "手上是空的时候一律收全部。")
                .define("match_hand_only", true);
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

        b.comment("猫耳娘随从：喂鱼驯服，空手右键切任务，潜行右键交易。",
                        "Cat girl companion: tame with fish, right-click bare-handed to cycle jobs,",
                        "sneak-right-click to open the barter menu.")
                .push("cat_girl");
        CAT_GIRL_CRAFT_FEE = b.comment("订做一件成品的手续费（爱心币）。")
                .defineInRange("craft_fee", 2, 0, 64);
        CAT_GIRL_SMELT = b.comment("她有个内部熔炉：有矿石 + 燃料就把矿石烧成锭（矿石/生铁 → 锭）。")
                .define("smelt", true);
        CAT_GIRL_ARMOR_RENDER = b.comment("把她的盔甲画在模型上（只影响画面）。")
                .define("armor_render", true);
        BLOOD_MOON_SPAWN_ENABLED = b.comment("血月期间主动刷怪。")
                .define("blood_moon_spawn", true);
        BLOOD_MOON_SPAWN_INTERVAL = b.comment("血月刷怪间隔（tick）。")
                .defineInRange("blood_moon_spawn_interval", 200, 20, 12000);
        BLOOD_MOON_SPAWN_COUNT = b.comment("血月每次刷怪数量（每名玩家）。")
                .defineInRange("blood_moon_spawn_count", 2, 1, 20);
        CAT_GIRL_PICKUP = b.comment("她会捡地上的东西收进自己库存（捡到的就是她的货架）。")
                .define("pickup", true);
        CAT_GIRL_AUTO_EQUIP = b.comment("她按工种自己换装备：伐木拿斧、挖矿拿镐、战斗拿剑（没剑用弓弩），顺手穿库存里更好的盔甲。")
                .define("auto_equip", true);
        CAT_GIRL_AUTO_CRAFT = b.comment("她自己把库存材料做成装备（工具 / 武器 / 盔甲 / 箭）。")
                .define("auto_craft", true);
        CAT_GIRL_NO_DURABILITY = b.comment("她的装备不吃耐久。")
                .define("no_durability", true);
        CAT_GIRL_ALWAYS_DROPS = b.comment("无视原版工具等级限制：她砸什么都有产物。")
                .define("always_drops", true);
        CAT_GIRL_UNIVERSAL_TOOL = b.comment("全功能工具：按方块「该用的工具类型」取掉落（斧砍树 / 锹挖土 / 剪刀剪叶 / 镐挖石），",
                        "除保护名单里的方块外，她砸什么都掉产物 —— 一根木镐也能挖下树来。")
                .define("universal_tool", true);
        CAT_GIRL_MINE_ALL = b.comment("什么都能挖：挖矿目标从「只有矿石」放开到所有非保护方块（土 / 沙 / 树叶都算）。")
                .define("mine_all", true);
        CAT_GIRL_MINE_PROTECTED = b.comment("挖矿保护名单（方块 id，带不带 minecraft: 都行）。名单内一律不砸。",
                        "默认：基岩 / 屏障 / 命令方块 / 结构方块 / 传送门与传送门框 / 刷怪笼 / 紫水晶母岩。",
                        "想让她连刷怪笼也挖掉，就把 minecraft:spawner 从名单里删掉。")
                .defineList("mine_protected", List.of(
                                "minecraft:bedrock",
                                "minecraft:barrier",
                                "minecraft:light",
                                "minecraft:structure_void",
                                "minecraft:command_block",
                                "minecraft:chain_command_block",
                                "minecraft:repeating_command_block",
                                "minecraft:structure_block",
                                "minecraft:jigsaw",
                                "minecraft:end_portal",
                                "minecraft:end_portal_frame",
                                "minecraft:end_gateway",
                                "minecraft:nether_portal",
                                "minecraft:reinforced_deepslate",
                                "minecraft:budding_amethyst",
                                "minecraft:spawner"),
                        o -> o instanceof String);
        CAT_GIRL_MINE_RADIUS = b.comment("挖矿时以她为中心的搜索半径（格）。一键挖掘也按这个半径找目标。")
                .defineInRange("mine_radius", 24, 4, 64);
        CAT_GIRL_MINE_MAX_BLOCKS = b.comment("一条 /apocalypse catgirl mine 指令最多挖多少块（一键挖掘的数量上限，最高 64）。")
                .defineInRange("mine_max_blocks", 64, 1, 64);
        CAT_GIRL_MINE_DEPTH = b.comment("自主挖矿：目标最多比她脚层低几格（0 = 只在脚下那层及以上找）。",
                        "默认 1：脚边浅层矿顺手捡，但绝不挖穿自己站着的地板 —— 她不会再垂直往下打洞、掉进自挖竖井。",
                        "她站着的那一格正下方永远不动（不管这个值多大）。想恢复老行为（一路往下挖）就把这里设成 8。")
                .defineInRange("mine_depth", 1, 0, 8);
        CAT_GIRL_MINE_ORDER_DEPTH = b.comment("一键挖掘订单：目标最多比她脚层低几格（订单是主人点名的活，允许往下挖一点）。",
                        "与 mine_depth 分开：自主挖矿不许下挖，你点名的矿脉在脚下也照样给你挖上来。")
                .defineInRange("mine_order_depth", 6, 0, 16);
        CAT_GIRL_PROSPECT = b.comment("探矿：附近一时找不到矿石时，她自己走到附近没探过的位置转一圈（而不是原地刨地 / 往下打洞）。",
                        "只在「她自己的挖矿工种 + 没订单」时生效；连着几个探点都空手就回主人身边待命。")
                .define("prospect", true);
        CAT_GIRL_PROSPECT_TRIES = b.comment("一趟探矿最多连走几个探点；连着空手这么多次就回主人身边待命。")
                .defineInRange("prospect_tries", 6, 1, 32);
        CAT_GIRL_PROSPECT_STEP = b.comment("每个探点大概走多远（格）。探点在 mine_radius 内随机取，且不会走离主人超过 autonomy_radius。")
                .defineInRange("prospect_step", 8, 2, 32);
        CAT_GIRL_HELD_ITEM_MIRROR = b.comment("她手里那件东西按镜像摆（贴图左右反过来）。",
                        "默认 false：与原版玩家右手拿东西完全同一条摆放链（倾角、朝向都跟玩家一致）。",
                        "只有当你看她手上的镐 / 斧头朝里侧、跟玩家拿反了才开这个。")
                .define("held_item_mirror", false);
        CAT_GIRL_STATION_USE = b.comment("干活去工作方块：合成去最近的合成台、熔炼去最近的熔炉，走过去再动手。",
                        "关掉 = 像以前一样就地空手做（她的 3×3 一手就能摆）。")
                .define("station_use", true);
        CAT_GIRL_STATION_RADIUS = b.comment("找工作方块的半径（格）。")
                .defineInRange("station_radius", 16, 2, 64);
        CAT_GIRL_STATION_SELF_CRAFT = b.comment("就近没有工作方块时，她自己把合成台 / 熔炉做出来并放在脚边用。",
                        "只限这两个方块，只放在空气/草/雪这类可替换的位置，绝不覆盖任何已有方块。")
                .define("station_self_craft", true);
        CAT_GIRL_INVULNERABLE = b.comment("全无敌：任何来源都不掉血、也不会死（连 /kill 也伤不到她）。")
                .define("invulnerable", true);
        CAT_GIRL_WORK_RADIUS = b.comment("伐木 / 挖矿时以她为中心的搜索半径（格）。")
                .defineInRange("work_radius", 12, 4, 32);
        CAT_GIRL_AUTONOMY_RADIUS = b.comment("她能自己走出去找目标的半径（格）—— 实际取它与 work_radius 的较大值，",
                        "所以老存档里的 12 不会把她关在院子里。")
                .defineInRange("autonomy_radius", 32, 8, 64);
        CAT_GIRL_CLEAR_WAY = b.comment("开路：导航走不通时砸掉挡路的自然方块（原木/树叶/土/沙/圆石类，绝不碰箱子·熔炉·门）。")
                .define("clear_way", true);
        CAT_GIRL_BRIDGE = b.comment("搭桥：正前方是坑（深谷/水/岩浆）时，用她自己背包里的实心方块铺一格落脚点。")
                .define("bridge", true);
        CAT_GIRL_FOLLOW_SPEED = b.comment("她的跟随速度（原版跟班是 1.15，主人冲刺时会被甩掉）。注册期读一次，改完要重进世界。")
                .defineInRange("follow_speed", 1.3D, 0.5D, 2.0D);
        CAT_GIRL_AUTO_JOB = b.comment("自主模式：她自己按需求挑活干（缺木→伐木、缺矿→挖矿、有敌人在主人身边→打）。",
                        "你一旦手动给她切过工种，自动模式对这个个体就关掉了；/apocalypse catgirl auto 可以再打开。")
                .define("auto_job", true);
        CAT_GIRL_CHEST = b.comment("用容器：把多余成品（工具/武器/盔甲，每种留一件）放进你给她绑定的储物点，",
                        "背包里缺矿石时再从那里取一组。储物点用 /apocalypse catgirl chest 绑定；没绑她一个箱子都不碰。")
                .define("chest", true);
        CAT_GIRL_ESCORT = b.comment("护卫：主人被攻击时她会贴到主人与攻击者之间站住（打谁仍由目标选择器决定）。")
                .define("escort", true);

        b.comment("本地 AI 助理：用你机器上的 Ollama 让她听懂人话（/apocalypse catgirl ai <一句话>）。",
                        "不联网、不花钱、离线也能用；连不上就当她没听懂，绝不会因此崩游戏。")
                .push("ai");
        CAT_GIRL_AI_ENABLED = b.comment("总开关。关掉后这个命令只会回一句「脑子关着」。")
                .define("enabled", true);
        CAT_GIRL_AI_ACTIONS = b.comment("允许她动手：把模型的提议落成「切工种 / 用她的材料下单做东西」。",
                        "关掉 = 只能陪你说话，游戏状态一点不改（想先看看她怎么说话就关这个）。")
                .define("actions", true);
        CAT_GIRL_AI_ENDPOINT = b.comment("Ollama 地址。默认本机；指向别的机器前想清楚那是谁在替你算。")
                .define("endpoint", "http://127.0.0.1:11434");
        CAT_GIRL_AI_MODEL = b.comment("模型名，和 `ollama list` 里的一字不差。默认是 qwen2 1.5B。")
                .define("model", "fableforge-ai/nexus-coder:q4_k_m");
        CAT_GIRL_AI_TIMEOUT_MS = b.comment("一轮最多等多久（毫秒）。小模型一般 0.2~1 秒就回；等太久说明机器忙。")
                .defineInRange("timeout_ms", 20000, 1000, 120000);
        CAT_GIRL_AI_NUM_CTX = b.comment("上下文长度（KV 缓存）。4096 够用；显存紧就调小，别指望它能读完你的书。")
                .defineInRange("num_ctx", 4096, 512, 32768);
        b.pop();
        CAT_GIRL_CHOP_TICKS = b.comment("破坏一根原木的基础耗时（tick，20 = 1 秒）。")
                .defineInRange("chop_ticks", 40, 4, 400);
        CAT_GIRL_MINE_TICKS = b.comment("破坏一块矿石的基础耗时（tick）。")
                .defineInRange("mine_ticks", 60, 4, 400);
        CAT_GIRL_TOOL_SPEEDUP = b.comment("手里拿着对口工具（斧砍树 / 镐挖矿）时的耗时倍率。")
                .defineInRange("tool_speedup", 0.5D, 0.05D, 1.0D);
        CAT_GIRL_TRADE_DEFAULT = b.comment("默认收购价：没有单独指定、也不是工具/武器的物品都按它折算爱心币。",
                        "模组物品天然走这一条，所以「任意物品包括模组物品」无需逐个登记。")
                .defineInRange("trade_default_value", 1, 0, 64);
        CAT_GIRL_TRADE_TOOL_VALUE = b.comment("工具 / 武器（含带攻击力属性的模组装备）的收购价。")
                .defineInRange("trade_tool_value", 3, 0, 64);
        CAT_GIRL_TRADE_VALUES = b.comment("覆盖价目表，格式 \"命名空间:物品=价格\"，例如：",
                        "[\"minecraft:diamond=8\", \"minecraft:netherite_ingot=16\"]",
                        "命中的物品用表里的价，未命中走默认价 / 工具价。")
                .defineList("trade_values", List.of("minecraft:diamond=8", "minecraft:emerald=4",
                                "minecraft:netherite_ingot=16", "minecraft:gold_ingot=3",
                                "minecraft:iron_ingot=2"),
                        value -> value instanceof String);
        CAT_GIRL_ENCHANT_COST = b.comment("附魔一次的爱心币价格：在她的界面里给装备附魔时扣这么多。")
                .defineInRange("enchant_cost", 8, 0, 64);
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
