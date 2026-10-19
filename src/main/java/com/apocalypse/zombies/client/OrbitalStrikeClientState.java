package com.apocalypse.zombies.client;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikePhase;
import com.apocalypse.zombies.orbital.engine.StrikeProtocol;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import net.minecraft.core.BlockPos;
import org.jetbrains.annotations.Nullable;

import java.util.UUID;

/**
 * 客户端「当前正在挨打的那一次轨道打击」的唯一状态。只被渲染读、被 packet 写 —— 
 * 不参与任何游戏判定，不向服务端回传。
 *
 * <p>v4.0 P3 起多了三个字段：本次打击的 {@link #strikeId}（相位/取消包靠它对号）、
 * {@link #spectator}（自己不是施放者、只是被广播）、以及服务端最后告知的
 * {@link #serverPhase}（HUD 显示权威相位，同时用来校正本地时间轴）。</p>
 *
 * <p><b>v4.0 P3-c 时间轴校正</b>：本地 {@code startGameTime} 只是「包到达那一刻」的客户端
 * gameTime，会比服务端真实起手晚 1~N tick（网络抖动、卡顿时会差更多），于是光柱落地与
 * 服务端结算、相位切换之间会出现肉眼可见的错拍。这里不改 {@code startGameTime}
 * （那会让镜头在相位边界瞬移），而是维护一个 {@link #phaseOffset}：收到相位包时用
 * {@code 协议.phaseStart(...)} 算出服务端认为的 elapsed，与本地 {@link #elapsed()} 差得超过
 * {@link #PHASE_DRIFT_THRESHOLD} tick 就把差值记进 {@link #phaseTarget}，之后每 tick 只追
 * {@link #PHASE_DRIFT_DECAY} 之外的 15%，一秒左右收敛到 1 tick 内。{@link #elapsed()} 返回
 * 「原始时长 + {@code round(phaseOffset)}」，镜头/光柱/相位条因此都跟着服务端走，但不会跳。</p>
 */
public final class OrbitalStrikeClientState {

    /** 下落阶段的默认 tick 数（服务端通过 {@link com.apocalypse.zombies.network.OrbitalStrikePacket} 传真实值）。 */
    public static final int DEFAULT_FALL_TICKS = 24;
    /** 落地后的余晖（渲染用，服务端不管）。 */
    public static final int AFTERGLOW_TICKS = 40;
    /** 服务端没告诉过相位时的哨兵值。 */
    public static final int NO_PHASE = -1;

    private static BlockPos target;
    private static int radius;
    private static int lockTicks;
    private static int fallTicks = DEFAULT_FALL_TICKS;
    private static OrbitalStrikeMode mode = OrbitalStrikeMode.CANNON;
    /** 触发时的朝向：断层裂谷用它决定折线方向。 */
    private static float yaw;
    private static long startGameTime;
    /** 本次打击标识；null = 旧路径（没有后续相位包）。 */
    @Nullable
    private static UUID strikeId;
    /** true = 我是被广播的旁观者，不是施放者。 */
    private static boolean spectator;
    /** 服务端最后告知的相位 ordinal；{@link #NO_PHASE} = 还没收到。 */
    private static int serverPhase = NO_PHASE;

    // ------------------------------------------------------------------ P3-c 时间轴校正

    /** 相位对表阈值（tick）：本地轴与服务端相位起点差超过它才校正（小抖动不值得动时间轴）。 */
    private static final double PHASE_DRIFT_THRESHOLD = 3.0D;
    /** 每 tick 保留的偏差比例：0.85 = 每 tick 追回 15%，约 1 秒收敛到 1 tick 内。 */
    private static final double PHASE_DRIFT_DECAY = 0.85D;
    /** 偏移上限（tick）：再离谱的漂移也不该让整场演出跳几十秒。 */
    private static final double PHASE_DRIFT_LIMIT = 200.0D;

