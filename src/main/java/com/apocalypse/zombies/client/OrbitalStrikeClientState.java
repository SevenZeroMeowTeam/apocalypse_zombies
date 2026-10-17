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
    private static long startGameTime;

    private OrbitalStrikeClientState() {
    }

    /** 收到新的打击：覆盖旧的（同一时刻只支持一次打击的观感，够用且不会叠图）。 */
    public static void start(BlockPos pos, int radius, int lockTicks, int fallTicks, OrbitalStrikeMode mode) {
        target = pos.immutable();
        OrbitalStrikeClientState.radius = radius;
        OrbitalStrikeClientState.lockTicks = lockTicks;
        OrbitalStrikeClientState.fallTicks = Math.max(1, fallTicks);
        OrbitalStrikeClientState.mode = mode == null ? OrbitalStrikeMode.CANNON : mode;
        OrbitalStrikeClientState.startGameTime = now();
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
        return elapsed >= 0L && elapsed <= (long) lockTicks + fallTicks + AFTERGLOW_TICKS;
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
