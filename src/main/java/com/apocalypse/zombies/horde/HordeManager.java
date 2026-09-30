package com.apocalypse.zombies.horde;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.HordeOverlord;
import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.zombie.ZombieEvolution;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitlesAnimationPacket;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.BossEvent;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * The siege: a fixed number of waves with a deliberately unpredictable head count.
 *
 * <p>Each wave rolls its own population inside a band that widens with the wave index and the
 * world's evolution stage, then jitters it again — so no two hordes ever look alike. Every wave is
 * spawned in a ring around the players, with each mob's evolution tier rolled individually.</p>
 */
public final class HordeManager {

    /** Mobs alive that belong to the current horde, pruned periodically. */
    private static final Set<UUID> LIVING = new HashSet<>();

    private static boolean active = false;
    private static int nextWaveIndex = 0;
    private static int totalWaves = 5;
    private static long nextWaveTick = 0L;
    private static boolean finalWaveLaunched = false;
    /** 这一场尸潮有没有放过 Boss。每个 {@link #start} 重置一次。 */
    private static boolean bossSpawned = false;
    private static int currentWaveSize = 0;
    private static ServerBossEvent bossBar;

    private HordeManager() {
    }

    public static boolean isActive() {
        return active;
    }

    // ------------------------------------------------------------------ lifecycle

