package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.AWMItem;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the AWM: which geometry file bakes, which texture skins it, which clip file
 * feeds the controller. Paths are written out explicitly (rather than using
 * {@code DefaultedItemGeoModel}) so the layout stays exactly the one documented in art/awm/README.md.
 *
 * <p>As on the Garand, the model also owns where it is this frame ({@link #frame}) and where the hands go
 * ({@link #rightHand}, {@link #leftHand}). The bolt gun differs in one telling way: its magazine is detachable,
 * so the support hand leaves the fore-end and swaps it, while the right hand stays on the firing grip until the
 * bolt needs cycling.
 */
public class AWMGeoModel extends GeoModel<AWMItem> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/awm.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/awm.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/awm.animation.json");

    /** The gun's pose this frame; see {@link GunFrame}. Written by the renderer, read by the arms. */
    public static final GunFrame frame = new GunFrame();

    /** Scratch for composing the bone chain — see the same field on the Garand model. */
    private static final Matrix4f SCRATCH = new Matrix4f();

    // ------------------------------------------------------------------ hand targets (model pixels)

    /** The firing grip, on the pistol grip below the receiver. */
    private static final float[] GRIP = {-0.26F, -0.30F, 0.95F};

    /**
     * The knob on the end of the bolt handle — the ball the hand actually closes on. Centre of the ring of
     * eight cubes at x −1.36, y 1.80, z 0.84 (read off the geo's {@code bolt} bone), which is what the right
     * hand is driven to while the bolt is being worked: wherever the clip has moved this point, the hand is.
     *
     * <p>The previous constant here sat 0.6 px further back along the bore than the knob and 0.33 px short of
     * the clip's travel, so the fist trailed the handle by about that much all the way through the pull.</p>
     */
    private static final float[] BOLT_KNOB = {-1.36F, 1.80F, 0.84F};

    /**
     * The bolt's own maxima over the clips — 60° of turn, 1.932 px of travel — used only to read how far off its
     * home position the bolt is this frame ({@link GunFrame#boltActivity}). Both are the {@code bolt} clip's
     * values, and {@code check_bolt_grip} asserts they still are.
     */
    private static final float BOLT_TURN_MAX = 60.0F;
    private static final float BOLT_PULL_MAX = 1.932F;

    /**
     * When the empty reload lets the right hand go back to the bolt, as a fraction of that clip: the clip starts
     * running the handle down at 0.6592, and the hand sets off a tenth of a second earlier so it is closed on
     * the handle before the handle moves. Before it the support hand is working the magazine and the right hand
     * stays on the firing grip.
     */
    private static final float BOLT_PICKUP = 0.64F;

    /**
     * How much of the hand's grip is on the handle, 0…1 — see the same field on the Mosin model for why this is
     * state rather than a fade in each clip.
     */
    private static float handleHold;

    /** Seconds for the fist to reach (or leave) the handle. */
    private static final float HOLD_TAU = 0.06F;

    /** The support hand's home: the fore-end, just behind the bipod. */
    private static final float[] SUPPORT = {0.55F, 0.68F, -8.40F};

    /** The magazine well, under the receiver — where the support hand goes to swap a magazine. */
    private static final float[] MAGWELL = {0.30F, -1.50F, -2.40F};

    /** How far a magazine drops out of the well, in model pixels. */
    private static final float MAG_DROP = 1.60F;

    /** Scratch: the live knob while the hand is on the handle, and the bolt's chain. See the Mosin model. */
    private static final float[] KNOB = new float[3];
    private static final Matrix4f SCRATCH_BOLT = new Matrix4f();

    @Override
    public ResourceLocation getModelResource(AWMItem animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(AWMItem animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(AWMItem animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /** Records this frame's pose from inside the renderer. See the Garand model's twin for the reasoning. */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, CoreGeoBone boltBone,
                               float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
        frame.bolt(GunFrame.partChain(SCRATCH_BOLT, boltBone, GunFrame.MOVE_BONE), boltBone);
    }

    /**
     * The right hand. On this gun it works the bolt and nothing else: the magazine is the support hand's job, so
     * the firing grip is kept through the reload until the clip comes to the bolt.
     *
     * <p>While the bolt is off home the hand is on the <em>knob</em> — the point {@link GunFrame#boltGrip} moves
     * with the live bone, so the fist and the handle are the same pose by construction rather than by a re-timing
     * of keyframes here. {@link #handleHold} eases the changeover at either end; the middle is the clip's own
     * answer, and {@code check_bolt_grip} measures the gap.</p>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action) || "inspect".equals(action) || "inspect_empty".equals(action)) {
            return onBolt(out, holdOnHandle());
        }
        if ("static_bolt_caught".equals(action)) {
            // The whole clip is the bolt held open, so there is no changeover to ease — the hand is simply on it.
            return onBolt(out, 1.0F);
        }
        if ("reload_empty".equals(action)) {
            if (progress < BOLT_PICKUP) {
                // Still on the firing grip: the support hand has the magazine, the right hand has nothing to do.
                handleHold = 0.0F;
                System.arraycopy(GRIP, 0, out, 0, 3);
                return out;
            }
            return onBolt(out, holdOnHandle());
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * Advances {@link #handleHold} for this frame: 1 while the live bolt is off its home position, 0 once the
     * clip has run it closed, with {@link HandMotion#ease} at {@link #HOLD_TAU} for the travel between the two.
     */
    private static float holdOnHandle() {
        float on = frame.boltActivity(BOLT_TURN_MAX, BOLT_PULL_MAX) > 0.02F ? 1.0F : 0.0F;
        handleHold = HandMotion.ease(handleHold, on, HOLD_TAU);
        return handleHold;
    }

    /**
     * The firing grip, or the live handle if the hand belongs on it: {@code k} runs from 0 with the fist at the
     * grip to 1 with it closed on the knob. Falls back to the grip whenever the renderer has handed no bolt over,
     * so a hand never chases nothing.
     */
    private static float[] onBolt(float[] out, float k) {
        if (k > 0.0F && frame.boltGrip(BOLT_KNOB, KNOB)) {
            return HandMotion.lerp(out, GRIP, KNOB, k);
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand: the fore-end at rest, dropping to the magazine well to swap the box out when one is
     * being reloaded.
     *
     * <p>The magazine's own keyframes run {@code 0.17…0.67} of the tactical clip's 3s and {@code 0.16…0.55} of
     * the empty one's 3.72s, so the hand travels down over about a sixth of the clip, out with the old magazine,
     * back up with the new, and only then returns to the fore-end.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            float cover = ("reload_empty".equals(action) ? 0.55F : 0.67F);
            if (progress < cover) {
                float down = HandMotion.ramp(progress, 0.05F, 0.18F);
                // Out with the old magazine, in with the new: one dip in the middle of the window.
                float out_ = HandMotion.bump(progress, 0.18F, 0.40F, cover) * MAG_DROP;
                float[] p = HandMotion.lerp(out, SUPPORT, MAGWELL, down);
                p[1] -= out_;
                return p;
            }
            float back = HandMotion.ramp(progress, cover, Math.min(1.0F, cover + 0.20F));
            return HandMotion.lerp(out, MAGWELL, SUPPORT, back);
        }
        System.arraycopy(SUPPORT, 0, out, 0, 3);
        return out;
    }
}
