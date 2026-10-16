package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.GunFrame;
import com.apocalypse.zombies.client.weapon.HandMotion;
import com.apocalypse.zombies.item.Win94Item;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.model.GeoModel;

/**
 * GeckoLib model binding for the 温彻斯特 M1894（Win94 杠杆狙击枪）: which geometry file bakes, which
 * texture skins it, which clip file feeds the controller. Paths are written out explicitly so the layout
 * matches the other rifles'.
 *
 * <p>The model is 17.83 u (1.11 blocks) — the proportions of a 24-inch-barrelled Model 1894, muzzle at
 * z -10.77 and buttplate at z +7.06, bore line at y 0. Its action is a lever, not a bolt handle: the right
 * hand works the lever loop hanging under the receiver (bone {@code lever}, pivot on the lever pin at
 * [0, -0.95, -2.30]), so the "knob" the hand chases is the loop's bottom bar and the whole cycle is that
 * one bone swinging 62°. See {@link Win94Item} for the clip table.</p>
 *
 * <p>Like the Mosin this class owns the two things the first-person hands need: where the gun is this
 * frame ({@link #frame}) and where the hands go on it ({@link #rightHand}, {@link #leftHand}). Every
 * number below is read off the geo file's own cubes.</p>
 */
public class Win94GeoModel extends GeoModel<Win94Item> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/win94.geo.json");
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/item/win94.png");
    private static final ResourceLocation ANIMATION =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/win94.animation.json");

    /** The gun's pose this frame, written by the renderer and read by the arms — see {@link GunFrame}. */
    public static final GunFrame frame = new GunFrame();

    private static final Matrix4f SCRATCH = new Matrix4f();

    // ------------------------------------------------------------------ hand targets (model pixels)

    /**
     * The firing grip: the hand wrapped round the wrist of the stock, behind the trigger. The wrist column
     * (z 2.3…4.6) runs y -0.69…-2.11, so -0.85 at z 3.4 is the upper wood where a fist closes.
     */
    private static final float[] GRIP = {0.00F, -0.85F, 3.40F};

    /**
     * The support hand, flat under the wooden fore-end ahead of the receiver (the forearm spans
     * z -6.30…-2.62, bottom edge y -0.72) — forward enough to balance the 24-inch barrel.
     */
    private static final float[] SUPPORT = {0.10F, -1.45F, -3.60F};

    /**
     * The lever loop's bottom bar — the part the right hand actually closes on. It is a point of the
     * {@code lever} bone, so the clips move it: {@link GunFrame#boltGrip} applies the lever's live chain and
     * the hand lands wherever the loop has swung to, 62° of arc and no slide. The loop's own geometry
     * (centre y -1.85, z +0.92, semi-axes z 0.84 / y 0.32 — measured off a real M1894, see
     * tools/win94/spec.py) puts its bottom bar here.
     */
    private static final float[] LEVER_KNOB = {0.00F, -2.17F, 0.92F};

    /** The lever's own maxima over the clips — 62° of swing, no linear travel. */
    private static final float LEVER_TURN_MAX = 62.0F;
    private static final float LEVER_PULL_MAX = 0.0F;

    /** Seconds for the fist to reach (or leave) the lever loop. A short reach down from the grip. */
    private static final float HOLD_TAU = 0.06F;

    /**
     * Where the loading hand closes on a round being pressed through the gate: the middle of the brass, a
     * hand's width outboard of the bore line so the case stays visible beside the fist, and a little above it
     * — the hand comes down onto the round as it pushes it in. The clips carry the cartridge bone, so this is
     * a point <em>of the round</em>: it rides whatever the clip does with it.
     */
    private static final float[] ROUND_GRIP = {0.22F, 0.15F, -1.08F};

    /**
     * {@link #ROUND_GRIP} on a round at its "out" pose — the clips park each fresh round a
     * {@code (OUT_X, 0.10, FEED_Z)} offset, {@code (0.86, 0.10, 0.16)} in model px, away from home. This is
     * where the hand waits between presses, so the next round steps straight into it.
     */
    private static final float[] ROUND_READY = {1.08F, 0.25F, -0.92F};

    /**
     * The stretch of each reload clip the right hand spends out at the gate, in ticks from the clip's start:
     * from the reach-out just before the first round appears to just after the last press lands. The presses
     * run 11.2–17.2 / 22–28 / 32.8–38.8 in the 44-tick tactical clip and 13–19 … 57–63 in the 88-tick empty
     * one — six ticks of travel per press, then the round steps back out for the next — which are also the
     * beats the reload sound tables in {@code Win94Item} fire on. Empty's closing lever cycle starts at 67
     * and takes the hand over from there, so its loading stretch ends before it.
     */
    private static final float LOAD_TACTICAL_FROM = 8.0F;
    private static final float LOAD_TACTICAL_TO = 42.0F;
    private static final float LOAD_EMPTY_FROM = 10.0F;
    private static final float LOAD_EMPTY_TO = 66.0F;

    /** Seconds for the hand to reach the gate — and to let go of it at the end. A short reach from the grip. */
    private static final float LOAD_TAU = 0.07F;
    /** Seconds the loading hand lags the round by: enough to smooth each step-out into a reach, not a snap. */
    private static final float ROUND_FOLLOW_TAU = 0.045F;

    /** Live eased hold 0…1 — see {@link #holdOnLever}. */
    private static float handleHold;

    /** Live eased hold 0…1 — see {@link #holdOnRound}. */
    private static float loadHold;
    /** The loading hand's smoothed target in model px — chases the round, see {@link #loadingPoint}. */
    private static final float[] loadPoint = new float[3];
    private static boolean loadPointSet;

    private static final float[] KNOB = new float[3];
    private static final float[] ROUND_NOW = new float[3];
    private static final Matrix4f SCRATCH_LEVER = new Matrix4f();
    private static final Matrix4f SCRATCH_ROUND = new Matrix4f();

    // ------------------------------------------------------------------ resources

    @Override
    public ResourceLocation getModelResource(Win94Item animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(Win94Item animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(Win94Item animatable) {
        return ANIMATION;
    }

    // ------------------------------------------------------------------ hands

    /**
     * Records this frame's pose. Called by the renderer once the model has drawn, so the bones hold the
     * values the clip just set and GeckoLib has published its own base matrix.
     *
     * @param leverBone the {@code lever} bone, whose live pose the right hand is driven from (may be null)
     * @param roundBone the {@code cartridge} bone, whose live pose the loading hand is driven from (may be null)
     */
    public static void capture(Matrix4f itemRenderTranslations, CoreGeoBone moveBone, CoreGeoBone leverBone,
                               CoreGeoBone roundBone, float aim) {
        if (itemRenderTranslations == null || moveBone == null) {
            frame.invalidate();
            return;
        }
        frame.capture(itemRenderTranslations, GunFrame.boneChain(SCRATCH, moveBone), aim);
        frame.bolt(GunFrame.partChain(SCRATCH_LEVER, leverBone, GunFrame.MOVE_BONE), leverBone);
        frame.round(GunFrame.partChain(SCRATCH_ROUND, roundBone, GunFrame.MOVE_BONE), roundBone);
    }

    /**
     * Where the right hand is, in model pixels, for the action the gun is running.
     *
     * <p>A lever gun loads by hand: rounds go in through the gate one at a time, pressed home by the right
     * hand. Both reloads therefore put that hand out at the gate for their loading stretch
     * ({@link #holdOnRound}), riding the round the clip is feeding — the clip moves it, the hand does not let
     * go of it. The lever outranks the round, so {@code reload_empty}'s closing cycle (and the {@code bolt}
     * cycle after every shot) takes the same hand onto the loop wherever it has swung to. Outside both, the
     * firing grip.</p>
     */
    public static float[] rightHand(String action, float progress, float[] out) {
        boolean reload = "reload_tactical".equals(action) || "reload_empty".equals(action);
        float lever = holdOnLever();
        float load = holdOnRound(reload ? action : "", progress);

        if (lever > 0.02F) {
            return onLever(out, lever);
        }
        if (load > 0.02F) {
            return HandMotion.lerp(out, GRIP, loadingPoint(), load);
        }
        loadPointSet = false;                    // 下次伸手从当帧的目标点起步，别从旧位置滑过来
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * Advances {@link #loadHold}: 1 through the clip's loading stretch, 0 outside it, eased at
     * {@link #LOAD_TAU} — the same one-rule shape as {@link #holdOnLever}, so the hand is already on its way
     * out as the first round appears and only settles home after the last one is in. A non-reload action
     * decays it, so a clip that ends mid-stretch cannot leak the hold into whatever plays next.
     */
    private static float holdOnRound(String action, float progress) {
        float from;
        float to;
        float ticks;
        if ("reload_tactical".equals(action)) {
            from = LOAD_TACTICAL_FROM;
            to = LOAD_TACTICAL_TO;
            ticks = 44.0F;
        } else if ("reload_empty".equals(action)) {
            from = LOAD_EMPTY_FROM;
            to = LOAD_EMPTY_TO;
            ticks = 88.0F;
        } else {
            loadHold = HandMotion.ease(loadHold, 0.0F, LOAD_TAU);
            return loadHold;
        }
        float t = progress * ticks;
        loadHold = HandMotion.ease(loadHold, t >= from && t <= to ? 1.0F : 0.0F, LOAD_TAU);
        return loadHold;
    }

    /**
     * The loading hand's target this frame: the live round's grip while one is at the gate, the waiting spot
     * outside it in between — smoothed, because each fresh round steps straight out and a hand welded to the
     * bone would teleport with it. The result is a real loading rhythm: in with the round, the round is home,
     * the hand pulls back out to meet the next one.
     */
    private static float[] loadingPoint() {
        boolean live = frame.roundAtGate() && frame.roundGrip(ROUND_GRIP, ROUND_NOW);
        float[] want = live ? ROUND_NOW : ROUND_READY;

        if (!loadPointSet) {
            System.arraycopy(want, 0, loadPoint, 0, 3);
            loadPointSet = true;
        } else {
            loadPoint[0] = HandMotion.ease(loadPoint[0], want[0], ROUND_FOLLOW_TAU);
            loadPoint[1] = HandMotion.ease(loadPoint[1], want[1], ROUND_FOLLOW_TAU);
            loadPoint[2] = HandMotion.ease(loadPoint[2], want[2], ROUND_FOLLOW_TAU);
        }
        return loadPoint;
    }

    /**
     * Advances {@link #handleHold} for this frame: 1 while the live lever is off home, 0 once the clip has
     * swung it shut, with {@link HandMotion#ease} at {@link #HOLD_TAU} between the two — one rule covering
     * every clip that touches the lever.
     */
    private static float holdOnLever() {
        float on = frame.boltActivity(LEVER_TURN_MAX, LEVER_PULL_MAX) > 0.02F ? 1.0F : 0.0F;
        handleHold = HandMotion.ease(handleHold, on, HOLD_TAU);
        return handleHold;
    }

    /** The firing grip, or the live lever loop if the hand belongs on it. */
    private static float[] onLever(float[] out, float k) {
        if (k > 0.0F && frame.boltGrip(LEVER_KNOB, KNOB)) {
            return HandMotion.lerp(out, GRIP, KNOB, k);
        }
        System.arraycopy(GRIP, 0, out, 0, 3);
        return out;
    }

    /**
     * The support hand stays on the fore-end through everything — a lever gun is cycled with the rifle
     * shouldered and the left hand holding it. Only a small settle during the reloads keeps the wrist from
     * locking rigid.
     */
    public static float[] leftHand(String action, float progress, float[] out) {
        float settle = 0.0F;
        if ("reload_empty".equals(action) || "reload_tactical".equals(action)) {
            settle = 0.18F * HandMotion.bump(progress, 0.10F, 0.35F, 0.80F);
        }
        out[0] = SUPPORT[0];
        out[1] = SUPPORT[1] - settle;
        out[2] = SUPPORT[2];
        return out;
    }
}
