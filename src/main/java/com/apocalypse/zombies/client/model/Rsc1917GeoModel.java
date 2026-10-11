package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.Rsc1917Item;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the RSC M1917: which geometry file bakes, which texture skins it, which clip
 * file feeds the controller. Paths are written out explicitly so the layout matches the AWM's exactly.
 *
 * <p>It also owns the two things the first-person hands need: where the gun is this frame ({@link #frame}) and
 * where the hands go on it ({@link #rightHand}, {@link #leftHand}). Both live here rather than in the renderer
 * because they are facts about the model — the numbers below are read straight off the geo file's cubes.</p>
 *
 * <p><b>The rig (17 bones, 与 geo 的契约):</b> {@code root, move, body, barrel, forend, cover, bolt,
 * mag_cover, clip, casing, trigger, safety, magazine, additional_magazine, hand_l, camera, constraint}.
 * Everything the clips animate lives under {@code move}. Three of those bones are the reason the hand targets
 * below differ from the M1's:</p>
 * <ul>
 *   <li>{@code mag_cover} — the magazine cover, hinged at its <em>front</em>, swinging forward and down. It is
 *       how the well opens, and it is why this rifle's reload is a from-below motion rather than the M1's
 *       from-above one.</li>
 *   <li>{@code clip} — the five-round en-bloc clip, which travels <em>up</em> into the fixed magazine through
 *       that open cover. In the geo it is hidden until the cover is shut; the gate that enforces that lives in
 *       the clip data (父代理的 {@code tools/check_rsc_1917_anim.py}), not here.</li>
 *   <li>{@code bolt} — the bolt <em>and</em> its charging handle and actuating rod. On the RSC the handle sits
 *       on the right of the receiver and translates along the bore axis only (it does not rotate, unlike a
 *       Mosin's turned-down handle), so the hand that works it slides straight back and straight forward.</li>
 * </ul>
 *
 * <p>There is no {@code clip_latch} bone: that is an M1 part. An RSC is unloaded through the cover, which the
 * right hand works, so the left hand never leaves the fore-end.</p>
 *
 * <p><b>手部目标点的来源：</b>下面六个点在 {@code rsc_1917.geo.json} 产出后<b>直接按它的 cube 原点实测</b>（与
 * {@link GunFrame#toCamera} 期望的坐标是同一套：geo 里 {@code origin} 写的那套，右为 −x、上为 +y、枪口为
 * −z）。左手的支撑点直接取自 geo 里那只 {@code hand_l} 标记方块的中心 —— 那是美术自己标出来的握点。仍留
 * 待校准的是 {@link Rsc1917Item} 里那一组 ADS/显示数值（{@code ADS_X/ADS_Y/DISPLAY_*}）。</p>
 */
public class Rsc1917GeoModel extends GeoModel<Rsc1917Item> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/rsc_1917.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/rsc_1917.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/rsc_1917.animation.json");

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

    /** The firing grip: the hand wrapped round the wrist of the stock, just behind the trigger.
     *  实测：扳机 rear z=0.30，托颈（body 在 z 1.5–3.0 的方块）下缘 y=−0.67 ⇒ 掌心在 z≈1.45、y≈−0.35。 */
    private static final float[] GRIP = {-0.12F, -0.35F, 1.45F};

    /**
     * Below the open magazine well, where the en-bloc clip is pressed <em>up</em> into the fixed magazine.
     *
     * <p>This is the single biggest difference from the M1's hand targets. An M1's clip is pressed down into the
     * well from above the receiver (M1: y 2.75, above a body that runs 0.84–2.85); an RSC's clip enters from
     * below, through the cover that has swung forward and down out of the way, so the hand comes up from under
     * the rifle rather than down onto it. 实测：弹匣井底 {@code magazine} 骨 y=−1.5、夹位 z≈−0.6
     * （{@code clip} 骨 pivot [0, −0.92, −0.6]，方块 z −1.15…−0.03），所以手在井底再往下约 0.6。</p>
     */
    private static final float[] CLIP = {-0.02F, -2.10F, -0.60F};

    /**
     * The magazine cover, at its free (rear) end — where the right hand goes to swing it open and to latch it
     * shut. 实测：{@code mag_cover} 骨 pivot [0, −1.5, −1.16] 是<b>前端</b>铰链，方块铺到 z=0.02；盖板
     * 本身在 y −1.60…−1.46，手从这块板的下方把它掀开。
     */
    private static final float[] COVER = {-0.05F, -1.75F, -0.05F};

    /**
     * The charging handle, on the right of the receiver — the part an RSC's right hand actually works. It
     * translates along the bore axis only (no rotating handle), so this target never leaves the receiver's
     * right flank in x or y. 实测：机柄那几块方块的 −x 侧伸出到 x=−0.46…−0.28，y −0.13…0.15，
     * z 0.92…1.48（静止位）⇒ 掌心点取 (−0.45, 0, 1.20)。
     */
    private static final float[] BOLT = {-0.45F, 0.00F, 1.20F};

    /** The support hand, flat under the fore-end ahead of the receiver.
     *  实测：geo 里那只 {@code hand_l} 标记方块的中心 (0, −0.83, −6.16)；x 比中心略偏 +0.20，与 M1 的左手
     *  偏置一致（M1 的 {@code SUPPORT} 也写 +0.20）。 */
    private static final float[] SUPPORT = {0.20F, -0.83F, -6.16F};

    /**
     * Where the right hand is thrown once the clip is home: up and to the <em>right</em> (−x) of the receiver,
     * out of the path of the bolt and of the closing cover. It saves a Garand thumb just as much as it does on
     * an M1, because the bolt runs home the moment the clip is pressed in. 实测：机柄 (−0.45, 0, 1.20) 的右上方。
     */
    private static final float[] CLEAR = {-0.95F, 0.75F, 1.30F};

    /** How far the charging handle travels rearward, in model pixels — the hand pulls back with it.
     *  Must equal the bolt channel's travel in {@code rsc_1917.animation.json}, or the hand lets go of the
     *  handle halfway through the pull. 实测：{@code bolt} 骨的 position z 在 bolt / shoot / reload_* 里都
     *  顶到 1.36（= 85 mm，按本模型 21.42 u ≈ 1.31 m 的比例）。 */
    private static final float BOLT_TRAVEL = 1.36F;

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(Rsc1917Item animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(Rsc1917Item animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(Rsc1917Item animatable) {
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
     * the clip has already put the part down reads as a mistake. All fractions are of the clip's own length, so
     * they line up with the sound cue tables in {@link Rsc1917Item}:
     * <ul>
     *   <li>{@code bolt} — the manual rack: grip the handle, pull rearward over {@code 0.17…0.62} of the clip
     *       and let it run home by {@code 0.92}. Straight back, straight forward: no rotation, because the
     *       RSC's charging handle does not turn.</li>
     *   <li>{@code reload_empty} — cover open, spent clip out, fresh clip <em>up</em> from below
     *       ({@code 0.18…0.39}), clear, and then — because the RSC does not hold its bolt open — an actual
     *       rack of the charging handle over {@code 0.50…0.80} to chamber the first round.</li>
     *   <li>{@code reload_tactical} — the same cover-and-clip sequence with a round still chambered, so no rack:
     *       cover open, clip swapped from below ({@code 0.30…0.52}), cover latched shut.</li>
     * </ul>
     * There is no {@code single_load} branch: an RSC has no single-round top-up drill.
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            float toHandle = HandMotion.ramp(progress, 0.08F, 0.18F);
            float pulled = HandMotion.bump(progress, 0.16F, 0.38F, 0.82F);
            return HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
        }
        if ("reload_empty".equals(action)) {
            // 真机空仓换弹，时刻与本类上面那张 RELOAD_EMPTY_SOUNDS 表同一套（全长 76 tick）：
            // 0.03–0.13 开弹匣盖（铰链在前端，向前下敞开）→ 0.18–0.30 空漏夹随盖脱出、右手去取新漏夹
            // → 0.32–0.39 从**下方**把新漏夹压进固定弹匣（夹在 0.395 落位）→ 0.42–0.50 向右上甩开让路
            // → 0.50–0.60 回到拉机柄 → 0.60–0.80 拉到底再放回 → 0.84–0.96 收回握把。
            // 本枪**无挂机**，所以这一拉是真需要的，这正是与 M1 的 reload_empty 最大的差别
            // （M1 枪机已被挂机爪咬在后退位，不用再拉）。
            float toCover = HandMotion.ramp(progress, 0.03F, 0.14F);
            float toClip = HandMotion.ramp(progress, 0.16F, 0.30F);
            float press = HandMotion.ramp(progress, 0.31F, 0.42F);
            float clear = HandMotion.ramp(progress, 0.44F, 0.52F);
            float toHandle = HandMotion.ramp(progress, 0.53F, 0.58F);
            float pulled = HandMotion.bump(progress, 0.57F, 0.65F, 0.75F);
            float home = HandMotion.ramp(progress, 0.78F, 0.94F);
            float[] p = HandMotion.lerpThenShift(out, GRIP, COVER, toCover, 0.0F, 0.0F, 0.0F);
            HandMotion.lerp(p, p, CLIP, toClip);
            HandMotion.lerpThenShift(p, p, CLEAR, press, 0.0F, 0.0F, 0.0F);
            HandMotion.lerp(p, p, BOLT, toHandle);
            // 手随拉机柄一起后拉：lerp 的起止都是当前点，只是叠一个位移（HandMotion 没有单独的 shift）。
            HandMotion.lerpThenShift(p, p, p, 1.0F, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
            HandMotion.lerp(p, p, GRIP, home);
            return p;
        }
        if ("reload_tactical".equals(action)) {
            // 战术换弹（全长 58 tick）：膛内仍有一发，所以**不用拉机柄**。0.03–0.14 开盖、0.30–0.42 残漏夹
            // 随盖脱出并换上新夹、0.44–0.52 从下方压到位（夹在 0.517 落位）、0.60–0.72 向右上甩开、
            // 0.74–0.90 合盖咬榫后收回握把。左手全程留在护木上（本枪没有 M1 那样的卡榫要按）。
            float toCover = HandMotion.ramp(progress, 0.03F, 0.14F);
            float toClip = HandMotion.ramp(progress, 0.16F, 0.30F);
            float press = HandMotion.ramp(progress, 0.30F, 0.43F);
            float clear = HandMotion.ramp(progress, 0.44F, 0.52F);
            float toHandle = HandMotion.ramp(progress, 0.53F, 0.60F);
            float pulled = HandMotion.bump(progress, 0.58F, 0.65F, 0.76F);
            float home = HandMotion.ramp(progress, 0.78F, 0.94F);
            float[] p = HandMotion.lerpThenShift(out, GRIP, COVER, toCover, 0.0F, 0.0F, 0.0F);
            HandMotion.lerp(p, p, CLIP, toClip);
            HandMotion.lerpThenShift(p, p, CLEAR, press, 0.0F, 0.0F, 0.0F);
            HandMotion.lerp(p, p, BOLT, toHandle);
            HandMotion.lerpThenShift(p, p, p, 1.0F, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
            HandMotion.lerp(p, p, GRIP, home);
            return p;
        }
        if ("single_load".equals(action)) {
            // Shift+R 单发补弹（1.50 s）：0.30 s 拉机柄到底（0.20）、0.56 s 前仍全开（0.37）、
            // 0.60 s 手送到膛口、1.06 s 扶着机柄可控闭锁（0.71）。本枪没有挂机，机柄全靠手拉手放。
            float toHandle = HandMotion.ramp(progress, 0.02F, 0.18F);
            float pulled = HandMotion.bump(progress, 0.20F, 0.40F, 0.72F);
            float home = HandMotion.ramp(progress, 0.76F, 0.94F);
            float[] q = HandMotion.lerpThenShift(out, GRIP, BOLT, toHandle, 0.0F, 0.0F, BOLT_TRAVEL * pulled);
            HandMotion.lerpThenShift(q, q, CLIP, 0.55F * HandMotion.bump(progress, 0.24F, 0.40F, 0.62F),
                    0.0F, 0.0F, 0.0F);
            HandMotion.lerp(q, q, GRIP, home);
            return q;
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand keeps the rifle's balance point through everything — the RSC is a two-handed rifle and
     * the left hand <em>stays</em> on the fore-end. There is no clip-latch pin to press (that is an M1 part) and
     * the cover is worked by the right hand, so the left hand's only motion through either reload is the small
     * settle as the fresh clip goes up into the well, which keeps the wrist from locking rigid.
     *
     * <p>Otherwise it is a target rather than a constant because the gun itself moves under it, which
     * {@link #frame} already accounts for.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        float settle = 0.0F;
        if ("reload_empty".equals(action)) {
            // 从下方压夹时手掌略沉，压到位即回位（对应 clip 在 1.5 s 落位 = 全段的 0.395）。
            settle = 0.18F * HandMotion.bump(progress, 0.10F, 0.47F, 0.70F);
        } else if ("reload_tactical".equals(action)) {
            settle = 0.18F * HandMotion.bump(progress, 0.10F, 0.43F, 0.80F);
        }
        out[0] = SUPPORT[0];
        out[1] = SUPPORT[1] - settle;
        out[2] = SUPPORT[2];
        return out;
    }
}
