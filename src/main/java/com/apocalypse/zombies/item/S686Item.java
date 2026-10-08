package com.apocalypse.zombies.item;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.S686ItemRenderer;
import com.apocalypse.zombies.registry.ModSounds;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.BlockEntityWithoutLevelRenderer;
import net.minecraft.core.Holder;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.extensions.common.IClientItemExtensions;
import net.minecraftforge.registries.RegistryObject;
import software.bernie.geckolib.animatable.GeoItem;
import software.bernie.geckolib.animatable.SingletonGeoAnimatable;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Gold Plate - S686 — a GeckoLib-boned <b>break-action over-under shotgun</b>, and the second gun of the
 * shotgun line.
 *
 * <p>Geometry and animation live in {@code assets/apocalypse_zombies/geo/s686.geo.json} and
 * {@code animations/s686.animation.json}: 25 bones, eight clips ({@value #ANIM_IDLE}, {@value #ANIM_DRAW},
 * {@value #ANIM_SHOOT}, {@value #ANIM_BOLT}, {@value #ANIM_RELOAD_TACTICAL}, {@value #ANIM_RELOAD_EMPTY},
 * {@value #ANIM_ADS_UP}, {@value #ANIM_ADS_DOWN}). The model is 1.22 blocks long (19.50 u), 281 cubes and one
 * 512² texture; every pose is per-bone rotation/translation, nothing scales the model, per 美术规范.md §5.</p>
 *
 * <p>Three things make this an S686 and not a sawn-off rifle, and all three are action logic:</p>
 * <ul>
 *   <li><b>There is no action to cycle.</b> A break-action O/U has no bolt, no self-loading cycle and no
 *       magazine: two chambers, one above the other, and the whole barrel group folds 38° about the hinge at
 *       {@code barrel}'s pivot to open them. So this class has no automatic-fire path at all — no
 *       {@code shoot_auto} clip, no fast re-trigger — and {@value #ANIM_BOLT} carries a different job here
 *       than on the Uzi: it is the <em>fold-and-check</em>, the action opened and shut with nothing loaded.
 *       {@value #FIRE_INTERVAL_TICKS} ticks between shots is not a rate of fire, it is the beat the shooter
 *       needs to find the second barrel.</li>
 *   <li><b>Two rounds, and the second one is a separate barrel.</b> {@value #MAGAZINE_SIZE} shells. Each
 *       trigger pull spends one; a sneak-pull spends both, because on a break-action the two chambers are
 *       independent and firing them together is a thing the gun can simply do — the {@value #ANIM_SHOOT}
 *       clip already fires the pair (the art's hammer bone falls once for both), so the volley needs no clip
 *       of its own.</li>
 *   <li><b>Eight pellets a shell.</b> Every shot is a cone of {@value #PELLETS} independent hitscans, each
 *       graded by its own distance, each stopping in the body it meets. That is the whole ballistic
 *       character of a shotgun and it cannot be faked by one hard-hitting ray: the pattern is what makes it
 *       devastating at contact and nearly useless past {@value #RANGE_FAR} blocks (see the ballistics block).</li>
 * </ul>
 *
 * <p><b>Reloading is the art's, not the code's.</b> The chambered/shell-swap split the Uzi makes with its
 * magazine is made here by what is already in the chambers: a round left in the gun runs
 * {@value #ANIM_RELOAD_TACTICAL} (open, catch the live shell, two fresh ones home, shut), a dry gun runs
 * {@value #ANIM_RELOAD_EMPTY} (open, shake the spent cases out, feed two, shut). Both credit a full pair
 * when the clip ends, which is also when the weapon unlocks.</p>
 *
 * <p><b>Sounds are borrowed.</b> The recordings in {@code sounds/awm/} are TaCZ's AWM set shipped under
 * CC BY-NC-ND 4.0 (see {@code registry/ModSounds}); this gun triggers those same ids rather than shipping an
 * S686 set it does not have — the same route the Uzi took. Nothing is re-encoded, and swapping in real
 * shotgun recordings is a resource change only, because the cue tables below are keyed by tick against the
 * clips in {@code s686.animation.json}.</p>
 *
 * <p>Ballistics are this project's own choice, not a transcription: a 12-gauge load of 00 buck out of a
 * 20-inch pair of barrels does {@value #DAMAGE_NEAR} per pellet inside {@value #RANGE_MID} blocks,
 * {@value #DAMAGE_MID} to {@value #RANGE_FAR}, {@value #DAMAGE_FAR} to {@value #MAX_RANGE}, and never passes
 * through a body. Server-authoritative throughout: the client only asks ({@code FirePacket} /
 * {@code ReloadPacket}) and every decision is made here from the stack's NBT.</p>
 */
public class S686Item extends Item implements GeoItem, GunItem {

    /** Always-on controller, loops the idle pose. */
    public static final String CONTROLLER_MAIN = "main";
    /** Trigger-driven controller for one-shot actions. */
    public static final String CONTROLLER_ACTION = "action";

    /** Trigger names — these are what Java passes to {@code triggerAnim}, not the clip names. */
    public static final String TRIGGER_DRAW = "draw";
    public static final String TRIGGER_SHOOT = "shoot";
    public static final String TRIGGER_BOLT = "bolt";
    public static final String TRIGGER_RELOAD_TACTICAL = "reload_tactical";
    public static final String TRIGGER_RELOAD_EMPTY = "reload_empty";
    public static final String TRIGGER_ADS_UP = "ADS_up";
    public static final String TRIGGER_ADS_DOWN = "ADS_down";

    /** Clip names as exported from Blockbench — must match s686.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_DRAW = "draw";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_BOLT = "bolt";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_RELOAD_EMPTY = "reload_empty";
    public static final String ANIM_ADS_UP = "ADS_up";
    public static final String ANIM_ADS_DOWN = "ADS_down";

    /** Clip lengths in ticks (20 t/s), taken from s686.animation.json. */
    private static final int DRAW_TICKS = 20;              // 1.0 s
    private static final int SHOOT_TICKS = 12;              // 0.6 s — the recoil, and nothing else
    private static final int BOLT_TICKS = 26;               // 1.2667 s — fold open, check, fold shut
    private static final int RELOAD_TACTICAL_TICKS = 52;    // 2.6 s
    private static final int RELOAD_EMPTY_TICKS = 66;       // 3.3 s

    /**
     * Ticks between shots: one second.
     *
     * <p>Not a cyclic rate — there is no cycle to run. It is the beat the second barrel costs: the trigger
     * has to be released and pulled again, which is also what the 0.6 s {@value #ANIM_SHOOT} clip leaves room
     * for. This is the client's own fire poll too, so a held button asks for exactly one shell a second and
     * nothing is dropped.</p>
     */
    private static final int FIRE_INTERVAL_TICKS = 20;

    /** Two chambers, one above the other — the whole gun. */
    public static final int MAGAZINE_SIZE = 2;

    // ------------------------------------------------------------------ sight

    /** Iron sights: a bead on a rib, so the gun zooms a little and draws no overlay. */
    private static final double AIMED_FOV = 55.0D;
    /** A shotgun comes up fast — it is short and it is carried at the shoulder. */
    private static final float AIM_TIME = 0.16F;
    /**
     * Where the sight line sits in the hip pose, expressed as the offset that brings it up to the eye.
     * Measured, not eyeballed, with the same chain {@code tools/pose_measure.py} walks — see the class note
     * on the sight line below.
     *
     * <p>{@code ADS_X} is the pair the iron-sighted guns settle on: the dominant term is the hand base
     * itself, scaled by {@link #FIRST_PERSON_SCALE}. {@code ADS_Y} is this gun's own, and it is the largest
     * of the rack (0.3596 against the rifles' 0.346 and the Uzi's 0.3015) because the S686's rib sits high
     * over a pair of barrels that straddle the model's own origin — see {@code models/item/s686.json}.</p>
     */
    private static final float ADS_X = -0.4749F;
    private static final float ADS_Y = 0.3533F;
    /**
     * The item model's first-person {@code display} rotation (degrees), cancelled while aiming so the sight
     * line ends up parallel to the view axis — see {@link GunItem#adsPitch()}.
     */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;
    /** How much bigger the gun reads in the first person, on top of the {@code display} block's own size. */
    private static final float FIRST_PERSON_SCALE = 1.25F;
    /**
     * Firing kick as a pitch about the grip (degrees at full kick). Heavier than the Uzi's 1.6 — a 12-gauge
     * load in a 3 kg gun is the hardest single kick in the rack — but still well under the rifles', because
     * the shot is one event a second rather than a burst and the picture has time to settle.
     */
    private static final float FIRE_PITCH = 3.2F;

    // ------------------------------------------------------------------ ballistics

    /**
     * Per <em>pellet</em>, not per shot: eight of these land on a body at contact.
     *
     * <p>{@value #DAMAGE_NEAR} × {@value #PELLETS} = 32 at arm's length, which is where a shotgun is
     * supposed to be worth carrying; past {@value #RANGE_MID} blocks the pattern has opened enough that
     * three or four pellets are the realistic hit, and past {@value #RANGE_FAR} it is a nuisance.</p>
     */
    private static final float DAMAGE_NEAR = 4.0F;
    private static final float DAMAGE_MID = 3.0F;
    private static final float DAMAGE_FAR = 2.0F;
    /** A 12-gauge is a close-quarters tool: the pattern does the work, the range does not. */
    private static final double RANGE_MID = 12.0D;
    private static final double RANGE_FAR = 32.0D;
    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    private static final double HEADSHOT_HEIGHT = 0.82D;
    /** A pellet stops in the body it meets — no exit, which is most of why the pattern stops a room. */
    private static final int PIERCE = 1;
    private static final double MAX_RANGE = 64.0D;

    /** Eight pellets a shell — the S686's cylinder-bore load, and the whole point of the weapon. */
    private static final int PELLETS = 8;
    /**
     * Pellet cone half-angle, degrees: the tangent of it is the radius the pattern has opened to, one block
     * down range. 3° is about 1 block of spread at 20 blocks — a cylinder-bore pattern, not a choked one.
     */
    private static final double SPREAD_DEGREES = 3.0D;
    /** Precomputed, so the per-pellet path does no trigonometry beyond its own polar sample. */
    private static final double SPREAD_TAN = Math.tan(Math.toRadians(SPREAD_DEGREES));

    /**
     * 独头弹：把八颗小弹丸换成一颗大铅弹。
     *
     * <p>贴脸 <b>34</b>，比鹿弹八颗全中的 32 略高；中远距离更耐打（26 / 18，鹿弹同距离是 24 / 16）。
     * 代价是<b>只有一次命中判定</b> —— 打偏就是零，鹿弹靠覆盖面兜底。散布也收到鹿弹的四分之一，
     * 它本来就是拿来打远的。</p>
     */
    private static final float SLUG_DAMAGE_NEAR = 34.0F;
    private static final float SLUG_DAMAGE_MID = 26.0F;
    private static final float SLUG_DAMAGE_FAR = 18.0F;
    private static final double SLUG_RANGE_MID = 32.0D;
    private static final double SLUG_RANGE_FAR = 64.0D;
    private static final double SLUG_SPREAD_TAN = SPREAD_TAN * 0.25D;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "s686_bullet"));

    // ------------------------------------------------------------------ tracer

    /** Wider spacing than the Uzi's: eight tracers at once must not become a wall of light. */
    private static final double TRACER_SPACING = 0.9D;
    private static final int TRACER_MAX_DOTS = 20;

    // ------------------------------------------------------------------ state keys

    private static final String TAG_AMMO = "Ammo";
    private static final String TAG_ACTION = "Action";
    private static final String TAG_ACTION_AT = "ActionAt";
    private static final String TAG_PENDING = "Pending";
    private static final String TAG_PENDING_AT = "PendingAt";
    private static final String TAG_LOCKED_UNTIL = "LockedUntil";
    /** Latches {@value #ANIM_DRAW} so it plays on selection rather than every tick the gun is held. */
    private static final String TAG_DRAWN = "Drawn";

    private static final long NONE = -1L;

    private static final String ACTION_DRAW = "draw";
    private static final String ACTION_SHOOT = "shoot";
    private static final String ACTION_BOLT = "bolt";
    private static final String ACTION_RELOAD_TACTICAL = "reload_tactical";
    private static final String ACTION_RELOAD_EMPTY = "reload_empty";

    /**
     * When each mechanical sound fires, in ticks from the start of its action.
     *
     * <p>These are keyed against the clips in {@code s686.animation.json}, and the beats below are read off
     * the clips' own keyframes: the top lever moves at 0.083 s in {@code bolt} and the barrel is at its 38°
     * stop from 0.42 s. The report itself is not here — it is played live in {@link #playShot}, on the tick
     * of the shot.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> SHOOT_SOUNDS = Map.of();

    /**
     * The fold-and-check: lever thrown (t=1), barrels off the face (t=8), barrels home (t=20), lever latched
     * (t=23). Read off {@code bolt}'s keyframes — lever at 0.083 s, barrel open 0.125→0.417 s and shut again
     * at 1.0 s, lever home at 1.125 s.
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            1, ModSounds.AWM_RECHAMBER_OUT,
            8, ModSounds.AWM_RELOAD_MAGOUT,
            20, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            23, ModSounds.AWM_RECHAMBER_END);

    /** Bringing the gun up: the stock settles against the shoulder, then the lever is checked. */
    private static final Map<Integer, RegistryObject<SoundEvent>> DRAW_SOUNDS = Map.of(
            4, ModSounds.AWM_RELOAD_RAISE,
            14, ModSounds.AWM_RECHAMBER_END);

    /**
     * The live-shell swap: open (t=2 lever, t=10 barrels), the shells out and back in at 1.625→2.0 s
     * (t=32…40), barrels shut at 2.042 s (t=41), lever home at 2.208 s (t=44).
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            2, ModSounds.AWM_RECHAMBER_OUT,
            10, ModSounds.AWM_RELOAD_MAGOUT,
            32, ModSounds.AWM_RELOAD_MAGIN,
            41, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            44, ModSounds.AWM_RELOAD_END);

    /**
     * The empty-gun reload: lever at 0.167 s (t=3), barrels open 0.125→0.542 s (t=11), the extractor lifts
     * the spent cases at 0.833 s (t=17), fresh shells ride home 2.0→2.333 s (t=41), barrels shut at 2.75 s
     * (t=55), lever latched at 2.792 s (t=61).
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            3, ModSounds.AWM_RECHAMBER_OUT,
            11, ModSounds.AWM_RELOAD_EMPTY_MAGOUT,
            17, ModSounds.AWM_RELOAD_EJECT,
            41, ModSounds.AWM_RELOAD_EMPTY_MAGIN,
            55, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            61, ModSounds.AWM_RELOAD_EMPTY_END);

    private static final double SHOT_HEARD_SQR = 64.0D * 64.0D;

    private static final RawAnimation IDLE = RawAnimation.begin().thenLoop(ANIM_IDLE);
    private static final RawAnimation DRAW = RawAnimation.begin().thenPlay(ANIM_DRAW);
    private static final RawAnimation SHOOT = RawAnimation.begin().thenPlay(ANIM_SHOOT);
    private static final RawAnimation BOLT = RawAnimation.begin().thenPlay(ANIM_BOLT);
    private static final RawAnimation RELOAD_TACTICAL = RawAnimation.begin().thenPlay(ANIM_RELOAD_TACTICAL);
    private static final RawAnimation RELOAD_EMPTY = RawAnimation.begin().thenPlay(ANIM_RELOAD_EMPTY);
    private static final RawAnimation ADS_UP = RawAnimation.begin().thenPlay(ANIM_ADS_UP);
    private static final RawAnimation ADS_DOWN = RawAnimation.begin().thenPlay(ANIM_ADS_DOWN);

    private static final int TRANSITION_TICKS = 4;

    private final AnimatableInstanceCache cache = GeckoLibUtil.createInstanceCache(this);

    public S686Item(Properties properties) {
        super(properties);
        SingletonGeoAnimatable.registerSyncedAnimatable(this);
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, CONTROLLER_MAIN, TRANSITION_TICKS,
                state -> state.setAndContinue(IDLE)));

        controllers.add(new AnimationController<>(this, CONTROLLER_ACTION, 0,
                        state -> PlayState.STOP)
                .triggerableAnim(TRIGGER_DRAW, DRAW)
                .triggerableAnim(TRIGGER_SHOOT, SHOOT)
                .triggerableAnim(TRIGGER_BOLT, BOLT)
                .triggerableAnim(TRIGGER_RELOAD_TACTICAL, RELOAD_TACTICAL)
                .triggerableAnim(TRIGGER_RELOAD_EMPTY, RELOAD_EMPTY)
                .triggerableAnim(TRIGGER_ADS_UP, ADS_UP)
                .triggerableAnim(TRIGGER_ADS_DOWN, ADS_DOWN));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.cache;
    }

    // ------------------------------------------------------------------ GunItem: what the gun is

    @Override
    public int magazineSize() {
        return MAGAZINE_SIZE;
    }

    @Override
    public double aimedFov() {
        return AIMED_FOV;
    }

    @Override
    public float aimTime() {
        return AIM_TIME;
    }

    @Override
    public boolean hasScopeOverlay() {
        return false;
    }

    /**
     * Iron sights: the front bead and the rib <em>are</em> the aim point, so the gun has to stay in the
     * frame — hiding it would leave the player aiming at a bare crosshair.
     */
    @Override
    public boolean hidesModelWhileAimed() {
        return false;
    }

    @Override
    public float adsX() {
        return ADS_X;
    }

    @Override
    public float adsY() {
        return ADS_Y;
    }

    @Override
    public float adsZ() {
        return 0.0F;
    }

    @Override
    public float adsPitch() {
        return DISPLAY_PITCH;
    }

    @Override
    public float adsYaw() {
        return DISPLAY_YAW;
    }

    @Override
    public float firstPersonScale() {
        return FIRST_PERSON_SCALE;
    }

    @Override
    public float firePitch() {
        return FIRE_PITCH;
    }

    @Override
    public int ammo(ItemStack stack) {
        return getAmmo(stack);
    }

    @Override
    public boolean isReloading(ItemStack stack, long now) {
        return isReloadAction(getAction(stack)) && now >= get(stack, TAG_ACTION_AT);
    }

    @Override
    public float reloadProgress(ItemStack stack, long now) {
        String action = getAction(stack);
        long length = actionLength(action);
        if (length <= 0 || now < get(stack, TAG_ACTION_AT)) {
            return 0.0F;
        }
        float done = (float) (now - get(stack, TAG_ACTION_AT)) / (float) length;
        return Math.max(0.0F, Math.min(1.0F, done));
    }

    @Override
    public String action(ItemStack stack, long now) {
        String action = getAction(stack);
        long length = actionLength(action);
        long at = get(stack, TAG_ACTION_AT);
        return length > 0 && now >= at && now < at + length ? action : "";
    }

    @Override
    public float actionProgress(ItemStack stack, long now) {
        String action = getAction(stack);
        long length = actionLength(action);
        long at = get(stack, TAG_ACTION_AT);
        if (length <= 0 || now < at) {
            return 0.0F;
        }
        return Math.max(0.0F, Math.min(1.0F, (float) (now - at) / (float) length));
    }

    // ------------------------------------------------------------------ firing

    /**
     * One trigger pull, straight off the wire.
     *
     * <p>Two shells, so there are exactly three cases and no state machine to hold them together:</p>
     * <ul>
     *   <li><b>Dry</b> — the trigger falls on empty chambers, and the gun answers the way a break-action
     *       does: the action is folded open to look at them. That is {@value #ANIM_BOLT} on this gun, and it
     *       is what pays for the clip existing at all. The weapon locks for its length, so the fold finishes
     *       before the auto-loader (see {@link #inventoryTick}) reaches for shells.</li>
     *   <li><b>Sneaking</b> with both chambers loaded — both barrels, one volley: two shells, sixteen
     *       pellets, one {@value #ANIM_SHOOT}. No new clip, because the art already fires the pair.</li>
     *   <li><b>Otherwise</b> — one shell, one barrel, eight pellets.</li>
     * </ul>
     *
     * <p>The lock is always the full {@value #FIRE_INTERVAL_TICKS}, spent chambers or not: the interval is
     * the game's, not the clip's, so a shooter cannot outrun the second barrel by tapping faster.</p>
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry. A break-action's answer to a dead trigger is to fold the action open and look at the
            // chambers, and that is the `bolt` clip: open, check, shut. Low and dry on purpose round a
            // shotgun's lever rather than a striker's click — nothing has fallen.
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    ModSounds.AWM_RECHAMBER_OUT.get(), SoundSource.PLAYERS, 0.5F, 0.9F);
            trigger(player, stack, level, TRIGGER_BOLT);
            startAction(stack, ACTION_BOLT, now);
            put(stack, TAG_LOCKED_UNTIL, now + BOLT_TICKS);
            return;
        }

        // Both barrels on a sneak-pull: the chambers are independent on a break-action, so the second shell
        // is not a second action, it is the other barrel. Firing them together needs no art of its own.
        int shells = player.isShiftKeyDown() && getAmmo(stack) >= MAGAZINE_SIZE ? MAGAZINE_SIZE : 1;
        setAmmo(stack, getAmmo(stack) - shells);
        clearPending(stack);
        put(stack, TAG_LOCKED_UNTIL, now + FIRE_INTERVAL_TICKS);
        trigger(player, stack, level, TRIGGER_SHOOT);
        startAction(stack, ACTION_SHOOT, now);

        fireShot(player, level, stack, shells);
    }

    /**
     * One shot's worth of pellets, all from the same muzzle.
     *
     * <p>The flash, the report and — if anything was hit in the head — the crit sound are played once for the
     * shot rather than once per pellet; eight of each a second would be a different, worse weapon.</p>
     *
     * @param shells 1, or {@value #MAGAZINE_SIZE} for the two-barrel volley
     */
    private void fireShot(ServerPlayer player, ServerLevel level, ItemStack stack, int shells) {
        // 弹种决定这一枪打出去的是"一片"还是"一颗"：鹿弹是 8 颗小弹丸、锥面覆盖；独头弹是 1 颗大弹丸、
        // 散布收四分之一。铝热弹不在这条分支里 —— 它只是把命中的敌对生物点着，由 ThermiteRounds 统一处理。
        boolean slug = currentAmmo(stack) == AmmoType.SLUG;
        int pellets = slug ? 1 : PELLETS;

        Vec3 eye = player.getEyePosition();
        Vec3 look = player.getLookAngle();
        Vec3 right = look.cross(new Vec3(0.0D, 1.0D, 0.0D)).normalize();
        Vec3 up = right.cross(look).normalize();
        // The longest gun in the rack: the muzzle sits most of a block out and only a little low, on the
        // bore between the two barrels.
        Vec3 muzzle = eye.add(look.scale(0.90D)).add(right.scale(-0.06D)).add(0.0D, -0.10D, 0.0D);

        boolean headshot = false;
        for (int pellet = 0; pellet < pellets * shells; pellet++) {
            headshot |= firePellet(player, level, eye, spread(look, right, up, level, slug), muzzle, slug);
        }
        if (headshot) {
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    SoundEvents.PLAYER_ATTACK_CRIT, SoundSource.PLAYERS, 1.0F, 1.2F);
        }

        level.sendParticles(ParticleTypes.FLAME, muzzle.x, muzzle.y, muzzle.z, 4, 0.02D, 0.02D, 0.02D, 0.03D);
        level.sendParticles(ParticleTypes.END_ROD, muzzle.x, muzzle.y, muzzle.z, 5, 0.05D, 0.05D, 0.05D, 0.03D);
        // Brass. A break-action throws nothing until it is opened, so there is no ejection here at all —
        // the cases are what {@value #ANIM_RELOAD_EMPTY} drives out of the chambers, on the shell bones.
        playShot(player, level);
    }

    /**
     * One pellet's direction: the aim line plus a sample taken evenly over the cone's <em>disc</em>.
     *
     * <p>{@code sqrt} on the radius is what makes the pattern even. Sampling the radius linearly would put
     * half the pellets in the middle third of the cone, which reads as a gun that cannot miss; the square
     * root spreads them over the area instead, so the pattern on a wall is a disc rather than a blob.</p>
     */
    private Vec3 spread(Vec3 look, Vec3 right, Vec3 up, ServerLevel level, boolean slug) {
        // 独头弹的散布收到鹿弹的四分之一：一颗弹丸没有覆盖面兜底，抖一点就是脱靶。
        double radius = (slug ? SLUG_SPREAD_TAN : SPREAD_TAN) * Math.sqrt(level.random.nextDouble());
        double angle = level.random.nextDouble() * Math.PI * 2.0D;
        return look.add(right.scale(Math.cos(angle) * radius))
                .add(up.scale(Math.sin(angle) * radius))
                .normalize();
    }

    /**
     * One pellet: block first, bodies after, nothing above {@value #PIERCE}.
     *
     * @return true when the pellet landed in a head, so the caller can play the crit sound once a shot
     */
    private boolean firePellet(ServerPlayer player, ServerLevel level, Vec3 eye, Vec3 direction, Vec3 muzzle,
                               boolean slug) {
        Vec3 reach = eye.add(direction.scale(MAX_RANGE));
        BlockHitResult blockHit = level.clip(
                new ClipContext(eye, reach, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
        double wallDistance = blockHit.getType() == HitResult.Type.MISS
                ? MAX_RANGE
                : eye.distanceTo(blockHit.getLocation());

        Vec3 impact = blockHit.getType() == HitResult.Type.MISS
                ? eye.add(direction.scale(wallDistance))
                : blockHit.getLocation();

        boolean headshot = false;
        int hits = 0;
        for (EntityHitResult hit : collectTargets(level, player, eye, direction, wallDistance)) {
            if (hits++ >= PIERCE) {
                break;
            }
            Entity target = hit.getEntity();
            double distance = eye.distanceTo(hit.getLocation());
            boolean head = hit.getLocation().y > target.getY() + target.getBbHeight() * HEADSHOT_HEIGHT;
            float damage = damageAt(distance, slug) * (head ? HEADSHOT_MULTIPLIER : 1.0F);

            target.invulnerableTime = 0;
            target.hurt(bulletSource(level, player), damage);
            level.sendParticles(ParticleTypes.DAMAGE_INDICATOR,
                    hit.getLocation().x, hit.getLocation().y, hit.getLocation().z,
                    4, 0.15D, 0.15D, 0.15D, 0.15D);
            headshot |= head;
            impact = hit.getLocation();
        }

        if (blockHit.getType() != HitResult.Type.MISS) {
            Vec3 surface = blockHit.getLocation();
            level.sendParticles(ParticleTypes.CRIT, surface.x, surface.y, surface.z, 4, 0.1D, 0.1D, 0.1D, 0.2D);
            level.sendParticles(ParticleTypes.SMOKE, surface.x, surface.y, surface.z, 2, 0.05D, 0.05D, 0.05D, 0.01D);
        }

        spawnTracer(level, muzzle, impact);
        return headshot;
    }

    /** The report: close mix for the shooter, distant one for everyone in earshot. */
    private void playShot(ServerPlayer player, ServerLevel level) {
        // Pitched down from the recording: the sample is a .338 rifle, and a 12-gauge is the deeper of the
        // two. Cheaper than a new set, and honest — see the class note on borrowed sounds.
        player.playNotifySound(ModSounds.AWM_SHOOT.get(), SoundSource.PLAYERS, 1.0F, 0.85F);
        SoundEvent distant = ModSounds.AWM_SHOOT_3P.get();
        for (ServerPlayer other : level.players()) {
            if (other != player && other.distanceToSqr(player) < SHOT_HEARD_SQR) {
                other.playNotifySound(distant, SoundSource.PLAYERS, 2.0F, 0.95F);
            }
        }
    }

    /** Every entity the ray can reach, sorted by distance, ignoring the shooter. */
    private List<EntityHitResult> collectTargets(ServerLevel level, ServerPlayer player, Vec3 from,
                                                 Vec3 direction, double maxDistance) {
        Vec3 to = from.add(direction.scale(maxDistance));
        List<EntityHitResult> targets = new ArrayList<>();

        for (Entity candidate : level.getEntities(player, new AABB(from, to).inflate(1.0D),
                entity -> entity instanceof LivingEntity && entity.isAlive() && entity.isPickable()
                        && !entity.isSpectator())) {
            candidate.getBoundingBox().inflate(0.25D).clip(from, to).ifPresent(point ->
                    targets.add(new EntityHitResult(candidate, point)));
        }

        targets.sort(Comparator.comparingDouble(hit -> from.distanceToSqr(hit.getLocation())));
        return targets;
    }

    /** Distance-graded damage, this file's breakpoints. 独头弹走自己那一套（更高、更耐远）。 */
    private static float damageAt(double distance, boolean slug) {
        if (slug) {
            if (distance <= SLUG_RANGE_MID) {
                return SLUG_DAMAGE_NEAR;
            }
            return distance <= SLUG_RANGE_FAR ? SLUG_DAMAGE_MID : SLUG_DAMAGE_FAR;
        }
        if (distance <= RANGE_MID) {
            return DAMAGE_NEAR;
        }
        return distance <= RANGE_FAR ? DAMAGE_MID : DAMAGE_FAR;
    }

    /**
     * 霰弹枪比别的枪多一个独头弹。铝热弹与普通弹来自 {@link GunItem} 的默认实现 —— 那是通用弹种，
     * 五把枪共用。
     */
    @Override
    public List<AmmoType> ammoTypes(ItemStack stack) {
        return List.of(AmmoType.STANDARD, AmmoType.SLUG, AmmoType.THERMITE);
    }

    private DamageSource bulletSource(ServerLevel level, ServerPlayer player) {
        Holder<DamageType> holder = level.registryAccess()
                .registryOrThrow(Registries.DAMAGE_TYPE)
                .getHolderOrThrow(DAMAGE_TYPE);
        return new DamageSource(holder, player, player);
    }

    /** Draws one pellet's path as a dashed line of glowing particles. */
    private void spawnTracer(ServerLevel level, Vec3 from, Vec3 to) {
        double distance = from.distanceTo(to);
        if (distance < 0.1D) {
            return;
        }
        double spacing = Math.max(TRACER_SPACING, distance / TRACER_MAX_DOTS);
        Vec3 step = to.subtract(from).normalize().scale(spacing);

        for (Vec3 point = from; point.distanceTo(from) < distance; point = point.add(step)) {
            level.sendParticles(ParticleTypes.END_ROD, point.x, point.y, point.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
    }

    // ------------------------------------------------------------------ reloading

    /**
     * Called from the reload key. A shell still in a chamber runs the short swap; a dry gun runs the full
     * 折开 → 退壳 → 上弹 → 合膛 sequence. The pair is credited back when the clip ends, which is also when
     * the weapon unlocks.
     *
     * <p>Both are full reloads — a break-action cannot be topped up one chamber at a time without opening it,
     * and opening it means handling what is already in there. Which of the two runs is simply whether there
     * is anything left to catch.</p>
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }
        boolean chambered = getAmmo(stack) > 0;
        int ticks = chambered ? RELOAD_TACTICAL_TICKS : RELOAD_EMPTY_TICKS;

        // Started on the spot, so the clip's own first sound cue (t=2 / t=3) lands where the file puts it.
        clearPending(stack);
        scheduleAction(stack, chambered ? ACTION_RELOAD_TACTICAL : ACTION_RELOAD_EMPTY, now);
        put(stack, TAG_LOCKED_UNTIL, now + ticks);
    }

    /** Server-side tick: drives the scheduled action and its sound cues. */
    @Override
    public void inventoryTick(ItemStack stack, Level level, Entity entity, int slot, boolean selected) {
        if (level.isClientSide || !(level instanceof ServerLevel serverLevel)) {
            return;
        }
        long now = serverLevel.getGameTime();

        // 0) Selection: the gun comes up once each time it is taken in hand, not every tick it is held.
        if (entity instanceof Player player) {
            boolean drawn = getBool(stack, TAG_DRAWN);
            if (selected && !drawn) {
                putBool(stack, TAG_DRAWN, true);
                if (!isLocked(stack, now)) {
                    trigger(player, stack, serverLevel, TRIGGER_DRAW);
                    startAction(stack, ACTION_DRAW, now);
                    put(stack, TAG_LOCKED_UNTIL, now + DRAW_TICKS);
                    return;
                }
            } else if (!selected && drawn) {
                putBool(stack, TAG_DRAWN, false);
            }
        }

        // 1) A scheduled action whose time has come. "now >= at" rather than "now == at" so a tick the
        //    server spent elsewhere delays the action instead of losing it.
        String pending = getPending(stack);
        if (!pending.isEmpty() && now >= get(stack, TAG_PENDING_AT)) {
            if (entity instanceof Player player) {
                trigger(player, stack, serverLevel, triggerFor(pending));
            }
            clearPending(stack);
            startAction(stack, pending, now);
            return;
        }

        // 2) The chambers ran dry and the weapon is idle again: a break-action with shells on the belt
        //    loads itself rather than sitting on two dead triggers. Held only — a gun left in the pack
        //    stays as it was put away. The dry-trigger fold (see tryFire) owns the weapon while it runs, so
        //    this waits for it rather than cutting across it.
        if (selected && getAmmo(stack) <= 0 && getAction(stack).isEmpty() && !isLocked(stack, now)
                && entity instanceof ServerPlayer serverPlayer) {
            beginReload(serverPlayer, stack, serverLevel);
        }

        // 3) A running action: play whatever its clip calls for at this tick.
        String action = getAction(stack);
        if (action.isEmpty()) {
            return;
        }
        long elapsed = now - get(stack, TAG_ACTION_AT);
        if (elapsed < 0) {
            return;
        }
        RegistryObject<SoundEvent> cue = soundCuesFor(action).get((int) elapsed);
        if (cue != null && entity instanceof Player player) {
            serverLevel.playSound(null, player.getX(), player.getY(), player.getZ(),
                    cue.get(), SoundSource.PLAYERS, 1.0F, 1.0F);
        }

        if (elapsed >= actionLength(action)) {
            // A finished reload is what credits the fresh pair; a shot or a fold just clears itself.
            if (isReloadAction(action)) {
                setAmmo(stack, MAGAZINE_SIZE);
            }
            clearAction(stack);
        }
    }

    /** Right-click is the sight, not the trigger — firing lives on the left button and arrives by packet. */
    @Override
    public InteractionResultHolder<ItemStack> use(Level level, Player player, InteractionHand hand) {
        return InteractionResultHolder.pass(player.getItemInHand(hand));
    }

    /** Server-side: plays one trigger on the stack's animation instance. */
    private void trigger(Player player, ItemStack stack, ServerLevel level, String trigger) {
        triggerAnim(player, GeoItem.getOrAssignId(stack, level), CONTROLLER_ACTION, trigger);
    }

    /** True while a shot, a fold or a reload owns the weapon. */
    private boolean isLocked(ItemStack stack, long now) {
        long lockedUntil = get(stack, TAG_LOCKED_UNTIL);
        return lockedUntil != NONE && now < lockedUntil;
    }

    // ------------------------------------------------------------------ state

    /** Shells left, defaulting to a full pair for a stack that has never been fired. */
    public static int getAmmo(ItemStack stack) {
        CompoundTag tag = stack.getTag();
        return tag != null && tag.contains(TAG_AMMO) ? tag.getInt(TAG_AMMO) : MAGAZINE_SIZE;
    }

    private static void setAmmo(ItemStack stack, int rounds) {
        stack.getOrCreateTag().putInt(TAG_AMMO, Math.max(0, rounds));
    }

    private static long get(ItemStack stack, String key) {
        CompoundTag tag = stack.getTag();
        return tag != null && tag.contains(key) ? tag.getLong(key) : NONE;
    }

    private static void put(ItemStack stack, String key, long value) {
        stack.getOrCreateTag().putLong(key, value);
    }

    private static boolean getBool(ItemStack stack, String key) {
        CompoundTag tag = stack.getTag();
        return tag != null && tag.getBoolean(key);
    }

    private static void putBool(ItemStack stack, String key, boolean value) {
        stack.getOrCreateTag().putBoolean(key, value);
    }

    // ------------------------------------------------------------------ action state

    private static String readString(ItemStack stack, String key) {
        CompoundTag tag = stack.getTag();
        return tag != null && tag.contains(key) ? tag.getString(key) : "";
    }

    private static void writeString(ItemStack stack, String key, String value) {
        stack.getOrCreateTag().putString(key, value);
    }

    private static void scheduleAction(ItemStack stack, String action, long at) {
        writeString(stack, TAG_PENDING, action);
        put(stack, TAG_PENDING_AT, at);
    }

    private static void startAction(ItemStack stack, String action, long now) {
        writeString(stack, TAG_ACTION, action);
        put(stack, TAG_ACTION_AT, now);
    }

    private static void clearPending(ItemStack stack) {
        writeString(stack, TAG_PENDING, "");
        put(stack, TAG_PENDING_AT, NONE);
    }

    private static void clearAction(ItemStack stack) {
        writeString(stack, TAG_ACTION, "");
        put(stack, TAG_ACTION_AT, NONE);
    }

    private static String getPending(ItemStack stack) {
        return readString(stack, TAG_PENDING);
    }

    private static String getAction(ItemStack stack) {
        return readString(stack, TAG_ACTION);
    }

    private static boolean isReloadAction(String action) {
        return ACTION_RELOAD_TACTICAL.equals(action) || ACTION_RELOAD_EMPTY.equals(action);
    }

    /** Animation trigger matching an action name. */
    private static String triggerFor(String action) {
        return switch (action) {
            case ACTION_DRAW -> TRIGGER_DRAW;
            case ACTION_SHOOT -> TRIGGER_SHOOT;
            case ACTION_BOLT -> TRIGGER_BOLT;
            case ACTION_RELOAD_TACTICAL -> TRIGGER_RELOAD_TACTICAL;
            default -> TRIGGER_RELOAD_EMPTY;
        };
    }

    /** Ticks the action's clip runs for, from s686.animation.json. */
    private static int actionLength(String action) {
        return switch (action) {
            case ACTION_DRAW -> DRAW_TICKS;
            case ACTION_SHOOT -> SHOOT_TICKS;
            case ACTION_BOLT -> BOLT_TICKS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_TICKS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_TICKS;
            default -> 0;
        };
    }

    private static Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case ACTION_SHOOT -> SHOOT_SOUNDS;
            case ACTION_BOLT -> BOLT_SOUNDS;
            case ACTION_DRAW -> DRAW_SOUNDS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_SOUNDS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_SOUNDS;
            default -> Map.of();
        };
    }

    // ------------------------------------------------------------------ client

    @Override
    public void initializeClient(Consumer<IClientItemExtensions> consumer) {
        consumer.accept(new IClientItemExtensions() {
            private S686ItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new S686ItemRenderer();
                }
                return this.renderer;
            }

            /**
             * Hands the first-person transform to {@link com.apocalypse.zombies.client.weapon.WeaponHandGrip}:
             * vanilla's hand base is kept, the sword-style attack swing is dropped, and the hold stance is
             * added. {@code true} means "handled" — vanilla skips its own transforms and renders.
             */
            @Override
            public boolean applyForgeHandTransform(PoseStack poseStack, LocalPlayer player, HumanoidArm arm,
                                                   ItemStack stack, float partialTick, float equipProcess,
                                                   float swingProcess) {
                return com.apocalypse.zombies.client.weapon.WeaponHandGrip
                        .apply(poseStack, player, arm, stack, equipProcess);
            }
        });
    }
}
