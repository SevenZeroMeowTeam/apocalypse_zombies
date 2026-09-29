package com.apocalypse.zombies.moon;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.ClientMoonState;
import com.apocalypse.zombies.horde.HordeManager;
import com.apocalypse.zombies.network.MoonSyncPacket;
import com.apocalypse.zombies.network.NetworkHandler;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitlesAnimationPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.BonemealableBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.network.PacketDistributor;

/**
 * Drives the apocalypse clock: rolls a moon at dusk, holds it until dawn, applies whatever that
 * moon does to the world, and forwards everything to clients.
 *
 * <p>Timeline used throughout (vanilla day time): 13000 is the moment night properly falls and
 * 23000 is first light, so "until dawn" means 23000.</p>
 */
public final class MoonEventManager {

    /** Night begins; mobs start spawning and the moon roll happens here. */
    public static final long NIGHT_START = 13000L;
    /** First light; every lunar event expires. */
    public static final long DAWN = 23000L;

    /** How often (in ticks) moon-bound buffs are refreshed. */
    private static final int EFFECT_REFRESH_INTERVAL = 40;
    /** How often crops are force-grown; super moons are faster, see {@link #cropGrowthInterval}. */
    private static final int CROP_INTERVAL = 20;

    private MoonEventManager() {
    }

    // ------------------------------------------------------------------ queries

    /** The moon above the given level. Only the overworld has a sky worth talking about. */
    public static MoonEvent getMoonEvent(Level level) {
        if (!level.dimension().equals(Level.OVERWORLD)) {
            return MoonEvent.NONE;
        }
        if (level.isClientSide()) {
            return ClientMoonState.getMoonEvent();
        }
        return ApocalypseData.get((ServerLevel) level).getMoonEvent();
    }

    /** How far the zombie population has evolved; derived from the world's age in days. */
    public static int getEvolutionLevel(ServerLevel level) {
        return ApocalypseData.get(level).getEvolutionLevel();
    }

    public static int getEvolutionLevel(Level level) {
        return level instanceof ServerLevel server ? getEvolutionLevel(server) : ClientMoonState.getEvolutionLevel();
    }

    /** Days the world has been running, counting the first day as day zero. */
    public static long getWorldDay(Level level) {
        return level.getDayTime() / 24000L;
    }

    // ------------------------------------------------------------------ ticking

    /** Called once per level tick on the logical server. */
    public static void tick(ServerLevel level) {
        if (!level.dimension().equals(Level.OVERWORLD)) {
            return;
        }
        ApocalypseData data = ApocalypseData.get(level);

        long time = level.getDayTime();
        long day = time / 24000L;
        long timeOfDay = time % 24000L;
        boolean night = timeOfDay >= NIGHT_START && timeOfDay < DAWN;

        if (night) {
            if (data.getLastRolledDay() != day) {
                data.setLastRolledDay(day);
                raiseMoon(level, data, roll(level.getRandom()), true);
            }
        } else if (data.getMoonEvent().isActive()) {
            lowerMoon(level, data);
        }

        int expectedEvolution = Math.min(Config.MAX_EVOLUTION_LEVEL.get(),
                (int) (day / Math.max(1, Config.DAYS_PER_EVOLUTION_LEVEL.get())));
        if (expectedEvolution != data.getEvolutionLevel()) {
            data.setEvolutionLevel(expectedEvolution);
            sync(level, data);
        }

        MoonEvent active = data.getMoonEvent();
        if (active.isActive()) {
            switch (active.getEffect()) {
                case LUCK -> applyLuck(level, active);
                case CROP_GROWTH -> growCrops(level, active);
                default -> {
                }
            }
        }
    }

