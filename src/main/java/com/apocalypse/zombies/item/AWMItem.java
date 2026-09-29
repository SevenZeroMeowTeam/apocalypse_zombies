package com.apocalypse.zombies.item;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.AWMItemRenderer;
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
 * Precision International AWM — a GeckoLib-boned bolt-action sniper rifle.
 *
 * <p>Geometry is authored in Blockbench and lives in {@code assets/apocalypse_zombies/geo/awm.geo.json};
 * its 25 bones are driven by the ten clips in {@code animations/awm.animation.json} — five of them wired
 * below, and five more ({@code draw} / {@code put_away} / {@code inspect} / {@code inspect_empty} /
 * {@code static_bolt_caught}) already in the file waiting for their triggers. Nothing here scales or
 * translates the whole model — every pose is per-bone rotation/translation, per 美术规范.md §5. The
 * magazine, bolt, casing and chambered round carry the whole performance: 手上无臂, so no arm bones are
 * animated and the first-person arm is the vanilla player arm.</p>
 *
 * <p>The <em>action logic</em> — which actions exist, in what order, and how long each runs — follows
 * TaCZ's own 精密国际AWM ({@code ai_awp}) and is adapted to this skeleton: their rig angles map onto our
 * bone names 1:1, displacements are recomputed with this model's ratio ({@code S_GUN = 57.07 / 23.97}),
 * and lengths scale with it. The ejection is <em>not</em> mirrored: our bolt and casing sit on the same
 * side (−X) as theirs. Transcription and conversion are this project's own
 * ({@code tools/tacz_anim_transcribe.py}), the result lands in {@code animations/awm.animation.json},
 * and {@code tools/check_awm_anim.py} audits it keyframe by keyframe against the reference. Reference
 * data: {@code art/awm/tacz_ai_awp_reference.md}.</p>
 *
 * <p>The code below, by contrast, is this project's own — no TaCZ source was copied and none is
 * referenced: no {@code com.tacz} class appears at compile time or runtime, and the whole behaviour
 * (server authority, the NBT-backed action machine, the packets) is implemented here.</p>
 *
 * <p>Controller layout:</p>
 * <ul>
 *   <li>{@value #CONTROLLER_MAIN} — always-on loop, plays {@value #ANIM_IDLE}.</li>
 *   <li>{@value #CONTROLLER_ACTION} — stopped until triggered. {@value #ANIM_SHOOT} + {@value #ANIM_BOLT}
 *       fire on every shot (狙击枪打一发拉一下栓), {@value #ANIM_RELOAD_TACTICAL} /
 *       {@value #ANIM_RELOAD_EMPTY} fire from the reload key.</li>
 * </ul>
 *
 * <p>The weapon itself is server-authoritative: the client only ever asks ({@code FirePacket} /
 * {@code ReloadPacket}), and every decision — is it loaded, is the action busy, what did the bullet hit —
 * is made here from the stack's NBT. The numbers are the reference gun's own
 * ({@code hexalunar/data/guns/awp_data.json}): 5 rounds, 24 damage falling to 21 at 160 m then 15, ×2 on a
 * head hit, four bodies pierced, 338 Lapua going through armour.</p>
 */
public class AWMItem extends Item implements GeoItem, GunItem {

    /** Always-on controller, loops the idle pose. */
    public static final String CONTROLLER_MAIN = "main";
    /** Trigger-driven controller for one-shot actions. */
    public static final String CONTROLLER_ACTION = "action";

    /** Trigger names — these are what Java passes to {@code triggerAnim}, not the clip names. */
    public static final String TRIGGER_SHOOT = "shoot";
    public static final String TRIGGER_BOLT = "bolt";
    public static final String TRIGGER_RELOAD_TACTICAL = "reload_tactical";
    public static final String TRIGGER_RELOAD_EMPTY = "reload_empty";

    /** Clip names as exported from Blockbench — must match awm.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_BOLT = "bolt";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_RELOAD_EMPTY = "reload_empty";

    /** Clip lengths in ticks (20 t/s), taken from awm.animation.json. */
    private static final int SHOOT_TICKS = 17;
    private static final int BOLT_TICKS = 26;
    public static final int RELOAD_TACTICAL_TICKS = 60;
    public static final int RELOAD_EMPTY_TICKS = 75;

    /** Rounds in a full magazine — also the "still chambered?" test that picks the reload clip. */
    public static final int MAGAZINE_SIZE = 5;

    // ------------------------------------------------------------------ ballistics (reference gun's numbers)

    /** Damage inside the first bracket, and the ranges (in blocks) the two fall-offs happen at. */
    private static final float DAMAGE_NEAR = 24.0F;
    private static final float DAMAGE_MID = 21.0F;
    private static final float DAMAGE_FAR = 15.0F;
    private static final double RANGE_MID = 80.0D;
    private static final double RANGE_FAR = 160.0D;

    /** A head hit multiplies damage — a .338 to the skull is a different conversation. */
    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    /** Fraction of the target's height above which a hit counts as a head hit. */
    private static final double HEADSHOT_HEIGHT = 0.82D;

    /** How many bodies one round goes through before it stops (TaCZ {@code pierce}). */
    private static final int PIERCE = 4;
    /** No shot reaches further than this. */
    private static final double MAX_RANGE = 256.0D;
    /** Tracer particles are spaced this far apart, so a long shot reads as a dashed line. */
    private static final double TRACER_SPACING = 4.0D;
    private static final int TRACER_MAX_DOTS = 48;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "awm_bullet"));

    private static final String TAG_AMMO = "Ammo";
    /** A one-shot action that has been asked for but has not begun yet (the bolt waits on the shot). */
    private static final String TAG_PENDING = "Pending";
    private static final String TAG_PENDING_AT = "PendingAt";
    /** The one-shot action running right now, and the tick it actually started on. */
    private static final String TAG_ACTION = "Action";
    private static final String TAG_ACTION_AT = "ActionAt";
    private static final String TAG_LOCKED_UNTIL = "LockedUntil";
    /** Sentinel for "nothing scheduled". */
    private static final long NONE = -1L;

    private static final String ACTION_BOLT = "bolt";
    private static final String ACTION_RELOAD_TACTICAL = "reload_tactical";
    private static final String ACTION_RELOAD_EMPTY = "reload_empty";

    /**
     * When each mechanical sound fires, in ticks from the start of its action.
     *
     * <p>These are TaCZ's own {@code sound_effects} keyframes, carried across by the transcription and
     * stored in {@code animations/awm.animation.json} beside the curves they belong to.
     * {@code tools/check_awm_anim.py} fails if they ever drift from that file, so the bang of the bolt
     * cannot quietly end up a beat behind the bolt itself.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            3, ModSounds.AWM_RECHAMBER_OUT,
            7, ModSounds.AWM_RECHAMBER_EJECT,
            12, ModSounds.AWM_RECHAMBER_IN,
            13, ModSounds.AWM_RECHAMBER_END);

    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            0, ModSounds.AWM_RELOAD_RAISE,
            6, ModSounds.AWM_RELOAD_RATTLE,
            7, ModSounds.AWM_RELOAD_EJECT,
            11, ModSounds.AWM_RELOAD_MAGOUT,
            20, ModSounds.AWM_RELOAD_FAST_RATTLE,
            32, ModSounds.AWM_RELOAD_MAGHIT,
            40, ModSounds.AWM_RELOAD_MAGIN,
            47, ModSounds.AWM_RELOAD_END);

    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            0, ModSounds.AWM_RELOAD_EMPTY_RAISE,
            12, ModSounds.AWM_RELOAD_EMPTY_MAGOUT,
            26, ModSounds.AWM_RELOAD_EMPTY_MAG_DROP,
            31, ModSounds.AWM_RELOAD_EMPTY_RATTLE,
            33, ModSounds.AWM_RELOAD_EMPTY_MAGHIT,
            41, ModSounds.AWM_RELOAD_EMPTY_MAGIN,
            49, ModSounds.AWM_RECHAMBER_OUT,
            52, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            61, ModSounds.AWM_RELOAD_EMPTY_END);

    /** How far a shot carries to other players' ears. */
    private static final double SHOT_HEARD_SQR = 64.0D * 64.0D;

    private static final RawAnimation IDLE = RawAnimation.begin().thenLoop(ANIM_IDLE);
    private static final RawAnimation SHOOT = RawAnimation.begin().thenPlay(ANIM_SHOOT);
    private static final RawAnimation BOLT = RawAnimation.begin().thenPlay(ANIM_BOLT);
    private static final RawAnimation RELOAD_TACTICAL = RawAnimation.begin().thenPlay(ANIM_RELOAD_TACTICAL);
    private static final RawAnimation RELOAD_EMPTY = RawAnimation.begin().thenPlay(ANIM_RELOAD_EMPTY);

    /** Ticks of cross-fade when the main controller swaps clips. */
    private static final int TRANSITION_TICKS = 4;

    // ------------------------------------------------------------------ sight (read through GunItem)

    /** Field of view while looking through the scope. Vanilla default is 70. */
    private static final double SCOPE_FOV = 20.0D;
    /** Seconds for the sight to come up, matching the reference gun's {@code aim_time}. */
    private static final float AIM_TIME = 0.25F;
    /**
     * Where the scope's optical axis sits in the hip pose, expressed as the offset that brings it to the eye.
     * The magnification makes a misalignment obvious, so these are measured, not eyeballed:
     * {@code tools/pose_measure.py} walks the whole transform chain (hand base 0.56/−0.52/−0.72 → stance →
     * display block → geometry) and prints the offset that lands the axis on the view axis, then re-checks
     * these constants against it. Both guns come out at the same pair, which is what one expects: the term
     * that dominates is the hand base itself, scaled by {@link #FIRST_PERSON_SCALE} (0.56 / 1.25 = 0.448).
     *
     * <p>See {@link GunItem#adsX()} for why they moved here from the item model's space, and
     * {@link GunItem#adsPitch()} for the display rotation that has to be cancelled <em>first</em> — with it
     * left standing, no pair of offsets can align the axis at any aim.
     */
    private static final float ADS_X = -0.475F;
    private static final float ADS_Y = 0.346F;
    /**
     * The item model's first-person {@code display} rotation (degrees), cancelled while aiming so the optical
     * axis ends up parallel to the view axis — see {@link GunItem#adsPitch()}.
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
     * Firing kick as a pitch about the grip (degrees at full kick). The bolt gun gets the full kick: one shot,
     * then a deliberate cycle, so the rifle jumping against the shoulder is the point.
     */
    private static final float FIRE_PITCH = 6.0F;

    // ------------------------------------------------------------------ GunItem: what the gun is

    @Override
    public int magazineSize() {
        return MAGAZINE_SIZE;
    }

    @Override
    public double aimedFov() {
        return SCOPE_FOV;
    }

    @Override
    public float aimTime() {
        return AIM_TIME;
    }

    /** A scope, so the overlay is drawn and vanilla's crosshair hidden. */
    @Override
    public boolean hasScopeOverlay() {
        return true;
    }

    /**
     * The lens is the view — behind the eyepiece there is no rifle to see, and the raise ends with the
     * optical axis on the eye, i.e. with the gun centred in the very circle it would be blocking. So the
     * rifle and the arms are dropped from the first-person pass while the sight is up; what the player looks
     * through is the scope overlay's lens and nothing else.
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

    private final AnimatableInstanceCache cache = GeckoLibUtil.createInstanceCache(this);

    public AWMItem(Properties properties) {
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
                .triggerableAnim(TRIGGER_RELOAD_EMPTY, RELOAD_EMPTY));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.cache;
    }

    // ------------------------------------------------------------------ firing

    /**
     * One trigger pull, straight off the wire. Refuses if the action is busy or the magazine is dry, so
     * holding the button down gives a shot every {@value #SHOOT_TICKS}+{@value #BOLT_TICKS} ticks and
     * nothing in between — exactly the cadence of a bolt gun.
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry: the trigger and the pin, nothing behind them. Then it loads itself: an empty weapon with
            // a magazine in reach does not stay empty, here or on any other gun in the mod.
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

    /**
     * The actual shot: one hitscan ray from the eye, blunt objects first, bodies after.
     *
     * <p>Nothing here is a projectile entity — the round is instant over any distance the player can see,
     * which is what makes a sniper rifle feel like a sniper rifle. What the player experiences as
     * "ballistics" is the block hit stopping the round, the damage falling off with distance, the tracer,
     * and the round going through up to {@value #PIERCE} bodies.</p>
     */
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
        Vec3 muzzle = eye.add(look.scale(0.9D)).add(right.scale(-0.16D)).add(0.0D, -0.12D, 0.0D);

        Vec3 impact = blockHit.getType() == HitResult.Type.MISS
                ? eye.add(direction.scale(wallDistance))
                : blockHit.getLocation();

        // Bodies, nearest first, up to the pierce limit and never past the wall.
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
            // The round keeps going: the next target is hit with a fresh ray from this impact.
            impact = hit.getLocation();
        }

        if (blockHit.getType() != HitResult.Type.MISS) {
            Vec3 surface = blockHit.getLocation();
            level.sendParticles(ParticleTypes.CRIT, surface.x, surface.y, surface.z, 8, 0.1D, 0.1D, 0.1D, 0.2D);
            level.sendParticles(ParticleTypes.SMOKE, surface.x, surface.y, surface.z, 3, 0.05D, 0.05D, 0.05D, 0.01D);
        }

        spawnTracer(level, muzzle, impact);

        // Muzzle flash and the report. Played to the whole level so it works in first person and is heard
        // by anyone standing next to the shooter.
        level.sendParticles(ParticleTypes.FLAME, muzzle.x, muzzle.y, muzzle.z, 4, 0.03D, 0.03D, 0.03D, 0.02D);
        level.sendParticles(ParticleTypes.END_ROD, muzzle.x, muzzle.y, muzzle.z, 6, 0.05D, 0.05D, 0.05D, 0.02D);
        playShot(player, level);
    }

    /**
     * The report, split the way TaCZ splits it: the shooter hears the close mix, everyone in earshot hears
     * the distant one. Two recordings rather than one is what stops a .338 from sounding like it went off
     * inside your own skull when the player beside you pulls the trigger.
     */
    private void playShot(ServerPlayer player, ServerLevel level) {
        player.playNotifySound(ModSounds.AWM_SHOOT.get(), SoundSource.PLAYERS, 1.0F, 1.0F);
        SoundEvent distant = ModSounds.AWM_SHOOT_3P.get();
        for (ServerPlayer other : level.players()) {
            if (other != player && other.distanceToSqr(player) < SHOT_HEARD_SQR) {
                other.playNotifySound(distant, SoundSource.PLAYERS, 2.0F, 1.0F);
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
            candidate.getBoundingBox().inflate(0.25D).clip(from, to).ifPresent(point -> {
                EntityHitResult result = new EntityHitResult(candidate, point);
                targets.add(result);
            });
        }

        targets.sort(Comparator.comparingDouble(hit -> from.distanceToSqr(hit.getLocation())));
        return targets;
    }

    /** Distance-graded damage, using the reference gun's breakpoints. */
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
     * Called from the reload key. A full magazine is swapped tactically (round stays chambered); an empty
     * one runs the full 换弹夹 → 拉栓抛壳 → 上弹 sequence. Either way the rounds are credited back when the
     * clip ends, which is also when the weapon unlocks.
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }
        boolean chambered = getAmmo(stack) > 0;
        int ticks = chambered ? RELOAD_TACTICAL_TICKS : RELOAD_EMPTY_TICKS;

        // Started on the spot, so the clip's own first sound cue (t=0) lands this very tick.
        scheduleAction(stack, chambered ? ACTION_RELOAD_TACTICAL : ACTION_RELOAD_EMPTY, now);
        put(stack, TAG_LOCKED_UNTIL, now + ticks);
    }

    /**
     * Runs on both sides but only the server schedules anything: the bolt that follows a shot and the
     * magazine that refills after a reload are both played from here.
     */
    @Override
    public void inventoryTick(ItemStack stack, Level level, Entity entity, int slot, boolean selected) {
        if (level.isClientSide || !(level instanceof ServerLevel serverLevel)) {
            return;
        }
        long now = serverLevel.getGameTime();

        // 1) A scheduled action whose time has come: trigger the clip and mark it running. Comparing
        //    "now >= at" instead of "now == at" means a tick the server spent elsewhere delays the
        //    action rather than losing it.
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

        // 3) A running action: play whatever the clip calls for at this tick. Cues are keyed on the tick
        //    the action actually started, so a late start shifts picture and sound together.
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
            // A finished reload is what credits the fresh magazine; the bolt just clears itself.
            if (ACTION_RELOAD_TACTICAL.equals(action) || ACTION_RELOAD_EMPTY.equals(action)) {
                setAmmo(stack, MAGAZINE_SIZE);
            }
            clearAction(stack);
        }
    }

    /**
     * Right-click is the sight, not the trigger — firing lives on the left mouse button and arrives through
     * {@code FirePacket}. Returning pass keeps vanilla from treating the gun as a usable item.
     */
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

    // ------------------------------------------------------------------ state (read by the HUD)

    /** Rounds left, defaulting to a full magazine for a stack that has never been fired. */
    public static int getAmmo(ItemStack stack) {
        CompoundTag tag = stack.getTag();
        return tag != null && tag.contains(TAG_AMMO) ? tag.getInt(TAG_AMMO) : MAGAZINE_SIZE;
    }

    /** True while a magazine swap is in flight, for the HUD's progress readout. */
    @Override
    public boolean isReloading(ItemStack stack, long now) {
        String action = getAction(stack);
        if (!ACTION_RELOAD_TACTICAL.equals(action) && !ACTION_RELOAD_EMPTY.equals(action)) {
            return false;
        }
        return now >= get(stack, TAG_ACTION_AT);
    }

    /** 0..1 through the reload clip, or 0 when nothing is being reloaded. */
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

    /** Asks for an action to begin at {@code at} — in the future for the bolt that trails a shot. */
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

    /** Animation trigger matching an action name. */
    private static String triggerFor(String action) {
        return switch (action) {
            case ACTION_BOLT -> TRIGGER_BOLT;
            case ACTION_RELOAD_TACTICAL -> TRIGGER_RELOAD_TACTICAL;
            default -> TRIGGER_RELOAD_EMPTY;
        };
    }

    /** Ticks the action's clip runs for, from awm.animation.json. */
    private static int actionLength(String action) {
        return switch (action) {
            case ACTION_BOLT -> BOLT_TICKS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_TICKS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_TICKS;
            default -> 0;
        };
    }

    /** The sound cues for an action, keyed by tick from its start. */
    private static Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case ACTION_BOLT -> BOLT_SOUNDS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_SOUNDS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_SOUNDS;
            default -> Map.of();
        };
    }

    // ------------------------------------------------------------------ client

    /**
     * Client-only hook: hands Forge a custom renderer so the stack is drawn by GeckoLib instead of a baked
     * item model. The body only runs on the client, so the renderer classes never load on a dedicated server.
     */
    @Override
    public void initializeClient(Consumer<IClientItemExtensions> consumer) {
        consumer.accept(new IClientItemExtensions() {
            private AWMItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new AWMItemRenderer();
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
