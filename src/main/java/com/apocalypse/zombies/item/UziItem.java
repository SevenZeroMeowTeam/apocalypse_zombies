package com.apocalypse.zombies.item;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.UziItemRenderer;
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
 * Uzi — a GeckoLib-boned blowback submachine gun, and the newest gun in the weapon layer.
 *
 * <p>Geometry and animation live in {@code assets/apocalypse_zombies/geo/uzi.geo.json} and
 * {@code animations/uzi.animation.json}: 23 bones, eight clips ({@value #ANIM_IDLE}, {@value #ANIM_DRAW},
 * {@value #ANIM_SHOOT}, {@value #ANIM_SHOOT_AUTO}, {@value #ANIM_BOLT}, {@value #ANIM_RELOAD_TACTICAL},
 * {@value #ANIM_RELOAD_EMPTY}, {@value #ANIM_ADS_UP}, {@value #ANIM_ADS_DOWN}). The model is 0.99 blocks long
 * (15.77 u), 185 cubes and one 512² texture; every pose is per-bone rotation/translation, nothing scales the
 * model, per 美术规范.md §5.</p>
 *
 * <p>Four things make this an Uzi and not a shortened Garand, and all four are action logic:</p>
 * <ul>
 *   <li><b>It fires from an open bolt, and it fires fast.</b> {@value #FIRE_INTERVAL_TICKS} ticks between
 *       rounds is 600 rpm. A real Uzi runs 738 rpm, which is 1.63 rounds per tick — <em>more than one per
 *       tick</em> — so the game cannot express it: the nearest expressible cadences are 1200 rpm (1 tick) and
 *       600 rpm (2 ticks). 600 is the one whose cycle a viewer can actually read. Holding the button gives one
 *       shot per {@value #FIRE_INTERVAL_TICKS} ticks and the fire is sustained until the magazine is dry.</li>
 *   <li><b>The bolt animation is a fast cycle, not the rifle's single-shot clip.</b> The {@value #ANIM_SHOOT}
 *       clip runs 0.6 s and carries the bolt through a 0.208 s cycle — re-triggered every
 *       {@value #FIRE_INTERVAL_TICKS} ticks it would restart before the bolt ever closed, leaving the action
 *       jittering at the rear. So automatic fire triggers {@value #ANIM_SHOOT_AUTO} instead: a two-frame
 *       {@value #AUTO_CYCLE_TICKS}-tick cycle authored to finish exactly as the next round fires, so the
 *       string reads as continuous cycling. {@value #ANIM_SHOOT} keeps its job as the <em>last</em> round's
 *       performance, where the longer recoil has room to play out.</li>
 *   <li><b>The magazine lives in the grip.</b> A tactical reload swaps a 32-round box, and because the well is
 *       inside the pistol grip the left hand does the work while the right keeps the trigger — see
 *       {@code UziGeoModel} for the hand split.</li>
 *   <li><b>Iron sights, no optic.</b> The rear notch on the receiver <em>is</em> the aim point, so the gun
 *       stays in frame while aimed: same choice as the Garand and the Mosin, see {@link #hasScopeOverlay()} /
 *       {@link #hidesModelWhileAimed()}.</li>
 * </ul>
 *
 * <p><b>Sounds are borrowed.</b> The recordings in {@code sounds/awm/} are TaCZ's AWM set shipped under
 * CC BY-NC-ND 4.0 (see {@code registry/ModSounds}); this gun triggers those same ids rather than shipping an
 * Uzi set it does not have. Nothing is re-encoded, and swapping in real Uzi recordings is a resource change
 * only — add the ids, point them at the new files — because the cue tables below are keyed by tick against the
 * clips in {@code uzi.animation.json}.</p>
 *
 * <p>Ballistics are this project's own choice, not a transcription: 9×19 mm out of an 8-inch barrel is a
 * close-quarters round, so it does 9/7.5/5.5 damage across 24/64 blocks, pierces one body rather than the
 * Garand's two, and reaches 120 m. Server-authoritative throughout: the client only asks ({@code FirePacket} /
 * {@code ReloadPacket}) and every decision is made here from the stack's NBT.</p>
 */
public class UziItem extends Item implements GeoItem, GunItem {

    /** Always-on controller, loops the idle pose. */
    public static final String CONTROLLER_MAIN = "main";
    /** Trigger-driven controller for one-shot actions. */
    public static final String CONTROLLER_ACTION = "action";

    /** Trigger names — these are what Java passes to {@code triggerAnim}, not the clip names. */
    public static final String TRIGGER_DRAW = "draw";
    public static final String TRIGGER_SHOOT = "shoot";
    public static final String TRIGGER_SHOOT_AUTO = "shoot_auto";
    public static final String TRIGGER_BOLT = "bolt";
    public static final String TRIGGER_RELOAD_TACTICAL = "reload_tactical";
    public static final String TRIGGER_RELOAD_EMPTY = "reload_empty";
    public static final String TRIGGER_ADS_UP = "ADS_up";
    public static final String TRIGGER_ADS_DOWN = "ADS_down";

    /** Clip names as exported from Blockbench — must match uzi.animation.json exactly. */
    public static final String ANIM_IDLE = "static_idle";
    public static final String ANIM_DRAW = "draw";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_SHOOT_AUTO = "shoot_auto";
    public static final String ANIM_BOLT = "bolt";
    public static final String ANIM_RELOAD_TACTICAL = "reload_tactical";
    public static final String ANIM_RELOAD_EMPTY = "reload_empty";
    public static final String ANIM_ADS_UP = "ADS_up";
    public static final String ANIM_ADS_DOWN = "ADS_down";

    /** Clip lengths in ticks (20 t/s), taken from uzi.animation.json. */
    private static final int DRAW_TICKS = 20;              // 1.0 s
    private static final int SHOOT_TICKS = 12;             // 0.6 s — the last round's longer performance
    private static final int AUTO_CYCLE_TICKS = 2;         // 0.0833 s — the automatic-fire bolt cycle
    private static final int BOLT_TICKS = 26;              // 1.25 s
    private static final int RELOAD_TACTICAL_TICKS = 52;   // 2.6 s
    private static final int RELOAD_EMPTY_TICKS = 66;      // 3.3 s

    /**
     * Ticks between rounds when the trigger is held: 600 rpm.
     *
     * <p>Not the 738 rpm of the real gun — see the class note. This is also the client's own fire poll, so a
     * held button asks for exactly one round per interval and nothing is dropped.</p>
     */
    private static final int FIRE_INTERVAL_TICKS = 2;

    /** Thirty-two rounds, one box magazine — the Uzi's standard magazine. */
    public static final int MAGAZINE_SIZE = 32;

    // ------------------------------------------------------------------ sight

    /** Iron sights: an SMG zooms less than a rifle, and draws no overlay. */
    private static final double AIMED_FOV = 55.0D;
    /** An SMG comes up fast. */
    private static final float AIM_TIME = 0.16F;
    /**
     * Where the sight line sits in the hip pose, expressed as the offset that brings it up to the eye.
     * Measured, not eyeballed: {@code tools/pose_measure.py uzi} walks the whole transform chain and prints
     * the offset that lands the sight line on the view axis, then re-checks these constants against it.
     *
     * <p>{@code ADS_X} is the same pair the other iron-sighted guns settle on — the dominant term is the hand
     * base itself, scaled by {@link #FIRST_PERSON_SCALE}. {@code ADS_Y} is this gun's own: the Uzi's sights sit
     * higher over the bore than the Garand's, and the model is shorter, so the number is measured per gun.</p>
     *
     * <p>Both come from {@code tools/pose_measure.py uzi}, which walks the geo and this gun's display block and
     * prints the offsets that put the <em>rear aperture</em> on the view axis. Measured, not guessed: the first
     * pass here carried the Garand's {@code ADS_Y} and put the peep 0.034 blocks low.</p>
     *
     * <p>Re-measured after the sight line was straightened: the post tip and the aperture centre are both at
     * 3.26 in the geo now, so the sight line runs parallel to the bore and the aperture rides 0.0103 blocks
     * lower than the crooked geometry had it. {@code pose_measure.py uzi} reports 0.00° off the view axis
     * with this value.</p>
     */
    private static final float ADS_X = -0.4746F;
    private static final float ADS_Y = 0.3015F;
    /**
     * The item model's first-person {@code display} rotation (degrees), cancelled while aiming so the sight
     * line ends up parallel to the view axis — see {@link GunItem#adsPitch()}.
     */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;
    /** How much bigger the gun reads in the first person, on top of the {@code display} block's own size. */
    private static final float FIRST_PERSON_SCALE = 1.25F;
    /**
     * Firing kick as a pitch about the grip (degrees at full kick). Much smaller than the rifles': at ten
     * rounds a second a Garand-sized kick would shake the picture apart inside the first second.
     */
    private static final float FIRE_PITCH = 1.6F;

    // ------------------------------------------------------------------ ballistics

    private static final float DAMAGE_NEAR = 9.0F;
    private static final float DAMAGE_MID = 7.5F;
    private static final float DAMAGE_FAR = 5.5F;
    private static final double RANGE_MID = 24.0D;
    private static final double RANGE_FAR = 64.0D;
    private static final float HEADSHOT_MULTIPLIER = 2.0F;
    private static final double HEADSHOT_HEIGHT = 0.82D;
    /** 9 mm stops in the body it hits — one, where the rifles pass through several. */
    private static final int PIERCE = 1;
    private static final double MAX_RANGE = 120.0D;

    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "uzi_bullet"));

    // ------------------------------------------------------------------ tracer

    private static final double TRACER_SPACING = 0.65D;
    private static final int TRACER_MAX_DOTS = 48;

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
    private static final String ACTION_SHOOT_AUTO = "shoot_auto";
    private static final String ACTION_BOLT = "bolt";
    private static final String ACTION_RELOAD_TACTICAL = "reload_tactical";
    private static final String ACTION_RELOAD_EMPTY = "reload_empty";

    /**
     * When each mechanical sound fires, in ticks from the start of its action.
     *
     * <p>These are keyed against the clips in {@code uzi.animation.json}. The report itself is not here — it is
     * played live in {@link #playShot}, on the tick of the shot.</p>
     */
    private static final Map<Integer, RegistryObject<SoundEvent>> SHOOT_SOUNDS = Map.of(
            3, ModSounds.AWM_RECHAMBER_OUT,
            6, ModSounds.AWM_RECHAMBER_EJECT,
            9, ModSounds.AWM_RECHAMBER_IN,
            11, ModSounds.AWM_RECHAMBER_END);

    /** The automatic-fire cycle is two ticks long, so it carries one cue and no room for a sequence. */
    private static final Map<Integer, RegistryObject<SoundEvent>> SHOOT_AUTO_SOUNDS = Map.of(
            0, ModSounds.AWM_RECHAMBER_EJECT);

    /** Manual 拉栓 — slower and more deliberate than the self-cycling action. */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            8, ModSounds.AWM_RECHAMBER_EJECT,
            16, ModSounds.AWM_RECHAMBER_IN,
            19, ModSounds.AWM_RECHAMBER_END);

    /** Bringing the gun up: the sling and the stock settle, then the bolt is let go. */
    private static final Map<Integer, RegistryObject<SoundEvent>> DRAW_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            13, ModSounds.AWM_RECHAMBER_IN);

    /** The empty-box reload: old magazine out, fresh one in, bolt released. */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            3, ModSounds.AWM_RELOAD_EMPTY_RAISE,
            10, ModSounds.AWM_RELOAD_EJECT,
            24, ModSounds.AWM_RELOAD_EMPTY_MAGIN,
            40, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            60, ModSounds.AWM_RELOAD_EMPTY_END);

    /** Tactical reload: magazine out, magazine in, then the bolt pulled and released by hand. */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            3, ModSounds.AWM_RELOAD_RAISE,
            8, ModSounds.AWM_RELOAD_RATTLE,
            13, ModSounds.AWM_RELOAD_MAGOUT,
            26, ModSounds.AWM_RELOAD_MAGIN,
            33, ModSounds.AWM_RECHAMBER_OUT,
            42, ModSounds.AWM_RELOAD_END);

    private static final double SHOT_HEARD_SQR = 64.0D * 64.0D;

    private static final RawAnimation IDLE = RawAnimation.begin().thenLoop(ANIM_IDLE);
    private static final RawAnimation DRAW = RawAnimation.begin().thenPlay(ANIM_DRAW);
    private static final RawAnimation SHOOT = RawAnimation.begin().thenPlay(ANIM_SHOOT);
    private static final RawAnimation SHOOT_AUTO = RawAnimation.begin().thenPlay(ANIM_SHOOT_AUTO);
    private static final RawAnimation BOLT = RawAnimation.begin().thenPlay(ANIM_BOLT);
    private static final RawAnimation RELOAD_TACTICAL = RawAnimation.begin().thenPlay(ANIM_RELOAD_TACTICAL);
    private static final RawAnimation RELOAD_EMPTY = RawAnimation.begin().thenPlay(ANIM_RELOAD_EMPTY);
    private static final RawAnimation ADS_UP = RawAnimation.begin().thenPlay(ANIM_ADS_UP);
    private static final RawAnimation ADS_DOWN = RawAnimation.begin().thenPlay(ANIM_ADS_DOWN);

    private static final int TRANSITION_TICKS = 4;

    private final AnimatableInstanceCache cache = GeckoLibUtil.createInstanceCache(this);

    public UziItem(Properties properties) {
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
                .triggerableAnim(TRIGGER_SHOOT_AUTO, SHOOT_AUTO)
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
     * Iron sights: the rear notch on the receiver <em>is</em> the aim point, so the gun has to stay in the
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
     * One trigger pull, straight off the wire. Refuses while the action is busy or the magazine is dry, so
     * holding the button gives one round every {@value #FIRE_INTERVAL_TICKS} ticks — 600 rpm, sustained.
     *
     * <p>The action recorded here is a shot rather than a bolt: {@value #ANIM_SHOOT_AUTO} already cycles the
     * bolt itself, so scheduling one would run the same motion twice. What the record buys is the file's
     * mechanical cues and the HUD's lock window.</p>
     *
     * <p>The round that empties the magazine plays {@value #ANIM_SHOOT} instead — the full 0.6 s performance
     * with room for the recoil to settle — and locks for its whole length, which doubles as the beat before
     * the player reloads.</p>
     */
    @Override
    public void tryFire(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now)) {
            return;
        }
        if (getAmmo(stack) <= 0) {
            // Dry: the trigger and the striker. The bolt is home on a closed-bolt build, so this is the
            // click of an empty gun rather than a misfire. Then it loads itself: a magazine on the belt is a
            // magazine it will use, here or on any other gun.
            level.playSound(null, player.getX(), player.getY(), player.getZ(),
                    ModSounds.AWM_RECHAMBER_EJECT.get(), SoundSource.PLAYERS, 0.5F, 1.2F);
            beginReload(player, stack, level);
            return;
        }

        int left = getAmmo(stack) - 1;
        setAmmo(stack, left);
        boolean last = left == 0;
        clearPending(stack);
        put(stack, TAG_LOCKED_UNTIL, now + (last ? SHOOT_TICKS : FIRE_INTERVAL_TICKS));
        if (last) {
            trigger(player, stack, level, TRIGGER_SHOOT);
            startAction(stack, ACTION_SHOOT, now);
        } else {
            trigger(player, stack, level, TRIGGER_SHOOT_AUTO);
            startAction(stack, ACTION_SHOOT_AUTO, now);
        }

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
        // The shortest gun in the rack: the muzzle sits close in and only a little low.
        Vec3 muzzle = eye.add(look.scale(0.62D)).add(right.scale(-0.10D)).add(0.0D, -0.08D, 0.0D);
        // The ejection port, right and slightly above the bore — where the brass leaves.
        Vec3 port = eye.add(look.scale(0.34D)).add(right.scale(0.16D)).add(0.0D, 0.02D, 0.0D);

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

        level.sendParticles(ParticleTypes.FLAME, muzzle.x, muzzle.y, muzzle.z, 3, 0.02D, 0.02D, 0.02D, 0.02D);
        level.sendParticles(ParticleTypes.END_ROD, muzzle.x, muzzle.y, muzzle.z, 4, 0.04D, 0.04D, 0.04D, 0.02D);
        // Brass. The automatic clip is two frames long, too short to carry a casing whose flight reads, so the
        // ejection is a puff at the port on every round instead — at ten a second it reads as a stream.
        level.sendParticles(ParticleTypes.CRIT, port.x, port.y, port.z, 2, 0.04D, 0.02D, 0.04D, 0.06D);
        playShot(player, level);
    }

    /** The report: close mix for the shooter, distant one for everyone in earshot. */
    private void playShot(ServerPlayer player, ServerLevel level) {
        player.playNotifySound(ModSounds.AWM_SHOOT.get(), SoundSource.PLAYERS, 1.0F, 1.15F);
        SoundEvent distant = ModSounds.AWM_SHOOT_3P.get();
        for (ServerPlayer other : level.players()) {
            if (other != player && other.distanceToSqr(player) < SHOT_HEARD_SQR) {
                other.playNotifySound(distant, SoundSource.PLAYERS, 2.0F, 1.15F);
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
     * Called from the reload key. A round still chambered runs the short swap; a dry gun runs the full
     * 空匣脱出 → 新匣插入 → 拉栓复位 sequence. The rounds are credited back when the clip ends, which is also
     * when the weapon unlocks.
     */
    @Override
    public void beginReload(ServerPlayer player, ItemStack stack, ServerLevel level) {
        long now = level.getGameTime();
        if (isLocked(stack, now) || getAmmo(stack) >= MAGAZINE_SIZE) {
            return;
        }
        boolean chambered = getAmmo(stack) > 0;
        int ticks = chambered ? RELOAD_TACTICAL_TICKS : RELOAD_EMPTY_TICKS;

        // Started on the spot, so the clip's own first sound cue (t=3) lands where the file puts it.
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
            // A finished reload is what credits the fresh magazine; a shot just clears itself.
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
            case ACTION_SHOOT_AUTO -> TRIGGER_SHOOT_AUTO;
            case ACTION_BOLT -> TRIGGER_BOLT;
            case ACTION_RELOAD_TACTICAL -> TRIGGER_RELOAD_TACTICAL;
            default -> TRIGGER_RELOAD_EMPTY;
        };
    }

    /** Ticks the action's clip runs for, from uzi.animation.json. */
    private static int actionLength(String action) {
        return switch (action) {
            case ACTION_DRAW -> DRAW_TICKS;
            case ACTION_SHOOT -> SHOOT_TICKS;
            case ACTION_SHOOT_AUTO -> AUTO_CYCLE_TICKS;
            case ACTION_BOLT -> BOLT_TICKS;
            case ACTION_RELOAD_TACTICAL -> RELOAD_TACTICAL_TICKS;
            case ACTION_RELOAD_EMPTY -> RELOAD_EMPTY_TICKS;
            default -> 0;
        };
    }

    private static Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case ACTION_SHOOT -> SHOOT_SOUNDS;
            case ACTION_SHOOT_AUTO -> SHOOT_AUTO_SOUNDS;
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
            private UziItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new UziItemRenderer();
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
