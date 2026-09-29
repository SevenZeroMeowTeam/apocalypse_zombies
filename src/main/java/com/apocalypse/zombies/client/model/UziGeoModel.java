package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.UziItem;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the Uzi: which geometry file bakes, which texture skins it, which clip file
 * feeds the controller. Paths are written out explicitly so the layout matches the other four guns' exactly.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — the numbers below are read straight off the geo file's cubes.</p>
 *
 * <h2>Hands: which one does the work</h2>
 * The Uzi is the one gun in the rack whose <em>left</em> hand reloads. Its magazine is inside the pistol grip
 * rather than ahead of the trigger guard, and its charging handle is a knob on <em>top</em> of the receiver —
 * both are reached by the support hand while the firing hand keeps the grip and the trigger. That is the
 * opposite of the Garand, whose right hand works the op-rod on the right of the receiver, so the split here is
 * deliberately asymmetric: {@link #rightHand} never leaves {@value #GRIP}.
 */
public class UziGeoModel extends GeoModel<UziItem> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/uzi.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/uzi.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/uzi.animation.json");

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

    /** The firing grip: the hand wrapped round the pistol grip, on the trigger. */
    private static final float[] GRIP = {0.00F, 0.50F, 2.00F};

    /** The magazine body below the well — what the left hand catches when it strips a magazine out. */
    private static final float[] MAG = {0.10F, -0.60F, 1.90F};

    /**
     * The charging handle, on <em>top</em> of the receiver just behind the ejection port. Reached by the left
     * hand coming over the gun, which is why its x is the shooter's left of centre rather than on the right
     * like the Garand's op-rod handle.
     */
    private static final float[] BOLT = {-0.25F, 3.12F, 2.40F};

    /**
     * The support hand, cupped under the receiver just ahead of the trigger guard. An Uzi's magazine is the
     * foregrip, so the support hand sits further back than the Garand's — there is no fore-end to hold.
     */
    private static final float[] SUPPORT = {0.00F, 0.35F, -0.50F};

    /** How far the bolt travels rearward, in model pixels — the hand pulls back with the handle. */
    private static final float BOLT_TRAVEL = 1.05F;

    /** How far the magazine drops out of the well, in model pixels — the hand rides it down. */
    private static final float MAG_DROP = 5.60F;

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(UziItem animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(UziItem animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(UziItem animatable) {
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
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
    }

    /**
     * The firing hand: it holds the grip through everything. On a blowback SMG the bolt cycles itself and the
     * magazine comes out of the grip the hand is already wrapped round, so there is no action that takes this
     * hand off the gun — see the class note on why the reload is the left hand's job here.
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand, which does the reload and the manual charging.
     *
     * <p>Timings follow the clips' own keyframes rather than round numbers, because a hand that arrives after
     * the clip has already put the part down reads as a mistake. The two reloads key the magazine at different
     * normalised times — {@code reload_tactical} seats it at {@code 0.59} of 2.6 s, {@code reload_empty} at
     * {@code 0.53} of 3.3 s — so the windows are read per clip rather than shared:</p>
     * <ul>
     *   <li>{@code bolt} — handle reached at {@code 0.05…0.18}, pulled rear over {@code 0.10…0.25…0.72}.</li>
     *   <li>{@code reload_tactical} — magazine out by {@code 0.35}, seated {@code 0.59}, charged
     *       {@code 0.58…0.80}.</li>
     *   <li>{@code reload_empty} — magazine out by {@code 0.32}, seated {@code 0.53}, charged
     *       {@code 0.64…0.83}.</li>
     *   <li>{@code shoot} — nothing. The bolt is cycling itself; the hand stays on the fore-end.</li>
     * </ul>
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.03F, 0.18F);
            float pulled = HandMotion.bump(progress, 0.10F, 0.25F, 0.72F);
            return HandMotion.lerpThenShift(out, SUPPORT, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }

        boolean tactical = !"reload_empty".equals(action);
        if ("reload_tactical".equals(action) || "reload_empty".equals(action)) {
            float magOutAt = tactical ? 0.35F : 0.32F;
            float magSeatAt = tactical ? 0.59F : 0.53F;
            float boltAt = tactical ? 0.58F : 0.64F;
            float boltHomeAt = tactical ? 0.80F : 0.83F;

            // Leaves the fore-end, catches the magazine, and rides it down out of the well. `drop` is how far
            // below the well the magazine currently is, so it is back at zero exactly when the fresh one seats.
            float toMag = HandMotion.ramp(progress, 0.03F, 0.16F);
            float drop = HandMotion.bump(progress, 0.16F, magOutAt, magSeatAt);
            float[] atMag = HandMotion.lerp(out, SUPPORT, MAG, toMag);
            atMag[1] -= MAG_DROP * drop;
            if (progress < magSeatAt) {
                return atMag;
            }

            // Seated: up to the charging handle over the top, pull, and let it run home.
            float toHandle = HandMotion.ramp(progress, magSeatAt, boltAt);
            float pulled = HandMotion.bump(progress, boltAt, (boltAt + boltHomeAt) * 0.5F, boltHomeAt);
            float[] back = HandMotion.lerp(out, atMag, BOLT, toHandle);
            back[2] += BOLT_TRAVEL * pulled;
            return back;
        }

        System.arraycopy(SUPPORT, 0, out, 0, 3);
        return out;
    }
}
