package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.RiftShape;
import com.apocalypse.zombies.orbital.engine.StrikeProtocol;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.apocalypse.zombies.orbital.engine.StrikePhase;
import com.apocalypse.zombies.registry.ModParticles;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobType;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraftforge.network.PacketDistributor;
import com.apocalypse.zombies.block.SkyfallTerminalBlockEntity;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.OrbitalStrikePacket;
import com.apocalypse.zombies.network.StrikeCancelPacket;
import com.apocalypse.zombies.network.StrikePhasePacket;
import org.jetbrains.annotations.Nullable;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 「轨道打击」的服务端主循环：玩家右键遥控器后，这里记一笔，按 tick 推进「锁定 → 下落 → 落地」三段。
 *
 * <p><b>三段时间轴</b>：锁定 {@code Config.ORBITAL_STRIKE_LOCK_TICKS}（默认 80 = 4 s）、
 * 下落 {@code Config.ORBITAL_STRIKE_FALL_TICKS}（默认 24 = 1.2 s，从 Y=320 落下来）、
 * 落地 tick 1（摧毁 + AOE 伤害 + 声音分层）。整个特效期间为该玩家单方执行 ——
 * 不同玩家各自记一条，多人互不干扰。</p>
 *
 * <p><b>为什么不在地上画轨迹</b>：从 Y=320 落下的「光柱」是为了视觉上像「从宇宙之外打下来」，
 * 不去模拟真实的弹道 —— 玩家瞄哪儿，光柱就笔直落在哪儿，没有任何抛物线或偏移。
 * 偏移/方向由玩家瞄的方向决定，瞄准者本人自负责。</p>
 */
public final class OrbitalStrikeManager {

    /** 从哪个高度开始往下打。Y=320 远高于世界构建上限（Y=256），所以视觉上像「从天上来的」。 */
    private static final double IMPACT_FALL_Y = 320.0D;
    /** 下落阶段每 tick 在光柱上的粒子密度。 */
    private static final int FALL_PARTICLES_PER_TICK = 12;
    /** 锁定阶段每 tick 在目标点周围 5x5x5 范围画的锁定粒子数。 */
    private static final int LOCK_PARTICLES_PER_TICK = 24;
    /** 落地 tick 时画的爆炸粒子数。 */
    private static final int IMPACT_PARTICLES = 96;

    private static final Map<UUID, ActiveStrike> ACTIVE = new HashMap<>();

    /**
     * 按距离延迟的雷声队列（1.8.0）：雷声 = 声音，速度 340 m/s —— 160 格外的玩家
     * 要 1~9 秒后才「听见」雷。落地帧先见光，雷声按玩家各自距离延迟到达，
     * 远近玩家的雷声不是同一拍 —— 这是「打击感」里最便宜也最真实的一层。
     * 玩家离线则雷声作废（sound 不会再发给已退出的人）。
     */
    private static final List<DelayedThunder> THUNDER_QUEUE = new ArrayList<>();

    /**
     * 黑雨的持续毒雨区：打击本身一 tick 就结束，但雨要下几十秒，
     * 且不依赖 {@link #ACTIVE}（施放者死了/退出了雨也照下）。
     */
    private static final List<ToxicRain> TOXIC_RAINS = new ArrayList<>();

    private static final class ToxicRain {
        final ServerLevel level;
        final double x;
        final double y;
        final double z;
        final int radius;
        final UUID owner;
        int remaining;
        int age;

        ToxicRain(ServerLevel level, Vec3 center, int radius, int duration, UUID owner) {
            this.level = level;
            this.x = center.x;
            this.y = center.y;
            this.z = center.z;
            this.radius = Math.max(6, radius);
            this.remaining = Math.max(20, duration);
            this.owner = owner;
        }
    }

    /** 延迟雷声：位置用玩家在落地帧的位置（不再追踪），到点就在原地炸雷。 */
    private static final class DelayedThunder {
        final ServerLevel level;
        final BlockPos pos;
        int delay;

        DelayedThunder(ServerLevel level, BlockPos pos, int delay) {
            this.level = level;
            this.pos = pos;
            this.delay = delay;
        }
    }

    /**
     * 大范围破坏的分批任务队列。radius=24 时选区是 49×49×49 ≈ 11.7 万个方块 ——
     * 一个 tick 里全挖掉会把主线程卡死几秒，所以拆成每 tick 最多 {@link #BLOCKS_PER_TICK} 个，
     * 顺带获得「地面从中间向外一圈圈塌下去」的观感。
     */
    private static final List<DestroyJob> DESTROY_QUEUE = new ArrayList<>();
    private static final int BLOCKS_PER_TICK = 4000;

    /** 每 tick 允许发出的「碎屑批」上限（每批 2 颗真实方块粒子）—— 防止整层塌方把网络刷爆。 */
    private static final int DEBRIS_BATCHES_PER_TICK = 28;
    /** 单个方块被挖掉时冒碎屑的概率；真正的总量由上面的预算兜底。 */
    private static final float DEBRIS_CHANCE = 0.010F;
    /** 本 tick 剩余的碎屑预算，每 tick 开头重置。 */
    private static int debrisBudget;

    /** 调试用 —— 暂时不开。{@code Config.ORBITAL_STRIKE_DEBUG.get()} 才打开。 */
    private static final boolean DEBUG = false;

    private OrbitalStrikeManager() {
    }

    /** 一次性把 {@link OrbitalStrikeManager} 挂到 {@code MinecraftForge.EVENT_BUS}。 */
    public static void register() {
        MinecraftForge.EVENT_BUS.register(OrbitalStrikeManager.class);
    }

    /**
     * 玩家右键触发了一次轨道打击：在目标点开始三段倒计时。
     *
     * <p>半径 / 前摇 / 下落都先按 {@link OrbitalStrikeMode} 的倍率换算成最终值，
     * 再存进 {@link ActiveStrike} 并随包发给客户端 —— 两边用的是同一组数。</p>
     *
     * <p>同一玩家在冷却期间重复右键会覆盖原有目标（避免队列堆叠 + 误触重置阶段）。</p>
     */
    @Nullable
    public static UUID schedule(ServerPlayer player, BlockPos target, OrbitalStrikeMode mode) {
        return schedule(player, target, mode, 0, 1.0F, 1.0F, null);
    }

    /**
     * 带覆盖参数的入口：遥控器自由开火走三参版本（全部沿用配置）；天陨终端授权时
     * 把终端面板上的半径 / 威力 / 下落速度带进来。
     *
     * <p><b>为什么半径是「绝对值」而不是倍率</b>：{@code SkyfallTerminalBlockEntity#radius()}
     * 已经把「配置半径 × 弹种倍率 × 终端滑条」算好并夹到终端上限，这里直接当最终半径用；
     * 服务端与客户端收到的（{@link com.apocalypse.zombies.network.OrbitalStrikePacket}）
     * 仍是同一个数，演出和挖地不会错位。</p>
     *
     * @param radius    终端算好的最终半径（格）；{@code <= 0} 表示沿用 {@code orbital_strike_radius} × 弹种倍率
     * @param damageMul 伤害倍率（1.0 = 原伤害；终端滑条 0.5~2.0）
     * @param fallMul   下落段速度倍率（1.0 = 原时长，> 1 更快；下落 tick 按 1/fallMul 缩短）
     */
    @Nullable
    public static UUID schedule(ServerPlayer player, BlockPos target, OrbitalStrikeMode mode,
                                int radius, float damageMul, float fallMul) {
        return schedule(player, target, mode, radius, damageMul, fallMul, null);
    }

    /**
     * v4.0 P3 完整入口：多带一个终端坐标（取消时用来退款），并返回本次打击 id。
     *
     * <p>返回 {@code null} = 被并发上限拒绝（提示已经发给玩家），调用方<b>不得</b>给终端扣充能。</p>
     *
     * @param terminalPos 授权来源终端；自由开火传 {@code null}
     */
    @Nullable
    public static UUID schedule(ServerPlayer player, BlockPos target, OrbitalStrikeMode mode,
                                int radius, float damageMul, float fallMul,
                                @Nullable BlockPos terminalPos) {
        int maxConcurrent = Math.max(1, Config.ORBITAL_STRIKE_MAX_CONCURRENT.get());
        if (ACTIVE.size() >= maxConcurrent) {
            player.displayClientMessage(Component.translatable("skyfall.strike.busy"), true);
            return null;
        }
        // 轨道设施维度是“参观区”：里面打任何协议，镜头看到的都是同一片星空 + 同一台卫星，
        // 会被误判成“六种效果一样”。统一在这里拒绝，让玩家回主世界打。
        if (player.level().dimension().equals(com.apocalypse.zombies.orbit.OrbitDimension.LEVEL)) {
            player.displayClientMessage(Component.literal(
                    "轨道设施维度内不能发射打击 —— 这里是参观区，请回主世界开火。"), true);
            return null;
        }
        int finalRadius = radius > 0
                ? radius
                : mode.radius(Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 96));
        int lockTicks = mode.lockTicks(Math.max(20, Config.ORBITAL_STRIKE_LOCK_TICKS.get()));
        int fallTicks = mode.fallTicks(Math.max(6, Config.ORBITAL_STRIKE_FALL_TICKS.get()));
        float yaw = player.getYRot();
        StrikeProtocol protocol = StrikeProtocols.protocolFor(mode);
        // v2 断层：前摇按协议 XML 的 mark+ascent+device 走，让电影相位和服务端完全对齐。
        if (protocol.migrated()) {
            lockTicks = Math.max(60, protocol.preFireTicks());
            // 蜂群要容下七枚巢荚的脱离，固定 56t；其余协议沿用各自弹种的下落倍率
            // （黎明 6t 光速、黑雨 43t 小行星飞行、焚城 24t、隔离 26t、断层 30t）。
            fallTicks = "swarm".equals(protocol.id())
                    ? 56
                    : mode.fallTicks(Math.max(6, Config.ORBITAL_STRIKE_FALL_TICKS.get()));
        }
        // 终端的下落速度倍率在**协议迁移之后**才乘：协议决定「这一击该演多久」，
        // 玩家滑条是在这个基准上加速/减速。速度倍率 → 时长倍率的倒数，且不短于 6t。
        float safeFallMul = fallMul > 0.0F ? fallMul : 1.0F;
        fallTicks = Math.max(6, Math.round(fallTicks / safeFallMul));
        // 威力滑条异常值（0/负/NaN）按 1.0 处理：宁可伤害不缩放，也不要变成治疗或负数。
        float safeDamageMul = damageMul > 0.0F ? damageMul : 1.0F;

