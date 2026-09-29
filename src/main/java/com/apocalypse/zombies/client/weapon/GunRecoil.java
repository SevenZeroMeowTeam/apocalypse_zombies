package com.apocalypse.zombies.client.weapon;

/**
 * The client's firing kick, as a single 0…1 impulse.
 *
 * <p>The server owns what a shot does to the world; this is purely what the shot does to the picture — the
 * rifle jumping against the shoulder. It has to live on the client because it must start on the frame the
 * trigger is pulled and decay every frame, neither of which a packet round-trip can do.
 *
 * <p>One value serves every gun because only one is ever in hand. The angle it drives is per-gun
 * ({@code GunItem.firePitch()}), because a .30-06 Garand and a .338 bolt gun do not kick the same.
 *
 * <p>Decay is {@code ×0.55} per tick: an impulse of 0.42 (shouldered) therefore falls under 5% in four ticks
 * — a short snap of the muzzle rather than a wobble.
 */
public final class GunRecoil {

    /** Impulse for a shot taken shouldered (sight up). Tuned against the aim picture. */
    public static final float SHOULDERED = 0.42F;

    /** Impulse for a shot taken from the hip — the weapon is not braced, so it moves more. */
    public static final float HIP = 0.60F;

    /** Below this the impulse is dropped to zero rather than left as an invisible offset. */
    private static final float EPSILON = 0.01F;

    /** Per-tick decay. */
    private static final float DECAY = 0.55F;

    private static float value;

    private GunRecoil() {
    }

    /** A shot went off; {@code shouldered} picks which impulse to add. Impulses stack, up to 1. */
    public static void impulse(boolean shouldered) {
        float add = shouldered ? SHOULDERED : HIP;
        value = Math.min(1.0F, value + add);
    }

    /** Current kick, 0…1. */
    public static float value() {
        return value;
    }

    /** Called once per client tick — always, so a stale kick never survives the weapon being put away. */
    public static void tick() {
        value *= DECAY;
        if (value < EPSILON) value = 0.0F;
    }

    /** Forget any kick in flight (gun put away, player died, world left). */
    public static void reset() {
        value = 0.0F;
    }
}