    public static void start(ServerLevel level, int waves) {
        if (!HORDES_ALLOWED) {
            return;
        }
        active = true;
        nextWaveIndex = 0;
        totalWaves = Math.max(1, waves);
        finalWaveLaunched = false;
        bossSpawned = false;
        currentWaveSize = 0;
        LIVING.clear();
        // A short breather so players hear the announcement before the first mob appears.
        nextWaveTick = level.getGameTime() + 120L;

        if (Config.HORDE_BOSS_BAR.get()) {
            bossBar = new ServerBossEvent(
                    Component.translatable("horde.apocalypse_zombies.bar", 0, totalWaves, 0),
                    BossEvent.BossBarColor.RED, BossEvent.BossBarOverlay.NOTCHED_10);
            bossBar.setProgress(0.0F);
            for (ServerPlayer player : level.players()) {
                bossBar.addPlayer(player);
            }
        }

        for (ServerPlayer player : level.players()) {
            player.connection.send(new ClientboundSetTitlesAnimationPacket(10, 50, 20));
            player.connection.send(new ClientboundSetTitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.title")));
            player.connection.send(new ClientboundSetSubtitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.subtitle", totalWaves)));
            player.sendSystemMessage(Component.translatable("horde.apocalypse_zombies.start", totalWaves));
            player.playNotifySound(SoundEvents.RAVAGER_ROAR, SoundSource.HOSTILE, 1.2F, 0.7F);
        }
    }

    public static void stop(ServerLevel level, boolean announce) {
        if (!active) {
            return;
        }
        active = false;
        finalWaveLaunched = false;
        LIVING.clear();
        if (bossBar != null) {
            bossBar.removeAllPlayers();
            bossBar.setVisible(false);
            bossBar = null;
        }
        if (announce) {
            for (ServerPlayer player : level.players()) {
                player.sendSystemMessage(Component.translatable("horde.apocalypse_zombies.end"));
                player.playNotifySound(SoundEvents.PLAYER_LEVELUP, SoundSource.AMBIENT, 0.8F, 1.4F);
            }
        }
    }

    // ------------------------------------------------------------------ ticking

    public static void tick(ServerLevel level) {
        if (!active || !level.dimension().equals(Level.OVERWORLD)) {
            return;
        }
        long now = level.getGameTime();

        if (now % 20L == 0L) {
            prune(level);
        }
        updateBossBar(level);

        if (!finalWaveLaunched) {
            if (now >= nextWaveTick) {
                launchWave(level, now);
            }
        } else if (LIVING.isEmpty() || now >= nextWaveTick) {
            stop(level, true);
        }
    }

    private static void prune(ServerLevel level) {
        Iterator<UUID> iterator = LIVING.iterator();
        while (iterator.hasNext()) {
            UUID id = iterator.next();
            net.minecraft.world.entity.Entity entity = level.getEntity(id);
            if (entity == null || !entity.isAlive()) {
                iterator.remove();
            }
        }
    }

    private static void updateBossBar(ServerLevel level) {
        if (bossBar == null) {
            return;
        }
        for (ServerPlayer player : level.players()) {
            bossBar.addPlayer(player);
        }
        int waveNumber = Math.min(nextWaveIndex + 1, totalWaves);
        bossBar.setName(Component.translatable("horde.apocalypse_zombies.bar",
                waveNumber, totalWaves, LIVING.size()));
        float progress = currentWaveSize <= 0
                ? 0.0F
                : 1.0F - Mth.clamp(LIVING.size() / (float) currentWaveSize, 0.0F, 1.0F);
        bossBar.setProgress(Mth.clamp(progress, 0.0F, 1.0F));
    }

    // ------------------------------------------------------------------ waves

    private static void launchWave(ServerLevel level, long now) {
        List<ServerPlayer> players = new ArrayList<>(level.players());
        if (players.isEmpty()) {
            // Nobody to besiege right now; keep the siege alive and try again shortly.
            nextWaveTick = now + 200L;
            return;
        }

        RandomSource random = level.getRandom();
        int count = rollWaveSize(level, random, nextWaveIndex);
        // 精英领队算进这一波的总人数，否则 boss bar 一开场就是满进度条
        int eliteTarget = eliteTargetFor(nextWaveIndex);
        currentWaveSize = count + eliteTarget;
        int spawned = spawnWave(level, players, random, count, nextWaveIndex);
        spawned += spawnEliteEscort(level, players, random, eliteTarget);

        // 最后一波：尸潮之主领场。它算进这一波的总人数 —— 清不掉它，这一波就永远不结算，
        // 这是「打过 Boss 才算守住」的机制落点。每场尸潮只放一只。
        if (!bossSpawned && nextWaveIndex + 1 >= totalWaves && Config.HORDE_BOSS_ON_FINAL_WAVE.get()) {
            int led = spawnOverlord(level, players, random);
            if (led > 0) {
                bossSpawned = true;
                currentWaveSize += led;
                spawned += led;
                for (ServerPlayer player : players) {
                    player.sendSystemMessage(Component.translatable(
                            "horde.apocalypse_zombies.boss.spawn.message"));
                }
            }
        }

        int waveNumber = nextWaveIndex + 1;
        for (ServerPlayer player : players) {
            player.connection.send(new ClientboundSetTitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.wave.title", waveNumber, totalWaves)));
            player.connection.send(new ClientboundSetSubtitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.wave.subtitle", spawned)));
            player.sendSystemMessage(Component.translatable(
                    "horde.apocalypse_zombies.wave.message", waveNumber, totalWaves, spawned));
            player.playNotifySound(SoundEvents.ZOMBIE_AMBIENT, SoundSource.HOSTILE, 1.0F, 0.6F);
        }

        nextWaveIndex++;
        int minDelay = Math.max(20, Config.WAVE_MIN_DELAY_TICKS.get());
        int maxDelay = Math.max(minDelay, Config.WAVE_MAX_DELAY_TICKS.get());
        int delay = minDelay + random.nextInt(maxDelay - minDelay + 1);

        if (nextWaveIndex >= totalWaves) {
            finalWaveLaunched = true;
            // Give the survivors a window to clear the last wave before the siege disbands.
            nextWaveTick = now + maxDelay;
        } else {
            nextWaveTick = now + delay;
        }
    }

    /**
     * Population for one wave. The band widens with the wave index and the world's evolution stage,
     * then the result is jittered so the exact head count is never the same twice.
     */
    public static int rollWaveSize(ServerLevel level, RandomSource random, int waveIndex) {
        double scale = 1.0D + MoonEventManager.getEvolutionLevel(level) * Config.HORDE_SCALE_PER_LEVEL.get();
        int lo = Math.max(1, (int) Math.round((4 + waveIndex * 3) * scale));
        int hi = Math.max(lo, (int) Math.round((9 + waveIndex * 5) * scale));
        int count = lo + random.nextInt(hi - lo + 1);
        count = (int) Math.round(count * (0.85D + random.nextDouble() * 0.30D));
        return Mth.clamp(count, 1, 90);
    }

    private static int spawnWave(ServerLevel level, List<ServerPlayer> players,
                                 RandomSource random, int count, int waveIndex) {
        int spawned = 0;
        for (int i = 0; i < count; i++) {
            ServerPlayer anchor = players.get(i % players.size());
            BlockPos pos = findSpawn(level, anchor, random);
            if (pos == null) {
                continue;
            }
            Zombie zombie = EntityType.ZOMBIE.create(level);
            if (zombie == null) {
                continue;
            }
            zombie.moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, random.nextFloat() * 360.0F, 0.0F);
            zombie.finalizeSpawn(level, level.getCurrentDifficultyAt(pos), MobSpawnType.EVENT, null, null);
            zombie.setPersistenceRequired();
            ZombieEvolution.setTier(zombie, ZombieEvolution.rollHordeTier(zombie, level, waveIndex), false);
            zombie.setTarget(anchor);
            if (level.addFreshEntity(zombie)) {
                LIVING.add(zombie.getUUID());
                spawned++;
            }
        }
        return spawned;
    }

    /**
     * 这一波带几只精英。从 {@code elite_horde_from_wave} 起带，越靠后带得越多，但一封顶就不再涨——
     * 精英是领队，靠数量堆只会让几个技能特效糊在一起，玩家反而读不出「谁在施法」。
     */
    private static int eliteTargetFor(int waveIndex) {
        int cap = Config.ELITE_HORDE_MAX_PER_WAVE.get();
        int from = Math.max(0, Config.ELITE_HORDE_FROM_WAVE.get());
        if (cap <= 0 || waveIndex < from) {
            return 0;
        }
        return Mth.clamp(1 + (waveIndex - from) / 2, 1, cap);
    }

    /**
     * 精英领队：跟普通僵尸混在同一条环带上出场。
     *
     * <p>走 {@code finalizeSpawn} 是为了跟原版僵尸一致——骸骨射手的弓就是在这条路径上发的
     * （{@code populateDefaultEquipmentSlots}），而僵尸那套「随机装备 / 幼年体」的掷骰
     * 已经在 {@code AbstractEliteZombie} 里堵掉了，不会被随机数改掉手调的数值。</p>
     *
     * <p>它们必须进 {@link #LIVING}，否则场上精英没清掉、这一波却已经判定打完了。</p>
     */
    private static int spawnEliteEscort(ServerLevel level, List<ServerPlayer> players,
                                        RandomSource random, int target) {
        int spawned = 0;
        for (int i = 0; i < target; i++) {
            ServerPlayer anchor = players.get(i % players.size());
            BlockPos pos = findSpawn(level, anchor, random);
            if (pos == null) {
                continue;
            }
            Mob elite = createElite(level, random);
            if (elite == null) {
                continue;
            }
            elite.moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, random.nextFloat() * 360.0F, 0.0F);
            elite.finalizeSpawn(level, level.getCurrentDifficultyAt(pos), MobSpawnType.EVENT, null, null);
            elite.setPersistenceRequired();
            elite.setTarget(anchor);
            if (level.addFreshEntity(elite)) {
                LIVING.add(elite.getUUID());
                spawned++;
            }
        }
        return spawned;
    }

    /**
     * 召来尸潮之主 —— 整场尸潮的高潮。
     *
     * <p>它走和精英护卫一样的落点逻辑（{@link #findSpawn}），但只放在<b>一个</b>玩家身边：
     * 2500 血的 Boss 是拿来正面打的，不是撒胡椒面。落点随机挑一个玩家，
     * 会让它在夜空里的方向感变得不可预测 —— 玩家得听声音找它，而不是看血条追它。</p>
     */
    private static int spawnOverlord(ServerLevel level, List<ServerPlayer> players, RandomSource random) {
        ServerPlayer anchor = players.get(random.nextInt(players.size()));
        BlockPos pos = findSpawn(level, anchor, random);
        if (pos == null) {
            return 0;
        }
        HordeOverlord boss = ModEntities.OVERLORD.get().create(level);
        if (boss == null) {
            return 0;
        }
        boss.moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, random.nextFloat() * 360.0F, 0.0F);
        boss.finalizeSpawn(level, level.getCurrentDifficultyAt(pos), MobSpawnType.EVENT, null, null);
        boss.setPersistenceRequired();
        boss.setTarget(anchor);
        if (level.addFreshEntity(boss)) {
            LIVING.add(boss.getUUID());
            return 1;
        }
        return 0;
    }

    /** 六只等概率出场。不按波次分配种类，免得玩家摸清规律之后专挑某几种来针对。 */
    private static Mob createElite(ServerLevel level, RandomSource random) {
        EntityType<? extends Mob> type = switch (random.nextInt(6)) {
            case 0 -> ModEntities.SCREAMER.get();
            case 1 -> ModEntities.CRUSHER.get();
            case 2 -> ModEntities.CORRODER.get();
            case 3 -> ModEntities.MARKSMAN.get();
            case 4 -> ModEntities.SOLDIER.get();
            default -> ModEntities.BRIDE.get();
        };
        return type.create(level);
    }

    /**
     * Picks a standable surface spot in a ring around the player, robust across rugged biomes.
     */
    private static BlockPos findSpawn(ServerLevel level, ServerPlayer player, RandomSource random) {
        int min = Math.max(1, Config.HORDE_MIN_RADIUS.get());
        int max = Math.max(min, Config.HORDE_MAX_RADIUS.get());

        for (int attempt = 0; attempt < 48; attempt++) {
            double angle = random.nextDouble() * Math.PI * 2.0D;
            int distance = min + random.nextInt(max - min + 1);
            int x = player.getBlockX() + (int) Math.round(Math.cos(angle) * distance);
            int z = player.getBlockZ() + (int) Math.round(Math.sin(angle) * distance);

            if (!level.hasChunkAt(new BlockPos(x, player.getBlockY(), z))) {
                continue;
            }
            // First try heightmap
            BlockPos surface = level.getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, new BlockPos(x, 0, z));
            
            // If the surface heightmap is way too high/low (e.g. badlands cliffs or underground), scan relative to player Y
            if (Math.abs(surface.getY() - player.getBlockY()) > 15) {
                int startY = player.getBlockY() + 6;
                int endY = Math.max(level.getMinBuildHeight(), player.getBlockY() - 12);
                surface = null;
                for (int y = startY; y >= endY; y--) {
                    BlockPos p = new BlockPos(x, y, z);
                    if (level.getBlockState(p).isAir() && level.getBlockState(p.above()).isAir() && level.getBlockState(p.below()).isSolidRender(level, p.below())) {
                        surface = p;
                        break;
                    }
                }
            }

            if (surface == null) {
                continue;
            }
            if (!level.getFluidState(surface).isEmpty()) {
                continue;
            }
            if (!level.getBlockState(surface).isAir() || !level.getBlockState(surface.above()).isAir()) {
                continue;
            }
            if (level.getBlockState(surface.below()).isAir() || !level.getBlockState(surface.below()).getFluidState().isEmpty()) {
                continue;
            }
            return surface;
        }
        // Fallback: spawn slightly offset from player if everywhere around is impassable
        BlockPos playerPos = player.blockPosition();
        for (int dx = -3; dx <= 3; dx++) {
            for (int dz = -3; dz <= 3; dz++) {
                if (Math.abs(dx) < 2 && Math.abs(dz) < 2) continue;
                BlockPos p = playerPos.offset(dx * 4, 0, dz * 4);
                if (level.getBlockState(p).isAir() && level.getBlockState(p.above()).isAir()) {
                    return p;
                }
            }
        }
        return null;
    }

    /** Master switch so the manager can be disabled wholesale in tests. */
    private static final boolean HORDES_ALLOWED = true;

    /** Keeps a disconnecting player off the siege boss bar. */
    public static void onPlayerLeft(ServerLevel level, ServerPlayer player) {
        if (bossBar != null) {
            bossBar.removePlayer(player);
        }
    }
}
