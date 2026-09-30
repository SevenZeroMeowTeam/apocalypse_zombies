package com.apocalypse.zombies.client.weapon;

import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;

/**
 * Where the gun is this frame, as "model pixels → camera space (blocks)".
 *
 * <h2>Why it exists</h2>
 * The first-person hands ({@link WeaponArms}) have to sit on points of the gun — the wrist, the fore-end, the
 * clip. The gun is not a static prop: raising the sight moves it to the centre of the screen, the reload dips
 * it, a shot kicks it, and the item model's {@code display} block shifts and scales it. The hands have to ride
 * all of that, or they slide off the weapon.
 *
 * <h2>How, and why it is built this way</h2>
 * Rather than reconstruct the long transform chain — hand base, item display, hold stance, bone rig, and the
 * unit conversion in between — this takes two matrices that already exist:
 * <ol>
 *   <li>{@code GeoItemRenderer.itemRenderTranslations} — the matrix GeckoLib captures in its own
 *       {@code preRender}, taken after the display and the stance have been applied. GeckoLib uses this very
 *       matrix to place the model's geometry, so using it too cannot disagree with what is on screen.</li>
 *   <li>The bone chain ({@link #boneChain}) for the {@code move} bone and its ancestors, which the clips
 *       animate. This is the only part that has to be reproduced by hand, and it is reproduced from
 *       {@code RenderUtils.prepMatrixForBone} rather than from memory.</li>
 * </ol>
 * A model point maps as {@code pose · (boneChain(point) / 16 + nudge)}: the geometry quads are built at model
 * pixels divided by 16, which is the same unit GeckoLib's own pivot translations use, and the pose matrix takes
 * that to blocks. GeckoLib's own half-unit nudge from {@code preRender} is added in that same block space,
 * <em>before</em> the pose — where GeckoLib adds it too, so the display's scale multiplies it there as well.
 *
 * <h2>When it is filled in</h2>
 * The renderer records here as the gun draws, and — because our first-person pass draws the gun itself and then
 * the arms ({@code ClientEvents.onRenderHand}) — the arms read the capture a few lines later, in the <em>same</em>
 * frame. No lag to hide, and no interpolation to get wrong.
 */
public final class GunFrame {

    /**
     * GeckoLib's nudge from {@code GeoItemRenderer.preRender}: it centres the conventional Bedrock model
     * (authored 0…16 with the origin on a block corner) inside the block. Our guns are authored around their
     * own origin, so this displaces them — but it displaces them in the game too, and the sight-up offsets were
     * tuned with it in place, so it belongs in the chain. If the hands ever sit a fraction off along all three
     * axes at once, this is the first thing to check.
     */
    private static final float GECKO_X = 0.5F;
    private static final float GECKO_Y = 0.51F;
    private static final float GECKO_Z = 0.5F;

    /** Guard: a capture further than this from the eye is nonsense, and no arm should be drawn for it. */
    private static final float SANITY = 4.0F;

    /** The bone the clips' whole-gun motion hangs off; {@link #boneChain} starts here. */
    public static final String MOVE_BONE = "move";

    private final Matrix4f pose = new Matrix4f();
    private final Matrix4f bones = new Matrix4f();
    private boolean valid;
    private float aim = 1.0F;

    /**
     * The bolt handle's own chain this frame — everything from the bolt up to, but not including, {@code move}
     * — plus the bolt's two clip values. See {@link #bolt} and {@link #boltGrip}.
     */
    private final Matrix4f boltChain = new Matrix4f();
    private float boltTurn;
    private float boltPull;
    private boolean boltValid;

    private final Vector3f v = new Vector3f();

    /** Scratch while composing one bone's own transform in {@link #partChain}. */
    private static final Matrix4f LOCAL = new Matrix4f();

