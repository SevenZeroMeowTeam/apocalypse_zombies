package com.apocalypse.zombies.client.weapon;

import com.apocalypse.zombies.client.model.AWMGeoModel;
import java.util.Locale;
import com.apocalypse.zombies.client.model.CrossbowGeoModel;
import com.apocalypse.zombies.client.model.M1GarandGeoModel;
import com.apocalypse.zombies.client.model.MosinNagantGeoModel;
import com.apocalypse.zombies.client.model.S686GeoModel;
import com.apocalypse.zombies.client.model.UziGeoModel;
import com.apocalypse.zombies.item.AWMItem;
import com.apocalypse.zombies.item.CrossbowItem;
import com.apocalypse.zombies.item.GunItem;
import com.apocalypse.zombies.item.M1GarandItem;
import com.apocalypse.zombies.item.MosinNagantItem;
import com.apocalypse.zombies.item.S686Item;
import com.apocalypse.zombies.item.UziItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.player.PlayerRenderer;
import net.minecraft.util.Mth;
import net.minecraft.world.item.ItemStack;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * The two first-person arms that hold the gun.
 *
 * <h2>Why they have to be drawn by hand</h2>
 * Vanilla draws an arm only when the hand is <em>empty</em> — {@code ItemInHandRenderer.renderArmWithItem}
 * branches on {@code itemStack.isEmpty()} and for anything else renders the item alone. So a held gun floats
 * with nothing holding it. These arms are drawn on {@code RenderHandEvent} on top of the vanilla pass, using
 * the player's own skin, which is why they can be put anywhere the weapon needs them.
 *
 * <h2>How a hand is placed</h2>
 * {@code PlayerRenderer.renderHand} resets the pose first, so in the pose stack it is handed the arm box
 * occupies {@code y[0, 0.75]} — the origin end is the shoulder, the {@code +0.75} end is the hand — and it is
 * centred on {@code x = ±0.375}. So "put the hand at H" is: translate the origin to
 * {@code H − s·R·(xCentre, 0.75, 0)}, with the orientation given by the shoulder → hand direction plus a roll
 * about the arm's own axis (which way the palm faces). The arms stretch along their length to reach, and are
 * never scaled sideways, so a long reach reads as a straight arm rather than a fat one.
 *
 * <p>The target points come from each weapon (in <b>model pixels</b>, converted by {@link GunFrame}), so the
 * arms follow the aim, the reload and the bolt on their own. No weapon logic is repeated here.
 */
public final class WeaponArms {

    /**
     * Shoulder points (camera space, blocks). Fixed: the further the hand is, the more the arm stretches.
     *
     * <p><b>TaCZ's entry angle, not vanilla's.</b> TaCZ's reference screenshots show the forearms coming
     * <em>diagonally in from the bottom corners</em> and running up to the grips, so a large part of each
     * arm is on screen — measured on the reference, the skin-coloured mass spans y ≈ 59 % of the frame down
     * to the bottom edge. Ours used to sit at {@code (±0.55, −0.85, −0.80)}: almost vertically under the gun
     * and low enough that with the old carry pose only a sliver of pink ever crossed the bottom edge (480
     * skin pixels in the hip screenshot against TaCZ's 11 356).
     *
     * <p>These values are the reverse solution of "the forearms enter at the bottom corners": NDC
     * (±0.9, −1.30) at z = −0.85 uncovers {@code (±0.93, −0.77)}. Against the five guns' new carry pose that
     * gives arm lengths of 0.96 (right, Uzi) to 1.26 blocks (left) — a stretch of 1.28× … 1.68× of vanilla's
     * 0.75-block arm, which is what the arm box's length-only scale is for. Keep them <em>below</em> the
     * bottom edge (NDC y ≈ −1.3) so the upper arm stays out of frame and only the forearm crosses it.
     */
    private static final float[] SHOULDER_R = {0.93F, -0.77F, -0.85F};
    private static final float[] SHOULDER_L = {-0.88F, -0.77F, -0.85F};

