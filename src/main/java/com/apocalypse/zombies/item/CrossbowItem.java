package com.apocalypse.zombies.item;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.CrossbowItemRenderer;
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
 * 现代复合狩猎弩 — a GeckoLib-boned modern compound hunting crossbow: the fourth weapon in the layer, and
 * the first one that is not a firearm.
 *
 * <p>Geometry and animation live in {@code assets/apocalypse_zombies/geo/crossbow.geo.json} and
 * {@code animations/crossbow.animation.json}: seven clips ({@value #ANIM_IDLE}, {@value #ANIM_DRAW},
 * {@value #ANIM_SHOOT}, {@value #ANIM_RELOAD_TACTICAL}, {@value #ANIM_ADS_UP}, {@value #ANIM_ADS_DOWN},
 * {@value #ANIM_INSPECT}) and one 512² texture. Every pose is per-bone rotation/translation, nothing
 * scales the model, per 美术规范.md §5.</p>
 *
 * <p>What makes this a crossbow and not another rifle is the loading cycle, and there are three things:</p>
 * <ul>
 *   <li><b>It does not cycle itself, and it fires one bolt.</b> A shot fires {@value #ANIM_SHOOT} (recoil
 *       only, {@value #SHOOT_TICKS} t) and leaves the string slack — the latch has let go and the bolt is
 *       gone. Holding the button gives one shot per {@value #SHOOT_TICKS} ticks and then nothing until the
 *       weapon is spanned again: there is no bolt to work, which is why nothing is scheduled behind the
 *       shot the way the AWM and the Mosin schedule their cycles.</li>
 *   <li><b>The magazine is one bolt, and getting it there takes two clips.</b> {@value #ANIM_DRAW} (拉弦,
 *       {@value #DRAW_TICKS} t) straps the string back onto the latch; {@value #ANIM_RELOAD_TACTICAL}
 *       ({@value #RELOAD_TACTICAL_TICKS} t) carries a bolt out of the side quiver and lays it in the
 *       channel. The reload key runs the span <em>first</em> and the load behind it — a bolt already lying
 *       on the rail cannot be spanned past — off one press and one lock, and the bolt is credited when the
 *       second clip ends, which is also when the weapon unlocks.</li>
 *   <li><b>A compact optic, so it aims like a scoped rifle and zooms like a hunting one.</b> The scope's
 *       eyepiece <em>is</em> the aim point: it is part of the model rather than an overlay, and the weapon
 *       stays in frame while aimed — same choice as the Garand and the Mosin, see {@link #hasScopeOverlay()}
 *       / {@link #hidesModelWhileAimed()}. {@value #ANIM_ADS_UP} / {@value #ANIM_ADS_DOWN} are the art's
 *       0.18 s sight transitions and are wired as triggers; the blend itself is the client's, driven by the
 *       aim progress, so the item does not schedule them.</li>
 * </ul>
 *
 * <p><b>Sounds are borrowed.</b> The recordings in {@code sounds/awm/} are TaCZ's AWM set shipped under
 * CC BY-NC-ND 4.0 (see {@code registry/ModSounds}); this crossbow triggers those same ids rather than
 * shipping a crossbow set it does not have — a latch is a latch and a bolt coming out of a clip sounds like
 * a bolt coming out of a clip, and the tables below only use the ids whose mechanism matches (no
 * magazine-out/magazine-in sounds: the spare bolts ride in a quiver, and there is no magazine to drop).
 * Nothing is re-encoded, and swapping in real crossbow recordings is a resource change only: the cue tables
 * are keyed by tick against the clips in {@code crossbow.animation.json}.</p>
 *
 * <p>Ballistics are this project's own choice, not a transcription, and a crossbow is not a rifle: a bolt
 * leaves at a fraction of 7.62×54R's energy, so it does 12/9/6 damage across 25/60 blocks, stops in the one
 * body it hits rather than piercing three, and reaches 120 m — and it still doubles on a headshot, which
 * is what makes it a hunting weapon rather than a plinker. Server-authoritative throughout: the client only asks
 * ({@code FirePacket} / {@code ReloadPacket}) and every decision is made here from the stack's NBT.</p>
 */
public class CrossbowItem extends Item implements GeoItem, GunItem {

    /** Always-on controller, loops the idle pose. */
    public static final String CONTROLLER_MAIN = "main";
    /** Trigger-driven controller for one-shot actions. */
    public static final String CONTROLLER_ACTION = "action";

    /** Trigger names — these are what Java passes to {@code triggerAnim}, not the clip names. */
    public static final String TRIGGER_SHOOT = "shoot";
    /** The span (拉弦): the reload chain's first half, and the one action nothing else in the mod fires. */
    public static final String TRIGGER_DRAW = "draw";
    public static final String TRIGGER_RELOAD_TACTICAL = "reload_tactical";
    /** The art's own sight transitions — wired here, but blended by the client's aim progress, not scheduled. */
    public static final String TRIGGER_ADS_UP = "ADS_up";
    public static final String TRIGGER_ADS_DOWN = "ADS_down";
    public static final String TRIGGER_INSPECT = "inspect";

    /** Clip names as exported from Blockbench — must match crossbow.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_DRAW = "draw";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_ADS_UP = "ADS_up";
    public static final String ANIM_ADS_DOWN = "ADS_down";
    public static final String ANIM_INSPECT = "inspect";

    /**
     * Clip lengths in ticks (20 t/s), taken from crossbow.animation.json — the contract is
     * {@code ceil(animation_length × 20)} and {@code tools/check_gun_resources.py} fails if these drift.
     */
    private static final int SHOOT_TICKS = 12;             // 0.6 s
    private static final int DRAW_TICKS = 24;              // 1.2 s — the span
    private static final int RELOAD_TACTICAL_TICKS = 32;   // 1.6 s — the bolt out of the quiver

    /**
     * One bolt on the rail: the whole magazine, and the "is it loaded?" test that picks between firing and
     * reloading. A fresh stack comes spanned and loaded — see {@link #getAmmo} — because picking one up and
     * having to span it before the first shot is not what a crossbow does.
     */
    public static final int MAGAZINE_SIZE = 1;

    // ------------------------------------------------------------------ sight

    /** A hunting optic on a crossbow: more zoom than iron sights, far less than the AWM's glass. */
    private static final double AIMED_FOV = 35.0D;
    /** Matches the art's {@value #ANIM_ADS_UP} / {@value #ANIM_ADS_DOWN} transitions, 0.18 s each. */
    private static final float AIM_TIME = 0.18F;
    /**
     * Where the sight line sits in the hip pose, expressed as the offset that brings it up to the eye.
     * Measured, not eyeballed: {@code tools/pose_measure.py} walks the whole transform chain (hand base
     * 0.56/−0.52/−0.72 → stance → display block → geometry) and prints the offset that lands the sight line
     * on the view axis, then re-checks these constants against it. The X matches the rifles' −0.475 — the
     * hand base dominates, scaled by {@link #FIRST_PERSON_SCALE} (0.56 / 1.25 = 0.448) — but the Y is this
     * weapon's own, 0.399 against their 0.346, because the offset follows the sight line and this optic does
     * not sit where a rifle's sights sit. Both numbers are that tool's output, re-checked against it. See
     * {@link GunItem#adsPitch()} for the display rotation that has to be cancelled <em>first</em> — left
     * standing, no pair of offsets can align it.
     */
    private static final float ADS_X = -0.475F;
    private static final float ADS_Y = 0.399F;
    /**
     * The item model's first-person {@code display} rotation (degrees), cancelled while aiming so the sight
     * line ends up parallel to the view axis — see {@link GunItem#adsPitch()}.
     */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;
    /**
     * How much bigger the weapon reads in the first person, on top of the {@code display} block's own size
     * (0.78). Applied up the chain from the stance so the sight-up compensation above scales with it — see
     * {@link GunItem#firstPersonScale()}. One number, to taste.
     */
    private static final float FIRST_PERSON_SCALE = 1.25F;
    /**
     * Firing kick as a pitch about the grip (degrees at full kick). A crossbow has almost no recoil — the
     * bolt leaves slowly and the limbs cancel most of what is left — so this is mostly the limb slap.
     */
    private static final float FIRE_PITCH = 4.0F;

    // ------------------------------------------------------------------ ballistics (this project's numbers)

    private static final float DAMAGE_NEAR = 12.0F;
    private static final float DAMAGE_MID = 9.0F;
    private static final float DAMAGE_FAR = 6.0F;
    private static final double RANGE_MID = 25.0D;
    private static final double RANGE_FAR = 60.0D;

    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    private static final double HEADSHOT_HEIGHT = 0.82D;

    /** A bolt stops in the body it hits — one, where the rifles pass through three. */
    private static final int PIERCE = 1;
    private static final double MAX_RANGE = 120.0D;
    private static final double TRACER_SPACING = 3.0D;
    private static final int TRACER_MAX_DOTS = 30;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "crossbow_bullet"));

    private static final String TAG_AMMO = "Ammo";
    private static final String TAG_PENDING = "Pending";
    private static final String TAG_PENDING_AT = "PendingAt";
    private static final String TAG_ACTION = "Action";
    private static final String TAG_ACTION_AT = "ActionAt";
    private static final String TAG_LOCKED_UNTIL = "LockedUntil";
    private static final long NONE = -1L;

    /** The span (拉弦), then the bolt out of the quiver: the reload key runs both, in this order. */
    private static final String ACTION_DRAW = "draw";
    private static final String ACTION_RELOAD_TACTICAL = "reload_tactical";

    /**
     * When each mechanical sound fires, in ticks from the start of its action.
     *
     * <p>Keyed against the keyframes in {@code crossbow.animation.json} rather than chosen: the string is
     * hooked at t≈2, runs back under load through the middle of the pull and seats on the latch at t≈16,
     * settling at t≈21. The report itself is not here — it is played live in {@link #playShot}, on the
     * tick of the shot.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> DRAW_SOUNDS = Map.of(
            2, ModSounds.AWM_RECHAMBER_OUT,
            9, ModSounds.AWM_RELOAD_RATTLE,
            16, ModSounds.AWM_RECHAMBER_IN,
            21, ModSounds.AWM_RECHAMBER_END);

    /**
     * Bolt out of the side quiver: the hand lifts one out (t≈3, rattling in its clips by t≈11) and lays it
     * in the channel (t≈20), then withdraws (t≈30) — the string has been spanned by then.
     *
     * <p>Deliberately no magazine-out / magazine-in ids: the spare bolts ride in a quiver on the stock, so
     * those sounds would be describing hardware that is not on the model.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            3, ModSounds.AWM_RELOAD_RAISE,
            11, ModSounds.AWM_RELOAD_RATTLE,
            20, ModSounds.AWM_RELOAD_EMPTY_MAGHIT,
            22, ModSounds.AWM_RECHAMBER_IN,
            30, ModSounds.AWM_RELOAD_EMPTY_END);

    private static final double SHOT_HEARD_SQR = 64.0D * 64.0D;

    private static final RawAnimation IDLE = RawAnimation.begin().thenLoop(ANIM_IDLE);
    private static final RawAnimation SHOOT = RawAnimation.begin().thenPlay(ANIM_SHOOT);
    private static final RawAnimation DRAW = RawAnimation.begin().thenPlay(ANIM_DRAW);
    private static final RawAnimation RELOAD_TACTICAL = RawAnimation.begin().thenPlay(ANIM_RELOAD_TACTICAL);
    private static final RawAnimation ADS_UP = RawAnimation.begin().thenPlay(ANIM_ADS_UP);
    private static final RawAnimation ADS_DOWN = RawAnimation.begin().thenPlay(ANIM_ADS_DOWN);
    private static final RawAnimation INSPECT = RawAnimation.begin().thenPlay(ANIM_INSPECT);

    private static final int TRANSITION_TICKS = 4;

    private final AnimatableInstanceCache cache = GeckoLibUtil.createInstanceCache(this);

    public CrossbowItem(Properties properties) {
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
                .triggerableAnim(TRIGGER_DRAW, DRAW)
                .triggerableAnim(TRIGGER_RELOAD_TACTICAL, RELOAD_TACTICAL)
                .triggerableAnim(TRIGGER_ADS_UP, ADS_UP)
                .triggerableAnim(TRIGGER_ADS_DOWN, ADS_DOWN)
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
        return true;
    }

    /**
     * The sight is a clear one: a wash of glass with a ring and a cross on it, over a world the player can still
     * see ({@link GunItem.SightStyle#CLEAR_SIGHT}).
     *
     * <p>This used to answer {@code false} — while the modelled tube was the only glass there was, the optic
     * <em>was</em> the aim point and there was nothing to draw on screen. What changed is what the sight is for:
     * a modern crossbow is aimed, not pointed, so a cross has to be there, and vanilla's own crosshair has to
     * get out of its way — it cannot follow the raise, the zoom or the sight's own glass. Both of those are
     * exactly what {@code hasScopeOverlay()} switches on.
     */
    @Override
    public GunItem.SightStyle sightStyle() {
        return GunItem.SightStyle.CLEAR_SIGHT;
    }

    /**
     * The optic: the scope's eyepiece <em>is</em> the aim point, so the weapon has to stay in the frame —
     * hiding it would leave the player aiming at a bare crosshair. Unchanged by {@link #sightStyle()}, and for
     * the same reason: a clear sight is looked <em>past</em>, so the crossbow and the hands belong in the
     * picture.
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
     * One trigger pull, straight off the wire. Refuses while the action is busy or the rail is empty, so
     * holding the button gives one bolt per {@value #SHOOT_TICKS} ticks and nothing in between — there is no
     * bolt to work behind the shot, and the string is left slack by it.
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry: the latch drops on nothing and the string snaps forward slack. Then it loads itself: an
            // empty weapon with a bolt in the quiver does not stay empty, here or on any other gun.
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    ModSounds.AWM_RECHAMBER_EJECT.get(), SoundSource.PLAYERS, 0.5F, 1.2F);
            beginReload(player, stack, level);
            return;
        }

        setAmmo(stack, getAmmo(stack) - 1);
        trigger(player, stack, level, TRIGGER_SHOOT);
        // Nothing is scheduled behind the shot: the clip ends with the latch open and the string slack, and
        // the weapon is dead until the player spans it again. The lock is the clip.
        put(stack, TAG_LOCKED_UNTIL, now + SHOOT_TICKS);

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
        // Where the bolt leaves: the centre of the rail, a little further out than the Garand's 0.72 because
        // the bow carries it forward of the grip.
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
     * Called from the reload key. One path, because the magazine is one bolt: a spanned and loaded weapon is
     * refused by the guard below, and everything else is empty.
     *
     * <p>The crossbow's own order, not a bolt gun's: the string is spanned <em>first</em>
     * ({@value #ANIM_DRAW}, {@value #DRAW_TICKS} t) and the bolt goes into the channel behind it
     * ({@value #ANIM_RELOAD_TACTICAL}, {@value #RELOAD_TACTICAL_TICKS} t) — the string cannot be pulled past a
     * bolt already lying on the rail. The second clip is queued in the pending slot and the lock covers both,
     * so the trigger stays dead for the whole cycle; the bolt is credited when the second clip ends, which is
     * also what releases the weapon.
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }

        // Started on the spot, so the clip's own first sound cue (t=2) lands where the file puts it.
        clearPending(stack);
        scheduleAction(stack, ACTION_DRAW, now);
        put(stack, TAG_LOCKED_UNTIL, now + DRAW_TICKS + RELOAD_TACTICAL_TICKS + 2);
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
            // A reload here is a chain of two clips: the span hands over to loading the bolt, and only the
            // last clip credits the bolt — which, with the lock, is also what releases the weapon.
            String next = nextAction(action);
            if (next.isEmpty()) {
                if (isReloadAction(action)) {
                    setAmmo(stack, MAGAZINE_SIZE);
                }
            } else {
                scheduleAction(stack, next, now);
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

    /**
     * Bolts on the rail, defaulting to one for a stack that has never been fired: a crossbow comes out of
     * the box spanned and loaded, and a player who picks one up should not have to work it before the first
     * shot. Any other value is what the state machine has written — see {@link #MAGAZINE_SIZE}.
     */
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

    /**
     * The clip that follows this one, if any: spanning the string hands over to loading the bolt. Empty for
     * everything else, which is also what ends the chain and credits the bolt.
     */
    private static String nextAction(String action) {
        return ACTION_DRAW.equals(action) ? ACTION_RELOAD_TACTICAL : "";
    }

    private static boolean isReloadAction(String action) {
        return ACTION_DRAW.equals(action) || ACTION_RELOAD_TACTICAL.equals(action);
    }

    /** Animation trigger matching an action name. */
    private static String triggerFor(String action) {
        return switch (action) {
            case ACTION_DRAW -> TRIGGER_DRAW;
            case ACTION_RELOAD_TACTICAL -> TRIGGER_RELOAD_TACTICAL;
            default -> TRIGGER_SHOOT;
        };
    }

    /** Ticks the action's clip runs for, from crossbow.animation.json. */
    private static int actionLength(String action) {
        return switch (action) {
            case ACTION_DRAW -> DRAW_TICKS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_TICKS;
            default -> 0;
        };
    }

    private static Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case ACTION_DRAW -> DRAW_SOUNDS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_SOUNDS;
            default -> Map.of();
        };
    }

    // ------------------------------------------------------------------ client

    @Override
    public void initializeClient(Consumer<IClientItemExtensions> consumer) {
        consumer.accept(new IClientItemExtensions() {
            private CrossbowItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new CrossbowItemRenderer();
                }
                return this.renderer;
            }

            /**
             * Hands the first-person transform to {@link WeaponHandGrip}: vanilla's hand base is kept, the
             * sword-style attack swing is dropped (held down, it made the weapon nod in the hand), and the hold
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