    /**
     * Records one frame, from inside the item renderer.
     *
     * @param itemRenderTranslations GeckoLib's own base matrix for this item, straight off the renderer
     * @param boneChain model px → model px, the composed {@code root → move} chain (see {@link #boneChain})
     * @param aim aim progress this frame (0 hip, 1 sight up), which the arms use for their shoulder push
     */
    public void capture(Matrix4f itemRenderTranslations, Matrix4f boneChain, float aim) {
        this.pose.set(itemRenderTranslations);
        this.bones.set(boneChain);
        this.aim = aim;
        this.valid = true;
    }

    /** True once a frame has been recorded — before that there is nothing to put hands on. */
    public boolean isValid() {
        return valid;
    }

    /** Aim progress of the recorded frame. */
    public float aim() {
        return aim;
    }

    /** Forget the capture (weapon put away): the arms must not be drawn onto a stale pose. */
    public void invalidate() {
        valid = false;
        boltValid = false;
    }

    /**
     * Records where the bolt handle is this frame, for the guns whose clips are worked by hand.
     *
     * <p>The point of it is the user-visible rule that a hand working a bolt stays <em>on</em> the handle,
     * not near it. Rather than re-timing the clips' keyframes in Java — which is a second copy of the art,
     * and drifts the moment the art is re-exported — the hand is driven from the live bone: whatever the clip
     * has done to the bolt is what the hand follows, so the two cannot disagree.
     *
     * @param boltChain the composed chain for the bolt, from {@link #partChain} (may be {@code null})
     * @param boltBone the bolt bone itself, read for its clip values (may be {@code null})
     */
    public void bolt(Matrix4f boltChain, CoreGeoBone boltBone) {
        if (boltChain == null || boltBone == null) {
            boltValid = false;
            return;
        }
        this.boltChain.set(boltChain);
        this.boltTurn = boltBone.getRotZ();
        this.boltPull = boltBone.getPosZ();
        this.boltValid = true;
    }

    /**
     * Where a point of the bolt has ended up this frame, in the same model pixels a hand target is written
     * in — so {@link #toCamera} can take it the rest of the way with the hands' own chain.
     *
     * @param grip the point's rest position in the geo file (the knob's centre, on the bolt)
     * @return false when no bolt was captured, in which case {@code out} is untouched
     */
    public boolean boltGrip(float[] grip, float[] out) {
        if (!valid || !boltValid) return false;
        v.set(grip[0], grip[1], grip[2]);
        boltChain.transformPosition(v);
        out[0] = v.x;
        out[1] = v.y;
        out[2] = v.z;
        return true;
    }

    /**
     * How far the bolt is off its home position this frame, 0…1 — the larger of its turn and its travel
     * against the maxima the clips use.
     *
     * <p>Read straight off the live bone, which is what makes the hand let go at the right moment: it holds
     * on for as long as the handle is open, and closes back onto the firing grip as the clip runs it home.
     */
    public float boltActivity(float turnMaxDeg, float pullMaxPx) {
        if (!boltValid) return 0.0F;
        return Math.max(Math.abs((float) Math.toDegrees(boltTurn)) / turnMaxDeg,
                        Math.abs(boltPull) / pullMaxPx);
    }

    /**
     * A point of the model (model pixels, the units the geo file is written in) → camera space in blocks.
     *
     * <p>Returns {@code null} when nothing has been recorded yet, or when the result is somewhere a hand could
     * not be — the caller then draws nothing for that frame rather than smearing an arm across the screen.
     */
    public float[] toCamera(float px, float py, float pz, float[] out) {
        if (!valid) return null;
        v.set(px, py, pz);
        bones.transformPosition(v);              // rig: the move bone and its ancestors, in model px
        v.mul(1.0F / 16.0F);                     // model px → blocks (the unit the geometry is built in)
        // GeckoLib's nudge goes on *before* the display, in the model's own block space: in preRender it is a
        // translate pushed onto a stack that already carries the display, so the display's scale multiplies it
        // (0.82 first person). Adding it after the pose instead — as this used to — leaves the hands a tenth of
        // a block, some seventy pixels, away from the gun GeckoLib actually drew.
        v.x += GECKO_X;
        v.y += GECKO_Y;
        v.z += GECKO_Z;
        pose.transformPosition(v);               // display + hold stance + hand base → camera space
        if (!(v.length() < SANITY)) return null;
        out[0] = v.x;
        out[1] = v.y;
        out[2] = v.z;
        return out;
    }

