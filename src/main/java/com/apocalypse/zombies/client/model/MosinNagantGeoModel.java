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
     * The straight bolt handle, on the right of the receiver — what the right hand actually works. At
     * z −2.10 the geo's x runs to −0.98 (the handle's own column, published space), and the knob sits at
     * the top of it, y ≈ 2.0.
     */
    private static final float[] BOLT = {-0.75F, 2.05F, -2.10F};

    /** The support hand, flat under the fore-end ahead of the receiver (that column runs y 0.56…2.06). */
    private static final float[] SUPPORT = {0.10F, 0.52F, -8.00F};

    /** How far the bolt handle travels rearward, in model pixels — the hand pulls back with it. */
    private static final float BOLT_TRAVEL = 1.55F;

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
     */
    public static void capture(org.joml.Matrix4f itemRenderTranslations, CoreGeoBone moveBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
    }

    /**
     * Where the right hand is, in model pixels, for the action the gun is running.
     *
     * <p>Timings follow the clips' own keyframes rather than round numbers, because a hand that arrives after
     * the clip has already put the part down reads as a mistake:
     * <ul>
     *   <li>{@code bolt} breaks the handle open over {@code 0.10…0.19}, pulls rearward to {@code 0.38} and is
     *       home again by {@code 0.68} (the file: t=4.2 / 8.3 / 15.0 of 22).</li>
     *   <li>The reloads hold the rounds over the receiver from {@code 0.04…0.16} through the last round at
     *       {@code 0.83}, then close the bolt over {@code 0.84…0.96}.</li>
     * </ul>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.10F, 0.19F);
            float pulled = HandMotion.bump(progress, 0.19F, 0.38F, 0.68F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            float toRounds = HandMotion.ramp(progress, 0.04F, 0.16F);
            float press = HandMotion.ramp(progress, 0.16F, 0.30F);
            if (progress < 0.84F) {
                // Over the receiver, pressing each round home — the thumb goes down, the hand follows.
                return HandMotion.lerpThenShift(out, GRIP, ROUNDS, toRounds, 0.0F, -0.35F * press, 0.0F);
            }
            // Then releases the handle and runs the bolt home, hand riding it forward.
            float toHandle = HandMotion.ramp(progress, 0.84F, 0.92F);
            float closed = HandMotion.bump(progress, 0.88F, 0.94F, 1.0F);
            float[] back = HandMotion.lerp(out, ROUNDS, BOLT, toHandle);
            back[2] -= BOLT_TRAVEL * closed;
            return back;
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