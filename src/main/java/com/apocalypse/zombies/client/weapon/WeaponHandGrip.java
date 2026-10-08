package com.apocalypse.zombies.client.weapon;

import com.apocalypse.zombies.item.GunItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.UseAnim;
import org.joml.Matrix4f;

/**
 * Holding the gun in the first person: let vanilla do the work, but take the attack swing out of it.
 *
 * <h2>Why</h2>
 * For a non-empty item, with nothing being used, vanilla's {@code ItemInHandRenderer.renderArmWithItem}
 * always applies two transforms:
 * <ol>
 *   <li>{@code applyItemArmTransform} — the hand base {@code (±0.56, −0.52 − 0.6·equip, −0.72)}.</li>
 *   <li>{@code applyItemArmAttackTransform} — the <b>sword swing</b>, up to {@code rotX −80°}. And
 *       {@code LivingEntity.swing} re-triggers it when the swing passes halfway, so an automatic weapon
 *       on left click makes the gun <b>nod up and down in the hand</b> continuously.</li>
 * </ol>
 * Our arms follow the {@code move} bone, so they cannot follow that swing — the result looks like the gun
 * slipping and shaking in the hand.
 *
 * <h2>What</h2>
 * Implement Forge's {@code IClientItemExtensions.applyForgeHandTransform} and return {@code true} (handled;
 * vanilla skips straight to rendering), keeping only the base translation. The firing kick is pushed by the
 * {@code move} bone instead (the clips own it), and because {@link GunFrame} records that bone for the arms,
 * <b>the gun moves and the hands follow</b>.
 *
 * <p>It also owns the hold stance: at the hip the body sits down and to the right with a little yaw and roll
 * ({@link GunPose}), and it goes to zero as the sight comes up, where the offset the gun asks for places the
 * sight line on the centre of the screen. The first-person enlargement ({@link GunItem#firstPersonScale()})
 * slots in between the two — see the note where it is applied.
 */
public final class WeaponHandGrip {

    /** Vanilla hand base (right hand +0.56 / left −0.56), in camera space. */
    public static final float BASE_X = 0.56F;
    public static final float BASE_Y = -0.52F;
    public static final float BASE_Z = -0.72F;

    /**
     * How far into the "raise the item" ramp this frame is (0 = settled, 1 = just swapped in).
     * Vanilla offsets the item by {@code −0.6·equip} in Y; the arms read the same value
     * ({@link WeaponArms#baseY()}) or they part company with the gun during a swap.
     */
    public static volatile float equipNow;

    /**
     * The most re-raise allowed.
     *
     * <p>Vanilla's {@code ItemInHandRenderer.tick} pulls {@code mainHandHeight} towards
     * {@code attackStrengthScale³}, and every attack resets the attack-strength counter (Forge's requip test
     * joins in), so equip can spike to 1 and drop the item by up to 0.6 blocks. The arms use the same equip, so
     * gun and hands sink together — visible as the weapon dropping whenever it fires or reloads, which for an
     * automatic weapon is meaningless. Clamped to 0.10 (0.06 blocks): enough to keep the "rises into the hand"
     * on a swap.
     */
    private static final float EQUIP_MAX = 0.10F;

    /**
     * Firing recoil as a pitch <b>about the hand</b> (degrees × {@link GunRecoil#value()}) — the bolt-action
     * answer: muzzle up, butt down. A positive angle is the muzzle (−Z, the front) rising and the butt (+Z)
     * settling, which is what a shouldered rifle does. The pivot is the stance origin, which is roughly the
     * grip, so both arms swing about the same point and the hands stay on the weapon.
     */

    /** Reused by {@link #apply} (single-threaded client render). */
    private static final Matrix4f SCRATCH = new Matrix4f();

    /** 诊断节流（{@code ClientEvents.DIAG_AIM} 打开时每 2 秒一行）。 */
    private static long lastDiag;

    /**
     * Writes the held gun's sight-up offset into {@link GunPose} (camera space, blocks), where both the gun and
     * the arms read it from.
     *
     * <p>Doing it here rather than on the {@code move} bone matters: keyframes override a bone, so an animation
     * that moves {@code move} (a reload dipping the weapon) would cancel the offset and the gun would drop out
     * of the sight mid-reload. A pose transform we fill in ourselves always applies.
     */
    public static void pushAds(GunItem gun) {
        if (gun == null) {
            GunPose.clearAds();
            return;
        }
        GunPose.setAds(gun.adsX(), gun.adsY(), gun.adsZ(), 0.0F, 0.0F, gun.firePitch() * GunRecoil.value(),
                gun.adsPitch(), gun.adsYaw());
    }

