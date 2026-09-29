package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.CrossbowItem;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the 现代复合狩猎弩: which geometry file bakes, which texture skins it, which clip
 * file feeds the controller. Paths are written out explicitly so the layout matches the other three guns' —
 * the one difference is that the art pipeline published this weapon's texture under {@code textures/models/}
 * rather than {@code textures/item/}, so that is where it is read from.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — every number below is read off the geo file's own cubes.</p>
 *
 * <p>A crossbow is worked the other way round from a bolt-action rifle: the <em>left</em> hand does the moving,
 * pulling the string back onto the latch and carrying a bolt out of the side quiver, while the right hand stays
 * on the pistol grip and pushes the bow away as the string comes back. The clips agree — the glove the art
 * animates through {@code draw} and {@code reload_tactical} is the model's own {@code hand_l}, and the same
 * {@code move} bone every other gun hangs off is the root here too.</p>
 */
public class CrossbowGeoModel extends GeoModel<CrossbowItem> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/crossbow.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/models/crossbow.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/crossbow.animation.json");

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
     * The firing grip: the hand wrapped round the pistol grip behind the trigger. The grip's own frame stands
     * y 0.06…0.86 (its bottom plate 0.06…0.22) between the columns at z −4.00 and −2.72, so 0.46 is the middle
     * of the opening and −3.28 sits between them, level with the trigger (whose pivot is z −3.40).
     */
    private static final float[] GRIP = {-0.06F, 0.46F, -3.28F};

    /**
     * The support hand's home: flat under the fore-end ahead of the receiver. That plate runs y 0.44…0.58 over
     * z −5.90…−3.90, so the hand rides a hand's width below it.
     */
    private static final float[] SUPPORT = {0.10F, 0.30F, -5.55F};

    /**
     * Where the string is taken: its centre at rest, out at the limb tips (the limb pivots sit at z −6.60)
     * with the channel's top at y ≈ 0.95.
     */
    private static final float[] STRING = {0.10F, 1.00F, -4.95F};

    /**
     * How far the string travels rearward to the latch, in model pixels — the hand comes back with it.
     * Kept equal to {@code |LATCH_Z − STRING.z|} = |−3.30 − (−4.95)| so the hand stops exactly on the latch
     * the geometry puts the string at full draw ({@code tools/crossbow_v2.py} → {@code LATCH_Z}).
     */
    private static final float PULL_TRAVEL = 1.65F;

    /**
     * The side quiver the spare bolts ride in: the art's {@code hand_l} rest geometry lives at
     * x 0.52…1.46 / y 0.10…0.66 / z −6.60…−4.13, so the hand meets it on the near face.
     */
    private static final float[] QUIVER = {0.55F, 0.34F, -5.45F};

    /**
     * The receive position on the rail: a bolt posted into the channel just ahead of the latch (pivot
     * z −3.30, y 0.95), which is the 待发位 the {@code reload_tactical} clip puts it down in. The bolt's own
     * geometry spans {@code LATCH_Z → LATCH_Z − 2.40} = −3.30…−5.70, so this is its midpoint.
     */
    private static final float[] CHANNEL = {0.00F, 1.02F, -4.50F};

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(CrossbowItem animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(CrossbowItem animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(CrossbowItem animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose. Called by the renderer once the model has drawn, so the bones hold the values
     * the clip just set and GeckoLib has published its own base matrix.
     *
     * @param itemRenderTranslations GeckoLib's {@code itemRenderTranslations} for this item, off the renderer
     * @param moveBone the bone the clips animate (everything is under it), or {@code null} before it exists
     * @param aim how far into the aim transition the player is, 0…1
     */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
    }

    /**
     * Where the right hand is, in model pixels, for the action the gun is running.
     *
     * <p>On a crossbow that hand never leaves the grip — it is the one holding the weapon — so this stays a
     * target rather than a path. The single motion it adds is the brace: over the span the bow is pushed away
     * from the shooter, which on this model is a small travel toward the muzzle (z decreasing) that peaks
     * through the middle of the pull (the file's {@code draw} is 24 t, the string breaks loose at t≈15).</p>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        System.arraycopy(GRIP, 0, out, 0, 3);
        if ("draw".equals(action)) {
            out[2] -= 0.30F * HandMotion.bump(progress, 0.10F, 0.55F, 0.95F);
        }
        return out;
    }

    /**
     * The left hand is the working hand here, and it follows the clip's own keyframes rather than round
     * numbers:
     * <ul>
     *   <li>{@code draw} takes the string at the limb tips, straps it back onto the latch over
     *       {@code 0.24…0.62} and lets it go by {@code 0.92} — the hand travels with it, so the pull is a
     *       shift of {@link #PULL_TRAVEL} along z rather than a second target.</li>
     *   <li>{@code reload_tactical} goes to the quiver ({@code 0.04…0.20}), lifts a bolt over the rail
     *       ({@code 0.28…0.60}), sets it down in the channel ({@code 0.60…0.78}) and comes home
     *       ({@code 0.80…1.00}).</li>
     * </ul>
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("draw".equals(action)) {
            float to = HandMotion.ramp(progress, 0.05F, 0.22F);
            float pull = HandMotion.bump(progress, 0.24F, 0.62F, 0.92F);
            return HandMotion.lerpThenShift(out, SUPPORT, STRING, to, 0.0F, 0.0F, PULL_TRAVEL * pull);
        }
        if ("reload_tactical".equals(action)) {
            float toQuiver = HandMotion.ramp(progress, 0.04F, 0.20F);
            float toRail = HandMotion.ramp(progress, 0.28F, 0.60F);
            float posted = HandMotion.ramp(progress, 0.60F, 0.78F);
            float away = HandMotion.ramp(progress, 0.80F, 1.00F);
            HandMotion.lerp(out, SUPPORT, QUIVER, toQuiver);
            HandMotion.lerp(out, out, CHANNEL, toRail);
            out[1] -= 0.10F * posted;
            HandMotion.lerp(out, out, SUPPORT, away);
            return out;
        }
        System.arraycopy(SUPPORT, 0, out, 0, 3);
        if ("shoot".equals(action)) {
            // The shot lands and the fore-end arm takes the jolt before settling again.
            out[1] -= 0.10F * HandMotion.bump(progress, 0.00F, 0.15F, 0.75F);
        }
        return out;
    }
}