    /** 当前已经叠加到 {@link #elapsed()} 上的时间偏移（tick，可为小数）。 */
    private static double phaseOffset;
    /** 平滑回追的目标偏移（tick）；相位包只改它，不动 {@code startGameTime}。 */
    private static double phaseTarget;

    /** 「打击已中止」提示的到期 gameTime；0 = 没有提示。 */
    private static long cancelNoticeUntil;
    /** 取消原因（{@link com.apocalypse.zombies.network.StrikeCancelPacket} 的常量），只给提示用。 */
    private static int cancelReason = -1;

    private OrbitalStrikeClientState() {
    }

    /** 收到新的打击：覆盖旧的（同一时刻只支持一次打击的观感，够用且不会叠图）。 */
    public static void start(BlockPos pos, int radius, int lockTicks, int fallTicks,
                             OrbitalStrikeMode mode, float yaw) {
        start(pos, radius, lockTicks, fallTicks, mode, yaw, null, false);
    }

    /** v4.0 P3：带标识与观众标记的版本。 */
    public static void start(BlockPos pos, int radius, int lockTicks, int fallTicks,
                             OrbitalStrikeMode mode, float yaw,
                             @Nullable UUID id, boolean spectator) {
        target = pos.immutable();
        OrbitalStrikeClientState.radius = radius;
        OrbitalStrikeClientState.lockTicks = lockTicks;
        OrbitalStrikeClientState.fallTicks = Math.max(1, fallTicks);
        OrbitalStrikeClientState.mode = mode == null ? OrbitalStrikeMode.CANNON : mode;
        OrbitalStrikeClientState.yaw = yaw;
        OrbitalStrikeClientState.startGameTime = now();
        OrbitalStrikeClientState.strikeId = id;
        OrbitalStrikeClientState.spectator = spectator;
        OrbitalStrikeClientState.serverPhase = NO_PHASE;
        phaseOffset = 0.0D;
        phaseTarget = 0.0D;
        cancelNoticeUntil = 0L;
        cancelReason = -1;
        com.apocalypse.zombies.client.renderer.OrbitalCinematic.onNewStrike();
    }

    /**
     * 服务端告知相位切换。
     *
     * <p>P3-c 起除了记录权威相位，还做一次<b>时间轴对表</b>：服务端认为这个相位应该从
     * {@code protocol.phaseStart(phase)} 开始，本地 {@link #elapsed()} 与它的差超过
     * {@link #PHASE_DRIFT_THRESHOLD} tick 就把差值记进 {@link #phaseTarget}；
     * 真正的追赶由 {@link #tick()} 每 tick 追 15%，避免在相位边界瞬移镜头。</p>
     */
    public static void onPhase(@Nullable UUID id, int phaseOrdinal) {
        if (target == null) {
            return;
        }
        if (id != null && strikeId != null && !id.equals(strikeId)) {
            return;
        }
        serverPhase = phaseOrdinal;
        applyPhaseCorrection(phaseOrdinal);
    }

    /**
     * 把本地时间轴往服务端相位起点对齐。
     *
     * <p>只改 {@link #phaseTarget}，不改 {@code startGameTime} —— 后者会让所有按 elapsed
     * 插值的镜头（升空/回位/拉远）在相位边界直接跳一段。相位 ordinal 越界（脏包）直接忽略。</p>
     */
    private static void applyPhaseCorrection(int phaseOrdinal) {
        StrikePhase[] phases = StrikePhase.values();
        if (phaseOrdinal < 0 || phaseOrdinal >= phases.length) {
            return;
        }
        StrikeProtocol protocol = StrikeProtocols.protocolFor(mode);
        double expected = protocol.phaseStart(phases[phaseOrdinal], lockTicks, fallTicks);
        double drift = expected - elapsed();
        if (Math.abs(drift) <= PHASE_DRIFT_THRESHOLD) {
            return;
        }
        double wanted = phaseOffset + drift;
        phaseTarget = Math.max(-PHASE_DRIFT_LIMIT, Math.min(PHASE_DRIFT_LIMIT, wanted));
    }