    /**
     * How far the shoulders are pushed out when the sight is up.
     *
     * <p>Aiming narrows the gun's projection field of view ({@link GunPose#MODEL_FOV_HIP} →
     * {@link GunPose#MODEL_FOV_AIM}), which magnifies the model about 1.7× — and the shoulders sit less than
     * a block from the eye, so without some push the arms balloon into skin-coloured wedges that smear over
     * the sight. Pushing them out scales the arm with the magnification and keeps it looking the same.
     *
     * <p>Was 1.55 against the old shoulders at {@code (±0.55, −0.85, −0.80)}. Those were already close to
     * the hands (arm length ≈ 0.9 blocks); the new corner shoulders start at 1.7 blocks, so the same push
     * stretched the arm to 2.6× and it read as a noodle. At 1.15 the aimed arms stay at 1.42 blocks /
     * 1.89×, i.e. the same order as the hip's 1.28×–1.68×.
     */
    private static final float ADS_SHOULDER_PUSH = 1.15F;

    /** Vanilla arm length (blocks). */
    private static final float ARM_LEN = 0.75F;
    /** The arm box's x centre within the pose stack (blocks). */
    private static final float HALF = 0.375F;
    /** Arm thickness relative to vanilla's 0.25 blocks — slimmer, to block less of the view. */
    private static final float THICK = 0.85F;
    /** Roll about the arm's own axis (degrees): roughly turns the palm towards the gun. */
    private static final float ROLL_R = 155.0F;
    private static final float ROLL_L = 24.0F;

    // ------------------------------------------------------------------ clean base
    /**
     * The clean base of the first-person render chain.
     *
     * <p><b>Why</b>: other mods hang off the same {@code RenderHandEvent} and some of them (gun mods with their
     * own first-person renderer) write straight into the event's {@code PoseStack}. When the held item is not
     * theirs they draw nothing, but their edits can be <em>left behind on the stack</em> — and then vanilla's
     * pass for our gun, and our arms with it, are dragged along by the leftovers, which on screen looks like
     * the gun floating up and to the right, detached from the hands.
     *
     * <p><b>What</b>: at {@code HIGHEST} priority (before anyone touches it) this layer's pose and normal are
     * recorded, and before the arms — and before {@code applyForgeHandTransform} places the gun — the layer is
     * overwritten with that copy, so gun and hands always share one base. With nothing meddling it is a
     * no-op copy.
     */
    private static final Matrix4f CLEAN_POSE = new Matrix4f();
    private static final Matrix3f CLEAN_NORMAL = new Matrix3f();
    private static boolean cleanValid;

    /** Call on {@code RenderHandEvent} at {@code HIGHEST} priority: record this layer before anyone edits it. */
    public static void captureCleanPose(PoseStack pose) {
        CLEAN_POSE.set(pose.last().pose());
        CLEAN_NORMAL.set(pose.last().normal());
        cleanValid = true;
    }

    /** Overwrite this layer with the clean copy (see {@link #captureCleanPose}). */
    public static void restoreCleanPose(PoseStack pose) {
        if (!cleanValid) return;
        pose.last().pose().set(CLEAN_POSE);
        pose.last().normal().set(CLEAN_NORMAL);
    }

