package com.apocalypse.zombies.item;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.Win94ItemRenderer;
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

/**
 * 温彻斯特 M1894（Win94 杠杆狙击枪） — a GeckoLib-boned lever-action rifle, and the fourth long gun in the
 * weapon layer.
 *
 * <p>Geometry and animation live in {@code assets/apocalypse_zombies/geo/win94.geo.json} and
 * {@code animations/win94.animation.json}: 16 bones, seven clips ({@value #ANIM_IDLE}, {@value #ANIM_DRAW},
 * {@value #ANIM_SHOOT}, {@value #ANIM_BOLT}, {@value #ANIM_RELOAD_TACTICAL}, {@value #ANIM_RELOAD_EMPTY},
 * {@value #ANIM_INSPECT}). The model is 1.11 blocks long (17.83 u) — a 24-inch Model 1894's proportions —
 * with a 512² texture. Every pose is per-bone rotation/translation, nothing scales the model.</p>
 *
 * <p>What makes this a Win94 and not a bolt gun with a different stock is the lever:</p>
 * <ul>
 *   <li><b>One swing of the lever is the whole action.</b> A shot fires {@value #ANIM_SHOOT} (recoil only)
 *       and the {@value #ANIM_BOLT} lever cycle is scheduled behind it — same shape as the Mosin's bolt —
 *       so holding the button gives one shot per {@value #SHOOT_TICKS}+{@value #BOLT_TICKS} ticks. The
 *       case leaves the receiver during the cycle, not during the shot.</li>
 *   <li><b>The magazine is a tube under the barrel and holds five.</b> Five .45-70 rounds nose-first in
 *       the magazine tube: {@value #ANIM_RELOAD_EMPTY} runs the lever slowly to feed the chamber, and
 *       {@value #ANIM_RELOAD_TACTICAL} tops a partly-full tube up with one quicker cycle. Both credit
 *       {@value #MAGAZINE_SIZE} rounds when the clip ends, which is also when the weapon unlocks.</li>
 *   <li><b>A clear sight, not a blackout scope.</b> The reference render's is a long hunting scope used
 *       with both eyes open, so aiming draws the {@link GunItem.SightStyle#CLEAR_SIGHT} lens — a pale
 *       wash with a transparent crosshair. The rifle and the hands then leave the frame entirely (see
 *       {@link #hidesModelWhileAimed()}), leaving the lens and the cross as the whole view. The zoom is a
 *       fixed {@value #AIMED_FOV}-degree field of view, about 2.5×.</li>
 * </ul>
 *
 * <p><b>Sounds are borrowed</b>, same as the Mosin: the recordings in {@code sounds/awm/} are TaCZ's AWM
 * set (CC BY-NC-ND 4.0, see {@code registry/ModSounds}); a lever cycled by hand uses the same
 * out/eject/in/end cadence as a bolt, and the tables below only touch those ids.</p>
 *
 * <p>Ballistics are this project's choice for .45-70 Gov: a heavy slow bullet — harder hitting than the
 * Mosin's 7.62×54R at close range, a shorter effective range to match ("威力大,射程中"). Server-authoritative
 * throughout: the client only asks ({@code FirePacket} / {@code ReloadPacket}).</p>
 */
public class Win94Item extends Item implements GeoItem, GunItem {

    /** Always-on controller, loops the idle pose. */
    public static final String CONTROLLER_MAIN = "main";
    /** Trigger-driven controller for one-shot actions. */
    public static final String CONTROLLER_ACTION = "action";

    /** Trigger names — these are what Java passes to {@code triggerAnim}, not the clip names. */
    public static final String TRIGGER_SHOOT = "shoot";
    public static final String TRIGGER_BOLT = "bolt";
    public static final String TRIGGER_RELOAD_TACTICAL = "reload_tactical";
    public static final String TRIGGER_RELOAD_EMPTY = "reload_empty";
    public static final String TRIGGER_DRAW = "draw";
    public static final String TRIGGER_INSPECT = "inspect";

