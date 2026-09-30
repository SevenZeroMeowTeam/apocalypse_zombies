package com.apocalypse.zombies.entity;

/**
 * 特殊敌对生物的施法状态。
 *
 * <p>服务端逐 tick 推进，客户端通过 {@link EliteMob} 读到同一份状态来摆攻击动画。
 * 每个技能都按「前摇 → 命中 → 收招」三段切分：{@code 0 → impactTick} 是前摇，
 * {@code impactTick} 那一 tick 结算伤害/召唤，{@code impactTick → duration} 是收招。
 * 模型只要拿到 progress 就能在任意剪辑时长下复用同一套姿态曲线。</p>
 */
public enum EliteAbility {

    /** 不在施法。客户端播放常规动作。 */
    NONE(0, -1),
    /** 尖啸者：仰头蓄力长啸，命中瞬间给周围僵尸上 buff 并召唤增援。 */
    SCREAM(46, 22),
    /** 碎颅者：双臂过顶蓄力，命中瞬间砸地，范围击退 + 破甲。 */
    SLAM(32, 18),
    /** 腐蚀者：后仰蓄酸，命中瞬间喷出酸液弹。 */
    SPIT(28, 15),
    /** 骸骨射手：拉满弓蓄力，命中瞬间射出穿透箭。 */
    SNIPE(42, 34),

    /** 美女僵尸「亡语魅惑」：双手捧在胸前的蓄力，命中瞬间放出一圈魅惑波动（死亡时也会触发）。 */
    DEATH_CHIME(40, 20),
    /** 美女僵尸「血月选妃」：提裙行礼的蓄力，命中瞬间召来选妃小队并给自己上 buff。 */
    CONSORT(60, 30),
    /** 美女僵尸「摄魂尖啸」：仰头蓄气，命中瞬间范围尖啸 + 拖拽玩家 + 吸血。 */
    SOUL_SHRIEK(46, 22),

    // 以下四条是美女僵尸的扩充技能。只允许追加在末尾：byId 用的是 ordinal，
    // 插在中间会让其他精英的施法状态在网络上错位到别的技能上。
    /** 美女僵尸「白纱缚足」：提纱外展的蓄力，命中瞬间裙纱暴涨，缠住周围玩家定身。 */
    VEIL_SNARE(44, 22),
    /** 美女僵尸「献祭召奬」：低头合掌的蓄力，命中瞬间献祭召奬换取自身强化。 */
    SACRIFICE(56, 32),
    /** 美女僵尸「抛花束」：右臂过肩蓄力，命中瞬间甩出花束，锥形范围伤害 + 减速。 */
    BOUQUET(38, 24),
    /** 美女僵尸「鬼嫁之吻」：伸手前探的蓄力，命中瞬间拉近并吸食最近玩家的血。 */
    BRIDAL_KISS(36, 20),
    /** 美女僵尸「血纱回春」：垂手含胸的蓄力，命中瞬间给自己与召奬挂上**低等级、长时长**的再生。 */
    BLOOD_REGEN(52, 18),

    // 以下两条是「近战 / 远程」两套攻击技能。上面那些是控场、召唤、续航，这两条才是纯粹的
    // 输出手段：贴脸用横扫，拉开距离用抛花。同样只允许追加在末尾，理由同上。
    /** 美女僵尸「纱袖横扫」：提袖后引的蓄力，命中瞬间以 ±75° / 3 格扇面横扫，重击 + 击退 + 短缓慢。 */
    VEIL_SWIPE(40, 20),
    /** 美女僵尸「抛花刺」：侧身低抛的蓄力，命中瞬间甩出一束走抛物线的花，命中中毒 + 缓慢。 */
    FLOWER_DART(36, 18),

    // 第三条「纯输出」技能，接在近战 / 远程之后。和上面两条一样**只能追加在末尾**：
    // byId 用 ordinal 联网同步，插在中间会让别的精英的施法状态错位到别的技能上。
    /** 美女僵尸「纱袖下劈」：抬臂过顶的蓄力，命中瞬间垂直直劈 —— 窄扇面重击 + 长缓慢。 */
    VEIL_CHOP(42, 22),

    // 以下六条是尸潮之主（Horde Overlord，三阶段 Boss）的技能组。和其它扩充技能一样
    // **只能追加在末尾**：byId 用 ordinal 联网同步，插在中间会让所有精英的施法状态错位。
    /** 尸潮之主「巨斧横扫」：过顶蓄力后横扫，命中瞬间 ±60° / 5 格扇面重击 + 击退。Phase 1 起有。 */
    BOSS_SWEEP(22, 11),
    /** 尸潮之主「骨刺齐射」：抬手集气，命中瞬间朝目标甩出 5 根带轻微制导的骨刺。三阶段都有。 */
    BONE_VOLLEY(26, 17),
    /** 尸潮之主「召唤尸群」：背后尸笼狂转，命中瞬间拍地召来 4 只僵尸。Phase 2 起有。 */
    RAISE_HORDE(36, 22),
    /** 尸潮之主「踏地冲击波」：下蹲蓄力，命中瞬间双脚踏地 —— 7 格半径伤害 + 上抛击退。Phase 2 起有，也是进入 Phase 2 的入场技。 */
    GROUND_QUAKE(28, 14),
    /** 尸潮之主「血怒」（Phase 3 入场技）：仰天咆哮，命中瞬间给自己挂力量/迅捷/抗性并震开周围。 */
    BLOOD_RAGE(40, 18),
    /** 尸潮之主「垂死崩解」：血量跌破 15% 时的亡语，命中瞬间 8 格范围重击 + 击退 + 再召 4 只僵尸。 */
    DEATH_WAIL(32, 18),

    /**
     * 骸骨射手「骨矢锁定」：举弓蓄力 2.1s，第 1.7s 射出一发必中骨矢 —— 伤害按目标最大血量算，
     * 无视护甲 / 无敌帧 / 抗性，命中即消失（不穿透）。
     *
     * <p>同其它扩充技能一样**只能追加在末尾**：{@code byId} 用 ordinal 联网同步，
     * 插在中间会让别的精英的施法状态错位到别的技能上。</p>
     */
    BONE_LOCK(42, 34);

    private static final EliteAbility[] BY_ID = values();

    private final int duration;
    private final int impactTick;

    EliteAbility(int duration, int impactTick) {
        this.duration = duration;
        this.impactTick = impactTick;
    }

    /** 整段技能的长度（tick）。 */
    public int getDuration() {
        return this.duration;
    }

    /** 效果结算发生在第几 tick。 */
    public int getImpactTick() {
        return this.impactTick;
    }

    public boolean isIdle() {
        return this == NONE;
    }

    /** 读网络同步来的原始字节；越界一律退回 {@link #NONE}，绝不让客户端因为脏数据崩。 */
    public static EliteAbility byId(int id) {
        if (id < 0 || id >= BY_ID.length) {
            return NONE;
        }
        return BY_ID[id];
    }
}