    /**
     * AWM: the <b>right</b> hand grips the wrist with the trigger finger, rises to the bolt handle during the
     * cycle and rides it back as the case is thrown, then returns to the grip; the <b>left</b> hand supports the
     * fore-end and only reaches down to the magazine while reloading.
     */
    public static void renderAwp(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                 String action, float progress) {
        render(mc, pose, buffer, light, AWMGeoModel.frame,
                AWMGeoModel.rightHand(action, progress, new float[3]),
                AWMGeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * M1 Garand: the <b>right</b> hand holds the wrist with the trigger finger and does <em>not</em> chase the
     * op-rod — the action is self-loading, so the hand stays put while firing; while reloading it lifts over the
     * receiver to press the clip home, then grabs the handle and follows the bolt into battery. The <b>left</b>
     * hand supports the fore-end throughout (the Garand is loaded one-handed, so the left hand holds the rifle
     * steady).
     */
    public static void renderM1Garand(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                      String action, float progress) {
        render(mc, pose, buffer, light, M1GarandGeoModel.frame,
                M1GarandGeoModel.rightHand(action, progress, new float[3]),
                M1GarandGeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * 莫辛-纳甘 M91/30: the <b>right</b> hand holds the wrist with the trigger finger and works the bolt
     * itself — a bolt gun does not cycle on its own, so it leaves the grip every shot, breaks the handle
     * open, drags it back and runs it home. While reloading it lifts over the receiver and presses the rounds
     * down into the fixed magazine one at a time, then closes the bolt on the last one. The <b>left</b> hand
     * supports the fore-end throughout: the rifle stays shouldered while it is fed.
     */
    public static void renderMosinNagant(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                         String action, float progress) {
        render(mc, pose, buffer, light, MosinNagantGeoModel.frame,
                MosinNagantGeoModel.rightHand(action, progress, new float[3]),
                MosinNagantGeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * 现代复合狩猎弩: the <b>left</b> hand does the work — it takes the string at the limb tips and straps it
     * back onto the latch over the {@code draw} clip, and over {@code reload_tactical} it goes to the side
     * quiver, lifts a bolt and lays it in the channel. The <b>right</b> hand stays on the pistol grip and
     * braces: the bow is pushed away from the shooter as the string comes back, and takes the small jolt of
     * the shot. That is the mirror image of the rifles, where the right hand runs the action.
     */
    public static void renderCrossbow(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                      String action, float progress) {
        render(mc, pose, buffer, light, CrossbowGeoModel.frame,
                CrossbowGeoModel.rightHand(action, progress, new float[3]),
                CrossbowGeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * Uzi: the <b>left</b> hand does everything, because the magazine sits inside the pistol grip and the
     * charging handle is on top of the receiver — neither is reachable by the firing hand without letting go of
     * the trigger, which is the last thing an SMG wants. So the <b>right</b> hand stays on the grip through
     * every clip; the left supports the front of the receiver, catches the magazine as it drops out of the
     * well, rides it down, slaps the fresh one home, and then reaches over the top to run the bolt.
     *
     * <p>Firing is the one clip where the left hand does not move: a blowback action cycles itself, so the
     * support hand just rides the fore-end while the gun shakes around it.</p>
     */
    public static void renderUzi(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                 String action, float progress) {
        render(mc, pose, buffer, light, UziGeoModel.frame,
                UziGeoModel.rightHand(action, progress, new float[3]),
                UziGeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * Gold Plate - S686: the <b>right</b> hand holds the grip through every clip, because the gun's one control
     * — the top lever — is a thumb latch sitting right above it, so opening the action never costs the trigger
     * hand its hold. The <b>left</b> hand carries the fore-end, which is the half of a break-action that moves:
     * the barrels fold 38° on their hinge, the fore-end goes with them, and so does the hand. While loading it
     * leaves the fore-end for the breech, takes the fresh pair of shells home, and is back on the fore-end to
     * ride the barrels shut.
     */
    public static void renderS686(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                  String action, float progress) {
        render(mc, pose, buffer, light, S686GeoModel.frame,
                S686GeoModel.rightHand(action, progress, new float[3]),
                S686GeoModel.leftHand(action, progress, new float[3]));
    }

    /**
     * Draws the arms for whichever of our guns is in hand, or nothing.
     *
     * <p>The gun answers for itself where its hands are: it knows which action is running
     * ({@link GunItem#action}) and how far through it is. Working that out here instead would mean this class
     * knowing every weapon's clips.
     */
    public static void renderHeld(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                                  String action, float progress) {
        ItemStack stack = mc.player == null ? ItemStack.EMPTY : mc.player.getMainHandItem();
        if (stack.getItem() instanceof CrossbowItem) {
            renderCrossbow(mc, pose, buffer, light, action, progress);
        } else if (stack.getItem() instanceof M1GarandItem) {
            renderM1Garand(mc, pose, buffer, light, action, progress);
        } else if (stack.getItem() instanceof MosinNagantItem) {
            renderMosinNagant(mc, pose, buffer, light, action, progress);
        } else if (stack.getItem() instanceof AWMItem) {
            renderAwp(mc, pose, buffer, light, action, progress);
        } else if (stack.getItem() instanceof UziItem) {
            renderUzi(mc, pose, buffer, light, action, progress);
        } else if (stack.getItem() instanceof S686Item) {
            renderS686(mc, pose, buffer, light, action, progress);
        } else {
            forgetFrames();
        }
    }

    /** Drops every capture — nothing is in hand, so there is no pose for the arms to ride. */
    public static void forgetFrames() {
        CrossbowGeoModel.frame.invalidate();
        M1GarandGeoModel.frame.invalidate();
        MosinNagantGeoModel.frame.invalidate();
        AWMGeoModel.frame.invalidate();
        UziGeoModel.frame.invalidate();
        S686GeoModel.frame.invalidate();
    }

    private static void render(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                               GunFrame frame, float[] rightPx, float[] leftPx) {
        float aim = Mth.clamp(frame.aim(), 0.0F, 1.0F);
        float push = 1.0F + (ADS_SHOULDER_PUSH - 1.0F) * aim;
        render(mc, pose, buffer, light, frame, rightPx, leftPx,
                scale(SHOULDER_R, push), scale(SHOULDER_L, push));
    }

    /** Scales a shoulder vector about the eye (camera space). */
    private static float[] scale(float[] v, float k) {
        return new float[]{v[0] * k, v[1] * k, v[2] * k};
    }

    private static void render(Minecraft mc, PoseStack pose, MultiBufferSource buffer, int light,
                               GunFrame frame, float[] rightPx, float[] leftPx,
                               float[] shoulderR, float[] shoulderL) {
        AbstractClientPlayer player = mc.player;
        if (player == null) return;
        if (!(mc.getEntityRenderDispatcher().getRenderer(player) instanceof PlayerRenderer pr)) {
            dbg(mc, "NO_PLAYER_RENDERER " + mc.getEntityRenderDispatcher().getRenderer(player).getClass().getName());
            return;
        }
        float[] handR = frame.toCamera(rightPx[0], rightPx[1], rightPx[2], new float[3]);
        dbgFull(mc, frame, light, rightPx, leftPx, handR, shoulderR, shoulderL);
        if (handR == null) return;                       // nothing captured yet: draw nothing this frame
        drawArm(pose, buffer, light, pr, player, true, handR, shoulderR, ROLL_R);
        float[] handL = frame.toCamera(leftPx[0], leftPx[1], leftPx[2], new float[3]);
        if (handL == null) return;
        drawArm(pose, buffer, light, pr, player, false, handL, shoulderL, ROLL_L);
    }

    // ------------------------------------------------------------------ TEMP arms diagnostic
    // One line a second into latest.log while a gun is in hand. Delete together with dbgFull/ndcOf.

    private static final boolean DEBUG_ARMS = false;
    private static long dbgTick = -1L;

    private static void dbg(Minecraft mc, String msg) {
        if (DEBUG_ARMS) System.out.println("[ARMSDBG] " + msg);
    }

    private static void dbgFull(Minecraft mc, GunFrame frame, int light, float[] rightPx, float[] leftPx,
                                float[] handR, float[] shoulderR, float[] shoulderL) {
        if (!DEBUG_ARMS) return;
        AbstractClientPlayer p = mc.player;
        long t = p == null || p.level() == null ? -1L : p.level().getGameTime();
        if (t < 0 || t - dbgTick < 20) return;           // keep it to one line a second
        dbgTick = t;
        float[] handL = frame.toCamera(leftPx[0], leftPx[1], leftPx[2], new float[3]);
        float[] origin = frame.toCamera(0.0F, 0.0F, 0.0F, new float[3]);
        System.out.println("[ARMSDBG] t=" + t
                + " gun=" + (p == null ? "?" : p.getMainHandItem().getItem())
                + " valid=" + frame.isValid()
                + String.format(Locale.ROOT, " aim=%.2f fov=%d light=%d", frame.aim(), mc.options.fov().get(), light)
                + "\n[ARMSDBG]   raw px R=" + fmt(rightPx) + " L=" + fmt(leftPx)
                + "\n[ARMSDBG]   camera origin=" + fmt(origin)
                + "\n[ARMSDBG]   handR=" + fmt(handR) + " NDC" + ndcOf(mc, handR)
                + "\n[ARMSDBG]   handL=" + fmt(handL) + " NDC" + ndcOf(mc, handL)
                + "\n[ARMSDBG]   shoulderR=" + fmt(shoulderR) + " NDC" + ndcOf(mc, shoulderR)
                + "\n[ARMSDBG]   shoulderL=" + fmt(shoulderL) + " NDC" + ndcOf(mc, shoulderL));
    }

    private static String fmt(float[] a) {
        return a == null ? "NULL" : String.format(Locale.ROOT, "(%.3f, %.3f, %.3f)", a[0], a[1], a[2]);
    }

    /** Screen position of a camera-space point under the client's own FOV — 屏内 means it should be visible. */
    private static String ndcOf(Minecraft mc, float[] p) {
        if (p == null) return "(null)";
        if (p[2] >= -0.01F) return "(behind the eye)";
        double halfH = Math.tan(Math.toRadians(mc.options.fov().get() / 2.0)) * -p[2];
        double halfW = halfH * mc.getWindow().getWidth() / (double) Math.max(1, mc.getWindow().getHeight());
        double x = p[0] / halfW, y = p[1] / halfH;
        return String.format(Locale.ROOT, "(%.2f, %.2f) %s", x, y,
                Math.abs(x) <= 1.0 && Math.abs(y) <= 1.0 ? "屏内" : "屏外");
    }

    /** Puts a hand at {@code hand} (camera space, blocks) with the arm reaching out from {@code shoulder}. */
    private static void drawArm(PoseStack pose, MultiBufferSource buffer, int light, PlayerRenderer pr,
                                AbstractClientPlayer player, boolean right, float[] hand,
                                float[] shoulder, float rollDeg) {
        Vector3f y = new Vector3f(hand[0] - shoulder[0], hand[1] - shoulder[1], hand[2] - shoulder[2]);
        float dist = y.length();
        // Nonsense numbers (not captured yet, capture went wrong) — better nothing than a smear of skin
        if (!(dist > 1.0E-4F) || dist > 3.0F) {
            dbg(null, "CULL " + (right ? "RIGHT" : "LEFT") + " dist=" + dist + " hand=" + fmt(hand));
            return;
        }
        restoreCleanPose(pose);
        float s = dist / ARM_LEN;                   // stretch along the length only, thickness unchanged
        y.div(dist);
        Vector3f ref = new Vector3f(0.0F, 1.0F, 0.0F);
        if (Math.abs(y.dot(ref)) > 0.95F) ref.set(0.0F, 0.0F, -1.0F);
        Vector3f z = new Vector3f(y).cross(ref).normalize();
        Vector3f x = new Vector3f(y).cross(z).normalize();
        float r = rollDeg * Mth.DEG_TO_RAD;
        float cr = Mth.cos(r);
        float sr = Mth.sin(r);
        Vector3f xr = new Vector3f(x).mul(cr).add(new Vector3f(z).mul(sr));
        Vector3f zr = new Vector3f(z).mul(cr).sub(new Vector3f(x).mul(sr));
        // ★ Fill this one column at a time. JOML's 9-argument Matrix3f constructor is column-major in its
        //   naming (m01 = column 0, row 1), so writing (x, y, z) in order gives the transpose = the inverse
        //   rotation: the arm swings behind the camera, the near plane slices it, and the screen fills with
        //   skin colour. Cost a debugging session once; do not "simplify" this back.
        Quaternionf q = new Matrix3f().setColumn(0, xr)
                                      .setColumn(1, y)
                                      .setColumn(2, zr)
                                      .getNormalizedRotation(new Quaternionf());
        // The arm box's local x centre: right arm −0.375, left arm +0.375 (the left arm is mirrored in the model)
        float dx = (right ? -HALF : HALF) * THICK;
        float ox = xr.x * dx + y.x * ARM_LEN * s;
        float oy = xr.y * dx + y.y * ARM_LEN * s;
        float oz = xr.z * dx + y.z * ARM_LEN * s;
        pose.pushPose();
        pose.translate(hand[0] - ox, hand[1] - oy, hand[2] - oz);
        pose.mulPose(q);
        pose.scale(THICK, s, THICK);
        if (right) {
            pr.renderRightHand(pose, buffer, light, player);
        } else {
            pr.renderLeftHand(pose, buffer, light, player);
        }
        pose.popPose();
    }

    private WeaponArms() {
    }
}
