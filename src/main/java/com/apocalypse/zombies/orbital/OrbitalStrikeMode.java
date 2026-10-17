package com.apocalypse.zombies.orbital;

import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;

/**
 * 轨道打击的四种「弹种」。玩家手持遥控器潜行右键切换，选择存在物品 NBT 里
 * （{@code StrikeMode} 字符串），开火时随包发给客户端。
 *
 * <p><b>为什么参数是「倍率」而不是绝对值</b>：所有模式都从同一组基础配置
 * （{@code radius} / {@code damage} / {@code lock_ticks} / {@code fall_ticks}）缩放而来。
 * 这样调一次配置，四种模式一起变；模式之间的强弱关系（长矛细而深、风暴广而浅）保持不变。</p>
 *
 * <p><b>时序</b>：{@link #lockTicks(int)} 等算出的是<b>最终 tick 数</b>，服务端把它写进
 * {@code OrbitalStrikePacket} —— 客户端不自己算，避免两端口径漂移导致光柱和挖地不同步。</p>
 */
public enum OrbitalStrikeMode {

    /** 轨道炮：大范围动能弹，**一路打穿到世界底层（含基岩，虚空见）**。 */
    CANNON("cannon", "轨道炮", "ORBITAL CANNON",
            1.00F, 1.00F, 1.00F, 1.00F, 1.00F, true),

    /**
     * 天基长矛：半径收得很小，但一路挖穿（含基岩）并造成极高单点伤害。
     * 前摇更长、下落更慢 —— 一根从宇宙扎下来的矛，过程本身就该看得见。
     */
    LANCE("lance", "天基长矛", "SKY LANCE",
            0.18F, 2.40F, 1.35F, 1.25F, 1.30F, true),

    /**
     * 引力奇点：先在下落段把周围生物往落点拽，落地瞬间反向爆开。
     * 范围中等、伤害偏高；不挖穿 —— 它压出一个坑，不是一根井。
     */
    GRAVITY("gravity", "引力奇点", "SINGULARITY",
            0.60F, 1.45F, 1.25F, 1.10F, 1.40F, false),

    /**
     * 等离子风暴：一次打击在目标周围撒下若干个小落点，每个都是独立的坑。
     * 单点伤害低，但覆盖面大 —— 对付散开的尸群。
     */
    STORM("storm", "等离子风暴", "PLASMA STORM",
            0.45F, 0.70F, 1.10F, 0.85F, 1.60F, false);

    /** 风暴模式的落点数（服务端挖地 + 客户端画环都用同一个常量）。 */
    public static final int STORM_POINTS = 5;

    private final String id;
    private final String display;
    private final String codename;
    private final float radiusScale;
    private final float damageScale;
    private final float lockScale;
    private final float fallScale;
    private final float cooldownScale;
    /**
     * 是否「打穿到虚空」：true 时无视 {@code destroy_mode}，强制整列挖到世界底层。
     * 轨道炮和长矛是贯穿型武器（用户明确要求轨道炮能打穿基岩到虚空），
     * 奇点和风暴是范围型 —— 它们只压坑，要不要整列仍归 {@code destroy_mode} 管。
     */
    private final boolean pierces;

    OrbitalStrikeMode(String id, String display, String codename,
                      float radiusScale, float damageScale,
                      float lockScale, float fallScale, float cooldownScale,
                      boolean pierces) {
        this.id = id;
        this.display = display;
        this.codename = codename;
        this.radiusScale = radiusScale;
        this.damageScale = damageScale;
        this.lockScale = lockScale;
        this.fallScale = fallScale;
        this.cooldownScale = cooldownScale;
        this.pierces = pierces;
    }

    /** 这个模式是否强制整列挖穿到世界底层（含基岩，配置允许时）。 */
    public boolean pierces() {
        return pierces;
    }

    /** NBT / 配置里用的稳定标识（不要改，会丢存档里已选好的模式）。 */
    public String id() {
        return id;
    }

    /** HUD 上的中文名。 */
    public String display() {
        return display;
    }

    /** HUD 上的英文代号（「天陨-01 · SKYFALL」那一行的风格）。 */
    public String codename() {
        return codename;
    }

    /** 基础半径 → 本模式的实际半径（格）。 */
    public int radius(int baseRadius) {
        return Mth.clamp(Math.round(baseRadius * radiusScale), 1, 96);
    }

    /** 基础伤害倍率。 */
    public float damageScale() {
        return damageScale;
    }

    /** 基础锁定 tick → 本模式的前摇长度。 */
    public int lockTicks(int baseLockTicks) {
        return Mth.clamp(Math.round(baseLockTicks * lockScale), 20, 900);
    }

    /** 基础下落 tick → 本模式的下落长度。 */
    public int fallTicks(int baseFallTicks) {
        return Mth.clamp(Math.round(baseFallTicks * fallScale), 6, 120);
    }

    /** 基础冷却秒 → 本模式冷却（大杀器冷却更长）。 */
    public int cooldownSeconds(int baseCooldown) {
        if (baseCooldown <= 0) {
            return 0;
        }
        return Math.max(1, Math.round(baseCooldown * cooldownScale));
    }

    /** 切换顺序：轨道炮 → 长矛 → 奇点 → 风暴 → 回到轨道炮。 */
    public OrbitalStrikeMode next() {
        OrbitalStrikeMode[] values = values();
        return values[(ordinal() + 1) % values.length];
    }

    /** 从 NBT / 配置字符串解析；认不出来就回落到轨道炮（绝不因为拼错而让物品失效）。 */
    public static OrbitalStrikeMode byId(String id) {
        if (id != null) {
            String trimmed = id.trim();
            for (OrbitalStrikeMode mode : values()) {
                if (mode.id.equalsIgnoreCase(trimmed)) {
                    return mode;
                }
            }
        }
        return CANNON;
    }

    /**
     * 风暴模式的落点偏移（相对目标中心的 x/z，单位格）。
     *
     * <p>服务端和客户端必须得到<b>完全一样</b>的五个点：用「落点坐标的哈希」做种子，
     * 不用世界随机数 —— 这样同一个目标无论谁来算、算几次，坑和光环都落在同一处。</p>
     */
    public static double[][] stormOffsets(BlockPos target, int radius) {
        RandomSource random = RandomSource.create(target.asLong() * 0x9E3779B97F4A7C15L ^ 0x5705L);
        double[][] out = new double[STORM_POINTS][2];
        for (int i = 0; i < STORM_POINTS; i++) {
            double angle = (i + 0.5D) * (Math.PI * 2.0D / STORM_POINTS)
                    + (random.nextDouble() - 0.5D) * 0.7D;
            double dist = radius * (0.35D + random.nextDouble() * 0.55D);
            out[i][0] = Math.cos(angle) * dist;
            out[i][1] = Math.sin(angle) * dist;
        }
        return out;
    }
}
