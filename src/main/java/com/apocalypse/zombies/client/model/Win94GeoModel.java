package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.Win94Item;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the 温彻斯特 M1894（Win94 杠杆狙击枪）: which geometry file bakes, which
 * texture skins it, which clip file feeds the controller. Paths are written out explicitly so the layout
 * matches the other rifles'.
 *
 * <p>The model is 17.83 u (1.11 blocks) — the proportions of a 24-inch-barrelled Model 1894, muzzle at
 * z -10.77 and buttplate at z +7.06, bore line at y 0. Its action is a lever, not a bolt handle: the right
 * hand works the lever loop hanging under the receiver (bone {@code lever}, pivot on the lever pin at
 * [0, -0.95, -2.30]), so the "knob" the hand chases is the loop's bottom bar and the whole cycle is that
 * one bone swinging 62°. See {@link Win94Item} for the clip table.</p>
 *
 * <p>Like the Mosin this class owns the two things the first-person hands need: where the gun is this
 * frame ({@link #frame}) and where the hands go on it ({@link #rightHand}, {@link #leftHand}). Every
 * number below is read off the geo file's own cubes.</p>
 */
public class Win94GeoModel extends GeoModel<Win94Item> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/win94.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/win94.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/win94.animation.json");

    /** The gun's pose this frame, written by the renderer and read by the arms — see {@link GunFrame}. */
    public static final GunFrame frame = new GunFrame();

    private static final Matrix4f SCRATCH = new Matrix4f();

    // ------------------------------------------------------------------ hand targets (model pixels)

    /**
     * The firing grip: the hand wrapped round the wrist of the stock, behind the trigger. The wrist column
     * (z 2.3…4.6) runs y -0.69…-2.11, so -0.85 at z 3.4 is the upper wood where a fist closes.
     */
    private static final float[] GRIP = {0.00F, -0.85F, 3.40F};

    /**
     * The support hand, flat under the wooden fore-end ahead of the receiver (the forearm spans
     * z -6.30…-2.62, bottom edge y -0.72) — forward enough to balance the 24-inch barrel.
     */
    private static final float[] SUPPORT = {0.10F, -1.45F, -3.60F};

    /**
     * The lever loop's bottom bar — the part the right hand actually closes on. It is a point of the
     * {@code lever} bone, so the clips move it: {@link GunFrame#boltGrip} applies the lever's live chain and
     * the hand lands wherever the loop has swung to, 62° of arc and no slide. The loop's own geometry
     * (centre y -1.85, z +0.92, semi-axes z 0.84 / y 0.32 — measured off a real M1894, see
     * tools/win94/spec.py) puts its bottom bar here.
     */
    private static final float[] LEVER_KNOB = {0.00F, -2.17F, 0.92F};

    /** The lever's own maxima over the clips — 62° of swing, no linear travel. */
    private static final float LEVER_TURN_MAX = 62.0F;
    private static final float LEVER_PULL_MAX = 0.0F;

    /** Seconds for the fist to reach (or leave) the lever loop. A short reach down from the grip. */
    private static final float HOLD_TAU = 0.06F;

    /** Live eased hold 0…1 — see {@link #holdOnLever}. */
    private static float handleHold;

    private static final float[] KNOB = new float[3];
    private static final Matrix4f SCRATCH_LEVER = new Matrix4f();

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(Win94Item animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(Win94Item animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(Win94Item animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose. Called by the renderer once the model has drawn, so the bones hold the
     * values the clip just set and GeckoLib has published its own base matrix.
     *
     * @param leverBone the {@code lever} bone, whose live pose the right hand is driven from (may be null)
     */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, CoreGeoBone leverBone,
                               float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
        frame.bolt(GunFrame.partChain(SCRATCH_LEVER, leverBone, GunFrame.MOVE_BONE), leverBone);
    }

    /**
     * Where the right hand is, in model pixels, for the action the gun is running.
     *
     * <p>The lever is worked by hand on this rifle and the hand holds the <em>loop</em>, not a spot near
     * it: for every clip that moves the lever (the {@code bolt} cycle, both reloads, the inspect) the hand
     * is aimed at the loop's bottom bar wherever the clip has swung it to ({@link GunFrame#boltGrip}).
     * Unlike a Mosin there is no trip to an ammo pouch mid-reload — a tube-fed lever gun feeds itself;
     * the cycling hand simply stays on the lever. Otherwise the firing grip.</p>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action) || "inspect".equals(action)
                || "reload_empty".equals(action) || "reload_tactical".equals(action)) {
            return onLever(out, holdOnLever());
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * Advances {@link #handleHold} for this frame: 1 while the live lever is off home, 0 once the clip has
     * swung it shut, with {@link HandMotion#ease} at {@link #HOLD_TAU} between the two — one rule covering
     * every clip that touches the lever.
     */
    private static float holdOnLever() {
        float on = frame.boltActivity(LEVER_TURN_MAX, LEVER_PULL_MAX) > 0.02F ? 1.0F : 0.0F;
        handleHold = HandMotion.ease(handleHold, on, HOLD_TAU);
        return handleHold;
    }

    /** The firing grip, or the live lever loop if the hand belongs on it. */
    private static float[] onLever(float[] out, float k) {
        if (k > 0.0F && frame.boltGrip(LEVER_KNOB, KNOB)) {
            return HandMotion.lerp(out, GRIP, KNOB, k);
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand stays on the fore-end through everything — a lever gun is cycled with the rifle
     * shouldered and the left hand holding it. Only a small settle during the reloads keeps the wrist from
     * locking rigid.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        float settle = 0.0F;
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            settle = 0.18F * HandMotion.bump(progress, 0.10F, 0.35F, 0.80F);
        }
        out[0] = SUPPORT[0];
        out[1] = SUPPORT[1] - settle;
        out[2] = SUPPORT[2];
        return out;
    }
}
