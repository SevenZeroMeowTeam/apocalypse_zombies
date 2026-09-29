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
