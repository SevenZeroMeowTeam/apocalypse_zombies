package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.S686Item;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for Gold Plate - S686: which geometry file bakes, which texture skins it, which clip
 * file feeds the controller. Paths are written out explicitly so the layout matches the other guns' exactly.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — the numbers below are read straight off the geo file's cubes.</p>
 *
 * <h2>Hands: which one does the work, and what it rides</h2>
 * The S686 splits the two jobs the way the gun itself does. The <b>right</b> hand holds the grip and the
 * trigger through every clip, because that is where the action is worked from: the top lever is a thumb latch
 * <em>on top of the receiver</em>, right above the firing hand, so the hand that opens the gun never leaves the
 * trigger. The whole fold is visible in the art, on the lever and the barrel bones; moving the hand to follow
 * the lever would be the firing hand letting go of the gun to press a latch it can already reach.
 *
 * <p>The <b>left</b> hand does everything else: it holds the fore-end, and the fore-end is a child of the
 * {@code barrel} bone — the bone the clips swing 38° to break the action open. So the support hand does not
 * need a fold motion authored in Java at all: it is glued to the fore-end and the barrels carry it down and
 * back. That is {@link GunFrame#partChain}'s job below, and it is the same rule {@link GunFrame#bolt} uses for
 * a bolt handle — read the live bone rather than re-time the clip in a second place.</p>
 *
 * <p>Loading is the one thing the fore-end cannot carry. The shells live on {@code shell_upper} /
 * {@code shell_lower}, which are bones of their own with their own keyframes, so the hand is put on the upper
 * shell for the window in which a fresh pair rides home, and comes back to the fore-end before the barrels
 * shut. See {@link #leftHand} for the windows, which are read off each clip's keyframes rather than rounded.</p>
 */
public class S686GeoModel extends GeoModel<S686Item> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/s686.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/s686.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/s686.animation.json");

    /**
     * The gun's pose this frame, written by the renderer as it draws and read by the arms a few lines earlier
     * in the next frame. See {@link GunFrame} for why it has to be handed over rather than recomputed.
     */
    public static final GunFrame frame = new GunFrame();

    /**
     * Scratch for composing the bone chain. Rendering is single-threaded on the client, and this is only ever
     * touched inside {@link #capture} and read straight away, so one instance is enough.
     */
    private static final Matrix4f SCRATCH = new Matrix4f();

    /**
     * The two part chains this gun's hands ride: the barrel group (the fore-end folds with it) and the upper
     * shell (the hand carries the fresh pair home). Both are model px → model px, composed from the live bones
     * every frame by {@link #capture}, and both stop at {@code move} — that bone is applied to a hand target
     * once, by {@link GunFrame#toCamera}.
     */
    private static final Matrix4f BARREL_CHAIN = new Matrix4f();
    private static final Matrix4f SHELL_CHAIN = new Matrix4f();
    private static boolean partsValid;

    /** Scratch for the points those chains are applied to (client render is single-threaded). */
    private static final float[] BREECH_AT = new float[3];
    private static final float[] SHELL_AT = new float[3];
    private static final float[] FOREND_AT = new float[3];
    private static final Vector3f V = new Vector3f();

    // ------------------------------------------------------------------ hand targets (model pixels)

    /**
     * The firing grip: the hand wrapped round the wrist of the stock, on the trigger. The stock's wrist runs
     * y −1.62…0.62 over z 4.44…5.36, so this sits in the middle of it and a little low, where a palm lands.
     */
    private static final float[] GRIP = {0.00F, -0.80F, 4.90F};

    /** The support hand under the fore-end, whose underside is at y −0.98 over z −3.64…1.02. */
    private static final float[] FOREND = {0.00F, -0.95F, -1.60F};

    /**
     * Where the shells come from: the belt at the player's hip, behind and below the gun.
     *
     * <p>A break-action has no magazine to pull from, so the pair has to be fetched. Unlike every other point
     * here this one is deliberately <b>not</b> on the barrel's chain (see {@link #onBarrel}) — the hand is
     * reaching for the player's own body, not for the folded barrels, and a belt that swung down with the
     * barrels would be nonsense. It only rides the {@code move} chain (the gun's whole-body pose), which is
     * what makes it sway with the player.</p>
     */
    private static final float[] AMMO = {-2.00F, -9.80F, 8.90F};

    /**
     * The breech face, between the two chambers and just behind the shell heads (the shells reach z 1.2), which
     * is where a shell is caught or fed. Expressed on the barrel, like the fore-end, so it folds with it.
     *
     * <p>Nudged left and down off the gun's centre line. The chambers sit on that centre line in the first
     * person, so a hand parked exactly on it covers the very thing the player is watching during a reload.
     * Coming in from the lower left instead reads as reaching under the action, and leaves the open chambers
     * and the shells going home visible.</p>
     */
    private static final float[] BREECH = {-0.20F, -0.15F, 1.30F};

    /**
     * The upper shell's body — y 0.26…0.30, z 0…1.2 — the point a hand holds a shell by. Lowered and shifted
     * left with {@link #BREECH} so the hand rides home beside the shell rather than over it.
     */
    private static final float[] SHELL = {-0.15F, 0.08F, 0.60F};

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(S686Item animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(S686Item animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(S686Item animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose. Called by the renderer once the model has drawn, so the bones hold the values
     * the clip just set and GeckoLib has published its own base matrix.
     *
     * @param itemRenderTranslations GeckoLib's {@code itemRenderTranslations} for this item, off the renderer
     * @param moveBone the bone the clips animate (everything is under it), or {@code null} before it exists
     * @param barrelBone the barrel group's bone, which the fold clips rotate — the fore-end's chain
     * @param shellBone the upper shell's bone, which the reload clips drive — the hand's chain while loading
     * @param aim aim progress this frame, which the arms use for their shoulder push
     */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, CoreGeoBone barrelBone,
                               CoreGeoBone shellBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            partsValid = false;
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);

        partsValid = barrelBone != null && shellBone != null;
        if (partsValid) {
            GunFrame.partChain(BARREL_CHAIN, barrelBone, GunFrame.MOVE_BONE);
            GunFrame.partChain(SHELL_CHAIN, shellBone, GunFrame.MOVE_BONE);
        }
    }

    /**
     * A rest point of the barrel group, moved to wherever the clip has folded it this frame — the same model
     * pixels, in the space a hand target is written in.
     *
     * <p>Without a captured chain (no bones yet, or nothing drawn) the rest point is handed back unchanged:
     * a hand in the wrong place for one frame beats an arm drawn to nowhere.</p>
     */
    private static float[] onBarrel(float[] rest, float[] out) {
        System.arraycopy(rest, 0, out, 0, 3);
        if (!partsValid) {
            return out;
        }
        V.set(out[0], out[1], out[2]);
        BARREL_CHAIN.transformPosition(V);
        out[0] = V.x;
        out[1] = V.y;
        out[2] = V.z;
        return out;
    }

    /** As {@link #onBarrel}, for a point of the upper shell. */
    private static float[] onShell(float[] rest, float[] out) {
        System.arraycopy(rest, 0, out, 0, 3);
        if (!partsValid) {
            return out;
        }
        V.set(out[0], out[1], out[2]);
        SHELL_CHAIN.transformPosition(V);
        out[0] = V.x;
        out[1] = V.y;
        out[2] = V.z;
        return out;
    }

    /**
     * The firing hand: it holds the grip through everything.
     *
     * <p>A break-action is opened with the thumb of this hand, on the top lever right above it, so there is no
     * clip in which the hand has to leave the trigger — see the class note.</p>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand: the fore-end, the breech, and the fresh shells.
     *
     * <p>Timings follow the clips' own keyframes rather than round numbers, because a hand that arrives after
     * the clip has already put the part down reads as a mistake. In {@code reload_empty} the spent cases leave
     * the chambers at {@code 0.24…0.40} of 3.3 s and the fresh pair rides home over {@code 0.40…0.71}, so the
     * hand is at the breech before the cases move and on the upper shell while it travels. {@code
     * reload_tactical} is the same job in less time: the shells turn round at {@code 0.63} and are home by
     * {@code 0.77}. Either way the hand rides the shell until it seats and is back on the fore-end for the
     * settle — the barrels shut at {@code 0.83} and {@code 0.79} respectively:</p>
     * <ul>
     *   <li>{@code bolt} — the fold-and-check. Nothing to load, so the hand just rides the fore-end open and
     *       shut; the whole motion is the barrel bone's.</li>
     *   <li>{@code reload_tactical} / {@code reload_empty} — fore-end → breech → upper shell → fore-end.</li>
     *   <li>everything else ({@code static_idle}, {@code draw}, {@code shoot}, the ADS pair) — the fore-end.</li>
     * </ul>
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            return onBarrel(FOREND, out);
        }

        if ("reload_tactical".equals(action) || "reload_empty".equals(action)) {
            boolean empty = "reload_empty".equals(action);

            // Off the gun entirely first: a break-action has no magazine, so the pair comes off the belt at the
            // player's hip and is carried back by hand. This is the one leg of the trip that is NOT on the
            // barrel's chain — see AMMO.
            float toAmmo = HandMotion.ramp(progress, empty ? 0.18F : 0.24F, empty ? 0.32F : 0.38F);
            // Back at the breech with the pair, while the spent cases are on their way out.
            float toBreech = HandMotion.ramp(progress, empty ? 0.40F : 0.46F, empty ? 0.52F : 0.58F);
            // The fresh pair turns round and starts home at 0.41 / 0.62, so the hand reaches for it there.
            float toShell = HandMotion.ramp(progress, empty ? 0.55F : 0.62F, empty ? 0.66F : 0.72F);
            // Off the shell once it is seated (0.71 / 0.76) and back on the fore-end before the barrels shut.
            float toForend = HandMotion.ramp(progress, empty ? 0.76F : 0.80F, empty ? 0.86F : 0.88F);

            onBarrel(FOREND, out);
            HandMotion.lerp(out, out, AMMO, toAmmo);
            HandMotion.lerp(out, out, onBarrel(BREECH, BREECH_AT), toBreech);
            HandMotion.lerp(out, out, onShell(SHELL, SHELL_AT), toShell);
            return HandMotion.lerp(out, out, onBarrel(FOREND, FOREND_AT), toForend);
        }

        return onBarrel(FOREND, out);
    }
}
