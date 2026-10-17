package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 「轨道打击」的服务端主循环：玩家右键遥控器后，这里记一笔，按 tick 推进「锁定 → 下落 → 落地」三段。
 *
 * <p><b>三段时间轴</b>：锁定 {@code Config.ORBITAL_STRIKE_LOCK_TICKS}（默认 30 = 1.5 s）、
 * 下落固定 6 tick（约 0.3 s，从 Y=320 落下来 Y 速 60/tick）、落地 tick 1（摧毁 + AOE 伤害）。
 * 整个特效期间为该玩家单方执行 —— 不同玩家各自记一条，多人互不干扰。</p>
 *
 * <p><b>为什么不在地上画轨迹</b>：从 Y=320 落下的「光柱」是为了视觉上像「从宇宙之外打下来」，
 * 不去模拟真实的弹道 —— 玩家瞄哪儿，光柱就笔直落在哪儿，没有任何抛物线或偏移。
 * 偏移/方向由玩家瞄的方向决定，瞄准者本人自负责。</p>
 */
public final class OrbitalStrikeManager {

    /** 从哪个高度开始往下打。Y=320 远高于世界构建上限（Y=256），所以视觉上像「从天上来的」。 */
    private static final double IMPACT_FALL_Y = 320.0D;
    /** 下落阶段固定走 6 tick（约 0.3 s），与锁定阶段合计约 1.8 s 整。 */
    private static final int FALL_TICKS = 6;
    /** 下落阶段每 tick 在光柱上的粒子密度。 */
    private static final int FALL_PARTICLES_PER_TICK = 12;
    /** 锁定阶段每 tick 在目标点周围 5x5x5 范围画的锁定粒子数。 */
    private static final int LOCK_PARTICLES_PER_TICK = 24;
    /** 落地 tick 时画的爆炸粒子数。 */
    private static final int IMPACT_PARTICLES = 96;

