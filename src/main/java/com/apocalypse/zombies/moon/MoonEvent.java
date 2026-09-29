package com.apocalypse.zombies.moon;

import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;

/**
 * The seven states the night sky can be in.
 *
 * <p>Every moon owns its own look (the colour the moon sprite is tinted with, how much bigger the
 * sprite is drawn, the colour wash painted across the sky and the fog tint) plus the rules it
 * imposes on the world for as long as it is up.</p>
 */
public enum MoonEvent {

    /** Ordinary night: vanilla sky, no rules attached. */
    NONE("none", false,
            0xFFFFFF, 1.0F,
            0x000000, 0.0F,
            0x000000,
            false, MoonEffect.NONE, 0),

    /** Blood moon: crimson moon, blood-washed sky, beds refuse to work. */
    BLOOD_MOON("blood_moon", false,
            0xFF3A24, 1.0F,
            0x8C0F08, 0.42F,
            0x52100B,
            true, MoonEffect.NONE, 0),

    /** Super blood moon: larger, deeper red, same sleeping ban. */
    SUPER_BLOOD_MOON("super_blood_moon", true,
            0xFF1E0E, 1.65F,
            0x9E1206, 0.55F,
            0x5E0A05,
            true, MoonEffect.NONE, 0),

    /** Yellow moon: bright yellow moon, crops accelerate until dawn. */
    YELLOW_MOON("yellow_moon", false,
            0xFFEE6B, 1.0F,
            0x9C8213, 0.30F,
            0x6B5A12,
            false, MoonEffect.CROP_GROWTH, 0),

    /** Super yellow moon: bigger and brighter, crops accelerate hard. */
    SUPER_YELLOW_MOON("super_yellow_moon", true,
            0xFFE23A, 1.65F,
            0xB39312, 0.42F,
            0x7C6610,
            false, MoonEffect.CROP_GROWTH, 1),

    /** Blue moon: pale blue moon, Luck until dawn. */
    BLUE_MOON("blue_moon", false,
            0xCDE8FF, 1.0F,
            0x2E5D8C, 0.30F,
            0x24486B,
            false, MoonEffect.LUCK, 1),

    /** Super blue moon: bigger pale blue moon, stronger Luck until dawn. */
    SUPER_BLUE_MOON("super_blue_moon", true,
            0xB6DDFF, 1.65F,
            0x2B6AA8, 0.42F,
            0x1F4C7C,
            false, MoonEffect.LUCK, 2);

    /** What a moon does to the world while it hangs overhead. */
    public enum MoonEffect {
        NONE,
        /** Luck (amplifier per moon) refreshed on every player until dawn. */
        LUCK,
        /** Crops are force-grown all night long. */
        CROP_GROWTH
    }

    private final String id;
    private final boolean superMoon;
    private final int moonTint;
    private final float moonScale;
    private final int skyColor;
    private final float skyAlpha;
    private final int fogColor;
    private final boolean blocksSleep;
    private final MoonEffect effect;
    private final int effectAmplifier;

    MoonEvent(String id, boolean superMoon, int moonTint, float moonScale,
              int skyColor, float skyAlpha, int fogColor,
              boolean blocksSleep, MoonEffect effect, int effectAmplifier) {
        this.id = id;
        this.superMoon = superMoon;
        this.moonTint = moonTint;
        this.moonScale = moonScale;
        this.skyColor = skyColor;
        this.skyAlpha = skyAlpha;
        this.fogColor = fogColor;
        this.blocksSleep = blocksSleep;
        this.effect = effect;
        this.effectAmplifier = effectAmplifier;
    }

    /** Stable identifier used by commands and the network protocol. */
    public String getId() {
        return this.id;
    }

    /** Super moons are drawn noticeably larger than their ordinary counterparts. */
    public boolean isSuperMoon() {
        return this.superMoon;
    }

    /** True for both blood moon variants. */
    public boolean isBloodMoon() {
        return this == BLOOD_MOON || this == SUPER_BLOOD_MOON;
    }

    /** RGB multiplier applied to the vanilla moon sprite. */
    public int getMoonTint() {
        return this.moonTint;
    }

    public float getMoonScale() {
        return this.moonScale;
    }

    /** RGB of the colour wash painted over the sky. */
    public int getSkyColor() {
        return this.skyColor;
    }

    public float getSkyAlpha() {
        return this.skyAlpha;
    }

    public int getFogColor() {
        return this.fogColor;
    }

    public boolean blocksSleep() {
        return this.blocksSleep;
    }

    public MoonEffect getEffect() {
        return this.effect;
    }

    public int getEffectAmplifier() {
        return this.effectAmplifier;
    }

    public float moonTintRed() {
        return ((this.moonTint >> 16) & 0xFF) / 255.0F;
    }

    public float moonTintGreen() {
        return ((this.moonTint >> 8) & 0xFF) / 255.0F;
    }

    public float moonTintBlue() {
        return (this.moonTint & 0xFF) / 255.0F;
    }

    public float skyRed() {
        return ((this.skyColor >> 16) & 0xFF) / 255.0F;
    }

    public float skyGreen() {
        return ((this.skyColor >> 8) & 0xFF) / 255.0F;
    }

    public float skyBlue() {
        return (this.skyColor & 0xFF) / 255.0F;
    }

    public float fogRed() {
        return ((this.fogColor >> 16) & 0xFF) / 255.0F;
    }

    public float fogGreen() {
        return ((this.fogColor >> 8) & 0xFF) / 255.0F;
    }

    public float fogBlue() {
        return (this.fogColor & 0xFF) / 255.0F;
    }

    /** Translation key for the moon's display name. */
    public String getTranslationKey() {
        return "moon.apocalypse_zombies." + this.id;
    }

    public MutableComponent getDisplayName() {
        return Component.translatable(this.getTranslationKey());
    }

    /** Short chat banner used when the moon rises or sets. */
    public Component getRiseMessage() {
        return Component.translatable("moon.apocalypse_zombies.rise", this.getDisplayName());
    }

    /** True for moons that do anything at all. */
    public boolean isActive() {
        return this != NONE;
    }

    public static MoonEvent byId(String id) {
        for (MoonEvent event : values()) {
            if (event.id.equalsIgnoreCase(id)) {
                return event;
            }
        }
        return NONE;
    }
}
