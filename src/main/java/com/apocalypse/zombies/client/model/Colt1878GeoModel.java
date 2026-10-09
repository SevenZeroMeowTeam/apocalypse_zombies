package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.Colt1878Item;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for 短管喷（Coach Gun）: which geometry bakes, which texture skins it, which clips
 * feed the controller, and where the first-person hands go on it.
 *
 * <p>几何与 S686 不是同一把：S686 是**上下双管**，这把是**并排双管**（Colt 1878 型教练枪，管长 20 英寸）。
 * 所以本类所有手部目标点都是**按这份 geo 的方块重新量的**，不是抄 S686 的数字 —— 两把枪的机匣、
 * 前托、托颈位置都不一样（本枪全长只有 0.93 格，机匣 16%、托 30%）。</p>
 *
 * <h2>双手分工（与折开式双管的实际操作一致）</h2>
 * <b>右手</b>全程握在托颈上、扣着扳机：开膛杆是机匣顶上的一根拇指拨杆，正压在持枪手上面，
 * 所以开膛的那只手根本不需要离开扳机 —— 全枪的折开动作都在 {@code barrel} 骨上完成。
 *
 * <p><b>左手</b>干其余的活：平时托在前托上，而前托（{@code forend}）是 {@code barrel} 骨的子骨，
 * 折开时枪管把它一起带下去，所以支撑手**不需要在 Java 里再写一遍折开动作** —— 这就是
 * {@link #onBarrel} 那条链的意义。</p>
 *
 * <p>唯一前托管不了的是**装弹**：新弹挂在 {@code bolt_loaded} / {@code shell_upper} 这类自有骨骼上，
 * 有自己的关键帧，所以那几个窗口里手要改挂在弹上，合膛之前再回到前托 —— 见 {@link #leftHand}。</p>
 */
public class Colt1878GeoModel extends GeoModel<Colt1878Item> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/colt_1878.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/colt_1878.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/colt_1878.animation.json");

    /** This frame's pose, written by the renderer as it draws and read by the arms next frame. */
    public static final GunFrame frame = new GunFrame();

    private static final Matrix4f SCRATCH = new Matrix4f();
    private static final Matrix4f BARREL_CHAIN = new Matrix4f();
    private static final Matrix4f SHELL_CHAIN = new Matrix4f();
    private static boolean partsValid;

    private static final float[] BREECH_AT = new float[3];
    private static final float[] SHELL_AT = new float[3];
    private static final float[] FOREND_AT = new float[3];
    private static final Vector3f V = new Vector3f();

    // ------------------------------------------------------------------ hand targets (model pixels)
    //
    // 下面每个数字都是从 tools/colt_1878_geo.js 的方块上量的（16 u = 1 格）：
    //   机匣  z −1.216…+1.216, y −0.608…+0.608   管轴 y 0.392, 管口 z −9.04, 膛口后端 z −0.916
    //   前托  z −6.28…−0.976, 下缘 y 0.141
    //   托颈  z +1.216…+1.636；枪托到 z +5.70，垂直下垂 0.96

    /**
     * 持枪手：握在托颈上、食指搭着扳机。托颈跑 z +1.22…+1.64、y 大约 −0.5…+0.5，
     * 所以落点取它中段略靠后、并压到掌根该在的高度。
     */
    private static final float[] GRIP = {0.00F, -0.34F, 1.92F};

    /** 支撑手：前托管下面（本枪前托下缘 y 0.141，横向包到 ±0.70），取中后段。 */
    private static final float[] FOREND = {0.00F, 0.13F, -3.60F};

    /**
     * 弹袋：折开式没有弹仓，两发新弹是从玩家腰间的弹袋里摸出来的。
     *
     * <p>这个点是全场唯一**不挂在枪管链上**的（见 {@link #onBarrel} 的对照）：手伸向的是玩家自己的身体，
     * 而不是折下去的枪管；跟随枪管一起摆动的弹袋是说不通的。它只吃 {@code move} 链（整枪姿态），
     * 所以玩家转身时它跟着晃 —— 这一点与 S686 相同，因为弹袋在身体上，与枪的型号无关。</p>
     */
    private static final float[] AMMO = {-2.00F, -9.80F, 8.90F};

    /**
     * 膛面：两个弹膛之间、弹壳头部稍后。表达在枪管链上，所以跟着枪一起折下去。
     *
     * <p>故意偏左下一点：第一人称里弹膛正压在准线上，手停在正中会挡住玩家正在看的东西；
     * 从左下进来读起来像"从机匣下面摸上去"，也让敞开的弹膛和上膛的两发弹都留在视野里。</p>
     */
    private static final float[] BREECH = {-0.20F, 0.19F, -0.92F};

    /** 上头那发新弹的弹体（{@code bolt_loaded} 在膛口附近），手捏的位置。 */
    private static final float[] SHELL = {-0.15F, 0.42F, -1.00F};

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(Colt1878Item animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(Colt1878Item animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(Colt1878Item animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose and the two part chains the hands ride.
     *
     * @param itemRenderTranslations GeckoLib's {@code itemRenderTranslations} for this item, off the renderer
     * @param moveBone the bone the clips animate (everything is under it), or {@code null} before it exists
     * @param barrelBone the {@code barrel} group, which the fold clips rotate — the fore-end's chain
     * @param shellBone the {@code bolt_loaded} group, which the reload clips drive — the hand's chain while loading
     * @param aim aim progress this frame, used by the arms for their shoulder push
     */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, CoreGeoBone barrelBone,
                               CoreGeoBone shellBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            partsValid = false;
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);

        partsValid = barrelBone != null && shellBone != null;
        if (partsValid) {
            GunFrame.partChain(BARREL_CHAIN, barrelBone, GunFrame.MOVE_BONE);
            GunFrame.partChain(SHELL_CHAIN, shellBone, GunFrame.MOVE_BONE);
        }
    }

    /**
     * A rest point of the barrel group, moved wherever the clip has folded it this frame.
     *
     * <p>Without a captured chain the rest point comes back unchanged: a hand in the wrong place for one
     * frame beats an arm drawn to nowhere.</p>
     */
    private static float[] onBarrel(float[] rest, float[] out) {
        System.arraycopy(rest, 0, out, 0, 3);
        if (!partsValid) {
            return out;
        }
        V.set(out[0], out[1], out[2]);
        BARREL_CHAIN.transformPosition(V);
        out[0] = V.x;
        out[1] = V.y;
        out[2] = V.z;
        return out;
    }

    /** As {@link #onBarrel}, for a point of the fresh shells. */
    private static float[] onShell(float[] rest, float[] out) {
        System.arraycopy(rest, 0, out, 0, 3);
        if (!partsValid) {
            return out;
        }
        V.set(out[0], out[1], out[2]);
        SHELL_CHAIN.transformPosition(V);
        out[0] = V.x;
        out[1] = V.y;
        out[2] = V.z;
        return out;
    }

    /**
     * The firing hand: holds the grip through every clip — the top lever is worked by this hand's thumb, right
     * above it, so there is no clip where it has to leave the trigger.
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand: fore-end, breech, fresh shells, back to the fore-end.
     *
     * <p>时间窗对齐**本枪自己的动画关键帧**（不是照抄 S686 的百分比），因为手到得比零件晚一拍就会读成失误。
     * 本枪两段换弹的动作点取自 {@code tools/colt_1878_anim.js}：</p>
     *
     * <ul>
     *   <li>{@code reload_tactical}（3.0 s）— 手离开前托去弹袋 {@code 0.30}，夹弹回到膛口 {@code 0.53}，
     *       挂在弹上送进膛 {@code 0.63}，弹到位后回到前托 {@code 0.81}；枪管在 {@code 0.87} 合上。</li>
     *   <li>{@code reload_empty}（3.6 s，故意更慢）— 同样的顺序，整体后移：{@code 0.30 / 0.56 / 0.65 / 0.82}，
     *       枪管 {@code 0.87} 合上。</li>
     *   <li>{@code bolt} — 只折开退壳、不装弹，整段动作都在枪管骨上，手一直贴前托。</li>
     *   <li>其余（{@code static_idle} / {@code draw} / {@code shoot} / ADS 两段）— 都在前托。</li>
     * </ul>
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        if ("bolt".equals(action)) {
            return onBarrel(FOREND, out);
        }

        if ("reload_tactical".equals(action) || "reload_empty".equals(action)) {
            boolean empty = "reload_empty".equals(action);

            // 先离开枪身：折开式没有弹仓，两发新弹在玩家腰间的弹袋里，这一段是全程唯一不吃枪管链的
            float toAmmo = HandMotion.ramp(progress, 0.30F, empty ? 0.47F : 0.45F);
            // 带着弹回到膛口，此时空壳正往外走
            float toBreech = HandMotion.ramp(progress, empty ? 0.56F : 0.53F, empty ? 0.65F : 0.63F);
            // 新弹翻身开始进膛，手改挂在弹上
            float toShell = HandMotion.ramp(progress, empty ? 0.65F : 0.63F, empty ? 0.74F : 0.73F);
            // 弹到位，手离弹回前托，枪管随后合上
            float toForend = HandMotion.ramp(progress, empty ? 0.82F : 0.81F, 0.88F);

            onBarrel(FOREND, out);
            HandMotion.lerp(out, out, AMMO, toAmmo);
            HandMotion.lerp(out, out, onBarrel(BREECH, BREECH_AT), toBreech);
            HandMotion.lerp(out, out, onShell(SHELL, SHELL_AT), toShell);
            return HandMotion.lerp(out, out, onBarrel(FOREND, FOREND_AT), toForend);
        }

        return onBarrel(FOREND, out);
    }
}