    private static final Map<UUID, ActiveStrike> ACTIVE = new HashMap<>();

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
     * <p>同一玩家在冷却期间重复右键会覆盖原有目标（避免队列堆叠 + 误触重置阶段）。</p>
     */
    public static void schedule(ServerPlayer player, BlockPos target) {
        ACTIVE.put(player.getUUID(),
                new ActiveStrike(target.immutable(), player.getUUID(), player.level().dimension()));
        // 视觉：把目标点告诉客户端（只对本人发，多人时各看各的；别人放技能时不会在你屏幕上画）
        int radius = Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 16);
        int lockTicks = Math.max(20, Config.ORBITAL_STRIKE_LOCK_TICKS.get());
        com.apocalypse.zombies.network.NetworkHandler.CHANNEL.send(
                net.minecraftforge.network.PacketDistributor.PLAYER.with(() -> player),
                new com.apocalypse.zombies.network.OrbitalStrikePacket(target, radius, lockTicks));
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || ACTIVE.isEmpty()) {
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
            int lockTicks = Math.max(20, Config.ORBITAL_STRIKE_LOCK_TICKS.get());
            ActiveStrike next = strike.advance();
            // 迭代中改值必须走 entry.setValue —— put 到已有 key 虽然不会触发 CME，
            // 但结构修改与迭代器混用是容易出错的写法，这里保持干净。
            entry.setValue(next);
            strike = next;
            if (strike.age() < lockTicks) {
                tickLocking(level, strike);
            } else if (strike.age() < lockTicks + FALL_TICKS) {
                tickFalling(level, strike, strike.age() - lockTicks);
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
        // 画 24 个 end_rod 粒子在 ±0.5 范围内随机
        for (int i = 0; i < LOCK_PARTICLES_PER_TICK; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * 6.0D;
            double oy = (level.random.nextDouble() - 0.5D) * 3.0D;
            double oz = (level.random.nextDouble() - 0.5D) * 6.0D;
            level.sendParticles(ParticleTypes.END_ROD, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        // 半 tick 一次的电弧音
        if ((strike.age() & 1) == 0) {
            level.playSound(null, target, SoundEvents.BEACON_AMBIENT, SoundSource.PLAYERS,
                    0.6F, 1.8F);
        }
        // 第一帧：轨道平台「上线」的提示音（与客户端平台渲染同时出现）
        if (strike.age() == 1) {
            level.playSound(null, target, SoundEvents.BEACON_POWER_SELECT, SoundSource.PLAYERS,
                    1.2F, 1.4F);
        }
        // 「太空里有人按了按钮」：锁定阶段在高空稀疏撒星点 —— 玩家抬头能看到上面有动静
        if ((strike.age() & 3) == 0) {
            double sx = (level.random.nextDouble() - 0.5D) * 10.0D;
            double sz = (level.random.nextDouble() - 0.5D) * 10.0D;
            level.sendParticles(ParticleTypes.END_ROD,
                    ground.x + sx, IMPACT_FALL_Y + level.random.nextDouble() * 24.0D, ground.z + sz,
                    1, 0.0D, -0.1D, 0.0D, 0.0D);
        }
        // 进度越大，目标圈收缩到目标点（视觉引导「锁定中」）
        if (DEBUG) {
            ApocalypseZombies.LOGGER.info("[orbital] lock tick {} target={}", strike.age(), target);
        }
    }

    private static void tickFalling(ServerLevel level, ActiveStrike strike, int local) {
        // local ∈ [0, FALL_TICKS)；+1 让最后一帧正好压到地面（t = 6/6 = 1.0），
        // 否则光柱头永远停在地面上方约一格，落地瞬间会「跳一格」。
        double t = (double) (local + 1) / FALL_TICKS;
        double y = Mth.lerp(t, IMPACT_FALL_Y, strike.target.getY() + 1.0D);
        Vec3 ground = Vec3.atCenterOf(strike.target);
        // 每 tick 在光柱本体上画 FALL_PARTICLES_PER_TICK 个粒子，沿 y 轴铺开
        for (int i = 0; i < FALL_PARTICLES_PER_TICK; i++) {
            double fy = y - level.random.nextDouble() * 30.0D;   // 拖一条 30 格长的尾迹
            double ox = (level.random.nextDouble() - 0.5D) * 0.6D;
            double oz = (level.random.nextDouble() - 0.5D) * 0.6D;
            level.sendParticles(ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, fy, ground.z + oz,
                    1, 0.0D, -0.4D, 0.0D, 0.0D);
            level.sendParticles(ParticleTypes.END_ROD, ground.x + ox, fy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        // 尾部加一点「拖慢的尘埃」—— 光柱从宇宙落下来，最上面留一点星尘不散
        for (int i = 0; i < 3; i++) {
            double sx = (level.random.nextDouble() - 0.5D) * 4.0D;
            double sz = (level.random.nextDouble() - 0.5D) * 4.0D;
            level.sendParticles(ParticleTypes.END_ROD, ground.x + sx, IMPACT_FALL_Y + 4.0D + level.random.nextDouble() * 20.0D,
                    ground.z + sz, 1, 0.0D, -0.2D, 0.0D, 0.0D);
        }
        // 下落音（从远到近越来越响）
        float volume = 0.3F + (float) t * 1.4F;
        float pitch = 0.6F + (float) t * 0.8F;
        level.playSound(null, strike.target, SoundEvents.BLAZE_SHOOT, SoundSource.PLAYERS, volume, pitch);
    }

    private static void tickImpact(ServerLevel level, ActiveStrike strike) {
        BlockPos target = strike.target;
        Vec3 ground = Vec3.atCenterOf(target);
        int radius = Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 16);
        boolean destroy = Config.ORBITAL_STRIKE_DESTROY_BLOCKS.get();
        boolean damage = Config.ORBITAL_STRIKE_DAMAGE_MOBS.get();

        if (destroy) {
            destroyArea(level, target, radius);
        }
        if (damage) {
            damageArea(level, target, radius, strike.owner);
        }
        // 爆炸视觉 + 大量粒子
        level.playSound(null, target, SoundEvents.GENERIC_EXPLODE, SoundSource.PLAYERS, 1.6F, 0.7F);
        level.playSound(null, target, SoundEvents.BEACON_DEACTIVATE, SoundSource.PLAYERS, 1.2F, 0.5F);
        // 远雷：光柱砸到地面那一下，别处也能听见（音量按距离衰减，玩家 120 格内可闻）
        level.playSound(null, target, SoundEvents.LIGHTNING_BOLT_THUNDER, SoundSource.WEATHER, 2.4F, 0.55F);
        // 起源：Y=320 处的太空爆点，六角星尘向外散开 —— 强调「这一击来自宇宙之外」
        for (int i = 0; i < 32; i++) {
            double angle = i * Math.PI * 2.0D / 32.0D;
            double spread = 1.5D + level.random.nextDouble() * 2.5D;
            level.sendParticles(ParticleTypes.END_ROD,
                    ground.x, IMPACT_FALL_Y, ground.z,
                    1, Math.cos(angle) * spread, 0.3D + level.random.nextDouble() * 0.6D, Math.sin(angle) * spread, 0.25D);
        }
        // 大爆 FLASH + 多色粉尘
        for (int i = 0; i < IMPACT_PARTICLES; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            double oy = (level.random.nextDouble() - 0.5D) * radius * 1.0D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.6D;
            level.sendParticles(ParticleTypes.EXPLOSION, ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            level.sendParticles(ParticleTypes.SOUL_FIRE_FLAME, ground.x + ox, ground.y + 0.4D + oy * 0.3, ground.z + oz,
                    1, 0.0D, 0.0D, 0.0D, 0.0D);
            if ((i & 1) == 0) {
                level.sendParticles(ParticleTypes.FLASH, ground.x, ground.y + 0.5D, ground.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
            }
        }
        // 蘑菇云：从地面向上翻腾的浓烟 + 火舌（落点越近越密，往外围越来越稀）
        for (int i = 0; i < 56; i++) {
            double ox = (level.random.nextDouble() - 0.5D) * radius * 1.2D;
            double oz = (level.random.nextDouble() - 0.5D) * radius * 1.2D;
            double oy = level.random.nextDouble() * radius * 0.9D;
            level.sendParticles(ParticleTypes.LARGE_SMOKE,
                    ground.x + ox, ground.y + oy, ground.z + oz,
                    1, 0.0D, 0.06D + level.random.nextDouble() * 0.10D, 0.0D, 0.03D);
            if ((i & 1) == 0) {
                level.sendParticles(ParticleTypes.FLAME,
                        ground.x + ox * 0.6D, ground.y + oy * 0.4D, ground.z + oz * 0.6D,
                        1, 0.0D, 0.12D, 0.0D, 0.03D);
            }
        }
    }

    /**
     * 摧毁 AABB 内方块，规则：
     * <ul>
     *   <li>流体/空气不动；</li>
     *   <li>{@link Blocks#BEDROCK} / 屏障 / 命令方块 不动；</li>
     *   <li>硬度 &gt; {@code MAX_HARDNESS} 不动（避开黑曜石等需时很长的方块，避免卡顿）；</li>
     *   <li>方块实体类（箱子、熔炉、刷怪箱、告示牌）不动；</li>
     *   <li>配置里 {@code protected} 名单不动；</li>
     *   <li>其余 destroyBlock(pos, false)：不掉落物，但触发 BreakEvent 留给其它 mod 处理。</li>
     * </ul>
     */
    private static void destroyArea(ServerLevel level, BlockPos center, int radius) {
        AABB box = new AABB(center).inflate(radius);
        List<BlockPos> positions = collectBox(box);
        for (BlockPos pos : positions) {
            BlockState state = level.getBlockState(pos);
            if (state.isAir()) {
                continue;
            }
            Block block = state.getBlock();
            if (block == Blocks.BEDROCK || block == Blocks.BARRIER || block == Blocks.COMMAND_BLOCK
                    || block == Blocks.CHAIN_COMMAND_BLOCK || block == Blocks.REPEATING_COMMAND_BLOCK
                    || block == Blocks.STRUCTURE_BLOCK || block == Blocks.JIGSAW) {
                continue;
            }
            if (state.getBlock().defaultBlockState().hasBlockEntity()) {
                continue;
            }
            if (state.getDestroySpeed(level, pos) < 0.0F) {
                continue;   // 不可破坏
            }
            if (state.getDestroySpeed(level, pos) > Config.ORBITAL_STRIKE_MAX_HARDNESS.get().floatValue()) {
                continue;   // 太硬（避开黑曜石、远古残骸的尴尬 50/50 临界）
            }
            // 保护名单（如果配置了）
            if (isProtected(block)) {
                continue;
            }
            level.destroyBlock(pos, false);
        }
    }

    private static void damageArea(ServerLevel level, BlockPos center, int radius, UUID owner) {
        AABB box = new AABB(center).inflate(radius);
        List<LivingEntity> targets = level.getEntitiesOfClass(LivingEntity.class, box);
        if (targets.isEmpty()) {
            return;
        }
        double max = Math.max(1.0D, radius);
        float base = Config.ORBITAL_STRIKE_DAMAGE.get().floatValue();
        int killPercent = Mth.clamp(Config.ORBITAL_STRIKE_KILL_CHANCE.get(), 0, 100);
        for (LivingEntity entity : targets) {
            if (entity.isRemoved() || !entity.isAlive()) {
                continue;
            }
            double d = entity.position().distanceTo(Vec3.atCenterOf(center));
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
            float dmg = base * scale;
            entity.hurt(source, dmg);
            // 击退：中心向外的纯径向推力
            if (!entity.isSpectator()) {
                Vec3 push = entity.position().subtract(Vec3.atCenterOf(center)).normalize().scale(0.6D);
                entity.push(push.x, 0.4D, push.z);
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

    /** Box 内整数 BlockPos（顺序：自上而下、从北到南；不重复不遗漏）。 */
    private static List<BlockPos> collectBox(AABB box) {
        int minX = Mth.floor(box.minX);
        int minY = Mth.floor(box.minY);
        int minZ = Mth.floor(box.minZ);
        int maxX = Mth.floor(box.maxX);
        int maxY = Mth.floor(box.maxY);
        int maxZ = Mth.floor(box.maxZ);
        List<BlockPos> out = new ArrayList<>((maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1));
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                for (int z = minZ; z <= maxZ; z++) {
                    out.add(new BlockPos(x, y, z));
                }
            }
        }
        return out;
    }

    private record ActiveStrike(BlockPos target, UUID owner,
                                net.minecraft.resources.ResourceKey<Level> dimension, int age) {
        ActiveStrike(BlockPos target, UUID owner, net.minecraft.resources.ResourceKey<Level> dimension) {
            this(target, owner, dimension, 0);
        }

        ActiveStrike advance() {
            return new ActiveStrike(target, owner, dimension, age + 1);
        }
    }
}
