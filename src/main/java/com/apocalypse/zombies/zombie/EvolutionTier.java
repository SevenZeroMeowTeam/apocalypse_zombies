package com.apocalypse.zombies.zombie;

import net.minecraft.ChatFormatting;
import net.minecraft.world.effect.MobEffect;
import net.minecraft.world.effect.MobEffects;

import java.util.List;

/**
 * The six rungs a zombie climbs over the course of an apocalypse.
 *
 * <p>Tier 0 is a plain vanilla zombie. Every rung above it stacks flat attribute bonuses on top of
 * the previous one, widens the follow range and eventually grants permanent potion effects, so a
 * tier 5 warlord is a genuinely dangerous mob rather than a re-skinned zombie.</p>
 */
public enum EvolutionTier {

    COMMON(0, "common", ChatFormatting.GRAY,
            0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D,
            1.00F, false, List.of()),

    REINFORCED(1, "reinforced", ChatFormatting.YELLOW,
            6.0D, 1.0D, 0.05D, 1.0D, 0.0D, 0.0D, 2.0D,
            1.06F, false, List.of()),

    ELITE(2, "elite", ChatFormatting.GOLD,
            16.0D, 3.0D, 0.10D, 3.0D, 1.0D, 0.10D, 5.0D,
            1.13F, false, List.of()),

    MUTANT(3, "mutant", ChatFormatting.RED,
            30.0D, 5.0D, 0.16D, 6.0D, 2.0D, 0.25D, 8.0D,
            1.22F, true, List.of(
                    new EffectSpec(MobEffects.MOVEMENT_SPEED, 0),
                    new EffectSpec(MobEffects.FIRE_RESISTANCE, 0))),

    TYRANT(4, "tyrant", ChatFormatting.DARK_RED,
            50.0D, 8.0D, 0.22D, 10.0D, 4.0D, 0.40D, 12.0D,
            1.34F, true, List.of(
                    new EffectSpec(MobEffects.MOVEMENT_SPEED, 0),
                    new EffectSpec(MobEffects.FIRE_RESISTANCE, 0),
                    new EffectSpec(MobEffects.DAMAGE_BOOST, 0),
                    new EffectSpec(MobEffects.REGENERATION, 0))),

    WARLORD(5, "warlord", ChatFormatting.DARK_PURPLE,
            80.0D, 12.0D, 0.28D, 15.0D, 6.0D, 0.55D, 18.0D,
            1.50F, true, List.of(
                    new EffectSpec(MobEffects.MOVEMENT_SPEED, 1),
                    new EffectSpec(MobEffects.FIRE_RESISTANCE, 0),
                    new EffectSpec(MobEffects.DAMAGE_BOOST, 1),
                    new EffectSpec(MobEffects.REGENERATION, 1),
                    new EffectSpec(MobEffects.DAMAGE_RESISTANCE, 0)));

    /** A permanent potion effect granted for as long as the zombie holds the tier. */
    public record EffectSpec(MobEffect effect, int amplifier) {
    }

    /** Highest tier index that exists. */
    public static final int MAX_TIER = WARLORD.index;

    private final int index;
    private final String id;
    private final ChatFormatting color;
    private final double bonusHealth;
    private final double bonusDamage;
    private final double bonusSpeedRatio;
    private final double bonusArmor;
    private final double bonusArmorToughness;
    private final double bonusKnockbackResistance;
    private final double bonusFollowRange;
    private final float renderScale;
    private final boolean showNamePlate;
    private final List<EffectSpec> effects;

    EvolutionTier(int index, String id, ChatFormatting color,
                  double bonusHealth, double bonusDamage, double bonusSpeedRatio,
                  double bonusArmor, double bonusArmorToughness, double bonusKnockbackResistance,
                  double bonusFollowRange, float renderScale, boolean showNamePlate,
                  List<EffectSpec> effects) {
        this.index = index;
        this.id = id;
        this.color = color;
        this.bonusHealth = bonusHealth;
        this.bonusDamage = bonusDamage;
        this.bonusSpeedRatio = bonusSpeedRatio;
        this.bonusArmor = bonusArmor;
        this.bonusArmorToughness = bonusArmorToughness;
        this.bonusKnockbackResistance = bonusKnockbackResistance;
        this.bonusFollowRange = bonusFollowRange;
        this.renderScale = renderScale;
        this.showNamePlate = showNamePlate;
        this.effects = effects;
    }

    public int getIndex() {
        return this.index;
    }

    public String getId() {
        return this.id;
    }

    public ChatFormatting getColor() {
        return this.color;
    }

    public double getBonusHealth() {
        return this.bonusHealth;
    }

    public double getBonusDamage() {
        return this.bonusDamage;
    }

    public double getBonusSpeedRatio() {
        return this.bonusSpeedRatio;
    }

    public double getBonusArmor() {
        return this.bonusArmor;
    }

    public double getBonusArmorToughness() {
        return this.bonusArmorToughness;
    }

    public double getBonusKnockbackResistance() {
        return this.bonusKnockbackResistance;
    }

    public double getBonusFollowRange() {
        return this.bonusFollowRange;
    }

    /** Client-side render scale applied to the zombie model. */
    public float getRenderScale() {
        return this.renderScale;
    }

    /** Whether the tier name is always shown above the zombie. */
    public boolean showsNamePlate() {
        return this.showNamePlate;
    }

    public List<EffectSpec> getEffects() {
        return this.effects;
    }

    public String getTranslationKey() {
        return "tier.apocalypse_zombies." + this.id;
    }

    public net.minecraft.network.chat.MutableComponent getDisplayName() {
        return net.minecraft.network.chat.Component.translatable(this.getTranslationKey());
    }

    public static EvolutionTier byIndex(int index) {
        EvolutionTier[] values = values();
        if (index < 0) {
            return COMMON;
        }
        return index >= values.length ? WARLORD : values[index];
    }
}
