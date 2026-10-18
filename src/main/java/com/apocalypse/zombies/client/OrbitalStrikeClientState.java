package com.apocalypse.zombies.client;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;

/**
 * 客户端「当前正在挨打的那一次轨道打击」的唯一状态。只被渲染读、被 packet 写 —— 
 * 不参与任何游戏判定，不向服务端回传。
 */
public final class OrbitalStrikeClientState {

    /** 下落阶段的默认 tick 数（服务端通过 {@link com.apocalypse.zombies.network.OrbitalStrikePacket} 传真实值）。 */
    public static final int DEFAULT_FALL_TICKS = 24;
    /** 落地后的余晖（渲染用，服务端不管）。 */
    public static final int AFTERGLOW_TICKS = 40;

    private static BlockPos target;
    private static int radius;
    private static int lockTicks;
    private static int fallTicks = DEFAULT_FALL_TICKS;
    private static OrbitalStrikeMode mode = OrbitalStrikeMode.CANNON;
    /** 触发时的朝向：断层裂谷用它决定折线方向。 */
    private static float yaw;
    private static long startGameTime;

    private OrbitalStrikeClientState() {
    }

    /** 收到新的打击：覆盖旧的（同一时刻只支持一次打击的观感，够用且不会叠图）。 */
    public static void start(BlockPos pos, int radius, int lockTicks, int fallTicks,
                             OrbitalStrikeMode mode, float yaw) {
        target = pos.immutable();
        OrbitalStrikeClientState.radius = radius;
        OrbitalStrikeClientState.lockTicks = lockTicks;
        OrbitalStrikeClientState.fallTicks = Math.max(1, fallTicks);
        OrbitalStrikeClientState.mode = mode == null ? OrbitalStrikeMode.CANNON : mode;
        OrbitalStrikeClientState.yaw = yaw;
        OrbitalStrikeClientState.startGameTime = now();
        com.apocalypse.zombies.client.renderer.OrbitalCinematic.onNewStrike();
    }

    public static void clear() {
        target = null;
    }

    /** 当前是否还有东西要画。渲染器每帧调用一次。 */
    public static boolean isActive() {
        if (target == null) {
            return false;
        }
        long elapsed = now() - startGameTime;
        return elapsed >= 0L && elapsed <= (long) lockTicks + fallTicks + afterglowTicks();
    }

    /**
     * HUD 的存活窗口（比 {@link #isActive()} 短得多）。
     *
     * <p>宇宙激光的光柱要一直烧到虚空（几十秒），但火控角框、状态行、模式提示不该跟着挂那么久 ——
     * 那些是「发射流程」的 UI，打完就该收。</p>
     */
    public static boolean isHudActive() {
        if (target == null) {
            return false;
        }
        long elapsed = now() - startGameTime;
        return elapsed >= 0L && elapsed <= (long) lockTicks + fallTicks + AFTERGLOW_TICKS;
    }

    /**
     * 余晖长度：
     * <ul>
     *   <li>风暴是分批落地的（5 道 × {@link OrbitalStrikeMode#STORM_STAGGER_TICKS}），状态必须活到
     *       最后一两道落地 + 它们的冲击环播完；</li>
     *   <li>宇宙激光要**一直烧到虚空**：按整列挖掘的估算时长来活，否则光柱会在井还没挖到底时消失。</li>
     * </ul>
     */
    public static int afterglowTicks() {
        if (mode == OrbitalStrikeMode.STORM) {
            return AFTERGLOW_TICKS + OrbitalStrikeMode.STORM_STAGGER_TICKS
                    * (OrbitalStrikeMode.STORM_POINTS - 1);
        }
        if (mode == OrbitalStrikeMode.PLANET) {
            // 黑雨：撞击只是一瞬，毒雨要在场上活几十秒 —— 状态必须陪到雨停
            return Math.max(AFTERGLOW_TICKS, blackRainTicks() + 120);
        }
        if ((mode == OrbitalStrikeMode.LASER || mode == OrbitalStrikeMode.CANNON)
                && com.apocalypse.zombies.Config.ORBITAL_STRIKE_DESTROY_BLOCKS.get()) {
            // 激光烧穿、炮弹下钻 —— 两者都要活到整列挖掘结束（虚空）
            return estimateDigTicks();
        }
        return AFTERGLOW_TICKS;
    }

    /**
     * 估算整列挖掘要多少 tick —— 与服务端 {@code ColumnJob} 的每 tick 预算（4000 格）对齐。
     * 客户端只用来决定「光柱还该不该亮着」，不需要精确。
     */
    public static int estimateDigTicks() {
        var level = net.minecraft.client.Minecraft.getInstance().level;
        int span = level == null ? 384 : level.getMaxBuildHeight() - level.getMinBuildHeight();
        long cells = (2L * radius + 1L) * (2L * radius + 1L) * span;
        long ticks = cells / 4000L + 60L;
        return (int) Math.max(60L, Math.min(1400L, ticks));
    }

    public static BlockPos target() {
        return target;
    }

    public static int radius() {
        return radius;
    }

    /** 本次打击选的是哪种弹种（服务端说的算）。 */
    public static OrbitalStrikeMode mode() {
        return mode;
    }

    /** 触发时的朝向（度）；断层裂谷沿它展开。 */
    public static float yaw() {
        return yaw;
    }

    /** 已经走过的 tick 数（用于光束下落进度 / 闪烁节奏）。 */
    public static long elapsed() {
        return now() - startGameTime;
    }

    public static int lockTicks() {
        return lockTicks;
    }

    /** 当前是否还在锁定阶段（计时器已启动且未进入下落）。 */
    public static boolean isLockPhase() {
        if (!isActive()) {
            return false;
        }
        long elapsed = elapsed();
        return elapsed < lockTicks;
    }

    /** 锁定阶段进度 0→1（用于倒计时/红晕强度）。 */
    public static float lockProgress() {
        if (!isLockPhase()) {
            return 1.0F;
        }
        return net.minecraft.util.Mth.clamp((float) elapsed() / Math.max(1, lockTicks), 0.0F, 1.0F);
    }

    /** 落地后经过的 tick 数；还在下落/锁定阶段返回 -1。 */
    public static long impactAge() {
        if (!isActive()) {
            return -1L;
        }
        long impact = (long) lockTicks + fallTicks;
        long elapsed = elapsed();
        return elapsed < impact ? -1L : elapsed - impact;
    }

    /** 当前这次打击的下落时长（tick）。 */
    public static int fallTicks() {
        return fallTicks;
    }

    /** 黑雨持续时间（tick）——服务端配置的客户端镜像。 */
    public static int blackRainTicks() {
        return com.apocalypse.zombies.Config.ORBITAL_STRIKE_BLACK_RAIN_TICKS.get();
    }

    /** 毒雨是否还在下（撞击帧之后、持续时间之内）。 */
    public static boolean isBlackRainRaining() {
        if (mode != OrbitalStrikeMode.PLANET) {
            return false;
        }
        long age = impactAge();
        return age >= 0L && age < blackRainTicks();
    }

    /** 本机玩家到打击目标的距离（格）。玩家不在世界时返回一个很大的值。 */
    public static double distanceToPlayer() {
        var minecraft = net.minecraft.client.Minecraft.getInstance();
        if (target == null || minecraft.player == null) {
            return Double.MAX_VALUE;
        }
        return minecraft.player.position().distanceTo(net.minecraft.world.phys.Vec3.atCenterOf(target));
    }

    private static long now() {
        var level = net.minecraft.client.Minecraft.getInstance().level;
        return level == null ? -1L : level.getGameTime();
    }
}
