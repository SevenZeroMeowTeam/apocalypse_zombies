package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.MosinNagantItem;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the 莫辛-纳甘 M91/30: which geometry file bakes, which texture skins it, which
 * clip file feeds the controller. Paths are written out explicitly so the layout matches the other two guns'.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — every number below is read off the geo file's own cubes.</p>
 */
public class MosinNagantGeoModel extends GeoModel<MosinNagantItem> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/mosin_nagant.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/mosin_nagant.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/mosin_nagant.animation.json");

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

    // ------------------------------------------------------------------ hand targets (model pixels)

    /**
     * The firing grip: the hand wrapped round the wrist of the stock, behind the trigger. Read off the geo
     * at z +0.62 — that column runs y 0.11…1.27 (mm 963 up the wrist), so 0.95 is the middle of the wood.
     */
    private static final float[] GRIP = {-0.10F, 0.95F, 0.62F};

    /**
     * Above the open receiver, where the rounds are pressed down into the fixed magazine.
     *
     * <p>Sits over the {@code round_in} bone's own pivot (z −4.53, y 2.64) — the point the clip animates the
     * rounds through — so the thumb rides the same path the geometry does. The receiver's top there is
     * y 2.81 (mm 697, the sight base), which is why the hand starts above the wood.</p>
     */
    private static final float[] ROUNDS = {0.00F, 2.90F, -4.50F};

    /**
     * The knob on the end of the handle — the part the hand actually closes on. Centre of the outer plate at
     * x −0.62 (that plate runs x −0.68…−0.56, y 1.69…2.15), which is the outermost of the handle's three
     * cubes; the hand is driven to wherever the clip has moved this point.
     *
     * <p>It is a point of the bolt, so the clip moves it: the handle turns about the bolt's own pivot — the
     * bore line at (0, 1.75, −2.108), straight off the geo — and slides rearward with it. Rather than redo
     * that arithmetic here, {@link GunFrame#boltGrip} applies the bolt's live chain, so the hand lands
     * wherever the drawn handle actually is.</p>
     */
    private static final float[] BOLT_KNOB = {-0.62F, 1.93F, -2.05F};

    /**
     * The bolt's own maxima over the clips — 80° of turn, 1.55 px of travel — used only to read how far off
     * its home position the bolt is this frame ({@link GunFrame#boltActivity}). Both are the values the
     * {@code bolt} clip and the reloads key, and {@code check_bolt_grip} asserts they still are.
     */
    private static final float BOLT_TURN_MAX = 80.0F;
    private static final float BOLT_PULL_MAX = 1.55F;

    /**
     * When each reload lets the right hand go back to the bolt, as a fraction of that clip. The clip itself
     * starts running the handle down at 0.8996 ({@code reload_empty}) and 0.8796 ({@code reload_tactical}); the
     * hand sets off a tenth of a second earlier so it is closed on the handle before the handle moves.
     * {@code check_bolt_grip} re-reads both clips and fails if these stop matching them.
     */
    private static final float BOLT_PICKUP_EMPTY = 0.88F;
    private static final float BOLT_PICKUP_TACTICAL = 0.86F;

    /**
     * How much of the hand's grip is on the handle, 0…1 — eased by {@link HandMotion#ease} at {@link #HOLD_TAU},
     * so the fist reaches the knob on its own time instead of teleporting with a handle that flies open.
     *
     * <p>State rather than a fade, and driven by {@link #holdOnHandle} off the live bolt: the hand is on the
     * handle for exactly as long as the clip holds the bolt off home, and lets go when the clip runs it closed —
     * one rule that covers cycling, inspecting and the tail of a reload alike. A fade per clip would have to
     * name a second timing for "still holding", and that is a second copy of the art, free to drift from it.</p>
     */
    private static float handleHold;

    /** Seconds for the fist to reach (or leave) the handle. A reach across the receiver, so: not a snap. */
    private static final float HOLD_TAU = 0.06F;

    /** The support hand, flat under the fore-end ahead of the receiver (that column runs y 0.56…2.06). */
    private static final float[] SUPPORT = {0.10F, 0.52F, -8.00F};

    /**
     * Scratch: the live knob while the hand is on the handle, and the bolt's chain. The client renders on one
     * thread and both are used inside a single {@link #rightHand} call, so one of each is enough — the same
     * reasoning as {@link #SCRATCH}.
     */
    private static final float[] KNOB = new float[3];
    private static final Matrix4f SCRATCH_BOLT = new Matrix4f();

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(MosinNagantItem animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(MosinNagantItem animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(MosinNagantItem animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose. Called by the renderer once the model has drawn, so the bones hold the values
     * the clip just set and GeckoLib has published its own base matrix.
     *
     * @param itemRenderTranslations GeckoLib's {@code itemRenderTranslations} for this item, off the renderer
     * @param moveBone the bone the clips animate (everything is under it), or {@code null} before it exists
     * @param boltBone the {@code bolt} bone, whose live pose the right hand is driven from (may be {@code null})
     */
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
     * Where the right hand is, in model pixels, for the action the gun is running.
     *
     * <p>The bolt is worked by hand on this rifle, and the rule the hand follows is the one the user sees: it
     * holds the <em>knob</em>, not a spot near it. So wherever the clip has the bolt, the hand is aimed at the
     * point the knob has moved to ({@link GunFrame#boltGrip}) — the hand and the handle are then the same
     * pose by construction, and no re-timing of keyframes here can drift away from the art.</p>
     *
     * <p>Timings follow the clips' own keyframes rather than round numbers, because a hand that arrives after
     * the clip has already put the part down reads as a mistake:
     * <ul>
     *   <li>{@code bolt} and {@code inspect} are the bolt cycle itself, so the hand simply holds the handle for
     *       as long as the clip holds the bolt off home ({@link #holdOnHandle}) — it lets go only once the clip
     *       has run it closed.</li>
     *   <li>The reloads hold the rounds over the receiver until the clip starts closing the bolt at
     *       {@code BOLT_PICKUP_*}, then the hand drops onto the handle and rides it home.</li>
     * </ul>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action) || "inspect".equals(action)) {
            return onBolt(out, holdOnHandle());
        }
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            float pickup = "reload_empty".equals(action) ? BOLT_PICKUP_EMPTY : BOLT_PICKUP_TACTICAL;
            if (progress < pickup) {
                // Over the receiver, pressing each round home — the thumb goes down, the hand follows. The bolt
                // is already open behind it, so the grip's own state is held down rather than left to follow it.
                handleHold = 0.0F;
                float toRounds = HandMotion.ramp(progress, 0.04F, 0.16F);
                float press = HandMotion.ramp(progress, 0.16F, 0.30F);
                return HandMotion.lerpThenShift(out, GRIP, ROUNDS, toRounds, 0.0F, -0.35F * press, 0.0F);
            }
            // Then the clip closes the bolt over its last tenth, and the hand goes with it.
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
     * The firing grip, or the live handle if the hand belongs on it: {@code k} runs from 0 with the fist at
     * the grip to 1 with it closed on the knob. Falls back to the grip whenever the renderer has handed no
     * bolt over (other display contexts, the first frames after a swap) so a hand never chases nothing.
     */
    private static float[] onBolt(float[] out, float k) {
        if (k > 0.0F && frame.boltGrip(BOLT_KNOB, KNOB)) {
            return HandMotion.lerp(out, GRIP, KNOB, k);
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand stays on the fore-end through everything — a Mosin is loaded with the rifle still
     * shouldered and the left hand holding it. It is a target rather than a constant because the gun itself
     * moves under it, which {@link #frame} already accounts for; the only change is a small settle while the
     * rounds go in, to keep the wrist from locking rigid.
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