    /** Rolls the night's moon using the configured weights; whatever is left is an ordinary night. */
    public static MoonEvent roll(RandomSource random) {
        double roll = random.nextDouble();
        double cursor = 0.0D;
        cursor += Config.BLOOD_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.BLOOD_MOON;
        }
        cursor += Config.SUPER_BLOOD_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.SUPER_BLOOD_MOON;
        }
        cursor += Config.YELLOW_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.YELLOW_MOON;
        }
        cursor += Config.SUPER_YELLOW_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.SUPER_YELLOW_MOON;
        }
        cursor += Config.BLUE_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.BLUE_MOON;
        }
        cursor += Config.SUPER_BLUE_MOON_CHANCE.get();
        if (roll < cursor) {
            return MoonEvent.SUPER_BLUE_MOON;
        }
        return MoonEvent.NONE;
    }

    /** Forces a specific moon (commands, tests) without rolling. */
    public static void forceMoon(ServerLevel level, MoonEvent event) {
        ApocalypseData data = ApocalypseData.get(level);
        data.setLastRolledDay(getWorldDay(level));
        raiseMoon(level, data, event, false);
    }

    private static void raiseMoon(ServerLevel level, ApocalypseData data, MoonEvent event, boolean rolled) {
        data.setMoonEvent(event);
        sync(level, data);
        if (!event.isActive()) {
            return;
        }
        announce(level, event);
        maybeStartHorde(level, event);
    }

    private static void lowerMoon(ServerLevel level, ApocalypseData data) {
        MoonEvent previous = data.getMoonEvent();
        data.setMoonEvent(MoonEvent.NONE);
        sync(level, data);
        HordeManager.stop(level, false);
        if (previous.isActive()) {
            for (ServerPlayer player : level.players()) {
                player.sendSystemMessage(Component.translatable("moon.apocalypse_zombies.set",
                        previous.getDisplayName()));
            }
        }
    }

    // ------------------------------------------------------------------ world effects

    /** Blue moon blessing: Luck, refreshed so it lasts exactly as long as the moon does. */
    private static void applyLuck(ServerLevel level, MoonEvent moon) {
        if (level.getGameTime() % EFFECT_REFRESH_INTERVAL != 0) {
            return;
        }
        int amplifier = moon.getEffectAmplifier();
        for (ServerPlayer player : level.players()) {
            player.addEffect(new MobEffectInstance(MobEffects.LUCK,
                    EFFECT_REFRESH_INTERVAL * 3, amplifier, false, true, true));
        }
    }

    /**
     * Yellow moon blessing: crops in the area around every player are force-grown all night.
     * Super yellow moons reach further and fire more often.
     */
    private static void growCrops(ServerLevel level, MoonEvent moon) {
        int interval = moon.isSuperMoon() ? CROP_INTERVAL : CROP_INTERVAL * 2;
        if (level.getGameTime() % interval != 0) {
            return;
        }
        boolean big = moon.isSuperMoon();
        int radius = big ? 32 : 20;
        int attempts = big ? 60 : 28;

        RandomSource random = level.getRandom();
        for (ServerPlayer player : level.players()) {
            for (int i = 0; i < attempts; i++) {
                BlockPos pos = player.blockPosition().offset(
                        random.nextInt(radius * 2 + 1) - radius,
                        random.nextInt(13) - 6,
                        random.nextInt(radius * 2 + 1) - radius);
                if (!level.hasChunkAt(pos)) {
                    continue;
                }
                BlockState state = level.getBlockState(pos);
                if (state.getBlock() instanceof BonemealableBlock bonemealable
                        && bonemealable.isValidBonemealTarget(level, pos, state, false)
                        && bonemealable.isBonemealSuccess(level, random, pos, state)) {
                    bonemealable.performBonemeal(level, random, pos, state);
                }
            }
        }
    }

    // ------------------------------------------------------------------ hordes

    private static void maybeStartHorde(ServerLevel level, MoonEvent moon) {
        if (!Config.HORDES_ENABLED.get() || HordeManager.isActive()) {
            return;
        }
        boolean start;
        if (moon.isBloodMoon()) {
            start = Config.HORDE_ON_EVERY_BLOOD_MOON.get();
        } else {
            start = level.getRandom().nextDouble() < Config.HORDE_ON_OTHER_MOON_CHANCE.get();
        }
        if (start) {
            HordeManager.start(level, Config.HORDE_WAVES.get());
        }
    }

    // ------------------------------------------------------------------ networking

    /** Pushes the current state to every client. */
    public static void sync(ServerLevel level, ApocalypseData data) {
        NetworkHandler.CHANNEL.send(PacketDistributor.ALL.noArg(),
                new MoonSyncPacket(data.getMoonEvent(), data.getEvolutionLevel()));
    }

    public static void sync(ServerLevel level) {
        sync(level, ApocalypseData.get(level));
    }

    public static void syncTo(ServerPlayer player) {
        ApocalypseData data = ApocalypseData.get((ServerLevel) player.level());
        NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new MoonSyncPacket(data.getMoonEvent(), data.getEvolutionLevel()));
    }

    // ------------------------------------------------------------------ messaging

    private static void announce(ServerLevel level, MoonEvent moon) {
        SoundEvent sound = soundFor(moon);
        for (ServerPlayer player : level.players()) {
            player.connection.send(new ClientboundSetTitlesAnimationPacket(12, 60, 24));
            player.connection.send(new ClientboundSetTitleTextPacket(moon.getDisplayName()));
            player.connection.send(new ClientboundSetSubtitleTextPacket(
                    Component.translatable(subtitleKey(moon))));
            player.sendSystemMessage(moon.getRiseMessage());
            player.playNotifySound(sound, SoundSource.AMBIENT, 1.0F, 1.0F);
        }
    }

    private static String subtitleKey(MoonEvent moon) {
        return switch (moon) {
            case BLOOD_MOON, SUPER_BLOOD_MOON -> "moon.apocalypse_zombies.subtitle.blood";
            case YELLOW_MOON, SUPER_YELLOW_MOON -> "moon.apocalypse_zombies.subtitle.yellow";
            case BLUE_MOON, SUPER_BLUE_MOON -> "moon.apocalypse_zombies.subtitle.blue";
            default -> "moon.apocalypse_zombies.subtitle.none";
        };
    }

    private static SoundEvent soundFor(MoonEvent moon) {
        return switch (moon) {
            case BLOOD_MOON -> SoundEvents.ENDER_DRAGON_GROWL;
            case SUPER_BLOOD_MOON -> SoundEvents.WITHER_SPAWN;
            case YELLOW_MOON, SUPER_YELLOW_MOON -> SoundEvents.PLAYER_LEVELUP;
            case BLUE_MOON, SUPER_BLUE_MOON -> SoundEvents.AMETHYST_BLOCK_CHIME;
            default -> SoundEvents.AMBIENT_CAVE.value();
        };
    }
}
