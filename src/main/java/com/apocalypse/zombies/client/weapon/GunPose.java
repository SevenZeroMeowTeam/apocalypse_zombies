package com.apocalypse.zombies.client.weapon;

import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * First-person "how the gun is held" — the TaCZ-style stance layer.
 *
 * <h2>Why a stance layer at all</h2>
 * At the hip the gun does not sit on the sight line: it is carried low and forward, off the eye's axis,
 * which is what makes it read as <em>carried</em> rather than aimed. Raising the sight blends the carry
 * offset away and translates the gun so the sight line lands on the centre of the screen; running blends
 * the same carry towards the {@link #SPRINT_PITCH run pose} — gun across the body, muzzle down.
 *
 * <p>The carry poses are <b>square</b> ({@link #HIP_YAW}/{@link #HIP_PITCH}/{@link #HIP_ROLL} are all
 * zero): with the model's own display rotation cancelled, the barrel axis stays exactly parallel to the
 * view axis while merely carried. The run pose is the only one that still rolls the weapon off-axis, by
 * design — {@link #SPRINT_YAW}/{@link #SPRINT_PITCH}/{@link #SPRINT_ROLL}.
 *
 * <h2>Why here and not on the model bones</h2>
 * The first-person transform chain is
 * <pre>
 * camera = Trans(±0.56, −0.52 − 0.6·equip, −0.72)   ItemInHandRenderer.applyItemArmTransform
 *        · Trans({@link #HIP_DX}, {@link #HIP_DY}, {@link #HIP_DZ}) · R(hip)   this class
 *        · Trans(display/16) · R(display) · S(display)   ItemTransform.apply
 *        · Trans(−0.5, −0.5, −0.5)                       ItemRenderer
 *        · model px / 16 + GeckoLib's (+0.5, +0.51, +0.5)   GeoItemRenderer.preRender
 * </pre>
 * This layer is filled in by hand from {@link WeaponHandGrip}, so it <em>always</em> applies. Pushing the
 * same motion onto the {@code move} bone instead would be overwritten by the clip's own keyframes — the
 * reload clip carries its own {@code move} transform, so the gun and the hands would sink together.
 *
 * <p>Everything that needs to know where the gun ended up reads this one copy: the arms
 * ({@link GunFrame}), the muzzle and ejection ports (the server-side ballistics). They can never drift
 * apart, because there is only one set of numbers.
 *
 * <h2>Rotations: this layer's, and the model's</h2>
 * <p><b>Rotation must be identity while aiming</b> — but identity of the <em>whole</em> chain, not just of
 * this layer. The item model's {@code display} block carries a rotation of its own (2° pitch, 4° yaw, on
 * both guns here), and it is applied <em>inside</em> this one: a model point is turned by {@code R_display}
 * <em>first</em>, and only then by this layer's quaternion. Because the display rotation lives inside this
 * layer, zeroing {@link #HIP_PITCH}/{@link #HIP_YAW}/{@link #HIP_ROLL} would <em>not</em> by itself
 * straighten the sight line: that 4.47° of display tilt would stand, and a tilted sight line cannot be
 * brought onto the eye's axis by <em>any</em> translation — it stays parallel-but-off-axis, and the error
 * grows with range. So this layer multiplies in the exact <em>conjugate</em> of the display rotation as
 * well, ramped with aim (values from {@code GunItem#adsPitch()}); at full aim a model point now arrives
 * axis-aligned, and the raise really is pure translation.
 *
 * <p>Since the carry angles are now zero, this conjugate is what puts the <em>hip</em> pose straight too:
 * the barrel ends up exactly parallel to the view axis while merely carried, not only while aiming.
 *
 * <p>The conjugate is built with JOML's own {@code rotationXYZ} — the same call vanilla's
 * {@code ItemTransform#apply} makes — so the cancellation is exact by construction, with no hand-rolled sign
 * convention to get wrong. The display block keeps its angles, so a model edit cannot silently desync the
 * two, because {@code tools/check_gun_resources.py} checks them against each other.
 */
public final class GunPose {

    /** Model projection FOV while aiming (45° — the value TaCZ gives its rifles). */
    public static final float MODEL_FOV_AIM = 45.0F;
    /** Model projection FOV at the hip (vanilla's own first-person pass uses 70). */
    public static final float MODEL_FOV_HIP = 76.0F;

    // ---------------------------------------------------------------- hip stance
    /**
     * Carry yaw — <b>zero on purpose</b>.
     *
     * <p>Was {@code 4.0}, described as "muzzle a touch left: you see the right side of the receiver
     * rather than a pipe aimed at you". In practice it read as a <em>skewed</em> weapon: this layer's
     * yaw is applied <em>outside</em> the item model's own 4° display yaw, so the two compounded to a
     * real 8° off the view axis and the receiver sat visibly tilted both lengthwise and on screen.
     * Zeroing it (with pitch and roll) makes the barrel axis exactly parallel to the view axis
     * ({@code (0, 0, −1)}, 0.00°) while merely carried, which is what "枪械要正" asks for. Measured
     * with {@code tools/hip_square_probe.py}: 4.31° off-axis (that metric is the display rotation's
     * contribution alone) → 0.00°.
     */
    public static final float HIP_YAW = 0.0F;
    /** Carry pitch — see {@link #HIP_YAW}; was {@code 1.6} (muzzle slightly up). */
    public static final float HIP_PITCH = 0.0F;
    /** Carry roll — see {@link #HIP_YAW}; was {@code −3.0} (body leaning clockwise on screen). */
    public static final float HIP_ROLL = 0.0F;
    /**
     * Stance offset (blocks, in the block space the stance is applied in — the same space as
     * {@code ADS}, so a value here is worth {@code value × FIRST_PERSON_SCALE} on screen).
     *
     * <p><b>These are the TaCZ carry pose, not vanilla's.</b> Vanilla's first-person hand base
     * ({@code ±0.56, −0.52, −0.72}) parks the weapon at the bottom-right corner; with the guns' own
     * display blocks on top of it the pistol grip — and therefore both hands — ended up <em>below the
     * bottom edge of the screen</em>: measured through the whole chain, the right hand sat at NDC
     * y −1.17 (M1) … −1.59 (Uzi), which is why no weapon ever showed a hand while merely carried. TaCZ
     * instead carries its guns <em>up</em>, in front of the player, with the sights just under the eye
     * line, and that is what reads as "held" rather than "parked off screen".
     *
     * <p><b>The lateral values are the "right hand toward the centre" pass.</b> Was
     * {@code −0.30 / +0.30}, which left the grip at NDC x +0.54 (M1/AWM) … +0.69 (Uzi) — most of the
     * weapon out in the right third of the frame, reading as "held off to one side" rather than
     * carried in front. Pulled in to {@code −0.38 / +0.27}: the grip now lands at NDC x +0.30 … +0.40,
     * inside the lower middle band, and the raise still reads as a raise because the hip stance stays
     * a little lower than {@code ADS_X/ADS_Y} (−0.475 / +0.30). Measured with
     * {@code tools/hip_square_probe.py}; the hand-to-shoulder distance grows from 0.983 to 1.048
     * blocks, i.e. {@link WeaponArms} stretches the arm bone ~6.6 %, which stays inside the range
     * {@code 美术规范.md} treats as acceptable for the first-person arms.
     */
    public static final float HIP_DX = -0.38F;
    public static final float HIP_DY = 0.27F;
    public static final float HIP_DZ = 0.05F;

    // ---------------------------------------------------------------- run carry
    /**
     * Running carry: the gun comes down off the sight line and across the body — muzzle well down, body
     * rolled — which is what separates "running" from "carrying". Rotating about the model origin swings
     * the muzzle down and the butt up, so the pose is dominated by these three angles.
     *
     * <p>Measured with the same chain as the carry pose above (client FOV 70 — the projection the
     * first-person pass actually renders under; {@link #MODEL_FOV_HIP} is the FOV a gun-specific projection
     * would use and nothing currently applies it): against the hip stance the muzzle drops 0.48 … 0.53 NDC
     * on all five guns (Uzi −0.18 → −0.68) while both hands stay inside the frame (right hand y −0.64 …
     * −0.88, x +0.17 … +0.39). The small translation is there to <em>keep the hands on screen</em> — a run
     * carry that hides them is the very thing this layer was pulled up to fix.
     */
    public static final float SPRINT_YAW = 22.0F;
    /** Muzzle down — the single most legible part of the pose. */
    public static final float SPRINT_PITCH = -20.0F;
    /** Body leaned over, so the silhouette on screen is a diagonal, not a vertical. */
    public static final float SPRINT_ROLL = 20.0F;
    public static final float SPRINT_DX = -0.35F;
    public static final float SPRINT_DY = 0.16F;
    public static final float SPRINT_DZ = 0.0F;

    /**
     * Run-cycle bob (blocks, peak). The phase comes from ground covered — one cycle per two blocks, the
     * same rhythm vanilla's own view bob rides — so the gun steps with the camera instead of against it.
     * Vertical leads, the lateral a quarter cycle behind; together they trace the small ellipse a carried
     * object actually makes.
     */
    public static final float SPRINT_BOB_Y = 0.028F;
    public static final float SPRINT_BOB_X = 0.016F;

    /**
     * This frame's aim translation, in camera space and in <b>blocks</b>.
     *
     * <p>[0..2] = xyz, [3] = the fire lift (unscaled — it is the snap on the shot, not a raise),
     * [4] = roll while aiming (degrees, about the <em>eye</em>), [5] = fire pitch (degrees, about the
     * <em>hand/grip</em>: positive = muzzle up, butt down), [6..7] = the item model's own first-person
     * display rotation, pitch and yaw in degrees, which this layer cancels.
     *
     * <p>Written once per frame by {@link WeaponHandGrip}; the arms and the gun read the same copy.
     */
    public static final float[] ADS = new float[8];

    /** Scratch quaternion for {@link #transform} (client render is single-threaded). */
    private static final Quaternionf PITCH = new Quaternionf();

    /** Scratch quaternion for the display counter-rotation (client render is single-threaded). */
    private static final Quaternionf CANCEL = new Quaternionf();

    /** Aim translation (blocks). Lift is not scaled by aim — it is the instant of the shot. */
    public static void setAds(float x, float y, float z, float lift, float rollDeg, float firePitch,
                              float displayPitch, float displayYaw) {
        ADS[0] = x;
        ADS[1] = y;
        ADS[2] = z;
        ADS[3] = lift;
        ADS[4] = rollDeg;
        ADS[5] = firePitch;
        ADS[6] = displayPitch;
        ADS[7] = displayYaw;
    }

    /** Clear it when the held item is not one of ours, or the previous gun's offset lingers for a frame. */
    public static void clearAds() {
        setAds(0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F);
    }

    /** Model projection FOV for this frame's aim, for guns that render through their own projection. */
    public static float modelFov(float aimFov, double aim) {
        return (float) (MODEL_FOV_HIP + (aimFov - MODEL_FOV_HIP) * aim01(aim));
    }

    /** Blend "hip stance → aim translation" by {@code aim}, using the copy in {@link #ADS}. */
    public static void matrix(float aim, Matrix4f out) {
        matrix(aim, ADS, out);
    }

    /**
     * The stance for one frame of <em>this</em> client, run carry included.
     *
     * @param sprint   0 = standing carry, 1 = running carry (see the {@code SPRINT_*} constants)
     * @param bobPhase run-cycle phase in radians; only read while {@code sprint} is above zero
     */
    public static void matrix(float aim, float sprint, float bobPhase, Matrix4f out) {
        matrix(aim, ADS, sprint, bobPhase, out);
    }

    /** Same, with the packet of offsets supplied by the caller and no run blend. */
    public static void matrix(float aim, float[] ads, Matrix4f out) {
        matrix(aim, ads, 0.0F, 0.0F, out);
    }

    /**
     * The full stance: the standing and running carries blended by {@code sprint}, then the sight-up
     * translation blended by {@code aim} on top of it.
     *
     * <p>The multiplication order is {@code Rz(roll) · Trans(offset) · R(hip) · Rx(fire) · R(model)⁻¹}. The
     * <em>last</em> transform added to the matrix is the <em>first</em> applied to a model point, so this
     * reads as "cancel the model's tilt, then the hip stance, then move into place, then roll about the
     * <b>eye</b>". The roll has to be last: the aim translation has put the sight line on the eye, and
     * rolling about the eye leaves the eye itself fixed — the sights stay pinned to the centre of the screen
     * while the body swings around them, which is the TaCZ "gun slung across the lower right" composition.
     * Rolling after the translation would rotate about the model origin and throw the sights off-centre.
     *
     * <p>{@code firePitch} and the counter-rotation act before the hip stance (and the counter-rotation
     * before the fire pitch), i.e. nearest the model: {@code firePitch} is about the <b>hand/grip</b> — muzzle
     * up, butt down, rather than the whole rifle rising — and the counter-rotation has to be the first thing
     * a model point meets, since the display rotation it undoes is applied even further in.
     *
     * <p>Aiming wins over running outright: you cannot sprint while holding a sight up, and scaling the run
     * blend by {@code k = 1 − aim} leaves the carry pose at zero by the time the sight is on — with no second
     * flag to keep in sync with the first.
     */
    public static void matrix(float aim, float[] ads, float sprint, float bobPhase, Matrix4f out) {
        float a = aim01(aim);
        float k = 1.0F - a;
        float s = aim01(sprint) * k;
        float m = 1.0F - s;
        out.identity();
        if (ads[4] != 0.0F) {
            out.rotateZ(ads[4] * a * Mth.DEG_TO_RAD);
        }
        out.translate((HIP_DX * m + SPRINT_DX * s) * k + ads[0] * a + s * SPRINT_BOB_X * Mth.cos(bobPhase),
                (HIP_DY * m + SPRINT_DY * s) * k + ads[1] * a + ads[3] + s * SPRINT_BOB_Y * Mth.sin(bobPhase),
                (HIP_DZ * m + SPRINT_DZ * s) * k + ads[2] * a);
        if (k > 1.0E-4F) {
            out.rotate(quat(k, s));
        }
        if (ads[5] != 0.0F) {
            out.rotateX(ads[5] * Mth.DEG_TO_RAD);
        }
        if (ads[6] != 0.0F || ads[7] != 0.0F) {
            out.rotate(cancelled(ads[6], ads[7], a));
        }
    }

    /**
     * The same stance applied to a camera-space <em>vector</em> — the matrix-free form, for a caller that
     * needs a direction or a point rather than a transform to push. The renderer itself goes through
     * {@link #matrix}: the gun wants the transform, and the arms read it back out of {@link GunFrame}'s capture.
     *
     * <p>It carries the standing carry and the sight-up translation only — no run blend, which is per-frame
     * state a vector call is not given. This uses JOML quaternions rather than hand-written trig so that it
     * is provably the same rotation {@link #matrix} applies: otherwise two callers could turn opposite ways.
     */
    public static void transform(float aim, float[] ads, Vector3f v) {
        float a = aim01(aim);
        float k = 1.0F - a;
        if (ads[6] != 0.0F || ads[7] != 0.0F) {
            cancelled(ads[6], ads[7], a).transform(v);
        }
        if (ads[5] != 0.0F) {
            PITCH.set(0.0F, 0.0F, 0.0F, 1.0F).rotateX(ads[5] * Mth.DEG_TO_RAD);
            PITCH.transform(v);
        }
        if (k > 1.0E-4F) {
            quat(k).transform(v);
        }
        v.x += HIP_DX * k + ads[0] * a;
        v.y += HIP_DY * k + ads[1] * a + ads[3];
        v.z += HIP_DZ * k + ads[2] * a;
        if (ads[4] != 0.0F) {
            float r = ads[4] * a * Mth.DEG_TO_RAD;
            float c = Mth.cos(r);
            float s = Mth.sin(r);
            float x = v.x * c - v.y * s;
            float y = v.x * s + v.y * c;
            v.x = x;
            v.y = y;
        }
    }

    /** The copy in {@link #ADS}, for call sites that have no packet of their own. */
    public static void transform(float aim, Vector3f v) {
        transform(aim, ADS, v);
    }

    /**
     * The three carry angles — the standing carry blended towards the running carry by {@code s} — all
     * ramped out by the aim weight {@code k}.
     *
     * <p>One call for all three, because a pose <em>is</em> the three of them together: blending them
     * separately is how a gun ends up rolled like a run but pitched like a carry.
     */
    private static Quaternionf quat(float k, float s) {
        float m = 1.0F - s;
        return new Quaternionf().rotateXYZ((HIP_PITCH * m + SPRINT_PITCH * s) * k * Mth.DEG_TO_RAD,
                (HIP_YAW * m + SPRINT_YAW * s) * k * Mth.DEG_TO_RAD,
                (HIP_ROLL * m + SPRINT_ROLL * s) * k * Mth.DEG_TO_RAD);
    }

    /** The standing carry angles ({@code sprint = 0}). */
    private static Quaternionf quat(float k) {
        return quat(k, 0.0F);
    }

    /**
     * The exact inverse of the item display's rotation for this aim, as a quaternion. Built with the very
     * same {@code rotationXYZ} constructor vanilla uses — so it cancels no matter which convention JOML
     * applies the three angles in — and conjugated, since a rotation's inverse is its conjugate.
     *
     * <p>Ramped by {@code a}: at the hip it is the identity, so the display block keeps full effect and the
     * carried pose is untouched.
     */
    private static Quaternionf cancelled(float pitch, float yaw, float a) {
        return CANCEL.rotationXYZ(pitch * a * Mth.DEG_TO_RAD, yaw * a * Mth.DEG_TO_RAD, 0.0F).conjugate();
    }

    private static float aim01(double aim) {
        return (float) Mth.clamp(aim, 0.0D, 1.0D);
    }

    private GunPose() {
    }
}