    /**
     * 姿态矩阵的健全性检查：它必须是「一个旋转 + 一小段平移」。
     *
     * <p><b>为什么需要</b>：实机上出现过「腰射正常、按住右键瞄准时枪与双手整层消失」。把所有代码路径逐条
     * 读过之后，这一层数学应当是正常的（量算与真代码对拍都指向同一个结果），但<b>完全不可见</b>在几何上
     * 只可能是矩阵把顶点送去了一个看不见的地方 —— 而 ADS 本身位移不到半格，做不到这一点。所以这里不再
     * 假设"它一定没问题"：只要矩阵出现 NaN、行列式偏离 1、或平移超过 2 格，就判定它坏了，由调用方退回
     * 腰射姿态（那种姿态已实测可见）。正常路径上这个检查恒为真，没有副作用。</p>
     */
    private static boolean saneStance(Matrix4f m) {
        float tx = m.m30();
        float ty = m.m31();
        float tz = m.m32();
        if (!Float.isFinite(tx) || !Float.isFinite(ty) || !Float.isFinite(tz)) {
            return false;
        }
        if (Math.abs(tx) > 2.0F || Math.abs(ty) > 2.0F || Math.abs(tz) > 2.0F) {
            return false;
        }
        float det = m.m00() * (m.m11() * m.m22() - m.m12() * m.m21())
                - m.m01() * (m.m10() * m.m22() - m.m12() * m.m20())
                + m.m02() * (m.m10() * m.m21() - m.m11() * m.m20());
        return Float.isFinite(det) && Math.abs(det - 1.0F) < 0.25F;
    }

    /**
     * @return {@code true} = done, let vanilla skip its own transforms
     */
    public static boolean apply(PoseStack pose, LocalPlayer player, HumanoidArm arm,
                                ItemStack stack, float equip) {
        // Clear any leftovers another first-person renderer left on the stack before we place the gun: the gun
        // and the arms have to share one base (see WeaponArms.captureCleanPose).
        WeaponArms.restoreCleanPose(pose);
        equipNow = Math.min(Math.max(equip, 0.0F), EQUIP_MAX);
        // Draw/bow-style poses (holding right click) go back to vanilla; while aiming the arms are hidden anyway
        if (player.isUsingItem() && player.getUseItem() == stack
                && stack.getUseAnimation() != UseAnim.NONE) {
            return false;
        }
        int i = arm == HumanoidArm.RIGHT ? 1 : -1;
        pose.translate(i * BASE_X, BASE_Y - 0.6F * equipNow, BASE_Z);
        if (stack.getItem() instanceof GunItem gun) {
            pushAds(gun);
            // 诊断（DIAG_AIM 打开时）：确认这一帧的 ADS 到底是什么值 —— 它是唯一"只在瞄准时生效"的位移项。
            if (com.apocalypse.zombies.client.ClientEvents.DIAG_AIM) {
                long now = System.currentTimeMillis();
                if (now - lastDiag > 2000L) {
                    lastDiag = now;
                    com.apocalypse.zombies.ApocalypseZombies.LOGGER.info(
                            "[瞄准调试·姿态] item={} ads=({}, {}, {} | lift={} roll={} fire={} pitch={} yaw={}) scaleFps={}",
                            stack.getItem(),
                            String.format("%.4f", GunPose.ADS[0]), String.format("%.4f", GunPose.ADS[1]),
                            String.format("%.4f", GunPose.ADS[2]), String.format("%.2f", GunPose.ADS[3]),
                            String.format("%.2f", GunPose.ADS[4]), String.format("%.2f", GunPose.ADS[5]),
                            String.format("%.1f", GunPose.ADS[6]), String.format("%.1f", GunPose.ADS[7]),
                            String.format("%.2f", gun.firstPersonScale()));
                }
            }
            // First-person enlargement, and this is the only place it can go. Downstream of the hand base, so
            // the gun stays in the hand instead of sliding towards the eye; upstream of the stance, so the
            // stance's own offsets — the sight-up compensation above all — are multiplied by it, which is what
            // keeps the sight line on the centre of the screen. The item model's display block scales neither
            // (the base and the stance are both outside it), so the size cannot live there.
            float scale = gun.firstPersonScale();
            if (scale != 1.0F) {
                pose.scale(scale, scale, scale);
            }
            // Interpolated, so the stance, the run carry and the zoom all ramp on the very same curve
            float partialTick = net.minecraft.client.Minecraft.getInstance().getFrameTime();
            GunPose.matrix(com.apocalypse.zombies.client.GunAimState.getAimProgress(partialTick),
                    com.apocalypse.zombies.client.GunAimState.getSprintProgress(partialTick),
                    bobPhase(player, partialTick), SCRATCH);
            if (!saneStance(SCRATCH)) {
                // 保底：这一帧的姿态矩阵退化了。宁可让枪停在腰射位（那种姿态已实测可见），
                // 也不能让它连同双手一起从画面上消失 —— 见 saneStance 的注释。
                com.apocalypse.zombies.ApocalypseZombies.LOGGER.warn(
                        "[S686] 姿态矩阵退化，已回退到腰射姿态：item={}", stack.getItem());
                GunPose.matrix(0.0F, 0.0F, 0.0F, SCRATCH);
            }
            pose.mulPoseMatrix(SCRATCH);
        }
        return true;
    }

    /**
     * Where the run cycle is, in radians, for the gun's bob — one full cycle per two blocks of ground
     * covered, the same rhythm vanilla's own view bob rides, so the weapon steps <em>with</em> the camera
     * instead of fighting it.
     *
     * <p>Driven by ground covered rather than wall-clock time, for two reasons: the phase then stops when the
     * player does instead of the gun bobbing on the spot while a menu is open, and a change of speed reads as
     * a change of speed. {@code walkDistO}/{@code walkDist} are the previous and current tick's totals, so
     * interpolating between them keeps the bob continuous across a tick boundary like everything else here.
     */
    private static float bobPhase(LocalPlayer player, float partialTick) {
        return Mth.lerp(partialTick, player.walkDistO, player.walkDist) * (float) Math.PI;
    }

    private WeaponHandGrip() {
    }
}