    /** Clip names as exported — must match win94.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_DRAW = "draw";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_BOLT = "bolt";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_RELOAD_EMPTY = "reload_empty";
    public static final String ANIM_INSPECT = "inspect";

    /**
     * Clip lengths in ticks (20 t/s), taken from win94.animation.json — the contract is
     * {@code ceil(animation_length × 20)} and {@code tools/check_gun_resources.py} fails if these drift.
     */
    private static final int SHOOT_TICKS = 12;             // 0.6 s
    private static final int BOLT_TICKS = 22;              // 1.1 s
    private static final int RELOAD_TACTICAL_TICKS = 44;   // 2.2 s（3 发压弹）
    private static final int RELOAD_EMPTY_TICKS = 88;      // 4.4 s（5 发压弹 + 收尾上膛）
    private static final int DRAW_TICKS = 16;              // 0.8 s

    /** Five rounds in the magazine tube under the barrel. Also picks which reload clip plays. */
    public static final int MAGAZINE_SIZE = 5;

    // ------------------------------------------------------------------ sight

    /**
     * Fixed zoom of the built-in scope — {@value #AIMED_FOV} degrees, about 2.5× the 70° default. Not a
     * sniper's 4×: the Win94's glass is short and the gun is meant to be quick off the hip.
     */
    private static final double AIMED_FOV = 31.0D;
    private static final float AIM_TIME = 0.22F;

    /**
     * Where the sight line sits in the hip pose, expressed as the offset that brings it up to the eye.
     * Starting from the Mosin's measured pair — the two rifles are within a centimetre of each other in
     * length and share the stock-wrist grip — to be refined with {@code tools/pose_measure.py} like the
     * others. See {@link GunItem#adsPitch()} for the display rotation that has to be cancelled first.
     * Only the visible half of the raise rides these — past {@code SCOPE_HIDE_MODEL_AT} the model is gone.
     */
    private static final float ADS_X = -0.475F;
    private static final float ADS_Y = 0.37F;
    /** Must equal {@code models/item/win94.json}'s firstperson rotation's first two components. */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;
    /**
     * On top of the display block's own 0.78 — see {@link GunItem#firstPersonScale()}. Deliberately above
     * the other rifles' 1.25: this model is true to the 24-inch rifle's own dimensions (17.83 u, where the
     * Mosin and the RSC are drawn 15–20% over), so at the shared 1.25 it read as a toy beside them. 1.50
     * draws it at 20.9 u on screen — still just under the Mosin, a carbine's presence, not a pistol's.
     */
    private static final float FIRST_PERSON_SCALE = 1.50F;
    /** .45-70 kicks harder than the Mosin's rifle round: a full-bodied push about the grip. */
    private static final float FIRE_PITCH = 5.5F;

    // ------------------------------------------------------------------ ballistics (this project's numbers)

    private static final float DAMAGE_NEAR = 20.0F;
    private static final float DAMAGE_MID = 16.0F;
    private static final float DAMAGE_FAR = 11.0F;
    private static final double RANGE_MID = 40.0D;
    private static final double RANGE_FAR = 120.0D;

    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    private static final double HEADSHOT_HEIGHT = 0.82D;