    /**
     * 每客户端 tick 一次：让时间偏移平滑回追目标值。
     *
     * <p>差值每 tick 乘 {@link #PHASE_DRIFT_DECAY}，也就是每次追 15%：一次 20 tick 的漂移
     * 约 1 秒收敛到 1 tick 内，过程中 {@link #elapsed()} 每次只走一两个 tick，渲染看不出跳变。</p>
     */
    public static void tick() {
        if (target == null) {
            phaseOffset = 0.0D;
            phaseTarget = 0.0D;
            return;
        }
        double difference = phaseTarget - phaseOffset;
        if (Math.abs(difference) < 0.05D) {
            phaseOffset = phaseTarget;
            return;
        }
        // phaseTarget - difference*0.85 == phaseOffset + difference*0.15
        phaseOffset = phaseTarget - difference * PHASE_DRIFT_DECAY;
    }

    /**
     * 服务端中止了这次打击：清画面状态并立刻交还镜头。
     *
     * <p>id 对不上就忽略 —— 防止上一发的取消包误杀刚起手的下一发。</p>
     */
    public static void cancel(@Nullable UUID id, int reason) {
        if (target == null) {
            return;
        }
        if (id != null && strikeId != null && !id.equals(strikeId)) {
            return;
        }
        // 状态清空后 HUD 还要能显示一行「打击已中止」：用 gameTime 记 3 秒窗口，不依赖 target。
        cancelNoticeUntil = now() + 60L;
        cancelReason = reason;
        clear();
        com.apocalypse.zombies.client.renderer.OrbitalCinematic.skip();
    }

    public static void clear() {
        target = null;
        strikeId = null;
        spectator = false;
        serverPhase = NO_PHASE;
        phaseOffset = 0.0D;
        phaseTarget = 0.0D;
    }

    /** 本次打击是否有唯一标识（旧路径没有）。 */
    @Nullable
    public static UUID strikeId() {
        return strikeId;
    }

    /** 我是不是被广播的旁观者。 */
    public static boolean spectator() {
        return spectator;
    }

    /** 服务端最后告知的相位 ordinal；{@link #NO_PHASE} = 还没收到。 */
    public static int serverPhase() {
        return serverPhase;
    }

    /** 服务端相位枚举；还没收到（{@link #NO_PHASE}）或脏包越界时返回 null（HUD 据此回退本地推算）。 */
    @Nullable
    public static StrikePhase serverPhaseValue() {
        StrikePhase[] phases = StrikePhase.values();
        if (serverPhase < 0 || serverPhase >= phases.length) {
            return null;
        }
        return phases[serverPhase];
    }

    /** 当前时间偏移（tick）：正 = 本地轴被往后拉（补上包延迟），负 = 往前追。诊断/测试用。 */
    public static double phaseOffsetTicks() {
        return phaseOffset;
    }

    /** 「打击已中止」提示是否还在 3 秒显示窗口内（此时 {@code target} 已经清空）。 */
    public static boolean cancelNoticeActive() {
        return cancelNoticeUntil > 0L && now() <= cancelNoticeUntil;
    }

    /** 取消原因（{@code StrikeCancelPacket.REASON_*}）；没有提示时返回 -1。 */
    public static int cancelReason() {
        return cancelReason;
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

    /**
     * 已经走过的 tick 数（用于光束下落进度 / 闪烁节奏 / 相位条）。
     *
     * <p>包含相位对表得到的时间偏移（见类注释）：原始值只反映「包什么时候到」，
     * 加上偏移后才是服务端眼里这一击已经走了多久。窗口判定（{@link #isActive()}）仍用原始值，
     * 避免偏移把观感窗口的上下界也一起拽动。</p>
     */
    public static long elapsed() {
        long raw = now() - startGameTime;
        return raw + Math.round(phaseOffset);
    }

    /** 未做相位校正的本地时长（tick）；窗口判定与调试用。 */
    public static long rawElapsed() {
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
