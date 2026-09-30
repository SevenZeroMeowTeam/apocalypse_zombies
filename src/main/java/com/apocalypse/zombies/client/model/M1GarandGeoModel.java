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

    /**
     * The clip-latch pin on the left of the receiver — what the left thumb presses in the tactical reload.
     * Read off the geo: the {@code clip_latch} bone pivots at (0.32, 1.72, -2.36) and its cubes span
     * y 1.62–1.78, so the palm comes to rest just above and inboard of the pin and the thumb falls on it.
     */
    private static final float[] LATCH = {0.26F, 1.90F, -2.30F};

    /**
     * Where the right hand is thrown once the clip is home: up and to the right of the receiver, out of the
     * path of the bolt. FM 23-5 asks for it in as many words — "Swing the right hand up and to the right to
     * clear the bolt" — and it is the difference between a Garand and a Garand thumb.
     */
    private static final float[] CLEAR = {-0.78F, 3.10F, -2.30F};

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
        if ("reload_empty".equals(action)) {
            // 真机空仓换弹（FM 23-5 "To load the rifle"）：枪机已被挂机爪咬在后退位，右手**不用再去拉
            // 导气杆**，直接从腰包取一支新漏夹压进井里（0.18…0.43，夹落位 1.2917 s —— 全段的 0.4306），
            // 压到位立刻**向右上甩开**给枪机让路，最后收回握把。
            float toClip = HandMotion.ramp(progress, 0.18F, 0.32F);
            float press = HandMotion.ramp(progress, 0.34F, 0.43F);
            float clear = HandMotion.ramp(progress, 0.45F, 0.56F);
            float home = HandMotion.ramp(progress, 0.64F, 0.82F);
            float[] p = HandMotion.lerpThenShift(out, GRIP, CLIP, toClip, 0.0F, -0.35F * press, 0.0F);
            HandMotion.lerp(p, p, CLEAR, clear);
            HandMotion.lerp(p, p, GRIP, home);
            return p;
        }
        if ("reload_tactical".equals(action)) {
            // 战术换弹：右手先拉导气杆到底并按住（0.03…0.10，真机换弹全程按住不放），左手按卡榫卸空夹，
            // 右手再压新夹（0.30…0.43），压到位后同样向右上甩开、收回握把。
            float pulled = HandMotion.bump(progress, 0.03F, 0.10F, 0.30F);
            if (progress < 0.30F) {
                float toHandle = HandMotion.ramp(progress, 0.02F, 0.06F);
                return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
            }
            float toClip = HandMotion.ramp(progress, 0.30F, 0.36F);
            float press = HandMotion.ramp(progress, 0.36F, 0.44F);
            float clear = HandMotion.ramp(progress, 0.46F, 0.58F);
            float home = HandMotion.ramp(progress, 0.66F, 0.84F);
            float[] p = HandMotion.lerpThenShift(out, BOLT, CLIP, toClip, 0.0F, -0.35F * press, 0.0F);
            HandMotion.lerp(p, p, CLEAR, clear);
            HandMotion.lerp(p, p, GRIP, home);
            return p;
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand keeps the rifle's balance point through everything — the Garand is held with it. On an
     * M1 that balance point is the receiver itself, so the tactical reload is the left hand's drill as much as
     * the right's: the palm comes back onto the left of the receiver and the thumb presses the clip latch —
     * "Place the palm of the left hand over the receiver and depress the clip latch with the left thumb" —
     * which is what {@code clip_latch} does in the animation between 0.2917 s and 0.7917 s.
     *
     * <p>Otherwise it is a target rather than a constant because the gun itself moves under it, which
     * {@link #frame} already accounts for; the only change is a small settle as the clip goes in, to keep the
     * wrist from locking rigid.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("reload_tactical".equals(action)) {
            // 时刻全部按剪辑长度归一化（reload_tactical 2.6 s）：clip_latch 在 0.2917 s（= 0.112）
            // 被按入、0.7917 s（= 0.3045）回位，所以手掌 0.06…0.11 回到机匣左侧、0.112 拇指同步下压、
            // 一直按到销子回位之后（0.31…0.42）才回护木。
            float there = HandMotion.ramp(progress, 0.06F, 0.11F);
            float press = HandMotion.ramp(progress, 0.112F, 0.14F);
            float back = HandMotion.ramp(progress, 0.31F, 0.42F);
            float[] p = HandMotion.lerpThenShift(out, SUPPORT, LATCH, there, 0.0F, -0.10F * press, 0.0F);
            HandMotion.lerp(p, p, SUPPORT, back);
            return p;
        }
        float settle = 0.0F;
        if ("reload_empty".equals(action)) {
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