    /**
     * Composes a GeckoLib bone chain into one matrix (model px → model px), for {@link #capture}.
     *
     * <p>Reproduces {@code RenderUtils.prepMatrixForBone} exactly:
     * {@code translate(-posX, +posY, +posZ) · translate(pivot) · rotateZ · rotateY · rotateX · scale ·
     * translate(-pivot)}. Two details are load-bearing and are copied verbatim rather than tidied up:
     * <ul>
     *   <li>The bone's <b>position</b> is applied with its X sign flipped, while the pivot and the rotation
     *       about it are not. That asymmetry is GeckoLib's own convention (Blockbench's animation X runs the
     *       other way from the geometry), not a mistake here.</li>
     *   <li>The rotations go on as {@code rotateZ}, then {@code rotateY}, then {@code rotateX} — three
     *       {@code mulPose} calls, so the matrix is {@code Rz·Ry·Rx}. The item display's rotation is the other
     *       convention ({@code Rx·Ry·Rz}); mixing the two turns the gun and the hands opposite ways.</li>
     * </ul>
     *
     * <p>Walks up through the ancestors, so a rig that animates {@code root} as well as {@code move} still puts
     * the hands in the right place.
     */
    public static Matrix4f boneChain(Matrix4f out, CoreGeoBone bone) {
        out.identity();
        for (CoreGeoBone b = bone; b != null; b = b.getParent()) {
            out.translate(-b.getPosX(), b.getPosY(), b.getPosZ());
            out.translate(b.getPivotX(), b.getPivotY(), b.getPivotZ());
            out.rotateZ(b.getRotZ());
            out.rotateY(b.getRotY());
            out.rotateX(b.getRotX());
            out.scale(b.getScaleX(), b.getScaleY(), b.getScaleZ());
            out.translate(-b.getPivotX(), -b.getPivotY(), -b.getPivotZ());
        }
        return out;
    }

    /**
     * Composes the chain from {@code bone} up to — but not including — the bone named {@code stopAt}, into one
     * matrix (model px → model px), nesting the ancestors the way the renderer does: the bone itself
     * innermost, each ancestor outside it.
     *
     * <p>{@link #boneChain} cannot be used for a chain like this. It multiplies each bone onto the
     * accumulator as it walks up, which ends up nesting the ancestors <em>inside</em> their descendants. That
     * never showed while every target sat on the one bone the clips animate (a single bone plus a static root
     * is order-blind), but a point on the bolt hangs off {@code body} as well, and an animated {@code body}
     * would then be applied the wrong side of the bolt.
     *
     * <p>A hand target is written in the space {@link #toCamera} expects — before the move chain — which is
     * why the walk stops at {@code move}: that bone, and everything above it, is applied to the hand target
     * once, by {@code toCamera}.
     */
    public static Matrix4f partChain(Matrix4f out, CoreGeoBone bone, String stopAt) {
        out.identity();
        for (CoreGeoBone b = bone; b != null && !stopAt.equals(b.getName()); b = b.getParent()) {
            LOCAL.identity();
            LOCAL.translate(-b.getPosX(), b.getPosY(), b.getPosZ());
            LOCAL.translate(b.getPivotX(), b.getPivotY(), b.getPivotZ());
            LOCAL.rotateZ(b.getRotZ());
            LOCAL.rotateY(b.getRotY());
            LOCAL.rotateX(b.getRotX());
            LOCAL.scale(b.getScaleX(), b.getScaleY(), b.getScaleZ());
            LOCAL.translate(-b.getPivotX(), -b.getPivotY(), -b.getPivotZ());
            out.set(LOCAL).mul(out);                 // this bone goes outside everything already composed
        }
        return out;
    }
}
