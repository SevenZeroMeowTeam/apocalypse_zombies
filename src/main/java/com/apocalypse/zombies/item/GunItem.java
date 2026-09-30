package com.apocalypse.zombies.item;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;

/**
 * Everything the rest of the mod needs from a gun, whatever gun it is.
 *
 * <p>The weapon layer started with one gun and the plumbing grew around it: the packets checked
 * {@code instanceof AWMItem}, the HUD read {@code AWMItem.getAmmo}, the zoom was {@code AWMClientState}'s
 * own constant. Adding a second gun by copying that code would have meant two action machines drifting
 * apart, so the shared surface is named here instead and the plumbing only ever looks at this.</p>
 *
 * <p>Two kinds of thing live on it. <b>What the gun is</b> — magazine size, how far the sight zooms, how
 * the weapon sits when raised — is read on the client, every frame. <b>What the gun does</b> —
 * {@link #tryFire} and {@link #beginReload} — is only ever called on the server, from a packet, and is the
 * whole of a gun's authority: the client asks, the stack's own NBT answers.</p>
 */
public interface GunItem {

    /** Rounds in a full magazine. */
    int magazineSize();

    /** Field of view while the sight is up. Vanilla default is 70, so anything smaller zooms in. */
    double aimedFov();

    /** Seconds for the sight to come up, ramped by the same progress that drives the zoom. */
    float aimTime();

    /**
     * True when the sight is an optic rather than iron sights: the scope overlay is drawn and vanilla's
     * crosshair is hidden. False for a gun whose sights <em>are</em> the aim point, where the crosshair is
     * the only thing telling the player where the barrel is pointed.
     *
     * <p>Which overlay is drawn is {@link #sightStyle()}'s question — this one only says there is one.
     */
    boolean hasScopeOverlay();

    /**
     * Which of the two overlays {@link #hasScopeOverlay()} is drawn as.
     *
     * <p>The overlay used to be one thing, a telescope's blacked-out circle, because there was one optic. There
     * are two shapes of sight now: one the player looks <em>through</em>, whose lens is the whole frame, and one
     * the player looks <em>past</em> — a clear lens with a cross on it, the world still visible through it. Both
     * want vanilla's crosshair out of the way, and that is what {@link #hasScopeOverlay()} answers; this says
     * which of the two to draw, because only the overlay renderer can tell the difference.
     *
     * <p>Read only when {@link #hasScopeOverlay()} is true. Defaults to {@link SightStyle#TELESCOPE}, so a gun
     * that simply has an optic does not have to say anything here.
     */
    default SightStyle sightStyle() {
        return SightStyle.TELESCOPE;
    }

    /**
     * True when the sight's lens <em>is</em> the view, so the first-person model has to get out of it: while
     * the sight is up the gun and the arms are not drawn at all, and the scope overlay is the only thing on
     * screen.
     *
     * <p>Separate from {@link #hasScopeOverlay()} on purpose — that one asks whether the <em>reticle</em> is
     * the gun's own, this one asks whether the <em>frame</em> is. A sight the player looks <em>through</em> (a
     * red dot's tube, an aperture) still wants the gun and the hands in frame, so it draws its own reticle and
     * then answers false here.</p>
     *
     * <p>An AWM's scope is the other case: the gun is raised until the optical axis sits on the eye and the
     * lens fills the screen — so anything still drawn in front of the camera is exactly what the player would
     * be looking through. {@code ClientEvents.onRenderHand} owns the timing of the handoff.</p>
     */
    boolean hidesModelWhileAimed();

    /**
     * Where the weapon moves to when the sight comes up, in camera space (blocks, right/up/forward with
     * forward being −Z). Together with {@link #aimTime} this is what puts the sight line on the centre of the
     * screen, so it is a number that has to be measured off the model rather than guessed: it is the negation
     * of where the sight sits in the hip pose.
     *
     * <p>It used to be a nudge applied inside the item model's transform space ({@code aimRaise}/{@code
     * aimDrift}). Those two are the same displacement expressed there, and the conversion is 1:1 — the item
     * display block and the model are both in 1/16 block units — so this is the same motion, moved to where
     * the hip stance lives so both can ramp together on one curve.
     */
    float adsX();

    /** See {@link #adsX()}. */
    float adsY();

    /** See {@link #adsX()}. */
    float adsZ();

