package com.apocalypse.zombies.zombie;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.ZombieTierPacket;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attribute;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraftforge.network.PacketDistributor;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

/**
 * Everything that makes a zombie climb the {@link EvolutionTier} ladder.
 *
 * <p>State lives in the entity's persistent data so it survives chunk unloads and world reloads with
 * no capability plumbing. The global evolution level (how far the world has progressed) lives in the
 * moon manager's saved data, so a zombie can never outrun the stage the world is at — but individual
 * zombies roll their own dice every few seconds, which is why a horde is never uniform.</p>
 */
public final class ZombieEvolution {

    /** Persistent-data key holding the zombie's tier index. */
    public static final String TIER_KEY = "az_evolution_tier";
    private static final String MULTIPLIER_KEY = "az_evolution_multiplier";
    private static final String MODIFIER_PREFIX = ApocalypseZombies.MOD_ID + ":tier_";

    private ZombieEvolution() {
    }

    // ------------------------------------------------------------------ state

    public static int getTierIndex(net.minecraft.world.entity.Entity entity) {
        CompoundTag data = entity.getPersistentData();
        return data.contains(TIER_KEY) ? data.getInt(TIER_KEY) : 0;
    }

    public static EvolutionTier getTier(net.minecraft.world.entity.Entity entity) {
        return EvolutionTier.byIndex(getTierIndex(entity));
    }

    /** True when the entity carries an apocalypse tier above the plain one. */
    public static boolean isEvolved(net.minecraft.world.entity.Entity entity) {
        return getTierIndex(entity) > 0;
    }

    // ------------------------------------------------------------------ spawning

    /**
     * Called for every zombie that finalises its spawn. Newly spawned zombies have a chance to
     * arrive already matching the current world stage, and hordes can force a minimum tier.
     */
    public static void onSpawn(Zombie zombie, ServerLevel level, int forcedMinimumTier) {
        int globalLevel = MoonEventManager.getEvolutionLevel(level);
        int roll = 0;
        if (zombie.getRandom().nextDouble() < Config.SPAWN_WITH_TIER_CHANCE.get()) {
            roll = globalLevel;
        } else if (globalLevel > 0) {
            // A fraction of the population lags one step behind the world stage.
            roll = Math.max(0, globalLevel - 1);
        }
        int tier = Math.max(roll, forcedMinimumTier);
        setTier(zombie, Math.min(tier, EvolutionTier.MAX_TIER), false);
    }

    /** Spawns a zombie that is guaranteed to be at least {@code minTier}, for horde waves. */
    public static int rollHordeTier(Zombie zombie, ServerLevel level, int waveIndex) {
        int globalLevel = MoonEventManager.getEvolutionLevel(level);
        int guaranteed = Math.min(EvolutionTier.MAX_TIER, Math.max(0, waveIndex - 1));
        int ceiling = Math.min(EvolutionTier.MAX_TIER, globalLevel + 1);
        int lo = Math.min(guaranteed, ceiling);
        int span = Math.max(0, ceiling - lo);
        return lo + (span == 0 ? 0 : zombie.getRandom().nextInt(span + 1));
    }

    // ------------------------------------------------------------------ ticking

    /** Executed once per zombie per server tick; the roll itself is rate-limited internally. */
    public static void tick(Zombie zombie) {
        if (zombie.level().isClientSide()) {
            return;
        }
        int interval = Math.max(20, Config.EVOLUTION_CHECK_INTERVAL.get());
        if (zombie.tickCount % interval != 0) {
            return;
        }
        if (!(zombie.level() instanceof ServerLevel level)) {
            return;
        }

        int tier = getTierIndex(zombie);
        int globalLevel = MoonEventManager.getEvolutionLevel(level);
        if (tier >= EvolutionTier.MAX_TIER || tier >= globalLevel) {
            return;
        }

        double chance = Config.EVOLUTION_CHANCE.get();
        MoonEvent moon = MoonEventManager.getMoonEvent(level);
        if (moon.isBloodMoon()) {
            chance *= Config.BLOOD_MOON_EVOLUTION_MULTIPLIER.get();
        }
        if (zombie.getRandom().nextDouble() < chance) {
            evolve(zombie, level);
        }
    }

    /** Pushes a zombie one tier up the ladder with the full transformation fanfare. */
    public static void evolve(Zombie zombie, ServerLevel level) {
        int next = Math.min(EvolutionTier.MAX_TIER, getTierIndex(zombie) + 1);
        setTier(zombie, next, true);
    }

    // ------------------------------------------------------------------ applying

