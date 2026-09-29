package com.apocalypse.zombies.item;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.MosinNagantItemRenderer;
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
 * 莫辛-纳甘 M91/30 — a GeckoLib-boned bolt-action service rifle, and the third gun in the weapon layer.
 *
 * <p>Geometry and animation live in {@code assets/apocalypse_zombies/geo/mosin_nagant.geo.json} and
 * {@code animations/mosin_nagant.animation.json}: 22 bones, seven clips ({@value #ANIM_IDLE},
 * {@value #ANIM_DRAW}, {@value #ANIM_SHOOT}, {@value #ANIM_BOLT}, {@value #ANIM_RELOAD_TACTICAL},
 * {@value #ANIM_RELOAD_EMPTY}, {@value #ANIM_INSPECT}). The model is 1.43 blocks long (22.9 u) — the
 * M91/30's real 1232 mm at this project's 53.8 mm per unit — 170 cubes and one 512² texture. Every pose
 * is per-bone rotation/translation, nothing scales the model, per 美术规范.md §5.</p>
 *
 * <p>What makes this a Mosin and not a Garand with a different stock is the action, and there are three
 * things:</p>
 * <ul>
 *   <li><b>It does not cycle itself.</b> A shot fires {@value #ANIM_SHOOT} (recoil only, 12 t) and the bolt
 *       is scheduled behind it — exactly the AWM's shape — so holding the button gives one shot per
 *       {@value #SHOOT_TICKS}+{@value #BOLT_TICKS} ticks. The case leaves the receiver during
 *       {@value #ANIM_BOLT}, not during the shot.</li>
 *   <li><b>The magazine is fixed and holds five.</b> Five 7.62×54R rounds in an internal box, no clip and no
 *       detachable magazine: {@value #ANIM_RELOAD_EMPTY} opens the bolt, presses the rounds in one at a
 *       time and closes on the last one. {@value #ANIM_RELOAD_TACTICAL} tops a partly-full magazine up by
 *       three. Both credit {@value #MAGAZINE_SIZE} rounds when the clip ends, which is also when the
 *       weapon unlocks.</li>
 *   <li><b>Iron sights, not glass.</b> The M91/30's post front sight and tangent rear sight <em>are</em> the
 *       aim point, so there is no scope overlay and the rifle stays in frame while aiming — same choice as
 *       the Garand, see {@link #hasScopeOverlay()} / {@link #hidesModelWhileAimed()}.</li>
 * </ul>
 *
 * <p><b>Sounds are borrowed.</b> The recordings in {@code sounds/awm/} are TaCZ's AWM set shipped under
 * CC BY-NC-ND 4.0 (see {@code registry/ModSounds}); this rifle triggers those same ids rather than
 * shipping a Mosin set it does not have — a bolt is a bolt, and the tables below only use the ids whose
 * mechanism matches (no magazine-out/magazine-in sounds, because this rifle has no detachable magazine).
 * Nothing is re-encoded, and swapping in real Mosin recordings is a resource change only: the cue tables
 * are keyed by tick against the clips in {@code mosin_nagant.animation.json}.</p>
 *
 * <p>Ballistics are this project's own choice, not a transcription: 7.62×54R sits between the Garand's
 * .30-06 and the AWM's .338 Lapua, so it does 17/14/10 damage across 50/140 blocks, pierces three bodies
 * rather than two or four, and reaches 200 m. Server-authoritative throughout: the client only asks
 * ({@code FirePacket} / {@code ReloadPacket}) and every decision is made here from the stack's NBT.</p>
 */
public class MosinNagantItem extends Item implements GeoItem, GunItem {

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

    /** Clip names as exported from Blockbench — must match mosin_nagant.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_DRAW = "draw";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_BOLT = "bolt";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_RELOAD_EMPTY = "reload_empty";
    public static final String ANIM_INSPECT = "inspect";

    /**
     * Clip lengths in ticks (20 t/s), taken from mosin_nagant.animation.json — the contract is
     * {@code ceil(animation_length × 20)} and {@code tools/check_gun_resources.py} fails if these drift.
     */
    private static final int SHOOT_TICKS = 12;             // 0.6 s
    private static final int BOLT_TICKS = 22;              // 1.1 s
    private static final int RELOAD_TACTICAL_TICKS = 72;   // 3.6 s
    private static final int RELOAD_EMPTY_TICKS = 88;      // 4.4 s

    /** Five rounds, one fixed box magazine. Also the "still chambered?" test that picks the reload clip. */
    public static final int MAGAZINE_SIZE = 5;

    // ------------------------------------------------------------------ sight

    /** Iron sights: a battle rifle zooms less than a scope, and draws no overlay. */
    private static final double AIMED_FOV = 50.0D;
    private static final float AIM_TIME = 0.20F;
    /**
     * Where the sight line sits in the hip pose, expressed as the offset that brings it up to the eye.
     * Measured, not eyeballed: {@code tools/pose_measure.py} walks the whole transform chain (hand base
     * 0.56/−0.52/−0.72 → stance → display block → geometry) and prints the offset that lands the sight line
     * on the view axis, then re-checks these constants against it. All three rifles come out at the same
     * pair, which is what one expects: the dominant term is the hand base itself, scaled by
     * {@link #FIRST_PERSON_SCALE} (0.56 / 1.25 = 0.448). See {@link GunItem#adsPitch()} for the display
     * rotation that has to be cancelled <em>first</em> — left standing, no pair of offsets can align it.
     */
    private static final float ADS_X = -0.475F;
    private static final float ADS_Y = 0.346F;
    /**
     * The item model's first-person {@code display} rotation (degrees), cancelled while aiming so the sight
     * line ends up parallel to the view axis — see {@link GunItem#adsPitch()}.
     */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;
    /**
     * How much bigger the rifle reads in the first person, on top of the {@code display} block's own size
     * (0.78). Applied up the chain from the stance so the sight-up compensation above scales with it — see
     * {@link GunItem#firstPersonScale()}. One number, to taste.
     */
    private static final float FIRST_PERSON_SCALE = 1.25F;
    /**
     * Firing kick as a pitch about the grip (degrees at full kick). A bolt gun gets the full kick — one shot,
     * then a deliberate cycle — but 7.62×54R is lighter than the AWM's .338, so it is a shade smaller.
     */
    private static final float FIRE_PITCH = 5.0F;

    // ------------------------------------------------------------------ ballistics (this project's numbers)

    private static final float DAMAGE_NEAR = 17.0F;
    private static final float DAMAGE_MID = 14.0F;
    private static final float DAMAGE_FAR = 10.0F;
    private static final double RANGE_MID = 50.0D;
    private static final double RANGE_FAR = 140.0D;

    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    private static final double HEADSHOT_HEIGHT = 0.82D;

    /** 7.62×54R goes through three bodies: between the Garand's two and the AWM's four. */
    private static final int PIERCE = 3;
    private static final double MAX_RANGE = 200.0D;
    private static final double TRACER_SPACING = 3.5D;
    private static final int TRACER_MAX_DOTS = 44;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "mosin_nagant_bullet"));

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
     * When each mechanical sound fires, in ticks from the start of its action.
     *
     * <p>These are keyed against the keyframes in {@code mosin_nagant.animation.json}, read off the file
     * rather than chosen: the handle breaks open at t=4.2, the case leaves the receiver at t=9.2 and the
     * bolt is home at t=17.5. The report itself is not here — it is played live in {@link #playShot}, on
     * the tick of the shot.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            9, ModSounds.AWM_RECHAMBER_EJECT,
            15, ModSounds.AWM_RECHAMBER_IN,
            18, ModSounds.AWM_RECHAMBER_END);

    /**
     * 空仓 reload: bolt opened (t=4, pulled by t=9), then the rounds go in one at a time — the clip seats
     * them at t=24.2 / 36.7 / 48.3 / 60.0 / 72.5 — and the bolt is closed on the last one (t=82…86).
     *
     * <p>Deliberately no magazine-out / magazine-in ids: this rifle's magazine is a fixed box, so those
     * sounds would be describing hardware that is not on the model.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            4, ModSounds.AWM_RELOAD_EMPTY_RAISE,
            9, ModSounds.AWM_RECHAMBER_OUT,
            24, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            37, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            48, ModSounds.AWM_RELOAD_EMPTY_MAGHIT,
            60, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            72, ModSounds.AWM_RELOAD_EMPTY_MAGHIT,
            82, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            86, ModSounds.AWM_RELOAD_EMPTY_END);

    /** 半仓 reload: three rounds go in (t=23.3 / 34.2 / 45.0), then the bolt is worked home at the end. */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            3, ModSounds.AWM_RELOAD_RAISE,
            8, ModSounds.AWM_RECHAMBER_OUT,
            23, ModSounds.AWM_RELOAD_RATTLE,
            34, ModSounds.AWM_RELOAD_RATTLE,
            45, ModSounds.AWM_RELOAD_MAGHIT,
            69, ModSounds.AWM_RECHAMBER_IN,
            71, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE);

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

    public MosinNagantItem(Properties properties) {
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

    @Override
    public boolean hasScopeOverlay() {
        return false;
    }

    /**
     * Iron sights: the notch of the tangent rear sight <em>is</em> the aim point, so the gun has to stay in
     * the frame — hiding it would leave the player aiming at a bare crosshair.
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
     * One trigger pull, straight off the wire. Refuses while the action is busy or the magazine is dry, so
     * holding the button gives a shot every {@value #SHOOT_TICKS}+{@value #BOLT_TICKS} ticks and nothing in
     * between — the cadence of a bolt gun.
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry: the trigger and the pin, nothing behind them. Then it loads itself: an empty weapon with
            // a clip in reach does not stay empty, on this rifle or on any other in the mod.
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    ModSounds.AWM_RECHAMBER_EJECT.get(), SoundSource.PLAYERS, 0.5F, 1.2F);
            beginReload(player, stack, level);
            return;
        }

        setAmmo(stack, getAmmo(stack) - 1);
        trigger(player, stack, level, TRIGGER_SHOOT);
        // The bolt follows the shot by exactly the length of the shoot clip, so the two read as one
        // motion; the lock keeps the trigger dead until the case is clear.
        scheduleAction(stack, ACTION_BOLT, now + SHOOT_TICKS);
        put(stack, TAG_LOCKED_UNTIL, now + SHOOT_TICKS + BOLT_TICKS);

        fireBullet(player, level);
    }

    /** One hitscan ray from the eye: blunt objects first, bodies after, nothing above {@value #PIERCE}. */
    private void fireBullet(ServerPlayer player, ServerLevel level) {
        Vec3 eye = player.getEyePosition();
        Vec3 direction = player.getLookAngle();
        Vec3 reach = eye.add(direction.scale(MAX_RANGE));

        BlockHitResult blockHit = level.clip(
                new ClipContext(eye, reach, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
        double wallDistance = blockHit.getType() == HitResult.Type.MISS
                ? MAX_RANGE
                : eye.distanceTo(blockHit.getLocation());

        Vec3 look = player.getLookAngle();
        Vec3 right = look.cross(new Vec3(0.0D, 1.0D, 0.0D)).normalize();
        // The longest of the three rifles (1232 mm against the Garand's 1105), so the muzzle sits a little
        // further out than the Garand's 0.72.
        Vec3 muzzle = eye.add(look.scale(0.78D)).add(right.scale(-0.13D)).add(0.0D, -0.105D, 0.0D);

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
        player.playNotifySound(ModSounds.AWM_SHOOT.get(), SoundSource.PLAYERS, 1.0F, 1.05F);
        SoundEvent distant = ModSounds.AWM_SHOOT_3P.get();
        for (ServerPlayer other : level.players()) {
            if (other != player && other.distanceToSqr(player) < SHOT_HEARD_SQR) {
                other.playNotifySound(distant, SoundSource.PLAYERS, 2.0F, 1.05F);
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
     * Called from the reload key. A magazine with rounds left in it runs the short top-up; a dry rifle runs
     * the full 开栓 → 逐发压入 5 发 → 闭锁 sequence. The rounds are credited back when the clip ends, which
     * is also when the weapon unlocks.
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }
        boolean chambered = getAmmo(stack) > 0;
        int ticks = chambered ? RELOAD_TACTICAL_TICKS : RELOAD_EMPTY_TICKS;

        // Started on the spot, so the clip's own first sound cue (t=4) lands where the file puts it.
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

        // 2) The magazine ran dry and the weapon is idle again: a gun with a spare magazine in reach
        //    reloads itself rather than sitting on a dead trigger. Checked after any scheduled action has
        //    had its turn, so a Garand still pings its clip clear and a bolt gun still cycles the case out
        //    before the reload starts. Held only — a gun left in the pack stays as it was put away.
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

    /** Rounds left, defaulting to a full magazine for a stack that has never been fired. */
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

    /** Ticks the action's clip runs for, from mosin_nagant.animation.json. */
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
            private MosinNagantItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new MosinNagantItemRenderer();
                }
                return this.renderer;
            }

            /**
             * Hands the first-person transform to {@link WeaponHandGrip}: vanilla's hand base is kept, the
             * sword-style attack swing is dropped (held down, it made the rifle nod in the hand), and the hold
             * stance is added. {@code true} means "handled" — vanilla skips its own transforms and renders.
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