    /**
     * The item model's <b>first-person display rotation</b>, pitch in degrees — index 0 of
     * {@code display.firstperson_righthand.rotation} in {@code models/item/<id>.json}. {@link #adsYaw()} is
     * index 1. Roll (index 2) must be 0.
     *
     * <p>Why the stance layer has to know these: that rotation is applied <em>inside</em> the stance — the
     * chain is {@code stance · display · geometry} — so blending the hip angles to zero at full aim removes
     * this layer's tilt but leaves the display's. Two degrees of pitch and four of yaw is 4.47° of
     * parallel-but-off-axis error over the ~0.7-block sight radius, and it grows with distance to the target,
     * so <b>no</b> change to {@link #adsX()}/{@link #adsY()} can ever remove it — only a counter-rotation.
     * {@code client/weapon/GunPose} applies the exact conjugate of this rotation, ramped with aim and
     * innermost; only with that in place is the sight line truly parallel to the view axis, and only then are
     * the two offsets above a pure screen-space shift. The item's display block keeps these angles, so the
     * hip pose is unchanged.
     *
     * <p>Values mirror the JSON, and {@code tools/check_gun_resources.py} fails if the two drift apart;
     * {@code tools/pose_measure.py} re-derives them from the geometry.
     */
    float adsPitch();

    /** See {@link #adsPitch()}. */
    float adsYaw();

    /**
     * How much bigger the weapon is drawn in the <b>first person only</b>. Third person, the GUI, the ground
     * and the item frame keep whatever size {@code models/item/<id>.json} gives them.
     *
     * <p>It is applied <em>up the chain from the hold stance</em>, which is the point: every offset that lives
     * in the stance — {@link #adsX() the sight-up compensation} above all — is multiplied by it too, so the
     * sight line still lands on the centre of the screen. Enlarging the item model's {@code display} block
     * instead would grow the geometry while leaving the stance where it was, and the sight would drift off
     * centre by exactly the amount the gun grew — which the scope's magnification makes obvious.
     *
     * <p>The first-person hands follow either way, because they are placed from GeckoLib's own render matrix
     * rather than from constants (see {@code client/weapon/GunFrame}). 1.0 = no change.
     */
    float firstPersonScale();

    /**
     * How far the muzzle jumps per unit of firing kick, in degrees, pitched about the grip: muzzle up, butt
     * down. Bigger for a heavier round, smaller for a gun that fires fast enough that a full kick would shake
     * the picture apart.
     */
    float firePitch();

    /** Rounds left in the stack. */
    int ammo(ItemStack stack);

    /** True while a magazine swap or a bolt cycle owns the weapon, for the HUD's progress bar. */
    boolean isReloading(ItemStack stack, long now);

    /** 0..1 through the reload clip, or 0 when nothing is being reloaded. */
    float reloadProgress(ItemStack stack, long now);

    /**
     * Which action currently owns the weapon — {@code "bolt"}, {@code "reload_tactical"},
     * {@code "reload_empty"} — or an empty string when it is settled.
     *
     * <p>The first-person hands need this, not just {@link #reloadProgress}: a Garand's right hand goes to the
     * clip during a reload but to the op-rod handle during a bolt cycle, and those are separate actions. Asking
     * the gun keeps that knowledge with the gun instead of in the renderer.
     */
    String action(ItemStack stack, long now);

    /** 0..1 through {@link #action}, or 0 when none is running. */
    float actionProgress(ItemStack stack, long now);

    /** Server-side: one trigger pull, straight off the wire. */
    void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level);

    /** Server-side: the reload key. */
    void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level);

    /**
     * Server-side: the reload key with a modifier held. {@code single} asks for the manual's single-round
     * top-up rather than a magazine change.
     *
     * <p>A default rather than an abstract method on purpose: only the Garand has that drill, and a gun
     * without one should ignore the flag instead of every implementation growing a parameter it never
     * reads. The Garand overrides it.</p>
     */
    default void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level, boolean single) {
        beginReload(player, stack, level);
    }

    /**
     * The two shapes a sight's overlay comes in.
     *
     * <p>A single {@code enum} rather than a pair of booleans because the two are one choice, and because the
     * renderer switches on it: a gun that wants a third kind of sight later says so here instead of growing
     * another method the plumbing has to remember to check.
     */
    enum SightStyle {
        /**
         * A telescope. Everything outside the lens goes opaque black ({@code ClientEvents.SCOPE_DARKNESS}) and
         * the view <em>is</em> the glass, which is why a gun answering this normally also answers
         * {@link #hidesModelWhileAimed()} true: a rifle drawn in front of the camera would be sitting exactly
         * where the player is looking.
         */
        TELESCOPE,

        /**
         * A lens the player looks <em>past</em>: a pale wash of glass with a ring round it and a cross on the
         * centre of the screen, and no blackout at all — the world stays visible, so the weapon stays in the
         * frame and the cross reads against whatever is behind it. The shape for an open sight, an aperture or a
         * red dot, and for a modern crossbow's scope, which is what it was added for.
         */
        CLEAR_SIGHT
    }
}
