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

    /** The bolt handle, on the right of the receiver. */
    private static final float[] BOLT = {-1.35F, 1.85F, 1.45F};

    /** The support hand's home: the fore-end, just behind the bipod. */
    private static final float[] SUPPORT = {0.55F, 0.68F, -8.40F};

    /** The magazine well, under the receiver — where the support hand goes to swap a magazine. */
    private static final float[] MAGWELL = {0.30F, -1.50F, -2.40F};

    /** How far the bolt handle travels rearward, in model pixels. */
    private static final float BOLT_TRAVEL = 1.60F;

    /** How far a magazine drops out of the well, in model pixels. */
    private static final float MAG_DROP = 1.60F;

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
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
    }

    /**
     * The right hand. On this gun it works the bolt and nothing else: the magazine is the support hand's job, so
     * the firing grip is kept through every reload and only released to cycle.
     *
     * <p>{@code bolt}'s own keyframes run {@code 0.25…0.85} of its 1.27s clip, so the hand is on the handle by
     * {@code 0.20} and peeling off it by {@code 0.90}; the reloads work the bolt late, at {@code 0.69…0.78}.
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.05F, 0.20F);
            float pulled = HandMotion.bump(progress, 0.20F, 0.50F, 0.92F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.55F, 0.68F);
            float pulled = HandMotion.bump(progress, 0.68F, 0.78F, 1.0F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
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