    /** A big slow bullet punches two bodies, not three — weight over speed. */
    private static final int PIERCE = 2;
    private static final double MAX_RANGE = 170.0D;
    private static final double TRACER_SPACING = 3.5D;
    private static final int TRACER_MAX_DOTS = 40;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "win94_bullet"));

    private static final String TAG_AMMO = "Ammo";
    private static final String TAG_PENDING = "Pending";
    private static final String TAG_PENDING_AT = "PendingAt";
    private static final String TAG_ACTION = "Action";
    private static final String TAG_ACTION_AT = "ActionAt";
    private static final String TAG_LOCKED_UNTIL = "LockedUntil";
    private static final long NONE = -1L;

    private static final String ACTION_BOLT = "bolt";
    private static final String ACTION_RELOAD_TACTICAL = "reload_tactical";
    private static final String ACTION_RELOAD_EMPTY = "reload_empty";

    /**
     * When each mechanical sound fires, in ticks from the start of its action — keyed against the lever
     * cycle clip: the loop is thrown down at t≈1, the case leaves the receiver at t≈7 and the lever is
     * home at t≈19. The report itself is played live in {@link #playShot}.
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            2, ModSounds.AWM_RECHAMBER_OUT,
            7, ModSounds.AWM_RECHAMBER_EJECT,
            15, ModSounds.AWM_RECHAMBER_IN,
            19, ModSounds.AWM_RECHAMBER_END);

    /**
     * 空仓 reload (4.4 s): five rounds pressed through the loading gate one at a time (t≈19…63),
     * then one lever cycle to chamber the first one (lever down t≈68, home t≈84).
     * The gate has no magazine to drop, so every beat below is a "press a round in" sound.
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            3, ModSounds.AWM_RELOAD_EMPTY_RAISE,
            19, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            30, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            41, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            52, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            63, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            68, ModSounds.AWM_RECHAMBER_OUT,
            76, ModSounds.AWM_RECHAMBER_IN,
            84, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            86, ModSounds.AWM_RELOAD_EMPTY_END);

    /**
     * 半仓 reload (2.2 s): three rounds topped up through the gate, no lever cycle (the chamber
     * already holds a live round). Beats at t≈17/28/39 are the three presses.
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            2, ModSounds.AWM_RELOAD_RAISE,
            17, ModSounds.AWM_RELOAD_RATTLE,
            28, ModSounds.AWM_RELOAD_RATTLE,
            39, ModSounds.AWM_RELOAD_RATTLE,
            42, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE);

    private static final double SHOT_HEARD_SQR = 64.0D * 64.0D;

    private static final RawAnimation IDLE = RawAnimation.begin().thenLoop(ANIM_IDLE);
    private static final RawAnimation SHOOT = RawAnimation.begin().thenPlay(ANIM_SHOOT);
    private static final RawAnimation BOLT = RawAnimation.begin().thenPlay(ANIM_BOLT);
    private static final RawAnimation RELOAD_TACTICAL = RawAnimation.begin().thenPlay(ANIM_RELOAD_TACTICAL);
    private static final RawAnimation RELOAD_EMPTY = RawAnimation.begin().thenPlay(ANIM_RELOAD_EMPTY);
    private static final RawAnimation DRAW = RawAnimation.begin().thenPlay(ANIM_DRAW);
    private static final RawAnimation INSPECT = RawAnimation.begin().thenPlay(ANIM_INSPECT);

    private static final int TRANSITION_TICKS = 4;

    private final AnimatableInstanceCache cache = GeckoLibUtil.createInstanceCache(this);

    public Win94Item(Properties properties) {
        super(properties);
        SingletonGeoAnimatable.registerSyncedAnimatable(this);
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, CONTROLLER_MAIN, TRANSITION_TICKS,
                state -> state.setAndContinue(IDLE)));

        controllers.add(new AnimationController<>(this, CONTROLLER_ACTION, 0,
                        state -> PlayState.STOP)
                .triggerableAnim(TRIGGER_SHOOT, SHOOT)
                .triggerableAnim(TRIGGER_BOLT, BOLT)
                .triggerableAnim(TRIGGER_RELOAD_TACTICAL, RELOAD_TACTICAL)
                .triggerableAnim(TRIGGER_RELOAD_EMPTY, RELOAD_EMPTY)
                .triggerableAnim(TRIGGER_DRAW, DRAW)
                .triggerableAnim(TRIGGER_INSPECT, INSPECT));
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

    /**
     * The scope draws the {@link GunItem.SightStyle#CLEAR_SIGHT} lens — the transparent crosshair the
     * reference render's glass reads as, not a blacked-out telescope.
     */
    @Override
    public boolean hasScopeOverlay() {
        return true;
    }

    @Override
    public GunItem.SightStyle sightStyle() {
        return GunItem.SightStyle.CLEAR_SIGHT;
    }

    /**
     * The rifle and both hands leave the frame while the sight is up — the request for this gun was
     * explicit: raise the sight and see only the glass and its crosshair. Past
     * {@code ClientEvents.SCOPE_HIDE_MODEL_AT} of the raise nothing of the first-person model is drawn,
     * and the {@link GunItem.SightStyle#CLEAR_SIGHT} overlay — pale lens, haloed crosshair, no blackout —
     * is the whole view. The ADS offsets below still shape the visible half of the raise.
     */
    @Override
    public boolean hidesModelWhileAimed() {
        return true;
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
        return 0.18F;
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
     * One trigger pull, straight off the wire. Refuses while the lever cycle is running or the tube is
     * dry, so holding the button gives a shot every {@value #SHOOT_TICKS}+{@value #BOLT_TICKS} ticks —
     * the cadence of a lever gun worked hard.
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry: the trigger and the pin, nothing behind them. Then it loads itself, like every other
            // gun in the mod — an empty weapon with rounds in the tube does not stay empty.
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    ModSounds.AWM_RECHAMBER_EJECT.get(), SoundSource.PLAYERS, 0.5F, 1.2F);
            beginReload(player, stack, level);
            return;
        }

        setAmmo(stack, getAmmo(stack) - 1);
        trigger(player, stack, level, TRIGGER_SHOOT);
        // The lever cycle follows the shot by exactly the length of the shoot clip, so the two read as
        // one motion; the lock keeps the trigger dead until the case is back in the tube.
        scheduleAction(stack, ACTION_BOLT, now + SHOOT_TICKS);
        put(stack, TAG_LOCKED_UNTIL, now + SHOOT_TICKS + BOLT_TICKS);

        fireBullet(player, level);
    }

    /** One hitscan ray from the eye: blunt objects first, bodies after, nothing above {@value #PIERCE}. */
    private void fireBullet(ServerPlayer player, ServerLevel level) {
        Vec3 eye = player.getEyePosition();
        Vec3 direction = player.getLookAngle();
        Vec3 reach = eye.add(direction.scale(MAX_RANGE));

        BlockHitResult blockHit = BulletRay.trace(level, player, eye, reach);
        double wallDistance = blockHit.getType() == HitResult.Type.MISS
                ? MAX_RANGE
                : eye.distanceTo(blockHit.getLocation());

        Vec3 look = player.getLookAngle();
        Vec3 right = look.cross(new Vec3(0.0D, 1.0D, 0.0D)).normalize();
        // Muzzle a touch further out than the Garand's — this rifle is 1.37 blocks long.
        Vec3 muzzle = eye.add(look.scale(0.76D)).add(right.scale(-0.12D)).add(0.0D, -0.10D, 0.0D);

        Vec3 impact = blockHit.getType() == HitResult.Type.MISS
                ? eye.add(direction.scale(wallDistance))
                : blockHit.getLocation();

        int hits = 0;
        for (EntityHitResult hit : collectTargets(level, player, eye, direction, wallDistance)) {
            if (hits++ >= PIERCE) {
                break;
            }
            Entity target = hit.getEntity();
            double distance = eye.distanceTo(hit.getLocation());
            boolean headshot = hit.getLocation().y > target.getY() + target.getBbHeight() * HEADSHOT_HEIGHT;
            float damage = damageAt(distance) * (headshot ? HEADSHOT_MULTIPLIER : 1.0F);

            target.invulnerableTime = 0;
            target.hurt(bulletSource(level, player), damage);
            level.sendParticles(ParticleTypes.DAMAGE_INDICATOR,
                    hit.getLocation().x, hit.getLocation().y, hit.getLocation().z,
                    headshot ? 10 : 5, 0.15D, 0.15D, 0.15D, 0.15D);
            if (headshot) {
                level.playSound(null, target.getX(), target.getY(), target.getZ(),
                        SoundEvents.PLAYER_ATTACK_CRIT, SoundSource.PLAYERS, 1.0F, 1.2F);
            }
            impact = hit.getLocation();
        }

        if (blockHit.getType() != HitResult.Type.MISS) {
            Vec3 surface = blockHit.getLocation();
            level.sendParticles(ParticleTypes.CRIT, surface.x, surface.y, surface.z, 8, 0.1D, 0.1D, 0.1D, 0.2D);
            level.sendParticles(ParticleTypes.SMOKE, surface.x, surface.y, surface.z, 3, 0.05D, 0.05D, 0.05D, 0.01D);
        }

        spawnTracer(level, muzzle, impact);

        level.sendParticles(ParticleTypes.FLAME, muzzle.x, muzzle.y, muzzle.z, 4, 0.03D, 0.03D, 0.03D, 0.02D);
        level.sendParticles(ParticleTypes.END_ROD, muzzle.x, muzzle.y, muzzle.z, 6, 0.05D, 0.05D, 0.05D, 0.02D);
        playShot(player, level);
    }

    /** The report: close mix for the shooter, distant one for everyone in earshot. */
    private void playShot(ServerPlayer player, ServerLevel level) {
        player.playNotifySound(ModSounds.AWM_SHOOT.get(), SoundSource.PLAYERS, 1.0F, 0.92F);
        SoundEvent distant = ModSounds.AWM_SHOOT_3P.get();
        for (ServerPlayer other : level.players()) {
            if (other != player && other.distanceToSqr(player) < SHOT_HEARD_SQR) {
                other.playNotifySound(distant, SoundSource.PLAYERS, 2.0F, 0.92F);
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

    /** Distance-graded damage, this file's breakpoints. */
    private static float damageAt(double distance) {
        if (distance <= RANGE_MID) {
            return DAMAGE_NEAR;
        }
        return distance <= RANGE_FAR ? DAMAGE_MID : DAMAGE_FAR;
    }

    private DamageSource bulletSource(ServerLevel level, ServerPlayer player) {
        Holder<DamageType> holder = level.registryAccess()
                .registryOrThrow(Registries.DAMAGE_TYPE)
                .getHolderOrThrow(DAMAGE_TYPE);
        return new DamageSource(holder, player, player);
    }

    /** Draws the round's path as a dashed line of glowing particles. */
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
     * Called from the reload key. A tube with rounds left runs the quick top-up cycle; a dry gun runs the
     * slow deliberate one. Either way the rounds are credited back when the clip ends, which is also when
     * the weapon unlocks.
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }
        boolean chambered = getAmmo(stack) > 0;
        int ticks = chambered ? RELOAD_TACTICAL_TICKS : RELOAD_EMPTY_TICKS;

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

        // 2) The tube ran dry and the weapon is idle again: cycle one in rather than sit on a dead trigger.
        //    Held only — a gun left in the pack stays as it was put away.
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
            // A finished reload is what credits the fresh rounds; a shot just clears itself.
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

    /** True while a shot or a reload owns the weapon. */
    private boolean isLocked(ItemStack stack, long now) {
        long lockedUntil = get(stack, TAG_LOCKED_UNTIL);
        return lockedUntil != NONE && now < lockedUntil;
    }

    // ------------------------------------------------------------------ state

    /** Rounds left, defaulting to a full tube for a stack that has never been fired. */
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
            case ACTION_BOLT -> TRIGGER_BOLT;
            case ACTION_RELOAD_TACTICAL -> TRIGGER_RELOAD_TACTICAL;
            default -> TRIGGER_RELOAD_EMPTY;
        };
    }

    /** Ticks the action's clip runs for, from win94.animation.json. */
    private static int actionLength(String action) {
        return switch (action) {
            case ACTION_BOLT -> BOLT_TICKS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_TICKS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_TICKS;
            default -> 0;
        };
    }

    private static Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case ACTION_BOLT -> BOLT_SOUNDS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_SOUNDS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_SOUNDS;
            default -> Map.of();
        };
    }

    // ------------------------------------------------------------------ client

    @Override
    public void initializeClient(Consumer<IClientItemExtensions> consumer) {
        consumer.accept(new IClientItemExtensions() {
            private Win94ItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new Win94ItemRenderer();
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