    /**
     * Writes a tier onto a zombie: attribute modifiers, permanent effects, name plate and health.
     *
     * @param announce whether the zombie should roar on the way up (player-visible evolution)
     */
    public static void setTier(Zombie zombie, int tierIndex, boolean announce) {
        EvolutionTier tier = EvolutionTier.byIndex(tierIndex);
        zombie.getPersistentData().putInt(TIER_KEY, tier.getIndex());

        setModifier(zombie, Attributes.MAX_HEALTH, "health",
                tier.getBonusHealth(), AttributeModifier.Operation.ADDITION);
        setModifier(zombie, Attributes.ATTACK_DAMAGE, "damage",
                tier.getBonusDamage(), AttributeModifier.Operation.ADDITION);
        setModifier(zombie, Attributes.MOVEMENT_SPEED, "speed",
                tier.getBonusSpeedRatio(), AttributeModifier.Operation.MULTIPLY_BASE);
        setModifier(zombie, Attributes.ARMOR, "armor",
                tier.getBonusArmor(), AttributeModifier.Operation.ADDITION);
        setModifier(zombie, Attributes.ARMOR_TOUGHNESS, "armor_toughness",
                tier.getBonusArmorToughness(), AttributeModifier.Operation.ADDITION);
        setModifier(zombie, Attributes.KNOCKBACK_RESISTANCE, "knockback",
                tier.getBonusKnockbackResistance(), AttributeModifier.Operation.ADDITION);
        setModifier(zombie, Attributes.FOLLOW_RANGE, "follow_range",
                tier.getBonusFollowRange(), AttributeModifier.Operation.ADDITION);

        // Permanent potion effects: duration -1 is vanilla's "infinite".
        for (EvolutionTier.EffectSpec spec : tier.getEffects()) {
            zombie.addEffect(new MobEffectInstance(spec.effect(), -1, spec.amplifier(), false, false, false));
        }

        if (tier.getIndex() > 0) {
            zombie.setCustomName(Component.translatable(tier.getTranslationKey())
                    .withStyle(tier.getColor()));
            zombie.setCustomNameVisible(tier.showsNamePlate());
            // Evolved zombies do not despawn at dawn; they are a persistent problem.
            zombie.setPersistenceRequired();
        }

        zombie.setHealth(zombie.getMaxHealth());
        zombie.getPersistentData().putFloat(MULTIPLIER_KEY, tier.getRenderScale());
        if (announce) {
            zombie.level().playSound(null, zombie.blockPosition(), SoundEvents.ZOMBIE_AMBIENT,
                    SoundSource.HOSTILE, 1.0F, 0.5F);
        }
        if (zombie.level() instanceof ServerLevel serverLevel) {
            // Persistent data never reaches clients, so tier changes ride their own packet.
            NetworkHandler.CHANNEL.send(PacketDistributor.TRACKING_ENTITY.with(() -> zombie),
                    new ZombieTierPacket(zombie.getId(), tier.getIndex()));
            if (announce) {
                serverLevel.sendParticles(ParticleTypes.SOUL_FIRE_FLAME,
                        zombie.getX(), zombie.getY() + zombie.getBbHeight(), zombie.getZ(),
                        12, zombie.getBbWidth(), 0.2D, zombie.getBbWidth(), 0.01D);
            }
        }
    }

    /**
     * Re-applies the stored tier. Used after a world reload where persistent data survived but the
     * attribute modifiers were rebuilt from scratch by the entity constructor.
     */
    public static void refresh(Zombie zombie) {
        int tier = getTierIndex(zombie);
        if (tier > 0) {
            setTier(zombie, tier, false);
        }
    }

    private static void setModifier(Mob mob, Attribute attribute, String key,
                                    double amount, AttributeModifier.Operation operation) {
        AttributeInstance instance = mob.getAttribute(attribute);
        if (instance == null) {
            return;
        }
        UUID id = modifierId(key);
        AttributeModifier existing = instance.getModifier(id);
        if (existing != null) {
            if (existing.getAmount() == amount) {
                return;
            }
            instance.removeModifier(id);
        }
        if (amount != 0.0D) {
            instance.addPermanentModifier(
                    new AttributeModifier(id, MODIFIER_PREFIX + key, amount, operation));
        }
    }

    /** Deterministic modifier UUID per tier slot so repeated applications replace rather than stack. */
    private static UUID modifierId(String key) {
        return UUID.nameUUIDFromBytes((MODIFIER_PREFIX + key).getBytes(StandardCharsets.UTF_8));
    }
}
