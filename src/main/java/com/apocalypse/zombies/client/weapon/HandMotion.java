package com.apocalypse.zombies.client.weapon;

import net.minecraft.client.Minecraft;

/**
 * Small interpolation helpers for the first-person hands.
 *
 * <p>A hand target is a point of the weapon in model pixels (see {@link GunFrame}), and every animated hand
 * path in the game is really just a lerp between a handful of those points, timed to a clip's keyframes. These
 * few functions are shared so both guns time their hands the same way.
 */
public final class HandMotion {

    private HandMotion() {
    }

    /** 0 below {@code from}, 1 above {@code to}, linear in between. */
    public static float ramp(float v, float from, float to) {
        if (to <= from) return v >= to ? 1.0F : 0.0F;
        return Math.max(0.0F, Math.min(1.0F, (v - from) / (to - from)));
    }

    /** A rise over {@code [from, mid]} and a fall back over {@code [mid, to]} — 0 at both ends, 1 in the middle. */
    public static float bump(float v, float from, float mid, float to) {
        return v < mid ? ramp(v, from, mid) : 1.0F - ramp(v, mid, to);
    }

    /** {@code a} → {@code b}, written into {@code out}. */
    public static float[] lerp(float[] out, float[] a, float[] b, float t) {
        float k = Math.max(0.0F, Math.min(1.0F, t));
        out[0] = a[0] + (b[0] - a[0]) * k;
        out[1] = a[1] + (b[1] - a[1]) * k;
        out[2] = a[2] + (b[2] - a[2]) * k;
        return out;
    }

    /** {@code lerp(a, b, t)}, then shifted by {@code offset} — for a hand that rides a part as it travels. */
    public static float[] lerpThenShift(float[] out, float[] a, float[] b, float t, float dx, float dy, float dz) {
        lerp(out, a, b, t);
        out[0] += dx;
        out[1] += dy;
        out[2] += dz;
        return out;
    }

    /**
     * Moves {@code current} towards {@code target}, closing about two thirds of the gap per {@code tau} seconds.
     *
     * <p>Frame time comes from the client, so a hand travels the same distance in the same time whatever the
     * frame rate. It is used for a state that has to sit at exactly 1 for a while — the hand's grip on a bolt
     * handle — where {@link #ramp} would need a second timing to say "still holding", and the two would drift
     * apart the moment the art changed. Only the ends are eased; the middle is the bone's own answer.</p>
     */
    public static float ease(float current, float target, float tau) {
        float dt = Minecraft.getInstance().getDeltaFrameTime() * 0.05F;   // in seconds: 1 tick = 50 ms
        return current + (target - current) * Math.min(1.0F, dt / tau);
    }
}
