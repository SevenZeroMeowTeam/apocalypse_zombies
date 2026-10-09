package com.apocalypse.zombies.client;

import com.apocalypse.zombies.item.GunItem;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.util.Mth;

/**
 * Client-only view of how the gun is being held: aiming or running, and how far into either we are.
 *
 * <p>Aiming is a purely local affair — the zoom, the raised pose and the scope overlay are all things only
 * this player can see, so nothing here is sent to the server (and the server never asks). The value is
 * advanced one tick at a time and interpolated in {@link ClientEvents} for rendering, which is what gives
 * the raise its ramp instead of a snap.</p>
 *
 * <p>The running carry lives here for the same reason, and on the same clock: which of the two poses the gun
 * is in is a fact about this client's legs, and the blend has to be ramped rather than snapped or the gun
 * would jump from one pose to the other. Aiming outranks running — you cannot hold a sight up and run at
 * once — so only one of the two is ever advancing at a time.</p>
 *
 * <p>This used to be {@code AWMClientState} and knew one gun's field of view and one gun's aim time. It now
 * holds a {@link GunItem} and asks it: how far does your sight zoom, how long do you take to come up, do you
 * draw an overlay. The gun reference is <em>sticky</em> — kept through the release so the zoom can ease back
 * out along the same curve it came in on, even on the tick the player has already swapped items.</p>
 */
public final class GunAimState {

    /** Used only in the window before any gun has ever been held. */
    private static final float FALLBACK_AIM_TIME = 0.25F;
    /** How long the gun takes to settle into — and back out of — the running carry, in seconds. */
    private static final float SPRINT_TIME = 0.18F;

    private static GunItem gun;
    private static boolean aiming;
    private static float aimProgress;
    private static boolean sprinting;
    private static float sprintProgress;

    /** 诊断节流（DIAG_AIM 打开时每 2 秒一行）。定位完可以连上面的日志一起删。 */
    private static long lastDiag;

    private GunAimState() {
    }

    /** True while the player holds the sight up — drives the zoom, the pose and the overlay. */
    public static boolean isAiming() {
        return aiming;
    }

    /** 0 = gun down, 1 = fully on the sight. Lerped, so it is safe to use directly in a transform. */
    public static float getAimProgress() {
        return aimProgress;
    }

    /** Interpolated progress for the current frame, for use while rendering. */
    public static float getAimProgress(float partialTick) {
        float step = partialTick / (aimTime() * 20.0F);
        return Mth.clamp(aiming ? aimProgress + step : aimProgress - step, 0.0F, 1.0F);
    }

    /** True while the player is running with the gun at the hip — drives the running carry pose. */
    public static boolean isSprinting() {
        return sprinting;
    }

    /** 0 = standing carry, 1 = full running carry. Lerped, so it is safe to use directly in a transform. */
    public static float getSprintProgress() {
        return sprintProgress;
    }

    /** Interpolated progress for the current frame, for use while rendering. */
    public static float getSprintProgress(float partialTick) {
        float step = partialTick / (SPRINT_TIME * 20.0F);
        return Mth.clamp(sprinting ? sprintProgress + step : sprintProgress - step, 0.0F, 1.0F);
    }

    /** Field of view the held gun zooms to, or 0 when no gun is involved. */
    public static double aimedFov() {
        return gun != null ? gun.aimedFov() : 0.0D;
    }

    /**
     * True while the sight in use is an optic. Iron-sighted guns answer false, which is what keeps vanilla's
     * crosshair on screen — with no scope overlay, the crosshair is the only aim point the player has.
     */
    public static boolean hasScopeOverlay() {
        return gun != null && gun.hasScopeOverlay();
    }

    /**
     * Which of the two overlays the held gun's sight is drawn as — the blacked-out circle of a telescope or the
     * clear lens of a sight looked past. Mirrors {@link GunItem#sightStyle()}; read only while
     * {@link #hasScopeOverlay()} is true.
     */
    public static GunItem.SightStyle sightStyle() {
        return gun != null ? gun.sightStyle() : GunItem.SightStyle.TELESCOPE;
    }

    private static float aimTime() {
        return gun != null ? gun.aimTime() : FALLBACK_AIM_TIME;
    }

    /**
     * Advances the aim state from live input. Called once per client tick, before anything renders.
     *
     * <p>Right-click is read straight off the key binding rather than through the item's {@code use} hook:
     * holding the button has to keep aiming, and a one-shot interaction callback cannot express that.</p>
     */
    public static void tick(Minecraft minecraft) {
        LocalPlayer player = minecraft.player;
        GunItem held = player != null && player.getMainHandItem().getItem() instanceof GunItem g ? g : null;
        if (held != null) {
            gun = held;
        }
        // 轮盘开着时不瞄：那会儿鼠标在选弹，枪还跟着右键抬起来只会挡住选项
        boolean holding = held != null && minecraft.screen == null
                && !com.apocalypse.zombies.client.weapon.AmmoWheel.isOpen();

        aiming = holding && minecraft.options.keyUse.isDown();

        /* 诊断（DIAG_AIM 打开时，每 2 秒一行）：aiming 有三个前置条件，任一个为假就永远不瞄准。
         * 只打"aim=0"看不出卡在哪一环，这里把三环逐个打出来。 */
        if (com.apocalypse.zombies.client.ClientEvents.DIAG_AIM) {
            long now = System.currentTimeMillis();
            if (now - lastDiag > 2000L) {
                lastDiag = now;
                com.apocalypse.zombies.ApocalypseZombies.LOGGER.info(
                        "[瞄准调试·输入] held={} screen={} wheelOpen={} keyUseDown={} → aiming={} progress={}",
                        held != null ? held : "无",
                        minecraft.screen == null ? "null(无界面)" : minecraft.screen.getClass().getSimpleName(),
                        com.apocalypse.zombies.client.weapon.AmmoWheel.isOpen(),
                        minecraft.options.keyUse.isDown(), aiming,
                        String.format("%.2f", aimProgress));
            }
        }

        float step = 1.0F / (aimTime() * 20.0F);
        aimProgress = Mth.clamp(aiming ? aimProgress + step : aimProgress - step, 0.0F, 1.0F);

        // Running the gun: only with one actually in hand, only at the hip, and only while the legs say so.
        // Read off the player rather than a key binding, so it also covers a sprint the server started (knock
        // back, a horse, a modded dash) — anything that sets the sprint flag carries the gun the same way.
        sprinting = holding && !aiming && player.isSprinting();
        float sprintStep = 1.0F / (SPRINT_TIME * 20.0F);
        sprintProgress = Mth.clamp(sprinting ? sprintProgress + sprintStep : sprintProgress - sprintStep,
                0.0F, 1.0F);
    }

    /** Wipes the state when the world goes away. */
    public static void reset() {
        gun = null;
        aiming = false;
        aimProgress = 0.0F;
        sprinting = false;
        sprintProgress = 0.0F;
    }
}