        UUID strikeId = UUID.randomUUID();
        List<UUID> viewers = collectViewers(player, target);
        ACTIVE.put(player.getUUID(), new ActiveStrike(target.immutable(), player.getUUID(),
                player.level().dimension(), mode, finalRadius, lockTicks, fallTicks, yaw,
                safeDamageMul, strikeId, terminalPos, viewers));
        // 视觉：P3 起按收件人逐个发（施放者 spectator=false，附近玩家 spectator=true）。
        long serverTime = player.level().getGameTime();
        for (UUID id : viewers) {
            ServerPlayer viewer = findPlayer(player.getServer(), id);
            if (viewer == null) {
                continue;
            }
            boolean spectator = !viewer.getUUID().equals(player.getUUID());
            NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> viewer),
                    new OrbitalStrikePacket(target, finalRadius, lockTicks, fallTicks, mode, yaw,
                            strikeId, spectator, serverTime));
        }
        return strikeId;
    }

    /**
     * 开场收件人：施放者 + 广播半径内的玩家（`broadcast_films=false` 时只有施放者）。
     *
     * <p>只收同一维度、同等级的玩家；离线/换维度在发包时再校验一次。</p>
     */
    private static List<UUID> collectViewers(ServerPlayer caster, BlockPos target) {
        List<UUID> viewers = new ArrayList<>();
        viewers.add(caster.getUUID());
        if (!Config.ORBITAL_STRIKE_BROADCAST_FILMS.get()) {
            return viewers;
        }
        MinecraftServer server = caster.getServer();
        if (server == null) {
            return viewers;
        }
        double range = Config.ORBITAL_STRIKE_BROADCAST_RADIUS.get();
        double rangeSq = range * range;
        double x = target.getX() + 0.5D;
        double y = target.getY() + 0.5D;
        double z = target.getZ() + 0.5D;
        for (ServerPlayer other : server.getPlayerList().getPlayers()) {
            if (other.getUUID().equals(caster.getUUID()) || other.level() != caster.level()) {
                continue;
            }
            if (other.distanceToSqr(x, y, z) <= rangeSq) {
                viewers.add(other.getUUID());
            }
        }
        return viewers;
    }

    private static ServerPlayer findPlayer(MinecraftServer server, UUID id) {
        return server == null ? null : server.getPlayerList().getPlayer(id);
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        // 碎屑预算每 tick 重置：塌方是「持续下」的，不是一口气喷完。
        debrisBudget = DEBRIS_BATCHES_PER_TICK;
        // 先推进「分批破坏」队列 —— 它和打击生命期无关（打击早结束了地还在塌）。
        // 全局预算：不管同时排了几个任务，每 tick 总共最多挖 BLOCKS_PER_TICK 个，
        // 无冷却狂点时任务会排队而不是一次全砸下来。
        if (!THUNDER_QUEUE.isEmpty()) {
            Iterator<DelayedThunder> tit = THUNDER_QUEUE.iterator();
            while (tit.hasNext()) {
                DelayedThunder thunder = tit.next();
                if (--thunder.delay > 0) {
                    continue;
                }
                tit.remove();
                // 在玩家当时的位置原地响：距离衰减已经由「延迟」表达过了，音量给足
                thunder.level.playSound(null, thunder.pos, SoundEvents.LIGHTNING_BOLT_THUNDER,
                        SoundSource.WEATHER, 2.2F, 0.55F);
            }
        }
        if (!DESTROY_QUEUE.isEmpty()) {
            int budget = Math.max(500, Config.ORBITAL_STRIKE_BLOCK_BUDGET.get());
            Iterator<DestroyJob> dit = DESTROY_QUEUE.iterator();
            while (dit.hasNext() && budget > 0) {
                DestroyJob job = dit.next();
                budget -= job.step(budget);
                if (job.done()) {
                    dit.remove();
                }
            }
        }
        // 毒雨独立推进：它比打击本身活得久，且 ACTIVE 清空后还要继续。
        tickToxicRains();
        if (ACTIVE.isEmpty()) {
            return;
        }
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            for (ActiveStrike strike : ACTIVE.values()) {
                broadcastCancel(strike, StrikeCancelPacket.REASON_CONFIG_OFF);
            }
            ACTIVE.clear();
            return;
        }
        Iterator<Map.Entry<UUID, ActiveStrike>> it = ACTIVE.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<UUID, ActiveStrike> entry = it.next();
            ActiveStrike strike = entry.getValue();
            ServerLevel level = resolveLevel(strike);
            if (level == null) {
                broadcastCancel(strike, StrikeCancelPacket.REASON_WORLD_UNLOAD);
                it.remove();
                continue;
            }
            // 年龄与时长都在 ActiveStrike 上：模式倍率已经在 schedule 时乘过了。
            int age = ++strike.age;
            // v4.0 P3：相位切换时给所有观众发一次权威相位（整场约 6 个包）。
            StrikeProtocol strikeProtocol = StrikeProtocols.protocolFor(strike.mode);
            StrikePhase phase = strikeProtocol.phaseAt(age, strike.lockTicks, strike.fallTicks);
            if ((byte) phase.ordinal() != strike.lastPhase) {
                strike.lastPhase = (byte) phase.ordinal();
                sendPhase(strike, phase);
            }
            if (age < strike.lockTicks) {
                tickLocking(level, strike);
            } else if (age < strike.lockTicks + strike.fallTicks) {
                tickFalling(level, strike, age - strike.lockTicks);
            } else if (strike.mode == OrbitalStrikeMode.STORM) {
                // 风暴：五道闪电**分批落地**，每 STORM_STAGGER_TICKS 落一道，不是一发全砸。
                int since = age - (strike.lockTicks + strike.fallTicks);
                // 还在路上的那几道继续拖尾（玩家看得到下一道正在来）
                tickStormIncoming(level, strike, since);
                if (since % OrbitalStrikeMode.STORM_STAGGER_TICKS == 0) {
                    int index = since / OrbitalStrikeMode.STORM_STAGGER_TICKS;
                    if (index < OrbitalStrikeMode.STORM_POINTS) {
                        impactStormBolt(level, strike, index);
                    }
                    if (index >= OrbitalStrikeMode.STORM_POINTS - 1) {
                        sendPhase(strike, StrikePhase.AFTERMATH);
                        it.remove();
                    }
                }
            } else {
                tickImpact(level, strike);
                // 命中已发生：移除前补发最后一个相位，HUD 才会从 IMPACT 走到 AFTERMATH。
                sendPhase(strike, StrikePhase.AFTERMATH);
                it.remove();
            }
        }
    }

    /**
     * 关服/退世界：清空所有挂起状态。否则下一次进世界时，静态表里的旧打击/毒雨
     * 会按旧坐标落在新世界的同一点上（ACTIVE 也是同理，顺手一起清）。
     */
    @SubscribeEvent
    public static void onServerStopping(net.minecraftforge.event.server.ServerStoppingEvent event) {
        // 先告诉所有观众「这一发不演了」，再清表 —— 否则客户端镜头会挂在太空。
        for (ActiveStrike strike : ACTIVE.values()) {
            broadcastCancel(strike, StrikeCancelPacket.REASON_WORLD_UNLOAD);
        }
        ACTIVE.clear();
        TOXIC_RAINS.clear();
        THUNDER_QUEUE.clear();
        DESTROY_QUEUE.clear();
    }

    /** 跨维度（拿到玩家所在维度的 ServerLevel）。玩家离线不影响 —— 已启动的打击照常走完。 */
    private static ServerLevel resolveLevel(ActiveStrike strike) {
        net.minecraft.server.MinecraftServer server = net.minecraftforge.server.ServerLifecycleHooks.getCurrentServer();
        if (server == null) {
            return null;
        }
        ServerLevel level = server.getLevel(strike.dimension);
        if (level == null) {
            return null;
        }
        return level;
    }

    private static void tickLocking(ServerLevel level, ActiveStrike strike) {
        BlockPos target = strike.target;
        // 地面中心点
        Vec3 ground = Vec3.atCenterOf(target);
        int age = strike.age;
        float progress = Mth.clamp((float) age / Math.max(1, strike.lockTicks), 0.0F, 1.0F);
        // 前摇现在是可配置的长过程（默认 7 s），粒子按 tick 节流，否则会刷成一片白。
        if ((age & 1) == 0) {
            for (int i = 0; i < LOCK_PARTICLES_PER_TICK; i++) {
                double ox = (level.random.nextDouble() - 0.5D) * 6.0D;
                double oy = (level.random.nextDouble() - 0.5D) * 3.0D;
                double oz = (level.random.nextDouble() - 0.5D) * 6.0D;
                broadcast(level, ParticleTypes.END_ROD, ground.x + ox, ground.y + oy, ground.z + oz,
                        1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        }
        // 每 8 tick 一次的电弧音。
        // 音量 3 = 48 格可闻：见证机位拉出去之后仍听得到「还在锁定」。
        if (age % 8 == 0) {
            level.playSound(null, target, SoundEvents.BEACON_AMBIENT, SoundSource.PLAYERS,
                    3.0F, 1.8F);
        }
        // 自定义「能量火花」：从外圈向目标点聚拢（count=0 才能用显式初速度）。
        // 收拢半径按模式变 —— 长矛像在压缩一根针，奇点像在把一整片区域拽过来。
        double near = switch (strike.mode) {
            case LANCE -> 1.6D;
            case GRAVITY -> 7.0D;
            case STORM -> 5.0D;
            default -> 3.5D;
        };
        double far = near + switch (strike.mode) {
            case LANCE -> 1.6D;
            case GRAVITY -> 5.0D;
            case STORM -> 4.0D;
            default -> 3.5D;
        };
        if ((age & 1) == 0) {
            double speed = 0.10D + progress * 0.18D;
            for (int i = 0; i < 3; i++) {
                double ang = level.random.nextDouble() * Math.PI * 2.0D;
                double dist = near + level.random.nextDouble() * (far - near);
                double sx = ground.x + Math.cos(ang) * dist;
                double sz = ground.z + Math.sin(ang) * dist;
                double sy = ground.y + 2.0D + level.random.nextDouble() * 5.0D;
                broadcast(level, ModParticles.ORBITAL_SPARK.get(),
                        sx, sy, sz, 0,
                        (ground.x - sx) * speed, (ground.y + 0.5D - sy) * speed, (ground.z - sz) * speed,
                        0.0D);
            }
        }
        // 第一帧：轨道平台「上线」的提示音（与客户端平台渲染同时出现）
        if (age == 1) {
            level.playSound(null, target, SoundEvents.BEACON_POWER_SELECT, SoundSource.PLAYERS,
                    4.0F, 1.4F);
        }
        // 「太空里有人按了按钮」：前摇阶段在高空稀疏撒星点 —— 玩家抬头能看到上面有动静
        if ((age & 3) == 0) {
            double sx = (level.random.nextDouble() - 0.5D) * 10.0D;
            double sz = (level.random.nextDouble() - 0.5D) * 10.0D;
            broadcast(level, ParticleTypes.END_ROD,
                    ground.x + sx, IMPACT_FALL_Y + level.random.nextDouble() * 24.0D, ground.z + sz,
                    1, 0.0D, -0.1D, 0.0D, 0.0D);
        }
        // 风暴模式：五个落点提前冒电荷，让「这一发会撒在哪」在落地前就看得到
        if (strike.mode == OrbitalStrikeMode.STORM && (age & 3) == 0) {
            double[][] offsets = OrbitalStrikeMode.stormOffsets(target, strike.radius);
            for (double[] offset : offsets) {
                broadcast(level, ParticleTypes.END_ROD,
                        ground.x + offset[0],
                        ground.y + 1.0D + level.random.nextDouble() * 2.0D,
                        ground.z + offset[1], 1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        }
        if (DEBUG) {
            ApocalypseZombies.LOGGER.info("[orbital] lock tick {} mode={} target={}", age, strike.mode, target);
        }
    }

    private static void tickFalling(ServerLevel level, ActiveStrike strike, int local) {
        int fallTicks = strike.fallTicks;
        // local ∈ [0, fallTicks)；+1 让最后一帧正好压到地面（t = fallTicks/fallTicks = 1.0），
        // 否则光柱头永远停在地面上方约一格，落地瞬间会「跳一格」。
        double t = (double) (local + 1) / fallTicks;
        double y = Mth.lerp(t, IMPACT_FALL_Y, strike.target.getY() + 1.0D);
        Vec3 ground = Vec3.atCenterOf(strike.target);
        // 引力奇点：下落段就把周围生物往落点拽 —— 这是它和别的模式最不一样的地方
        if (strike.mode == OrbitalStrikeMode.GRAVITY
                && !"quarantine".equals(StrikeProtocols.protocolFor(strike.mode).id())) {
            pullToward(level, strike, t);
        }
        // 下落粒子也按模式分 —— 客户端是四套形态，世界里就不能还是同一根柱。
        if (strike.mode == OrbitalStrikeMode.STORM) {
            // 风暴：五道闪电各自的下落窗口（分批落地），这里只负责还在路上的那几道的拖尾
            tickStormIncoming(level, strike, local - strike.fallTicks);
        } else if (strike.mode == OrbitalStrikeMode.LANCE) {
            // 长矛：一条细长的白热尾（52 格），没有粗柱
            for (int i = 0; i < 8; i++) {
                double fy = y - level.random.nextDouble() * 52.0D;
                broadcast(level, ParticleTypes.END_ROD, ground.x, fy, ground.z,
                        1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        } else if (strike.mode == OrbitalStrikeMode.GRAVITY) {
            // 奇点：粒子从四周向焦点收（配合 pullToward）
            for (int i = 0; i < 6; i++) {
                double ang = level.random.nextDouble() * Math.PI * 2.0D;
                double dist = 3.0D + level.random.nextDouble() * 6.0D;
                double sx = ground.x + Math.cos(ang) * dist;
                double sz = ground.z + Math.sin(ang) * dist;
                double sy = y + (level.random.nextDouble() - 0.5D) * 6.0D;
                double speed = 0.10D;
                broadcast(level, ModParticles.ORBITAL_SPARK.get(), sx, sy, sz, 0,
                        (ground.x - sx) * speed, (y - sy) * speed, (ground.z - sz) * speed, 0.0D);
            }
        } else if (strike.mode == OrbitalStrikeMode.PLANET) {
            // 行星陨落：陨石斜着切进来，沿路径拖一条火尾 + 烟
            double[] offset = OrbitalStrikeMode.meteorOffset(strike.target);
            double startX = ground.x + offset[0];
            double startZ = ground.z + offset[1];
            double headX = Mth.lerp(t, startX, ground.x);
            double headY = Mth.lerp(t, strike.mode.originY(), ground.y);
            double headZ = Mth.lerp(t, startZ, ground.z);
            for (int i = 0; i < 8; i++) {
                double jx = (level.random.nextDouble() - 0.5D) * 3.0D;
                double jy = (level.random.nextDouble() - 0.5D) * 3.0D;
                double jz = (level.random.nextDouble() - 0.5D) * 3.0D;
                broadcast(level, ParticleTypes.FLAME, headX + jx, headY + jy, headZ + jz,
                        1, 0.0D, -0.15D, 0.0D, 0.03D);
                if ((i & 1) == 0) {
                    broadcast(level, ParticleTypes.LARGE_SMOKE, headX + jx * 1.6D,
                            headY + jy * 1.6D, headZ + jz * 1.6D,
                            1, 0.0D, 0.02D, 0.0D, 0.01D);
                }
                broadcast(level, ModParticles.ORBITAL_SPARK.get(), headX + jx, headY + jy, headZ + jz,
                        1, 0.35D, -0.25D, 0.35D, 0.20D);
            }
        } else if (strike.mode == OrbitalStrikeMode.LASER) {
            // 宇宙激光：整根柱子同时亮 —— 光没有飞行时间，没有「下落头」可画
            for (int i = 0; i < 18; i++) {
                double fy = ground.y + level.random.nextDouble() * strike.mode.originY();
                broadcast(level, ParticleTypes.END_ROD, ground.x, fy, ground.z,
                        1, 0.0D, -0.20D, 0.0D, 0.0D);
                if ((i & 1) == 0) {
                    broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, fy, ground.z,
                            1, 0.40D, -0.10D, 0.40D, 0.12D);
                }
            }
        } else {
            // 轨道炮：短粗的弹体尾迹（只拖弹体上方 7 格）+ 烟
            for (int i = 0; i < FALL_PARTICLES_PER_TICK; i++) {
                double fy = y + level.random.nextDouble() * 7.0D;
                double ox = (level.random.nextDouble() - 0.5D) * 2.2D;
                double oz = (level.random.nextDouble() - 0.5D) * 2.2D;
                broadcast(level, ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, fy, ground.z + oz,
                        1, 0.0D, -0.15D, 0.0D, 0.0D);
                if ((i & 1) == 0) {
                    broadcast(level, ParticleTypes.LARGE_SMOKE, ground.x + ox, fy - 2.0D, ground.z + oz,
                            1, 0.0D, 0.02D, 0.0D, 0.01D);
                }
            }
        }
        // 下落音（从远到近越来越响；每 4 tick 一声，否则连成噪音）。
        // 「两拍静默」：落地前 2 tick 截止 —— 让那一声轰鸣落在真空上（1.8.0 打击感）。
        if (local % 4 == 0 && local + 2 < fallTicks) {
            float volume = 0.6F + (float) t * 2.4F;
            float pitch = 0.6F + (float) t * 0.8F;
            level.playSound(null, strike.target, SoundEvents.BLAZE_SHOOT, SoundSource.PLAYERS, volume, pitch);
        }
    }

    /**
     * 风暴的「还在路上的闪电」拖尾。
     *
     * <p>第 i 道在第 {@code i * STORM_STAGGER_TICKS} tick 落地，落地前 {@code fallTicks} 开始下落，
     * 所以它的下落窗口是 {@code [i*stagger - fallTicks, i*stagger]}。{@code since} 是相对
     * 「第一道落地」的 tick 数（下落阶段是负数）—— 这样从下落段到整场风暴结束都用同一套判定。</p>
     */
    private static void tickStormIncoming(ServerLevel level, ActiveStrike strike, int since) {
        Vec3 ground = Vec3.atCenterOf(strike.target);
        double[][] offsets = OrbitalStrikeMode.stormOffsets(strike.target, strike.radius);
        int fallTicks = Math.max(1, strike.fallTicks);
        int stagger = OrbitalStrikeMode.STORM_STAGGER_TICKS;
        for (int i = 0; i < offsets.length; i++) {
            int land = i * stagger;
            int start = land - fallTicks;
            if (since < start || since >= land) {
                continue;
            }
            double t = Mth.clamp((double) (since - start + 1) / fallTicks, 0.0D, 1.0D);
            double y = Mth.lerp(t, IMPACT_FALL_Y, ground.y);
            double bx = ground.x + offsets[i][0];
            double bz = ground.z + offsets[i][1];
            for (int k = 0; k < 3; k++) {
                double fy = y - level.random.nextDouble() * 12.0D;
                broadcast(level, ParticleTypes.ELECTRIC_SPARK,
                        bx + (level.random.nextDouble() - 0.5D) * 0.8D, fy,
                        bz + (level.random.nextDouble() - 0.5D) * 0.8D,
                        1, 0.0D, -0.20D, 0.0D, 0.15D);
            }
        }
    }

    /**
     * 引力奇点的吸附：把半径 {@code max(8, radius*2.2)} 内的活物朝落点上方拽。
     * 越近越强、越到后段越强；{@code hurtMarked} 让玩家客户端的速度也同步。
     */
    private static void pullToward(ServerLevel level, ActiveStrike strike, double t) {
        Vec3 center = Vec3.atCenterOf(strike.target).add(0.0D, 2.0D, 0.0D);
        double pullRadius = Math.max(8.0D, strike.radius * 2.2D);
        AABB box = new AABB(center, center).inflate(pullRadius);
        for (LivingEntity entity : level.getEntitiesOfClass(LivingEntity.class, box)) {
            if (entity.isRemoved() || entity.isSpectator()) {
                continue;
            }
            Vec3 delta = center.subtract(entity.position());
            double dist = delta.length();
            if (dist < 0.5D || dist > pullRadius) {
                continue;
            }
            double strength = (0.03D + 0.07D * (1.0D - dist / pullRadius)) * (0.4D + t * 0.6D);
            entity.push(delta.x / dist * strength, delta.y / dist * strength * 0.7D, delta.z / dist * strength);
            entity.hurtMarked = true;
        }
    }

    /** 落地：按弹种分派。半径 / 时长在服务端已按模式缩放过，这里直接用 {@code strike} 里的最终值。 */
    private static void tickImpact(ServerLevel level, ActiveStrike strike) {
        Vec3 ground = Vec3.atCenterOf(strike.target);
        boolean destroy = Config.ORBITAL_STRIKE_DESTROY_BLOCKS.get();
        boolean damage = Config.ORBITAL_STRIKE_DAMAGE_MOBS.get();
        // 远雷按距离延迟：雷声 = 声音（340 m/s）—— 每个玩家按自己到落点的距离各自延迟
        // （1 格 = 1 米：160 格 ≈ 0.47 s ≈ 9.4 tick），近的先听见、远的后听见，320 格外不闻雷。
        queueThunder(level, ground);

        switch (strike.mode) {
            case LANCE -> impactLance(level, strike, ground, strike.radius, destroy, damage);
            case GRAVITY -> impactGravity(level, strike, ground, strike.radius, destroy, damage);
            case STORM -> {
                // 风暴永远走 onServerTick 里的分批分支，这里只是保底（不该被走到）
                impactStormBolt(level, strike, 0);
            }
            case LASER -> impactLaser(level, strike, ground, strike.radius, destroy, damage);
            case PLANET -> impactPlanet(level, strike, ground, strike.radius, destroy, damage);
            default -> impactCannon(level, strike, ground, strike.radius, destroy, damage);
        }
    }

    /**
     * 焚城 CINDER：轨道钨棒贯穿 + 坑沿火风暴 + 灰烬雨。
     * 地形仍是整列贯穿（ColumnJob），额外的「焚城」由坑沿熔岩/火焰粒子与余烬表达。
     */
    private static void impactCinder(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                     int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, true);
            placeCinderRim(level, target, radius);
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.CANNON, strike.damageMul);
        }
        spawnSurfaceDebris(level, target, radius);
        spawnCinderStorm(level, ground, radius);
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 5.0F, 0.55F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.55F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 4.0F, 0.45F);
        level.playSound(null, target, SoundEvents.FIRE_AMBIENT, SoundSource.PLAYERS, 4.0F, 0.6F);
        level.playSound(null, target, SoundEvents.LAVA_AMBIENT, SoundSource.PLAYERS, 3.0F, 0.5F);
    }

    /** 坑沿一圈熔岩斑：只铺地表，稀疏放置，避免烧穿/连锁。 */
    private static void placeCinderRim(ServerLevel level, BlockPos target, int radius) {
        int segments = Math.max(24, Math.min(96, radius * 4));
        double ringR = radius + 3.0D;
        for (int i = 0; i < segments; i++) {
            if (i % 3 != 0) {
                continue;
            }
            double angle = i * Math.PI * 2.0D / segments;
            int x = target.getX() + (int) Math.round(Math.cos(angle) * ringR);
            int z = target.getZ() + (int) Math.round(Math.sin(angle) * ringR);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(x, 0, z));
            if (level.getBlockState(surface).isAir() && !level.getBlockState(surface.below()).isAir()) {
                level.setBlockAndUpdate(surface, Blocks.MAGMA_BLOCK.defaultBlockState());
            }
        }
    }

    /** 火风暴：坑沿的火焰/熔岩/灰烬粒子，持续到余烬阶段由客户端接手。 */
    private static void spawnCinderStorm(ServerLevel level, Vec3 ground, int radius) {
        int flames = Math.min(260, 60 + radius * 7);
        for (int i = 0; i < flames; i++) {
            double ang = level.random.nextDouble() * Math.PI * 2.0D;
            double dist = radius * (0.65D + level.random.nextDouble() * 0.75D);
            double x = ground.x + Math.cos(ang) * dist;
            double z = ground.z + Math.sin(ang) * dist;
            broadcast(level, level.random.nextBoolean() ? ParticleTypes.FLAME : ParticleTypes.SOUL_FIRE_FLAME,
                    x, ground.y + 0.5D + level.random.nextDouble() * 2.0D, z,
                    1, 0.0D, 0.14D + level.random.nextDouble() * 0.16D, 0.0D, 0.03D);
            if (i % 3 == 0) {
                broadcast(level, ParticleTypes.LARGE_SMOKE, x, ground.y + 1.0D, z,
                        1, 0.0D, 0.08D, 0.0D, 0.02D);
            }
            if (i % 9 == 0) {
                broadcast(level, ParticleTypes.LAVA, x, ground.y + 0.4D, z,
                        1, 0.0D, 0.20D, 0.0D, 0.05D);
            }
        }
        int ash = Math.min(180, 40 + radius * 5);
        for (int i = 0; i < ash; i++) {
            double x = ground.x + (level.random.nextDouble() - 0.5D) * radius * 3.0D;
            double z = ground.z + (level.random.nextDouble() - 0.5D) * radius * 3.0D;
            double y = ground.y + 2.0D + level.random.nextDouble() * radius * 0.9D;
            broadcast(level, ModParticles.ORBITAL_EMBER.get(), x, y, z, 0,
                    (level.random.nextDouble() - 0.5D) * 0.10D,
                    0.03D + level.random.nextDouble() * 0.08D,
                    (level.random.nextDouble() - 0.5D) * 0.10D, 0.0D);
        }
    }

    /**
     * 行星陨落：一颗陨石斜着砸下来 —— 又大又浅的坑 + 强径向击退 + 漫天火雨。
     * 和轨道炮的垂直贯穿不同，它是「撞击事件」：范围更大、坑更浅、击退更狠。
     */
    private static void impactPlanet(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                     int radius, boolean destroy, boolean damage) {
        // v2：行星陨落 = 黑雨协议（脏弹陨石 + 持续毒雨），旧火雨保留给未迁移的弹种。
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        if ("black_rain".equals(protocol.id())) {
            impactBlackRain(level, strike, ground, radius, destroy, damage);
            return;
        }
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.PLANET, strike.damageMul);
        }
        spawnSurfaceDebris(level, target, radius);
        // 声音：一记闷到胸口的地动 + 高频碎裂
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 5.0F, 0.45F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.40F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 4.0F, 0.35F);
        level.playSound(null, target, SoundEvents.ANVIL_LAND, SoundSource.PLAYERS, 4.0F, 0.35F);
        // 大爆 + 火雨 + 蘑菇云
        int impactParticles = Math.min(420, 80 + radius * 9);
        for (int i = 0; i < impactParticles; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            double oy = (level.random.nextDouble() - 0.5D) * radius * 1.0D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            broadcast(level, ParticleTypes.EXPLOSION, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, ground.y + 0.4D + oy * 0.3D, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            if ((i & 1) == 0) {
                broadcast(level, ParticleTypes.FLAME, ground.x + ox, ground.y + 0.6D + oy * 0.4D, ground.z + oz,
                        1, 0.0D, 0.12D, 0.0D, 0.04D);
            }
        }
        int rings = Math.min(8, 3 + radius / 10);
        for (int r = 0; r < rings; r++) {
            double ringR = 1.0D + r * (radius / (double) rings) * 1.5D;
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x + ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x - ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z + ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z - ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, ground.y + 0.8D, ground.z,
                Math.min(120, 36 + radius * 3), radius * 0.6D, 2.6D, radius * 0.6D, 0.9D);
        int embers = Math.min(140, 50 + radius * 3);
        for (int i = 0; i < embers; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.7D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.7D;
            double oy = 0.3D + level.random.nextDouble() * radius * 0.7D;
            broadcast(level, ModParticles.ORBITAL_EMBER.get(),
                    ground.x + ox, ground.y + oy, ground.z + oz, 0,
                    (level.random.nextDouble() - 0.5D) * 0.14D,
                    0.06D + level.random.nextDouble() * 0.09D,
                    (level.random.nextDouble() - 0.5D) * 0.14D, 0.0D);
        }
        int cloud = Math.min(300, 60 + radius * 7);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.3D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.3D;
            double oy = level.random.nextDouble() * radius * 1.0D;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.07D + level.random.nextDouble() * 0.10D, 0.0D, 0.03D);
        }
    }

    /**
     * 黑雨 BLACK RAIN：脏弹陨石。浅而宽的黑玻璃坑 + 持续毒雨区。
     *
     * <p>和黎明正好是镜像：黎明只烧亡灵、给活人留一片玻璃；黑雨只毒生者，
     * 亡灵（僵尸/骷髅）在雨里毫发无伤 —— 这是给「尸潮世界」专门设计的武器，
     * 也是六种协议里唯一一个会持续改变战场几十秒的。</p>
     */
    private static void impactBlackRain(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                        int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (destroy) {
            DESTROY_QUEUE.add(new BlackRainJob(level, target, radius, Math.max(3, radius / 5)));
            placeBlackRim(level, target, radius);
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.PLANET, strike.damageMul);
            // 毒雨区比坑大一圈：躲到坑外不代表安全
            TOXIC_RAINS.add(new ToxicRain(level, ground, (int) Math.round(radius * 1.6D),
                    Config.ORBITAL_STRIKE_BLACK_RAIN_TICKS.get(), strike.owner));
        }
        spawnSurfaceDebris(level, target, radius);
        // 声音：闷响 + 次声 + 碎裂。雨声由 ToxicRain 每隔几秒续一层。
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 5.0F, 0.35F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.30F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 4.0F, 0.28F);
        level.playSound(null, target, SoundEvents.ANVIL_LAND, SoundSource.PLAYERS, 4.0F, 0.30F);
        level.playSound(null, target, SoundEvents.WEATHER_RAIN, SoundSource.WEATHER, 2.0F, 0.55F);
        int impactParticles = Math.min(380, 80 + radius * 8);
        for (int i = 0; i < impactParticles; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.9D;
            double oy = (level.random.nextDouble() - 0.5D) * radius * 1.0D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.9D;
            broadcast(level, ParticleTypes.EXPLOSION, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SQUID_INK,
                    ground.x + ox, ground.y + 0.4D + oy * 0.4D, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            if ((i & 1) == 0) {
                broadcast(level, ParticleTypes.ASH,
                        ground.x + ox, ground.y + 0.7D + oy * 0.4D, ground.z + oz,
                        1, 0.0D, 0.05D, 0.0D, 0.02D);
            }
        }
        int rings = Math.min(9, 3 + radius / 9);
        for (int r = 0; r < rings; r++) {
            double ringR = 1.0D + r * (radius / (double) rings) * 1.5D;
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x + ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x - ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z + ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z - ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        // 黑烟柱：横向扩散小于火雨，但更高、更久
        int cloud = Math.min(340, 70 + radius * 8);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oy = level.random.nextDouble() * radius * 1.4D;
            broadcast(level, i % 4 == 0 ? ParticleTypes.SQUID_INK : ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.08D + level.random.nextDouble() * 0.12D, 0.0D, 0.03D);
        }
    }

    /** 坑沿的菌岩/黑曜石斑：给坑边一圈「被污染」的地表签名。 */
    private static void placeBlackRim(ServerLevel level, BlockPos target, int radius) {
        int segments = Math.max(24, Math.min(96, radius * 4));
        double ringR = radius + 2.0D;
        for (int i = 0; i < segments; i++) {
            if (i % 4 != 0) {
                continue;
            }
            double angle = i * Math.PI * 2.0D / segments;
            int x = target.getX() + (int) Math.round(Math.cos(angle) * ringR);
            int z = target.getZ() + (int) Math.round(Math.sin(angle) * ringR);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(x, 0, z));
            if (level.getBlockState(surface).isAir() && !level.getBlockState(surface.below()).isAir()) {
                level.setBlockAndUpdate(surface, (i % 12 == 0 ? Blocks.OBSIDIAN : Blocks.SCULK)
                        .defaultBlockState());
            }
        }
    }

    /**
     * 毒雨：每 10 tick 结算一次范围效果（毒 + 凋零 + 灭火），每 2 tick 补一层落雨粒子。
     * 施放者免疫；亡灵免疫 —— 这是黑雨的身份，而不是漏判。
     */
    private static void tickToxicRains() {
        if (TOXIC_RAINS.isEmpty()) {
            return;
        }
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            TOXIC_RAINS.clear();
            return;
        }
        Iterator<ToxicRain> it = TOXIC_RAINS.iterator();
        while (it.hasNext()) {
            ToxicRain rain = it.next();
            if (--rain.remaining <= 0) {
                it.remove();
                continue;
            }
            rain.age++;
            if ((rain.age & 1) == 0) {
                int drops = 4 + rain.radius / 6;
                for (int i = 0; i < drops; i++) {
                    double angle = rain.level.random.nextDouble() * Math.PI * 2.0D;
                    double dist = Math.sqrt(rain.level.random.nextDouble()) * rain.radius;
                    double px = rain.x + Math.cos(angle) * dist;
                    double pz = rain.z + Math.sin(angle) * dist;
                    int top = rain.level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                            Mth.floor(px), Mth.floor(pz));
                    double py = top + 4.0D + rain.level.random.nextDouble() * 10.0D;
                    broadcast(rain.level,
                            rain.level.random.nextBoolean()
                                    ? ParticleTypes.FALLING_OBSIDIAN_TEAR : ParticleTypes.ASH,
                            px, py, pz, 1, 0.0D, -0.35D, 0.0D, 0.0D);
                }
            }
            if (rain.age % 10 == 0) {
                AABB box = new AABB(rain.x - rain.radius, rain.y - 10.0D, rain.z - rain.radius,
                        rain.x + rain.radius, rain.y + 20.0D, rain.z + rain.radius);
                for (LivingEntity entity : rain.level.getEntitiesOfClass(LivingEntity.class, box)) {
                    if (entity instanceof Player player
                            && (player.isCreative() || player.isSpectator())) {
                        continue;
                    }
                    if (entity.getUUID().equals(rain.owner)) {
                        continue;
                    }
                    entity.setRemainingFireTicks(0);
                    if (entity.getMobType() == MobType.UNDEAD) {
                        continue;
                    }
                    entity.addEffect(new MobEffectInstance(MobEffects.POISON, 80, 0, true, true));
                    entity.addEffect(new MobEffectInstance(MobEffects.WITHER, 60, 0, true, true));
                }
            }
            if (rain.age % 100 == 5) {
                rain.level.playSound(null,
                        new BlockPos(Mth.floor(rain.x), Mth.floor(rain.y), Mth.floor(rain.z)),
                        SoundEvents.WEATHER_RAIN, SoundSource.WEATHER, 1.1F, 0.75F);
            }
        }
    }

    /**
     * 宇宙激光：从深空（Y=700）直射下来的一束光。没有飞行时间，充能完成即命中；
     * 破坏性全场最强 —— 半径 1.35×、伤害 3×、秒杀 +30%，并且一路打穿到虚空。
     */
    private static void impactLaser(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                    int radius, boolean destroy, boolean damage) {
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        if ("dawn".equals(protocol.id())) {
            impactDawn(level, strike, ground, radius, destroy, damage);
            return;
        }
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.LASER, strike.damageMul);
        }
        spawnSurfaceDebris(level, target, radius);
        // 声音：一声切穿大气的高频炸裂 + 极低的持续轰鸣（音量 > 4，44 格外的机位也听得见）
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 6.0F, 0.35F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 5.0F, 0.30F);
        level.playSound(null, target, SoundEvents.BEACON_DEACTIVATE, SoundSource.PLAYERS, 4.0F, 0.35F);
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 5.0F, 0.85F);
        // 整根光柱的白热粒子：从地面一直撒到深空发射点
        for (int i = 0; i < 80; i++) {
            double fy = ground.y + level.random.nextDouble() * strike.mode.originY();
            broadcast(level, ParticleTypes.END_ROD, ground.x, fy, ground.z,
                    1, 0.0D, -0.25D, 0.0D, 0.0D);
        }
        // 地面：大爆 + 多层冲击环 + 电弧
        int impactParticles = Math.min(480, 80 + radius * 10);
        for (int i = 0; i < impactParticles; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            double oy = (level.random.nextDouble() - 0.5D) * radius * 1.1D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            broadcast(level, ParticleTypes.EXPLOSION, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, ground.y + 0.4D + oy * 0.3D, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            if ((i & 1) == 0) {
                broadcast(level, ParticleTypes.FLASH, ground.x, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        }
        int rings = Math.min(9, 3 + radius / 10);
        for (int r = 0; r < rings; r++) {
            double ringR = 1.0D + r * (radius / (double) rings) * 1.4D;
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x + ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x - ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z + ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z - ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, ground.y + 1.0D, ground.z,
                Math.min(140, 40 + radius * 4), radius * 0.6D, 3.5D, radius * 0.6D, 1.1D);
        int embers = Math.min(120, 40 + radius * 2);
        for (int i = 0; i < embers; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            double oy = 0.3D + level.random.nextDouble() * radius * 0.6D;
            broadcast(level, ModParticles.ORBITAL_EMBER.get(),
                    ground.x + ox, ground.y + oy, ground.z + oz, 0,
                    (level.random.nextDouble() - 0.5D) * 0.12D,
                    0.05D + level.random.nextDouble() * 0.08D,
                    (level.random.nextDouble() - 0.5D) * 0.12D, 0.0D);
        }
        int cloud = Math.min(320, 60 + radius * 8);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oy = level.random.nextDouble() * radius * 1.1D;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.06D + level.random.nextDouble() * 0.10D, 0.0D, 0.03D);
        }
    }

    /** 远雷队列：按玩家到落点的距离换算成 tick（雷声也是声音，不是瞬时）。 */
    private static void queueThunder(ServerLevel level, Vec3 ground) {
        for (ServerPlayer p : level.players()) {
            double d = p.position().distanceTo(ground);
            if (d > 320.0D) {
                continue;
            }
            THUNDER_QUEUE.add(new DelayedThunder(level, p.blockPosition(),
                    (int) Math.round(d / 340.0D * 20.0D)));
        }
    }

    /**
     * 轨道炮（默认模式）：大范围 + 蘑菇云 + 音爆环。
     * 这是 1.2.7 以来那一套，模式化之后只把「半径 / 伤害」换成按模式缩放过的值。
     */
    /**
     * 黎明 DAWN：太阳反射镜的净白光柱。只杀亡灵，玩家/普通生物安全；
     * 地面留下一个浅玻璃碗 + 中心光柱，不挖穿。
     */
    private static void impactDawn(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                   int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (damage) {
            purgeUndead(level, ground, radius, strike.owner);
        }
        if (destroy) {
            DESTROY_QUEUE.add(new DawnJob(level, target, radius, 6));
            placeDawnRim(level, target, radius);
        }
        spawnSurfaceDebris(level, target, Math.max(4, radius / 2));
        // 白金光柱：从地面到深空的一整列 END_ROD / 白色闪光
        for (int i = 0; i < 90; i++) {
            double fy = ground.y + level.random.nextDouble() * OrbitalStrikeMode.LASER.originY();
            broadcast(level, ParticleTypes.END_ROD, ground.x, fy, ground.z,
                    1, 0.0D, -0.18D, 0.0D, 0.0D);
        }
        for (int i = 0; i < 80; i++) {
            double ang = level.random.nextDouble() * Math.PI * 2.0D;
            double dist = Math.sqrt(level.random.nextDouble()) * radius;
            broadcast(level, ParticleTypes.FLASH,
                    ground.x + Math.cos(ang) * dist, ground.y + 0.5D, ground.z + Math.sin(ang) * dist,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.END_ROD,
                    ground.x + Math.cos(ang) * dist, ground.y + 1.0D + level.random.nextDouble() * 4.0D,
                    ground.z + Math.sin(ang) * dist, 1, 0.0D, 0.18D, 0.0D, 0.02D);
        }
        level.playSound(null, target, SoundEvents.BELL_BLOCK, SoundSource.PLAYERS, 5.0F, 0.8F);
        level.playSound(null, target, SoundEvents.AMETHYST_BLOCK_CHIME, SoundSource.PLAYERS, 5.0F, 1.4F);
        level.playSound(null, target, SoundEvents.BEACON_ACTIVATE, SoundSource.PLAYERS, 4.0F, 1.8F);
        level.playSound(null, target, SoundEvents.GLASS_BREAK, SoundSource.PLAYERS, 4.0F, 1.2F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 3.0F, 1.6F);
    }

    /** 玻璃碗边缘：一圈白玻璃刻度（在坑外，不会被 DawnJob 挖掉）。 */
    private static void placeDawnRim(ServerLevel level, BlockPos target, int radius) {
        int segments = Math.max(24, Math.min(96, radius * 4));
        for (int i = 0; i < segments; i++) {
            if (i % 3 != 0) {
                continue;
            }
            double angle = i * Math.PI * 2.0D / segments;
            int x = target.getX() + (int) Math.round(Math.cos(angle) * radius);
            int z = target.getZ() + (int) Math.round(Math.sin(angle) * radius);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(x, 0, z));
            if (level.getBlockState(surface).isAir() && !level.getBlockState(surface.below()).isAir()) {
                level.setBlockAndUpdate(surface, Blocks.WHITE_STAINED_GLASS.defaultBlockState());
            }
        }
    }

    private static void impactCannon(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                     int radius, boolean destroy, boolean damage) {
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        if ("cinder".equals(protocol.id())) {
            impactCinder(level, strike, ground, radius, destroy, damage);
            return;
        }
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.CANNON, strike.damageMul);
        }
        // 真实方块碎屑：从被清理的那块地皮上掀起来 —— 飞的是土/石/草，而不是通用火星。
        spawnSurfaceDebris(level, target, radius);
        // 爆炸视觉 + 大量粒子。
        // 音量都 > 1：原版的音量同时决定可闻半径（16 × volume），而见证机位会把镜头
        // 拉到 44 格外 —— 音量 1.6 只有 25 格，落地那一声在演出里会「哑掉」。
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 4.0F, 0.7F);
        level.playSound(null, target, SoundEvents.BEACON_DEACTIVATE, SoundSource.PLAYERS, 3.0F, 0.5F);
        // 低频下潜：warden 音波垫在最底下（1.8.0 音效分层 —— 高频的爆炸粒子感 + 低频的「重」）
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 4.0F, 0.65F);
        // 龙吼压低：给「从宇宙来的东西」一点沉重感（音高 0.5 = 低两个八度左右）
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 3.0F, 0.5F);
        // 起源：Y=320 处的太空爆点，六角星尘向外散开 —— 强调「这一击来自宇宙之外」
        for (int i = 0; i < 32; i++) {
            double angle = i * Math.PI * 2.0D / 32.0D;
            double spread = 1.5D + level.random.nextDouble() * 2.5D;
            broadcast(level, ParticleTypes.END_ROD,
                    ground.x, IMPACT_FALL_Y, ground.z,
                    1, Math.cos(angle) * spread, 0.3D + level.random.nextDouble() * 0.6D, Math.sin(angle) * spread, 0.25D);
        }
        // 大爆 FLASH + 多色粉尘（数量随半径缩放，上限防止一次刷上万粒子）
        int impactParticles = Math.min(360, 64 + radius * 8);
        for (int i = 0; i < impactParticles; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            double oy = (level.random.nextDouble() - 0.5D) * radius * 1.0D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            broadcast(level, ParticleTypes.EXPLOSION, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, ground.y + 0.4D + oy * 0.3, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            if ((i & 1) == 0) {
                broadcast(level, ParticleTypes.FLASH, ground.x, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        }
        // 音爆光环：SONIC_BOOM 是原版最像「能量冲击波」的粒子（青色圆环），一圈圈往外推
        int rings = Math.min(6, 2 + radius / 8);
        for (int r = 0; r < rings; r++) {
            double ringR = 1.0D + r * (radius / (double) rings);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x + ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x - ringR, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z + ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            broadcast(level, ParticleTypes.SONIC_BOOM, ground.x, ground.y + 0.5D, ground.z - ringR, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        // 电弧：ELECTRIC_SPARK 从落点向四周乱窜 —— 「能量还在放电」
        int sparks = Math.min(80, 20 + radius * 2);
        for (int i = 0; i < sparks; i++) {
            broadcast(level, ParticleTypes.ELECTRIC_SPARK,
                    ground.x + (level.random.nextDouble() - 0.5D) * radius,
                    ground.y + 0.4D + level.random.nextDouble() * 2.0D,
                    ground.z + (level.random.nextDouble() - 0.5D) * radius,
                    1, 0.0D, 0.25D, 0.0D, 0.4D);
        }
        // 能量火花爆发：一圈从落点向四面八方炸开（count>0 = 位置随机散布 + 速度随机方向）
        broadcast(level, ModParticles.ORBITAL_SPARK.get(),
                ground.x, ground.y + 0.5D, ground.z,
                Math.min(90, 30 + radius * 2),
                radius * 0.45D, 2.2D, radius * 0.45D, 0.75D);
        // 悬浮余烬：落地后慢慢上飘的碎屑 —— 慢速、飘得久，与屏幕层的青白泛光同一条色带
        int embers = Math.min(80, 30 + radius);
        for (int i = 0; i < embers; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.4D;
            double oy = 0.3D + level.random.nextDouble() * radius * 0.5D;
            broadcast(level, ModParticles.ORBITAL_EMBER.get(),
                    ground.x + ox, ground.y + oy, ground.z + oz, 0,
                    (level.random.nextDouble() - 0.5D) * 0.12D,
                    0.05D + level.random.nextDouble() * 0.08D,
                    (level.random.nextDouble() - 0.5D) * 0.12D, 0.0D);
        }
        // 蘑菇云：从地面向上翻腾的浓烟 + 火舌（落点越近越密；数量随半径缩放）
        int cloudParticles = Math.min(240, 48 + radius * 6);
        for (int i = 0; i < cloudParticles; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.2D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.2D;
            double oy = level.random.nextDouble() * radius * 0.9D;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.06D + level.random.nextDouble() * 0.10D, 0.0D, 0.03D);
            if ((i & 1) == 0) {
                broadcast(level, ParticleTypes.FLAME,
                        ground.x + ox * 0.6D, ground.y + oy * 0.4D, ground.z + oz * 0.6D,
                        1, 0.0D, 0.12D, 0.0D, 0.03D);
            }
        }
    }

    /**
     * 天基长矛：窄、深、狠。强制整列挖穿（含基岩，如果配置允许），
     * 伤害集中在一个很小的圆里。声音是「一根金属矛钉进地层」——
     * 高频的金属撞击 + 极低的次声，和轨道炮的爆炸完全不同。
     */
    private static void impactLance(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                    int radius, boolean destroy, boolean damage) {
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        if (protocol.fault()) {
            impactFault(level, strike, ground, destroy, damage, protocol);
            return;
        }
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            // 半径小，但伤害密度高：用 1.6 倍的判定半径，中心一击几乎必杀
            damageArea(level, ground, radius * 1.6D, strike.owner, OrbitalStrikeMode.LANCE, strike.damageMul);
        }
        spawnSurfaceDebris(level, target, radius);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 1.35F);
        level.playSound(null, target, SoundEvents.ANVIL_LAND, SoundSource.PLAYERS, 4.5F, 0.45F);
        level.playSound(null, target, SoundEvents.BEACON_DEACTIVATE, SoundSource.PLAYERS, 3.0F, 1.6F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 3.0F, 0.85F);
        // 穿刺闪光：沿 Y 轴排列的光柱 + 一层收束电弧
        int particles = Math.min(160, 40 + radius * 14);
        for (int i = 0; i < particles; i++) {
            double y = ground.y + level.random.nextDouble() * 14.0D;
            double ox = (level.random.nextDouble() - 0.5D) * 0.9D;
            double oz = (level.random.nextDouble() - 0.5D) * 0.9D;
            broadcast(level, ParticleTypes.END_ROD, ground.x + ox, y, ground.z + oz,
                    1, 0.0D, 0.18D, 0.0D, 0.02D);
        }
        for (int i = 0; i < 48; i++) {
            broadcast(level, ParticleTypes.ELECTRIC_SPARK,
                    ground.x + (level.random.nextDouble() - 0.5D) * radius,
                    ground.y + 0.4D + level.random.nextDouble() * 3.0D,
                    ground.z + (level.random.nextDouble() - 0.5D) * radius,
                    1, 0.0D, 0.30D, 0.0D, 0.50D);
        }
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, ground.y + 1.0D, ground.z,
                Math.min(60, 16 + radius * 3), 0.5D, 5.0D, 0.5D, 0.9D);
    }

    /**
     * 断层 FAULT（v2）：不是圆坑，而是一条沿玩家朝向展开的折线裂谷。
     *
     * <p>服务端和客户端共用 {@link RiftShape} 生成同一条折线；服务端用 {@link RiftJob}
     * 分 tick 挖开，客户端用同一条线画裂缝预览和谷底辉光。伤害沿折线判定（不是只打圆心），
     * 裂开声立即响、音爆/地鸣按距离延迟（{@code queueThunder}）。</p>
     */
    private static void impactFault(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                    boolean destroy, boolean damage, StrikeProtocol protocol) {
        BlockPos target = strike.target;
        StrikeProtocol.Terrain terrain = protocol.terrain();
        List<RiftShape.Point> points = RiftShape.points(target, strike.yaw, terrain.riftLength());
        if (destroy && !points.isEmpty()) {
            DESTROY_QUEUE.add(new RiftJob(level, points, terrain.riftWidth(),
                    terrain.riftDepth(), target.getY()));
        }
        if (damage && !points.isEmpty()) {
            damageRift(level, points, terrain.riftWidth(), strike.owner, ground);
        }
        spawnSurfaceDebris(level, target, Math.max(4, terrain.riftWidth() + 2));
        // 沿裂谷撒真实地表碎屑 + 烟
        for (int i = 0; i < points.size(); i += 2) {
            RiftShape.Point p = points.get(i);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(p.x(), 0, p.z()));
            BlockState state = level.getBlockState(surface.below());
            if (!state.isAir() && state.getFluidState().isEmpty()) {
                broadcast(level, new BlockParticleOption(ParticleTypes.BLOCK, state),
                        surface.getX() + 0.5D, surface.getY() + 0.2D, surface.getZ() + 0.5D,
                        4, 0.7D, 0.9D, 0.7D, 0.38D);
            }
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    p.x() + 0.5D, surface.getY() + 0.8D, p.z() + 0.5D,
                    2, 0.8D, 1.0D, 0.8D, 0.12D);
            if (i % 4 == 0) {
                broadcast(level, ModParticles.ORBITAL_SPARK.get(),
                        p.x() + 0.5D, surface.getY() + 0.5D, p.z() + 0.5D,
                        6, 0.3D, 1.2D, 0.3D, 0.35D);
            }
        }
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, ground.y + 0.8D, ground.z,
                Math.min(80, 24 + terrain.riftWidth() * 4), 0.8D, 3.0D, 0.8D, 0.7D);
        // 金属钉入 + 岩层裂开 + 远处地鸣（音爆延迟）
        level.playSound(null, target, SoundEvents.ANVIL_LAND, SoundSource.PLAYERS, 5.0F, 0.35F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.55F);
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 4.5F, 0.40F);
        level.playSound(null, target, SoundEvents.STONE_BREAK, SoundSource.PLAYERS, 4.5F, 0.35F);
        // 远处的音爆/地鸣由 tickImpact 顶部的 queueThunder 统一按距离延迟，别在这里重复排队。
    }

    /** 沿裂谷折线做伤害：宽 {@code width+1.5} 内按到折线的距离衰减，中心必杀率叠加长矛加成。 */
    private static void damageRift(ServerLevel level, List<RiftShape.Point> points, int width,
                                   UUID owner, Vec3 ground) {
        int minX = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE;
        int minZ = Integer.MAX_VALUE;
        int maxZ = Integer.MIN_VALUE;
        for (RiftShape.Point p : points) {
            minX = Math.min(minX, p.x());
            maxX = Math.max(maxX, p.x());
            minZ = Math.min(minZ, p.z());
            maxZ = Math.max(maxZ, p.z());
        }
        AABB box = new AABB(minX - 8.0D, ground.y - 96.0D, minZ - 8.0D,
                maxX + 8.0D, ground.y + 96.0D, maxZ + 8.0D);
        List<LivingEntity> targets = level.getEntitiesOfClass(LivingEntity.class, box);
        if (targets.isEmpty()) {
            return;
        }
        float base = Config.ORBITAL_STRIKE_DAMAGE.get().floatValue()
                * OrbitalStrikeMode.LANCE.damageScale();
        int killPercent = Mth.clamp(Config.ORBITAL_STRIKE_KILL_CHANCE.get()
                + OrbitalStrikeMode.LANCE.killBonus(), 0, 100);
        double max = width + 1.5D;
        DamageSource source = level.damageSources().explosion(null, ownerPlayer(level, owner));
        for (LivingEntity entity : targets) {
            if (entity.isRemoved() || !entity.isAlive() || entity.isSpectator()) {
                continue;
            }
            double d = RiftShape.distanceTo(points, entity.getX(), entity.getZ());
            if (d > max) {
                continue;
            }
            if (killPercent > 0 && level.random.nextInt(100) < killPercent) {
                entity.hurt(source, Float.MAX_VALUE);
                if (entity.isAlive()) {
                    entity.setHealth(0.0F);
                    entity.die(source);
                }
                level.sendParticles(ParticleTypes.EXPLOSION_EMITTER,
                        entity.getX(), entity.getY() + 0.5D, entity.getZ(), 1,
                        0.0D, 0.0D, 0.0D, 0.0D);
                continue;
            }
            float scale = (float) (1.0D - 0.7D * (d / max));
            entity.hurt(source, base * scale);
            // 沿裂缝横向被推开，并轻微抬起：像被地裂甩了一下。
            double dx = entity.getX() - (minX + maxX) * 0.5D;
            double dz = entity.getZ() - (minZ + maxZ) * 0.5D;
            double len = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
            entity.push(dx / len * 0.8D, 0.45D, dz / len * 0.8D);
            entity.hurtMarked = true;
        }
    }

    /**
     * 隔离 QUARANTINE：不炸坑，只圈地。边界铺一圈玻璃/海晶灯，中心竖信标；
     * 圈内亡灵即死，玩家与普通生物不受伤害。它是防御/净化协议，不是破坏协议。
     */
    private static void impactQuarantine(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                         int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (damage) {
            purgeUndead(level, ground, radius, strike.owner);
        }
        if (destroy) {
            placeQuarantineRing(level, target, radius);
            placeQuarantineBeacon(level, target);
        }
        // 纯白/冷青的力场收束：不是爆炸，而是一圈「合拢」的光
        for (int i = 0; i < 64; i++) {
            double angle = i * Math.PI * 2.0D / 64.0D;
            double x = ground.x + Math.cos(angle) * radius;
            double z = ground.z + Math.sin(angle) * radius;
            broadcast(level, ParticleTypes.END_ROD, x, ground.y + 0.6D, z,
                    1, 0.0D, 0.25D, 0.0D, 0.02D);
            if (i % 4 == 0) {
                broadcast(level, ParticleTypes.ELECTRIC_SPARK, x, ground.y + 1.2D, z,
                        1, 0.0D, 0.10D, 0.0D, 0.05D);
            }
        }
        broadcast(level, ParticleTypes.FLASH, ground.x, ground.y + 2.0D, ground.z,
                1, 0.0D, 0.0D, 0.0D, 0.0D);
        level.playSound(null, target, SoundEvents.BEACON_ACTIVATE, SoundSource.PLAYERS, 4.0F, 1.5F);
        level.playSound(null, target, SoundEvents.AMETHYST_BLOCK_CHIME, SoundSource.PLAYERS, 4.0F, 1.2F);
        level.playSound(null, target, SoundEvents.GLASS_PLACE, SoundSource.PLAYERS, 4.0F, 0.8F);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 3.0F, 1.2F);
    }

    /** 圈内亡灵处决；玩家、村民、动物、宠物都不碰。 */
    private static void purgeUndead(ServerLevel level, Vec3 center, int radius, UUID owner) {
        AABB box = new AABB(center.x - radius - 2.0D, center.y - 64.0D, center.z - radius - 2.0D,
                center.x + radius + 2.0D, center.y + 64.0D, center.z + radius + 2.0D);
        List<LivingEntity> targets = level.getEntitiesOfClass(LivingEntity.class, box);
        DamageSource source = level.damageSources().explosion(null, ownerPlayer(level, owner));
        for (LivingEntity entity : targets) {
            if (entity.isRemoved() || !entity.isAlive() || entity.isSpectator()
                    || entity.getMobType() != MobType.UNDEAD) {
                continue;
            }
            entity.hurt(source, Float.MAX_VALUE);
            if (entity.isAlive()) {
                entity.setHealth(0.0F);
                entity.die(source);
            }
            level.sendParticles(ParticleTypes.END_ROD,
                    entity.getX(), entity.getY() + 0.6D, entity.getZ(),
                    8, 0.25D, 0.45D, 0.25D, 0.03D);
            level.sendParticles(ParticleTypes.SOUL,
                    entity.getX(), entity.getY() + 0.5D, entity.getZ(),
                    6, 0.25D, 0.35D, 0.25D, 0.02D);
        }
    }

    /** 边界玻璃环：每 8 格一盏海晶灯做刻度，其余白玻璃；只铺地表一层。 */
    private static void placeQuarantineRing(ServerLevel level, BlockPos target, int radius) {
        int segments = Math.max(24, Math.min(96, radius * 4));
        for (int i = 0; i < segments; i++) {
            double angle = i * Math.PI * 2.0D / segments;
            int x = target.getX() + (int) Math.round(Math.cos(angle) * radius);
            int z = target.getZ() + (int) Math.round(Math.sin(angle) * radius);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(x, 0, z));
            if (!level.getBlockState(surface).isAir() || level.getBlockState(surface.below()).isAir()) {
                continue;
            }
            level.setBlockAndUpdate(surface, (i % 8 == 0
                    ? Blocks.SEA_LANTERN
                    : Blocks.WHITE_STAINED_GLASS).defaultBlockState());
        }
    }

    /** 中心信标：三格白玻璃 + 顶部海晶灯，昼夜可见。 */
    private static void placeQuarantineBeacon(ServerLevel level, BlockPos target) {
        BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, target);
        for (int i = 0; i < 3; i++) {
            BlockPos pos = surface.above(i);
            if (!level.getBlockState(pos).isAir()) {
                continue;
            }
            level.setBlockAndUpdate(pos, Blocks.WHITE_STAINED_GLASS.defaultBlockState());
        }
        BlockPos top = surface.above(3);
        if (level.getBlockState(top).isAir()) {
            level.setBlockAndUpdate(top, Blocks.SEA_LANTERN.defaultBlockState());
        }
    }

    /**
     * 引力奇点：先塌缩再爆开。下落段已经把周围生物往落点拖（见 {@link #tickFalling}），
     * 落地瞬间给一个向上的反冲 —— 被「吸进去」的东西又被「吐出来」。
     */
    private static void impactGravity(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                      int radius, boolean destroy, boolean damage) {
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        if ("quarantine".equals(protocol.id())) {
            impactQuarantine(level, strike, ground, radius, destroy, damage);
            return;
        }
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.GRAVITY, strike.damageMul);
        }
        spawnSurfaceDebris(level, target, radius);
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.35F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 4.0F, 0.35F);
        level.playSound(null, target, SoundEvents.BEACON_DEACTIVATE, SoundSource.PLAYERS, 3.0F, 0.4F);
        // 向心（塌缩）的粒子：外圈给指向中心的初速度
        for (int i = 0; i < 70; i++) {
            double angle = level.random.nextDouble() * Math.PI * 2.0D;
            double dist = radius * (1.0D + level.random.nextDouble() * 0.8D);
            double y = 0.5D + level.random.nextDouble() * radius * 0.8D;
            double sx = ground.x + Math.cos(angle) * dist;
            double sz = ground.z + Math.sin(angle) * dist;
            double speed = 0.18D + level.random.nextDouble() * 0.12D;
            broadcast(level, ModParticles.ORBITAL_SPARK.get(), sx, ground.y + y, sz, 0,
                    (ground.x - sx) * speed, (2.0D - y) * speed, (ground.z - sz) * speed, 0.0D);
        }
        // 反冲：一圈向外/向上的火花
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), ground.x, ground.y + 0.6D, ground.z,
                Math.min(90, 30 + radius * 3), radius * 0.5D, 3.0D, radius * 0.5D, 1.0D);
        int cloud = Math.min(140, 30 + radius * 4);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius;
            double oz = (level.random.nextDouble() - 0.5D) * radius;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + level.random.nextDouble() * 3.0D, ground.z + oz,
                    1, 0.0D, 0.02D, 0.0D, 0.02D);
        }
    }

    /**
     * 等离子风暴：一次打击在目标周围撒下 {@link OrbitalStrikeMode#STORM_POINTS} 个小落点。
     * 偏移由「落点坐标哈希」决定，客户端用同一个函数算 —— 坑和光环必然重合。
     */
    /**
     * 等离子风暴的**单道**闪电落地。五道按 {@link OrbitalStrikeMode#STORM_STAGGER_TICKS}
     * 分批落下（见 {@link #onServerTick}），每一道都是一个独立的小坑 + 独立的伤害判定。
     */
    /**
     * 蜂群 SWARM：在落点留下一个可破坏的巢荚（sculk catalyst）+ 菌毯斑块。
     * 不挖坑 —— 巢荚本身就是地形签名，后续最后一道落地时再统一孵化。
     */
    private static void placeBroodPod(ServerLevel level, BlockPos subPos, Vec3 sub) {
        BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, subPos);
        if (!level.getBlockState(surface.below()).isAir()
                && level.getBlockState(surface).isAir()) {
            level.setBlockAndUpdate(surface, Blocks.SCULK_CATALYST.defaultBlockState());
        }
        for (int i = 0; i < 5; i++) {
            double ang = level.random.nextDouble() * Math.PI * 2.0D;
            int dx = (int) Math.round(Math.cos(ang) * (1.0D + level.random.nextDouble() * 2.0D));
            int dz = (int) Math.round(Math.sin(ang) * (1.0D + level.random.nextDouble() * 2.0D));
            BlockPos patch = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    surface.offset(dx, 0, dz));
            if (level.getBlockState(patch).isAir() && !level.getBlockState(patch.below()).isAir()) {
                level.setBlockAndUpdate(patch, Blocks.SCULK.defaultBlockState());
            }
        }
        level.playSound(null, sub.x, sub.y + 0.5D, sub.z,
                SoundEvents.SCULK_CATALYST_BLOOM, SoundSource.PLAYERS, 2.6F, 1.1F);
        broadcast(level, ParticleTypes.SCULK_SOUL, sub.x, sub.y + 0.8D, sub.z,
                18, 0.8D, 1.2D, 0.8D, 0.08D);
    }

    /** 最后一道落地：七个巢荚同时孵化，按配置每荚刷 0~8 只僵尸。 */
    private static void spawnSwarmBrood(ServerLevel level, ActiveStrike strike, double[][] offsets) {
        int perPod = Config.ORBITAL_STRIKE_SWARM_BROOD.get();
        if (perPod <= 0) {
            return;
        }
        Vec3 ground = Vec3.atCenterOf(strike.target);
        for (double[] offset : offsets) {
            BlockPos subPos = BlockPos.containing(ground.x + offset[0], ground.y, ground.z + offset[1]);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, subPos);
            for (int i = 0; i < perPod; i++) {
                Zombie zombie = EntityType.ZOMBIE.create(level);
                if (zombie == null) {
                    continue;
                }
                double x = surface.getX() + 0.5D + (level.random.nextDouble() - 0.5D) * 3.0D;
                double z = surface.getZ() + 0.5D + (level.random.nextDouble() - 0.5D) * 3.0D;
                zombie.moveTo(x, surface.getY() + 0.1D, z,
                        level.random.nextFloat() * 360.0F, 0.0F);
                zombie.setPersistenceRequired();
                level.addFreshEntity(zombie);
            }
            broadcast(level, ParticleTypes.SCULK_SOUL,
                    surface.getX() + 0.5D, surface.getY() + 1.0D, surface.getZ() + 0.5D,
                    28, 1.0D, 1.4D, 1.0D, 0.10D);
            level.playSound(null, surface, SoundEvents.SCULK_SHRIEKER_SHRIEK,
                    SoundSource.PLAYERS, 2.4F, 0.8F);
        }
    }

    private static void impactStormBolt(ServerLevel level, ActiveStrike strike, int index) {
        Vec3 ground = Vec3.atCenterOf(strike.target);
        int radius = strike.radius;
        double[][] offsets = OrbitalStrikeMode.stormOffsets(strike.target, radius);
        double[] offset = offsets[Mth.clamp(index, 0, offsets.length - 1)];
        Vec3 sub = new Vec3(ground.x + offset[0], ground.y, ground.z + offset[1]);
        BlockPos subPos = BlockPos.containing(sub);
        int subRadius = Mth.clamp(Math.round(radius * 0.45F), 2, 12);
        boolean destroy = Config.ORBITAL_STRIKE_DESTROY_BLOCKS.get();
        boolean damage = Config.ORBITAL_STRIKE_DAMAGE_MOBS.get();
        StrikeProtocol protocol = StrikeProtocols.protocolFor(strike.mode);
        boolean swarm = "swarm".equals(protocol.id());

        if (index == 0) {
            // 第一道落地时排雷声队列（整场风暴只排一次）
            queueThunder(level, ground);
        }
        if (destroy && !swarm) {
            enqueueDestroy(level, subPos, subRadius, strike.mode.pierces());
        }
        if (swarm && destroy) {
            // 蜂群：不挖坑，留下会孵化/可拆的巢荚与菌毯。
            placeBroodPod(level, subPos, sub);
        }
        if (damage) {
            damageArea(level, sub, subRadius * 1.8D, strike.owner, OrbitalStrikeMode.STORM, strike.damageMul);
        }
        spawnSurfaceDebris(level, subPos, subRadius);
        level.playSound(null, subPos, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 3.0F, 1.1F);
        broadcast(level, ParticleTypes.FLASH, sub.x, sub.y + 1.0D, sub.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        broadcast(level, ModParticles.ORBITAL_SPARK.get(), sub.x, sub.y + 0.6D, sub.z,
                Math.min(30, 12 + subRadius * 2), subRadius * 0.5D, 2.0D, subRadius * 0.5D, 0.7D);
        for (int i = 0; i < 12; i++) {
            broadcast(level, ParticleTypes.ELECTRIC_SPARK,
                    sub.x + (level.random.nextDouble() - 0.5D) * subRadius,
                    sub.y + 0.4D + level.random.nextDouble() * 2.0D,
                    sub.z + (level.random.nextDouble() - 0.5D) * subRadius,
                    1, 0.0D, 0.25D, 0.0D, 0.35D);
        }
        // 每道落点都补一小团烟（整片区域的大烟留到最后一道）
        int cloud = Math.min(40, 10 + subRadius * 4);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * subRadius * 1.6D;
            double oz = (level.random.nextDouble() - 0.5D) * subRadius * 1.6D;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    sub.x + ox, sub.y + level.random.nextDouble() * 2.0D, sub.z + oz,
                    1, 0.0D, 0.05D, 0.0D, 0.02D);
        }
        // 最后一道：一记更低的轰鸣把所有落点「串」起来 + 整片区域翻腾的烟
        if (index >= OrbitalStrikeMode.STORM_POINTS - 1) {
            if (swarm && Config.ORBITAL_STRIKE_SWARM_SPAWN.get()) {
                spawnSwarmBrood(level, strike, offsets);
            }
            level.playSound(null, strike.target, SoundEvents.WARDEN_SONIC_BOOM,
                    SoundSource.PLAYERS, 5.0F, 0.55F);
            level.playSound(null, strike.target, SoundEvents.ENDER_DRAGON_GROWL,
                    SoundSource.PLAYERS, 3.0F, 0.8F);
            int bigCloud = Math.min(180, 40 + radius * 6);
            for (int i = 0; i < bigCloud; i++) {
                double ox = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
                double oz = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
                broadcast(level, ParticleTypes.LARGE_SMOKE,
                        ground.x + ox, ground.y + level.random.nextDouble() * 2.5D, ground.z + oz,
                        1, 0.0D, 0.05D, 0.0D, 0.02D);
            }
        }
    }

    // ------------------------------------------------------------------ 粒子 / 碎屑 / 坍塌

    /**
     * 把粒子发给 512 格内的所有玩家。
     *
     * <p>{@code ServerLevel.sendParticles(...)} 的默认接收半径只有 32 格 —— 见证机位拉到
     * 44 格外、以及半径 24 的弹坑边缘（离玩家最远 48 格）都会「看不见」。原版另有一个
     * {@code force=true}（512 格）的重载，但它只对单个玩家生效，所以这里自己遍历一遍。</p>
     */
    private static void broadcast(ServerLevel level, ParticleOptions options,
                                  double x, double y, double z,
                                  int count, double dx, double dy, double dz, double speed) {
        for (ServerPlayer player : level.players()) {
            if (player.distanceToSqr(x, y, z) <= 512.0D * 512.0D) {
                level.sendParticles(player, options, true, x, y, z, count, dx, dy, dz, speed);
            }
        }
    }

    /**
     * 落地瞬间从地皮上掀起的真实方块碎屑：在弹坑范围内取样地表方块，
     * 用 {@link BlockParticleOption} 原样飞出它们的材质 —— 草方块飞草、沙子飞沙、石头飞石。
     * 这一层是「特效与世界挂钩」最值钱的部分：飞的东西来自这块地，而不是通用火星。
     */
    private static void spawnSurfaceDebris(ServerLevel level, BlockPos center, int radius) {
        int samples = Math.min(64, 20 + radius * 2);
        for (int i = 0; i < samples; i++) {
            double angle = level.random.nextDouble() * Math.PI * 2.0D;
            double dist = Math.sqrt(level.random.nextDouble()) * radius * 0.9D;
            int x = center.getX() + (int) Math.round(Math.cos(angle) * dist);
            int z = center.getZ() + (int) Math.round(Math.sin(angle) * dist);
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING, new BlockPos(x, 0, z));
            BlockState state = level.getBlockState(surface.below());
            if (state.isAir() || !state.getFluidState().isEmpty()) {
                continue;
            }
            broadcast(level, new BlockParticleOption(ParticleTypes.BLOCK, state),
                    surface.getX() + 0.5D, surface.getY() + 0.2D, surface.getZ() + 0.5D,
                    4, 0.8D, 0.9D, 0.8D, 0.42D);
        }
    }

    /** 单个方块被挖掉时的碎屑（受每 tick 预算限制，整层塌方也不会刷爆网络）。 */
    private static void spawnDebris(ServerLevel level, BlockPos pos, BlockState state) {
        if (state == null || state.isAir() || debrisBudget <= 0) {
            return;
        }
        if (level.random.nextFloat() > DEBRIS_CHANCE) {
            return;
        }
        debrisBudget--;
        broadcast(level, new BlockParticleOption(ParticleTypes.BLOCK, state),
                pos.getX() + 0.5D, pos.getY() + 0.5D, pos.getZ() + 0.5D,
                2, 0.35D, 0.45D, 0.35D, 0.16D);
    }

    /**
     * 分层坍塌的闷响：每 10 层响一次，越深越闷。
     * 音量给到 5 —— 原版音量 &gt; 1 会同比放大可闻半径（16 × volume），
     * 44 格外的见证机位才听得见「地在一层层塌」。
     */
    private static void collapseRumble(ServerLevel level, int x, int y, int z) {
        if (Math.floorMod(y, 10) != 0) {
            return;
        }
        BlockPos pos = new BlockPos(x, y, z);
        level.playSound(null, pos, SoundEvents.GENERIC_EXPLODE, SoundSource.BLOCKS, 5.0F, 0.40F);
        if (Math.floorMod(y, 30) == 0) {
            level.playSound(null, pos, SoundEvents.STONE_BREAK, SoundSource.BLOCKS, 5.0F, 0.45F);
        }
    }

    /**
     * 排队一次大范围破坏（模式由 {@code [orbital_strike] destroy_mode} 决定）。
     * 真正挖方块在 {@link #onServerTick} 里分 tick 推进 ——
     * radius=24 时选区约 11.7 万格，一个 tick 全挖会让主线程卡住好几秒。
     *
     * @param forceColumn 天基长矛用：无视配置，强制整列挖穿（这是它作为「矛」的定义）
     */
    private static void enqueueDestroy(ServerLevel level, BlockPos center, int radius, boolean forceColumn) {
        String mode = Config.ORBITAL_STRIKE_DESTROY_MODE.get();
        String normalized = mode == null ? "" : mode.trim().toLowerCase(java.util.Locale.ROOT);
        boolean column = forceColumn || "column".equals(normalized);
        if (column) {
            // 整列挖穿（参考 the-shooting-star 的招牌观感）：从建筑上限一路挖到虚空。
            // 这一模式不预计算列表 —— 半径 32 就有 160 万个位置，游标式推进省内存。
            DESTROY_QUEUE.add(new ColumnJob(level, center.getX(), center.getZ(), radius,
                    level.getMinBuildHeight(), level.getMaxBuildHeight() - 1));
        } else if ("cube".equals(normalized)) {
            AABB box = new AABB(center).inflate(radius);
            // 游标推进，不预计算列表：半径 96 的立方体是 193³ ≈ 720 万格，
            // 一个 BlockPos 列表能吃掉一百多 MB 堆内存。
            DESTROY_QUEUE.add(new BoxJob(level,
                    Mth.floor(box.minX), Mth.floor(box.minY), Mth.floor(box.minZ),
                    Mth.floor(box.maxX), Mth.floor(box.maxY), Mth.floor(box.maxZ)));
        } else {
            // 默认 'layers'：一层一层往下削（地表 → 半径深），层间停顿可配置。
            DESTROY_QUEUE.add(new LayerJob(level, center, radius));
        }
    }

    /**
     * 单个方块的处理，规则：
     * <ul>
     *   <li>流体/空气不动；</li>
     *   <li>{@link Blocks#BEDROCK} / 屏障 / 命令方块 不动；</li>
     *   <li>方块实体类（箱子、熔炉、刷怪箱、告示牌）不动；</li>
     *   <li>不可破坏 / 硬度 &gt; 配置上限 不动；</li>
     *   <li>配置里 {@code protected} 名单不动；</li>
     *   <li>其余 destroyBlock(pos, false)：不掉落物，但触发 BreakEvent 留给其它 mod 处理。</li>
     * </ul>
     *
     * @return 真正被挖掉的方块状态（给碎屑用）；跳过的方块返回 {@code null}。
     */
    private static BlockState destroyOne(ServerLevel level, BlockPos pos) {
        BlockState state = level.getBlockState(pos);
        if (state.isAir()) {
            return null;
        }
        Block block = state.getBlock();
        // 基岩：配置打开时允许抹掉 —— 「能挖穿基岩」是天基武器该有的权限。
        // 硬度检查对它无效（bedrock 的 destroySpeed 是 -1），所以必须在硬度判断之前处理。
        // 屏障 / 命令方块 / 结构方块仍然永久保护：那些不是地形，是管理员用的东西。
        if (block == Blocks.BEDROCK) {
            if (!Config.ORBITAL_STRIKE_BREAK_BEDROCK.get()) {
                return null;
            }
            level.destroyBlock(pos, false);
            return state;
        }
        if (block == Blocks.BARRIER || block == Blocks.COMMAND_BLOCK
                || block == Blocks.CHAIN_COMMAND_BLOCK || block == Blocks.REPEATING_COMMAND_BLOCK
                || block == Blocks.STRUCTURE_BLOCK || block == Blocks.JIGSAW) {
            return null;
        }
        if (state.hasBlockEntity()) {
            return null;
        }
        float hardness = state.getDestroySpeed(level, pos);
        if (hardness < 0.0F) {
            return null;   // 不可破坏
        }
        if (hardness > Config.ORBITAL_STRIKE_MAX_HARDNESS.get().floatValue()) {
            return null;   // 太硬（避开黑曜石、远古残骸的尴尬 50/50 临界）
        }
        if (isProtected(block)) {
            return null;
        }
        level.destroyBlock(pos, false);
        return state;
    }

    /** 分批破坏任务的统一接口：每 tick 处理至多 budget 个位置，返回实际处理数。 */
    private interface DestroyJob {
        int step(int budget);

        boolean done();
    }

    /** 立方体模式：游标按「从高到低、逐层」推进。不预计算列表，半径多大都不会吃内存。 */
    private static final class BoxJob implements DestroyJob {
        private final ServerLevel level;
        private final int minX;
        private final int maxX;
        private final int minY;
        private final int minZ;
        private final int maxZ;
        private final BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        private int y;
        private int x;
        private int z;
        /** 上一次触发坍塌闷响的层高（同一层只响一次）。 */
        private int lastRumbleY = Integer.MIN_VALUE;

        BoxJob(ServerLevel level, int minX, int minY, int minZ, int maxX, int maxY, int maxZ) {
            this.level = level;
            this.minX = minX;
            this.minY = minY;
            this.minZ = minZ;
            this.maxX = maxX;
            this.maxZ = maxZ;
            this.y = maxY;
            this.x = minX;
            this.z = minZ;
        }

        @Override
        public int step(int budget) {
            int processed = 0;
            while (processed < budget && !done()) {
                cursor.set(x, y, z);
                BlockState destroyed = destroyOne(level, cursor);
                if (destroyed != null) {
                    spawnDebris(level, cursor, destroyed);
                    // 一层开始塌的时候闷响一声（只在真的挖到方块时响，空中层不响）
                    if (y != lastRumbleY) {
                        lastRumbleY = y;
                        collapseRumble(level, x, y, z);
                    }
                }
                processed++;
                z++;
                if (z > maxZ) {
                    z = minZ;
                    x++;
                }
                if (x > maxX) {
                    x = minX;
                    y--;
                }
            }
            return processed;
        }

        @Override
        public boolean done() {
            return y < minY;
        }
    }

    /**
     * 黑雨 BLACK RAIN 的浅黑碗：宽而浅，坑底按噪声铺成菌岩 / 黑曜石 / 黑色混凝土，
     * 全部结束后在坑心种一枚幽匿催发体 —— 污染会从那里继续往外长。
     */
    private static final class BlackRainJob implements DestroyJob {
        private final ServerLevel level;
        private final int cx;
        private final int cz;
        private final int radius;
        private final int depth;
        private int x;
        private int z;
        private int y;
        private int surface;
        private int drop;
        private boolean inColumn;
        private boolean sealPlaced;

        BlackRainJob(ServerLevel level, BlockPos center, int radius, int depth) {
            this.level = level;
            this.cx = center.getX();
            this.cz = center.getZ();
            this.radius = Math.max(4, Math.min(48, radius));
            this.depth = Math.max(2, Math.min(10, depth));
            this.x = -this.radius;
            this.z = -this.radius;
        }

        @Override
        public int step(int budget) {
            int processed = 0;
            while (processed < budget && !done()) {
                if (!inColumn) {
                    if (x * x + z * z > radius * radius) {
                        advance();
                        continue;
                    }
                    int px = cx + x;
                    int pz = cz + z;
                    surface = Math.max(level.getMinBuildHeight() + 1,
                            level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, px, pz));
                    double d2 = (x * (double) x + z * (double) z) / (radius * (double) radius);
                    drop = Math.max(1, (int) Math.round(depth * (1.0D - d2 * d2)));
                    y = surface - 1;
                    inColumn = true;
                }
                if (y >= surface - drop) {
                    BlockPos pos = new BlockPos(cx + x, y, cz + z);
                    BlockState destroyed = destroyOne(level, pos);
                    if (destroyed != null) {
                        spawnDebris(level, pos, destroyed);
                    }
                    y--;
                    processed++;
                    continue;
                }
                BlockPos floor = new BlockPos(cx + x, surface - drop - 1, cz + z);
                if (!level.getBlockState(floor).isAir()) {
                    float roll = level.random.nextFloat();
                    Block block = roll < 0.16F ? Blocks.OBSIDIAN
                            : roll < 0.34F ? Blocks.BLACK_CONCRETE : Blocks.SCULK;
                    level.setBlockAndUpdate(floor, block.defaultBlockState());
                }
                inColumn = false;
                advance();
            }
            return processed;
        }

        private void advance() {
            z++;
            if (z > radius) {
                z = -radius;
                x++;
            }
        }

        @Override
        public boolean done() {
            if (x <= radius) {
                return false;
            }
            if (!sealPlaced) {
                sealPlaced = true;
                placeBlackSeal(level, cx, cz, depth);
            }
            return true;
        }
    }

    /** 坑心种一枚幽匿催发体：黑雨的长期地形签名。 */
    private static void placeBlackSeal(ServerLevel level, int cx, int cz, int depth) {
        int surface = Math.max(level.getMinBuildHeight() + 1,
                level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, cx, cz));
        BlockPos center = new BlockPos(cx, surface - depth, cz);
        if (level.getBlockState(center).isAir()) {
            level.setBlockAndUpdate(center, Blocks.SCULK_CATALYST.defaultBlockState());
        }
    }

    /**
     * 黎明 DAWN 的浅玻璃碗：每个柱子按到中心的距离决定下挖深度（中心 6 格、边缘 1 格），
     * 挖完把坑底换成白玻璃；全部结束后在中心立 4 格白玻璃 + 海晶灯的光柱。
     */
    private static final class DawnJob implements DestroyJob {
        private final ServerLevel level;
        private final int cx;
        private final int cz;
        private final int radius;
        private final int depth;
        private int x;
        private int z;
        private int y;
        private int surface;
        private int drop;
        private boolean inColumn;
        private boolean pillarPlaced;

        DawnJob(ServerLevel level, BlockPos center, int radius, int depth) {
            this.level = level;
            this.cx = center.getX();
            this.cz = center.getZ();
            this.radius = Math.max(4, Math.min(48, radius));
            this.depth = Math.max(2, Math.min(12, depth));
            this.x = -this.radius;
            this.z = -this.radius;
        }

        @Override
        public int step(int budget) {
            int processed = 0;
            while (processed < budget && !done()) {
                if (!inColumn) {
                    if (x * x + z * z > radius * radius) {
                        advance();
                        continue;
                    }
                    int px = cx + x;
                    int pz = cz + z;
                    surface = Math.max(level.getMinBuildHeight() + 1,
                            level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, px, pz));
                    double d2 = (x * (double) x + z * (double) z) / (radius * (double) radius);
                    drop = Math.max(1, (int) Math.round(depth * (1.0D - d2)));
                    y = surface - 1;
                    inColumn = true;
                }
                if (y >= surface - drop) {
                    BlockPos pos = new BlockPos(cx + x, y, cz + z);
                    BlockState destroyed = destroyOne(level, pos);
                    if (destroyed != null) {
                        spawnDebris(level, pos, destroyed);
                    }
                    y--;
                    processed++;
                    continue;
                }
                // 坑底换成白玻璃（只换坑底那一块，不再向下扩张）
                BlockPos floor = new BlockPos(cx + x, surface - drop - 1, cz + z);
                if (!level.getBlockState(floor).isAir()) {
                    level.setBlockAndUpdate(floor, Blocks.WHITE_STAINED_GLASS.defaultBlockState());
                }
                inColumn = false;
                advance();
            }
            return processed;
        }

        private void advance() {
            z++;
            if (z > radius) {
                z = -radius;
                x++;
            }
        }

        @Override
        public boolean done() {
            if (x <= radius) {
                return false;
            }
            if (!pillarPlaced) {
                pillarPlaced = true;
                placeDawnPillar(level, cx, cz, radius, depth);
            }
            return true;
        }
    }

    /** 黎明光柱：坑底中心 4 格白玻璃 + 顶部海晶灯。 */
    private static void placeDawnPillar(ServerLevel level, int cx, int cz, int radius, int depth) {
        int surface = Math.max(level.getMinBuildHeight() + 1,
                level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, cx, cz));
        int bottom = surface - depth;
        for (int i = 0; i < 4; i++) {
            BlockPos pos = new BlockPos(cx, bottom + i, cz);
            if (level.getBlockState(pos).isAir()) {
                level.setBlockAndUpdate(pos, Blocks.WHITE_STAINED_GLASS.defaultBlockState());
            }
        }
        BlockPos top = new BlockPos(cx, bottom + 4, cz);
        if (level.getBlockState(top).isAir()) {
            level.setBlockAndUpdate(top, Blocks.SEA_LANTERN.defaultBlockState());
        }
    }

    /**
     * 断层 FAULT 的折线裂谷：沿 {@link RiftShape} 的节点逐点挖开。
     *
     * <p>每个节点向下挖到 {@code centerY - depth}，横截面随深度收窄（V 形/阶梯），
     * 节点之间每 3 格一个、宽 7，彼此重叠所以不会出现断口。全局每 tick 预算由
     * {@code DESTROY_QUEUE} 统一分配，和圆坑/整列共享同一份 4000 格上限。</p>
     */
    private static final class RiftJob implements DestroyJob {
        private final ServerLevel level;
        private final List<RiftShape.Point> points;
        private final int width;
        private final int depth;
        private final int centerY;
        private int index;
        private int xi;
        private int zi;
        private int y;
        private int surfaceY;
        private int bottomY;
        private boolean started;

        RiftJob(ServerLevel level, List<RiftShape.Point> points, int width, int depth, int centerY) {
            this.level = level;
            this.points = points;
            this.width = Math.max(2, Math.min(16, width));
            this.depth = Math.max(6, Math.min(128, depth));
            this.centerY = centerY;
            if (!points.isEmpty()) {
                startPoint();
            }
        }

        private void startPoint() {
            RiftShape.Point p = points.get(index);
            surfaceY = Math.max(level.getMinBuildHeight() + 1,
                    level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, p.x(), p.z()));
            bottomY = Math.max(level.getMinBuildHeight() + 1, centerY - depth);
            y = surfaceY - 1;
            xi = -width;
            zi = -width;
            started = true;
        }

        @Override
        public int step(int budget) {
            if (points.isEmpty()) {
                return 0;
            }
            int processed = 0;
            while (processed < budget && !done()) {
                if (!started) {
                    startPoint();
                }
                RiftShape.Point p = points.get(index);
                // 越深越窄：每 10 格收 1 格，形成 V 形裂谷和阶梯状谷壁。
                int taper = Math.max(1, width - Math.max(0, (surfaceY - 1 - y)) / 10);
                if (Math.abs(xi) + Math.abs(zi) <= taper) {
                    BlockPos pos = new BlockPos(p.x() + xi, y, p.z() + zi);
                    BlockState destroyed = destroyOne(level, pos);
                    if (destroyed != null) {
                        spawnDebris(level, pos, destroyed);
                    }
                    // 只把真正落在菱形截面内的格子算进全局预算；扫描空白不算。
                    processed++;
                }
                zi++;
                if (zi > width) {
                    zi = -width;
                    xi++;
                }
                if (xi > width) {
                    xi = -width;
                    zi = -width;
                    y--;
                    if (y < bottomY) {
                        index++;
                        if (index >= points.size()) {
                            started = false;
                            break;
                        }
                        startPoint();
                    }
                }
            }
            return processed;
        }

        @Override
        public boolean done() {
            return points.isEmpty() || index >= points.size();
        }
    }

    /**
     * 逐层下削模式（默认）：以落点为圆心、半径 {@code r} 的方形区域，<b>一层（同高度的一整片）
     * 挖完之后停 {@code layer_ticks} tick，再往下一层</b> —— 激光不是一炮到底，而是看得见地
     * 一层一层把弹坑磨深。深度与立方体模式一致（半径格）。
     *
     * <p>每层选区的格子数 (2r+1)² 超过每 tick 预算时，这一层会跨多个 tick 慢慢挖完，
     * 但绝不在本层没挖净时先动下一层 —— 「层」是原子单位。</p>
     */
    private static final class LayerJob implements DestroyJob {
        private final ServerLevel level;
        private final int cx;
        private final int cz;
        private final int radius;
        private final int topY;
        private final int bottomY;
        private final int layerTicks;
        private int y;
        private int xi;
        private int zi;
        /** 距下一层开始的剩余停顿 tick。 */
        private int pause;

        LayerJob(ServerLevel level, BlockPos center, int radius) {
            this.level = level;
            this.cx = center.getX();
            this.cz = center.getZ();
            this.radius = radius;
            // 从地表上一层开始（那一层几乎全是空气，扫过去很快），一直削到半径深度。
            this.topY = Math.min(level.getMaxBuildHeight() - 1, center.getY() + 1);
            this.bottomY = Math.max(level.getMinBuildHeight(), center.getY() - radius);
            this.layerTicks = Math.max(1, Config.ORBITAL_STRIKE_LAYER_TICKS.get());
            this.y = topY;
            this.xi = -radius;
            this.zi = -radius;
        }

        @Override
        public int step(int budget) {
            if (pause > 0) {
                pause--;
                return 0;
            }
            int processed = 0;
            while (processed < budget && !done()) {
                destroyOne(level, new BlockPos(cx + xi, y, cz + zi));
                processed++;
                zi++;
                if (zi > radius) {
                    zi = -radius;
                    xi++;
                }
                if (xi > radius) {
                    // 这一层挖净了：火花 + 闷响，然后停 layerTicks 再下一层
                    layerFinished();
                    xi = -radius;
                    zi = -radius;
                    y--;
                    pause = layerTicks;
                    break;
                }
            }
            return processed;
        }

        /** 每层收尾：中心一撮星火；每三层一声石头闷响，让「削下去」有节奏。 */
        private void layerFinished() {
            double gx = cx + 0.5D;
            double gz = cz + 0.5D;
            int sparks = Math.min(20, 6 + radius / 3);
            level.sendParticles(ModParticles.ORBITAL_SPARK.get(),
                    gx, y + 1.2D, gz, sparks,
                    radius * 0.35D, 0.15D, radius * 0.35D, 0.03D);
            int depth = topY - y;
            if (depth > 0 && depth % 3 == 0) {
                BlockPos at = new BlockPos(cx, y, cz);
                level.playSound(null, at, SoundEvents.STONE_BREAK, SoundSource.BLOCKS, 1.6F, 0.55F);
                level.playSound(null, at, SoundEvents.LAVA_EXTINGUISH, SoundSource.BLOCKS, 0.35F, 0.5F);
            }
        }

        @Override
        public boolean done() {
            return y < bottomY;
        }
    }

    /**
     * 整列模式：以 (cx, cz) 为圆心、radius 为半径的方形列，从 {@code maxY} 一路挖到 {@code minY}。
     * 不预计算列表（半径 32 约 160 万格，列表会吃掉几十 MB），用游标按层推进。
     */
    private static final class ColumnJob implements DestroyJob {
        private final ServerLevel level;
        private final int cx;
        private final int cz;
        private final int radius;
        private final int minY;
        private final BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        private int y;
        private int xi;
        private int zi;
        /** 上一次触发坍塌闷响的层高（同一层只响一次）。 */
        private int lastRumbleY = Integer.MIN_VALUE;

        ColumnJob(ServerLevel level, int cx, int cz, int radius, int minY, int maxY) {
            this.level = level;
            this.cx = cx;
            this.cz = cz;
            this.radius = radius;
            this.minY = minY;
            this.y = maxY;
            this.xi = -radius;
            this.zi = -radius;
        }

        @Override
        public int step(int budget) {
            int processed = 0;
            while (processed < budget && !done()) {
                cursor.set(cx + xi, y, cz + zi);
                BlockState destroyed = destroyOne(level, cursor);
                if (destroyed != null) {
                    spawnDebris(level, cursor, destroyed);
                    // 只在真的挖到方块的层响：从 Y=320 往下的一大段空气不该有坍塌声
                    if (y != lastRumbleY) {
                        lastRumbleY = y;
                        collapseRumble(level, cx, y, cz);
                    }
                }
                processed++;
                // 方形列游标：z 走完换 x，x 走完下一层
                zi++;
                if (zi > radius) {
                    zi = -radius;
                    xi++;
                }
                if (xi > radius) {
                    xi = -radius;
                    y--;
                }
            }
            return processed;
        }

        @Override
        public boolean done() {
            return y < minY;
        }
    }

    /**
     * 范围伤害。{@code damageMul} 来自天陨终端的威力滑条（1.0 = 不缩放），
     * 只乘常规伤害，不碰秒杀几率 —— 玩家调的是「打多疼」，不是「秒杀概率」。
     */
    private static void damageArea(ServerLevel level, Vec3 center, double radius, UUID owner,
                                   OrbitalStrikeMode mode, float damageMul) {
        AABB box = new AABB(center.x, center.y, center.z, center.x, center.y, center.z).inflate(radius);
        List<LivingEntity> targets = level.getEntitiesOfClass(LivingEntity.class, box);
        if (targets.isEmpty()) {
            return;
        }
        double max = Math.max(1.0D, radius);
        float base = Config.ORBITAL_STRIKE_DAMAGE.get().floatValue() * mode.damageScale()
                * damageMul;
        int killPercent = Mth.clamp(Config.ORBITAL_STRIKE_KILL_CHANCE.get() + mode.killBonus(), 0, 100);
        for (LivingEntity entity : targets) {
            if (entity.isRemoved() || !entity.isAlive() || entity.isSpectator()) {
                continue;
            }
            double d = entity.position().distanceTo(center);
            if (d > max) {
                continue;
            }
            DamageSource source = level.damageSources().explosion(null, ownerPlayer(level, owner));
            // 秒杀判定：roll 通过直接「处死」，绕过血量/护甲/无敌帧，这才配叫天基武器。
            if (killPercent > 0 && level.random.nextInt(100) < killPercent) {
                entity.hurt(source, Float.MAX_VALUE);
                // 有些生物 hurt 后还活着（抗性/event 拦截），补一刀 setHealth(0) + die
                if (entity.isAlive()) {
                    entity.setHealth(0.0F);
                    entity.die(source);
                }
                // 秒杀反馈：一团爆炸 + 一撮灵魂粒子（让「秒了」这件事看得见）
                level.sendParticles(ParticleTypes.EXPLOSION_EMITTER,
                        entity.getX(), entity.getY() + 0.5D, entity.getZ(), 1, 0.0D, 0.0D, 0.0D, 0.0D);
                level.sendParticles(ParticleTypes.SOUL,
                        entity.getX(), entity.getY() + 0.5D, entity.getZ(), 8, 0.3D, 0.4D, 0.3D, 0.02D);
                continue;
            }
            // 常规伤害：中心 100%，边缘 30% —— 越靠近中心伤害越高
            float scale = (float) (1.0D - 0.7D * (d / max));
            entity.hurt(source, base * scale);
            // 击退方向按模式：引力奇点「向上掀飞」、行星陨落「炸开式击退」，其余径向推力。
            if (!entity.isSpectator()) {
                if (mode == OrbitalStrikeMode.GRAVITY) {
                    entity.push(0.0D, 1.6D, 0.0D);
                } else if (mode == OrbitalStrikeMode.PLANET) {
                    Vec3 push = entity.position().subtract(center).normalize().scale(1.4D);
                    entity.push(push.x, 1.0D, push.z);
                } else {
                    Vec3 push = entity.position().subtract(center).normalize().scale(0.6D);
                    entity.push(push.x, 0.4D, push.z);
                }
                entity.hurtMarked = true;
            }
        }
    }

    private static Player ownerPlayer(ServerLevel level, UUID owner) {
        return owner == null ? null : level.getPlayerByUUID(owner);
    }

    /** 用 {@code modid:block_id} 字符串与 {@link Block} 比较：列表里写着「这个名字」就算命中。 */
    private static boolean isProtected(Block block) {
        var ids = Config.ORBITAL_STRIKE_PROTECTED.get();
        if (ids == null || ids.isEmpty()) {
            return false;
        }
        var key = net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(block);
        if (key == null) {
            return false;
        }
        String full = key.getNamespace() + ":" + key.getPath();
        for (String s : ids) {
            if (s != null && s.equals(full)) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------ v4.0 P3：相位 / 取消

    private static MinecraftServer currentServer() {
        return net.minecraftforge.server.ServerLifecycleHooks.getCurrentServer();
    }

    /** 给一次打击的所有观众发当前相位。 */
    private static void sendPhase(ActiveStrike strike, StrikePhase phase) {
        MinecraftServer server = currentServer();
        if (server == null) {
            return;
        }
        int tick = server.getTickCount();
        for (UUID id : strike.viewers) {
            ServerPlayer viewer = server.getPlayerList().getPlayer(id);
            if (viewer != null) {
                NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> viewer),
                        new StrikePhasePacket(strike.strikeId, phase.ordinal(), tick));
            }
        }
    }

    /** 告诉所有人这次打击中止了。 */
    private static void broadcastCancel(ActiveStrike strike, int reason) {
        MinecraftServer server = currentServer();
        if (server == null) {
            return;
        }
        for (UUID id : strike.viewers) {
            ServerPlayer viewer = server.getPlayerList().getPlayer(id);
            if (viewer != null) {
                NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> viewer),
                        new StrikeCancelPacket(strike.strikeId, reason));
            }
        }
    }

    /** 当前进行中的打击数（命令 / 调试用）。 */
    public static int activeCount() {
        return ACTIVE.size();
    }

    /** 按 id 取消一次打击；返回是否真的取消了。 */
    public static boolean cancel(UUID strikeId, int reason) {
        Iterator<Map.Entry<UUID, ActiveStrike>> it = ACTIVE.entrySet().iterator();
        while (it.hasNext()) {
            ActiveStrike strike = it.next().getValue();
            if (strike.strikeId.equals(strikeId)) {
                it.remove();
                broadcastCancel(strike, reason);
                refundTerminal(strike);
                return true;
            }
        }
        return false;
    }

    /** 取消所有进行中的打击（管理员命令 / 配置总开关用）。 */
    public static int cancelAll(int reason) {
        if (ACTIVE.isEmpty()) {
            return 0;
        }
        int count = 0;
        for (ActiveStrike strike : ACTIVE.values()) {
            broadcastCancel(strike, reason);
            refundTerminal(strike);
            count++;
        }
        ACTIVE.clear();
        return count;
    }

    /** 某个终端被拆/被替换：取消它授权的、还没结算完的打击。 */
    public static int cancelForTerminal(net.minecraft.resources.ResourceKey<Level> dimension,
                                        BlockPos terminalPos) {
        int count = 0;
        Iterator<Map.Entry<UUID, ActiveStrike>> it = ACTIVE.entrySet().iterator();
        while (it.hasNext()) {
            ActiveStrike strike = it.next().getValue();
            if (strike.terminalPos != null && strike.terminalPos.equals(terminalPos)
                    && strike.dimension.equals(dimension)) {
                it.remove();
                broadcastCancel(strike, StrikeCancelPacket.REASON_TERMINAL_BROKEN);
                refundTerminal(strike);
                count++;
            }
        }
        return count;
    }

    /** FIRE 之前取消才退款（弹已经出去了就不退）。 */
    private static void refundTerminal(ActiveStrike strike) {
        if (strike.terminalPos == null || strike.age >= strike.lockTicks) {
            return;
        }
        MinecraftServer server = currentServer();
        if (server == null) {
            return;
        }
        ServerLevel level = server.getLevel(strike.dimension);
        if (level == null) {
            return;
        }
        if (level.getBlockEntity(strike.terminalPos) instanceof SkyfallTerminalBlockEntity terminal) {
            terminal.refundCharge();
        }
    }

    /** Box 内整数 BlockPos，**从高到低**逐层（分批挖掘时一层层往下塌，观感比乱序好）。 */
    /** 一次进行中的打击：目标、模式，以及已经乘过模式倍率的半径/时长（客户端收到的是同一组数）。 */
    private static final class ActiveStrike {
        final BlockPos target;
        final UUID owner;
        final net.minecraft.resources.ResourceKey<Level> dimension;
        final OrbitalStrikeMode mode;
        final int radius;
        final int lockTicks;
        final int fallTicks;
        /** 触发时的朝向：断层裂谷沿它展开。 */
        final float yaw;
        /** 终端威力滑条带来的伤害倍率（1.0 = 原伤害）。 */
        final float damageMul;
        /** v4.0 P3：本次打击标识，相位/取消包都带它。 */
        final UUID strikeId;
        /** v4.0 P3：授权来源终端；自由开火为 null（取消时不退款）。 */
        @Nullable
        final BlockPos terminalPos;
        /** v4.0 P3：开场时确定的过场收件人（施放者 + 广播范围内玩家）。 */
        final List<UUID> viewers;
        /** v4.0 P3：最后发给观众的相位 ordinal，-1 = 还没发过。 */
        byte lastPhase = -1;
        int age;

        ActiveStrike(BlockPos target, UUID owner, net.minecraft.resources.ResourceKey<Level> dimension,
                     OrbitalStrikeMode mode, int radius, int lockTicks, int fallTicks, float yaw,
                     float damageMul, UUID strikeId, @Nullable BlockPos terminalPos,
                     List<UUID> viewers) {
            this.target = target;
            this.owner = owner;
            this.dimension = dimension;
            this.mode = mode;
            this.radius = radius;
            this.lockTicks = lockTicks;
            this.fallTicks = fallTicks;
            this.yaw = yaw;
            this.damageMul = damageMul;
            this.strikeId = strikeId;
            this.terminalPos = terminalPos;
            this.viewers = viewers;
        }
    }
}
