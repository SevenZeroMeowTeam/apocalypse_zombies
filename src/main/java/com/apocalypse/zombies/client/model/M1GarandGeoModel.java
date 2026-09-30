package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.M1GarandItem;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the M1 加兰德: which geometry file bakes, which texture skins it, which clip
 * file feeds the controller. Paths are written out explicitly so the layout matches the AWM's exactly.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — the numbers below are read straight off the geo file's cubes.
 */
public class M1GarandGeoModel extends GeoModel<M1GarandItem> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/m1_garand.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/m1_garand.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/m1_garand.animation.json");

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

    /** The firing grip: the hand wrapped round the wrist of the stock, behind the trigger. */
    private static final float[] GRIP = {-0.12F, 1.30F, 0.70F};

    /**
     * Above the open receiver, where the en-bloc clip is pressed home.
     *
     * <p>Sits over the clip well at 601–700 mm from the muzzle — true-gun calibration: the well's
     * front wall is the breech face (24" barrel → 610 mm) and its rear wall is flush with the
     * rear-sight base / op-rod handle front at 700 mm. See {@code tools/m1_well_shift.py}.
     */
    private static final float[] CLIP = {-0.05F, 2.75F, -3.29F};

    /** The op-rod handle, on the right of the receiver — what a Garand's right hand actually works. */
    private static final float[] BOLT = {-0.40F, 2.28F, -2.60F};

    /** The support hand, flat under the fore-end ahead of the receiver. */
    private static final float[] SUPPORT = {0.20F, 1.02F, -6.00F};

    /** How far the op-rod handle travels rearward, in model pixels — the hand pulls back with it.
     *  Must equal the bolt channel's travel in {@code m1_garand.animation.json} (全行程 1.36u = 85mm,
     * 够退过漏夹末弹底缘), or the hand lets go of the handle halfway through the pull. */
    private static final float BOLT_TRAVEL = 1.36F;

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(M1GarandItem animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(M1GarandItem animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(M1GarandItem animatable) {
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
     *   <li>{@code bolt} pulls rearward over {@code 0.17…0.62} of the clip and is home again by {@code 0.92}.</li>
     *   <li>The reloads press the clip over roughly {@code 0.15…0.35}, then work the op-rod over
     *       {@code 0.61…0.78}.</li>
     * </ul>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.05F, 0.20F);
            float pulled = HandMotion.bump(progress, 0.17F, 0.45F, 0.92F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }
        if ("single_load".equals(action)) {
            // 单发补弹：右手始终在导气杆手柄上 —— 拉到底、挂住等左手送弹、再扶着机柄让它可控闭锁。
            float toHandle = HandMotion.ramp(progress, 0.03F, 0.08F);
            float pulled = HandMotion.bump(progress, 0.06F, 0.19F, 0.78F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            // 三次到访，顺序跟动画一致：先拉导气杆（0.03…0.10）、再压新夹（0.30…0.44）、最后跟着
            // 枪机前冲把它送回（0.49…0.60）。原来写成"先压夹后拉栓"，跟剪辑里的顺序是反的。
            float pulled = HandMotion.bump(progress, 0.03F, 0.10F, 0.30F);
            if (progress < 0.30F) {
                float toHandle = HandMotion.ramp(progress, 0.02F, 0.06F);
                return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
            }
            if (progress < 0.45F) {
                float toClip = HandMotion.ramp(progress, 0.30F, 0.36F);
                float press = HandMotion.ramp(progress, 0.36F, 0.44F);
                return HandMotion.lerpThenShift(out, BOLT, CLIP, toClip, 0.0F, -0.35F * press, 0.0F);
            }
            float toHandle = HandMotion.ramp(progress, 0.45F, 0.52F);
            float home = HandMotion.bump(progress, 0.49F, 0.53F, 0.62F);
            float[] back = HandMotion.lerp(out, CLIP, BOLT, toHandle);
            back[2] += BOLT_TRAVEL * home;
            return back;
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand stays on the fore-end through everything — the Garand is held with it. It is a target
     * rather than a constant because the gun itself moves under it, which {@link #frame} already accounts for;
     * the only change is a small settle as the clip goes in, to keep the wrist from locking rigid.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        float settle = 0.0F;
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            settle = 0.18F * HandMotion.bump(progress, 0.10F, 0.35F, 0.80F);
        } else if ("single_load".equals(action)) {
            // 单发补弹：左手离开护木去送那一发（0.30…0.82 之间一个来回）。
            settle = 0.18F * HandMotion.bump(progress, 0.30F, 0.55F, 0.82F);
        }
        out[0] = SUPPORT[0];
        out[1] = SUPPORT[1] - settle;
        out[2] = SUPPORT[2];
        return out;
    }
}
