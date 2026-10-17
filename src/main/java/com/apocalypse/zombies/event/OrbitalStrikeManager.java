package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
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
import net.minecraft.world.entity.LivingEntity;
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
    public static void schedule(ServerPlayer player, BlockPos target, OrbitalStrikeMode mode) {
        int radius = mode.radius(Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 96));
        int lockTicks = mode.lockTicks(Math.max(20, Config.ORBITAL_STRIKE_LOCK_TICKS.get()));
        int fallTicks = mode.fallTicks(Math.max(6, Config.ORBITAL_STRIKE_FALL_TICKS.get()));
        ACTIVE.put(player.getUUID(), new ActiveStrike(target.immutable(), player.getUUID(),
                player.level().dimension(), mode, radius, lockTicks, fallTicks));
        // 视觉：把目标点告诉客户端（只对本人发，多人时各看各的；别人放技能时不会在你屏幕上画）
        com.apocalypse.zombies.network.NetworkHandler.CHANNEL.send(
                net.minecraftforge.network.PacketDistributor.PLAYER.with(() -> player),
                new com.apocalypse.zombies.network.OrbitalStrikePacket(
                        target, radius, lockTicks, fallTicks, mode));
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
            int budget = BLOCKS_PER_TICK;
            Iterator<DestroyJob> dit = DESTROY_QUEUE.iterator();
            while (dit.hasNext() && budget > 0) {
                DestroyJob job = dit.next();
                budget -= job.step(budget);
                if (job.done()) {
                    dit.remove();
                }
            }
        }
        if (ACTIVE.isEmpty()) {
            return;
        }
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            ACTIVE.clear();
            return;
        }
        Iterator<Map.Entry<UUID, ActiveStrike>> it = ACTIVE.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<UUID, ActiveStrike> entry = it.next();
            ActiveStrike strike = entry.getValue();
            ServerLevel level = resolveLevel(strike);
            if (level == null) {
                it.remove();
                continue;
            }
            // 年龄与时长都在 ActiveStrike 上：模式倍率已经在 schedule 时乘过了。
            int age = ++strike.age;
            if (age < strike.lockTicks) {
                tickLocking(level, strike);
            } else if (age < strike.lockTicks + strike.fallTicks) {
                tickFalling(level, strike, age - strike.lockTicks);
            } else {
                tickImpact(level, strike);
                it.remove();
            }
        }
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
        if (strike.mode == OrbitalStrikeMode.GRAVITY) {
            pullToward(level, strike, t);
        }
        // 下落粒子也按模式分 —— 客户端是四套形态，世界里就不能还是同一根柱。
        if (strike.mode == OrbitalStrikeMode.STORM) {
            // 风暴：五个落点各自一道闪电的噼啪火花
            double[][] offsets = OrbitalStrikeMode.stormOffsets(strike.target, strike.radius);
            for (double[] offset : offsets) {
                double bx = ground.x + offset[0];
                double bz = ground.z + offset[1];
                for (int i = 0; i < 3; i++) {
                    double fy = y - level.random.nextDouble() * 12.0D;
                    broadcast(level, ParticleTypes.ELECTRIC_SPARK,
                            bx + (level.random.nextDouble() - 0.5D) * 0.8D, fy,
                            bz + (level.random.nextDouble() - 0.5D) * 0.8D,
                            1, 0.0D, -0.20D, 0.0D, 0.15D);
                }
            }
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
            case STORM -> impactStorm(level, strike, ground, strike.radius, destroy, damage);
            case LASER -> impactLaser(level, strike, ground, strike.radius, destroy, damage);
            default -> impactCannon(level, strike, ground, strike.radius, destroy, damage);
        }
    }

    /**
     * 宇宙激光：从深空（Y=700）直射下来的一束光。没有飞行时间，充能完成即命中；
     * 破坏性全场最强 —— 半径 1.35×、伤害 3×、秒杀 +30%，并且一路打穿到虚空。
     */
    private static void impactLaser(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                    int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.LASER);
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
    private static void impactCannon(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                     int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.CANNON);
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
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            // 半径小，但伤害密度高：用 1.6 倍的判定半径，中心一击几乎必杀
            damageArea(level, ground, radius * 1.6D, strike.owner, OrbitalStrikeMode.LANCE);
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
     * 引力奇点：先塌缩再爆开。下落段已经把周围生物往落点拖（见 {@link #tickFalling}），
     * 落地瞬间给一个向上的反冲 —— 被「吸进去」的东西又被「吐出来」。
     */
    private static void impactGravity(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                      int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        if (destroy) {
            enqueueDestroy(level, target, radius, strike.mode.pierces());
        }
        if (damage) {
            damageArea(level, ground, radius, strike.owner, OrbitalStrikeMode.GRAVITY);
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
    private static void impactStorm(ServerLevel level, ActiveStrike strike, Vec3 ground,
                                    int radius, boolean destroy, boolean damage) {
        BlockPos target = strike.target;
        double[][] offsets = OrbitalStrikeMode.stormOffsets(target, radius);
        int subRadius = Mth.clamp(Math.round(radius * 0.45F), 2, 12);
        for (double[] offset : offsets) {
            Vec3 sub = new Vec3(ground.x + offset[0], ground.y, ground.z + offset[1]);
            BlockPos subPos = BlockPos.containing(sub);
            if (destroy) {
                enqueueDestroy(level, subPos, subRadius, strike.mode.pierces());
            }
            if (damage) {
                damageArea(level, sub, subRadius * 1.8D, strike.owner, OrbitalStrikeMode.STORM);
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
        }
        // 中心一记更低的轰鸣把所有落点「串」起来
        level.playSound(null, target, SoundEvents.WARDEN_SONIC_BOOM, SoundSource.PLAYERS, 5.0F, 0.55F);
        level.playSound(null, target, SoundEvents.ENDER_DRAGON_GROWL, SoundSource.PLAYERS, 3.0F, 0.8F);
        // 整片区域一层翻腾的烟
        int cloud = Math.min(180, 40 + radius * 6);
        for (int i = 0; i < cloud; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.8D;
            broadcast(level, ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + level.random.nextDouble() * 2.5D, ground.z + oz,
                    1, 0.0D, 0.05D, 0.0D, 0.02D);
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
        boolean column = forceColumn || (mode != null && "column".equalsIgnoreCase(mode.trim()));
        if (column) {
            // 整列挖穿（参考 the-shooting-star 的招牌观感）：从建筑上限一路挖到虚空。
            // 这一模式不预计算列表 —— 半径 32 就有 160 万个位置，游标式推进省内存。
            DESTROY_QUEUE.add(new ColumnJob(level, center.getX(), center.getZ(), radius,
                    level.getMinBuildHeight(), level.getMaxBuildHeight() - 1));
        } else {
            AABB box = new AABB(center).inflate(radius);
            // 游标推进，不预计算列表：半径 96 的立方体是 193³ ≈ 720 万格，
            // 一个 BlockPos 列表能吃掉一百多 MB 堆内存。
            DESTROY_QUEUE.add(new BoxJob(level,
                    Mth.floor(box.minX), Mth.floor(box.minY), Mth.floor(box.minZ),
                    Mth.floor(box.maxX), Mth.floor(box.maxY), Mth.floor(box.maxZ)));
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

    private static void damageArea(ServerLevel level, Vec3 center, double radius, UUID owner,
                                   OrbitalStrikeMode mode) {
        AABB box = new AABB(center.x, center.y, center.z, center.x, center.y, center.z).inflate(radius);
        List<LivingEntity> targets = level.getEntitiesOfClass(LivingEntity.class, box);
        if (targets.isEmpty()) {
            return;
        }
        double max = Math.max(1.0D, radius);
        float base = Config.ORBITAL_STRIKE_DAMAGE.get().floatValue() * mode.damageScale();
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
            // 击退方向按模式：引力奇点是「向上掀飞」，其余是中心向外的径向推力。
            if (!entity.isSpectator()) {
                if (mode == OrbitalStrikeMode.GRAVITY) {
                    entity.push(0.0D, 1.6D, 0.0D);
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
        int age;

        ActiveStrike(BlockPos target, UUID owner, net.minecraft.resources.ResourceKey<Level> dimension,
                     OrbitalStrikeMode mode, int radius, int lockTicks, int fallTicks) {
            this.target = target;
            this.owner = owner;
            this.dimension = dimension;
            this.mode = mode;
            this.radius = radius;
            this.lockTicks = lockTicks;
            this.fallTicks = fallTicks;
        }
    }
}
