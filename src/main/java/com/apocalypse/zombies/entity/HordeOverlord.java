package com.apocalypse.zombies.entity;

import java.util.List;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.BossEvent;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.level.Level;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.zombie.EvolutionTier;
import com.apocalypse.zombies.zombie.ZombieEvolution;

/**
 * 尸潮之主 —— 三阶段 Boss，2500 点生命。
 *
 * <p>和其余精英的差别只在「数量级」和「阶段」两件事上：</p>
 * <ul>
 *   <li><b>2500 HP 分三段</b>：1666（2/3）以上是 Phase 1，833（1/3）以上是 Phase 2，
 *       之下是 Phase 3。阶段不是纯数值墙 —— 每跨一段都会当场放一个<b>入场技</b>，
 *       并把后续的技能轮转换成更长的表（Phase 1 两招，Phase 2 四招，Phase 3 五招 + 亡语）。</li>
 *   <li><b>技能全部走 {@link EliteAbility} 的三段切分</b>（前摇 → 命中 → 收招），
 *       模型侧不做任何数值推算：{@code impactTick} 就是结算那一 tick，也是动画的收放点。</li>
 * </ul>
 *
 * <p><b>下面这组常量与 {@code tools/boss_v1.py} 双向同步</b>：生成器写完 geo/anim 之后会回来读这几行，
 * 对不上就报 FAIL。改血量分段必须同时改生成器，否则自校验会拦住。</p>
 */
public class HordeOverlord extends AbstractEliteZombie implements GeoEntity {

    // ---------------------------------------------------------------- 阶段阈值（生成器回读）

    /** Boss 总生命。 */
    public static final float BOSS_MAX_HEALTH = 2500.0F;
    /** Phase 1 → Phase 2 的分界：2500 × 2/3。 */
    public static final float PHASE2_HP = 1666.0F;
    /** Phase 2 → Phase 3 的分界：2500 × 1/3。 */
    public static final float PHASE3_HP = 833.0F;
    /** 「垂死崩解」的触发线：跌破总生命的 15%。 */
    public static final float DEATH_WAIL_HP = 375.0F;

    /** 阶段数。三阶段的技能表见 {@link #ROTATION_PHASE_1} / 2 / 3。 */
    public static final int PHASE_COUNT = 3;

    // ---------------------------------------------------------------- 剪辑名（生成器回读）
    // 剪辑本身住在 assets/apocalypse_zombies/animations/horde_overlord.animation.json，
    // 由 tools/boss_v1.py 生成；下面这几行字符串是两边的接口约定。

    /** 静置（呼吸 + 尸笼慢转 + 披风轻摆）。 */
    public static final String ANIM_IDLE = "idle";
    /** 行走（基础循环：迈步 + 摆臂 + 斧头拖拽）。 */
    public static final String ANIM_WALK = "walk";
    /** 巨斧横扫（近战，1.1s，命中 0.55s）。 */
    public static final String ANIM_MELEE = "attack_melee";
    /** 骨刺齐射（远程，1.3s，命中 0.85s）。 */
    public static final String ANIM_RANGED = "attack_ranged";
    /** 召唤尸群（1.8s，命中 1.1s）。 */
    public static final String ANIM_SUMMON = "summon";
    /** 踏地冲击波（1.4s，命中 0.7s）。 */
    public static final String ANIM_QUAKE = "skill_quake";
    /** 血怒（Phase 3 入场，2.0s，命中 0.9s）。 */
    public static final String ANIM_RAGE = "skill_rage";
    /** 垂死崩解（1.6s，命中 0.9s）。 */
    public static final String ANIM_DEATH = "skill_death";

    // ---------------------------------------------------------------- 技能轮转表

    /** Phase 1（>1666）：只有近战与远程两招 —— 让玩家先学会躲斧头。 */
    private static final EliteAbility[] ROTATION_PHASE_1 = {
            EliteAbility.BOSS_SWEEP, EliteAbility.BONE_VOLLEY,
    };
    /** Phase 2（≤1666）：加上踏地与召唤，进场先来一记踏地。 */
    private static final EliteAbility[] ROTATION_PHASE_2 = {
            EliteAbility.BOSS_SWEEP, EliteAbility.GROUND_QUAKE,
            EliteAbility.RAISE_HORDE, EliteAbility.BONE_VOLLEY,
    };
    /** Phase 3（≤833）：五招齐全 + 垂死崩解；进场放血怒。 */
    private static final EliteAbility[] ROTATION_PHASE_3 = {
            EliteAbility.BOSS_SWEEP, EliteAbility.GROUND_QUAKE, EliteAbility.RAISE_HORDE,
            EliteAbility.BONE_VOLLEY, EliteAbility.DEATH_WAIL,
    };

    /** 两招之间的间隔（tick）。剪辑普遍 22~40 tick，留 24 就给玩家一个换位/回血的窗口。 */
    private static final int ABILITY_GAP = 24;

    /** 防御 5 / 攻击 15 —— 设计给定值，改数值只改这两行（{@link #createAttributes()} 直接引用）。 */
    public static final double ARMOR_POINTS = 5.0D;
    public static final float ATTACK_POWER = 15.0F;

    /** 巨斧横扫：扇面半角（度）、半径（格）、伤害、击退。 */
    private static final double SWEEP_HALF_ANGLE = 60.0D;
    private static final double SWEEP_RADIUS = 5.0D;
    /** 横扫与基础攻击同一口径（15），免得同一个 Boss 身上挂着两套对不上的「攻击力」。 */
    private static final float SWEEP_DAMAGE = ATTACK_POWER;
    /** 踏地冲击波：半径（格）、伤害、上抛量。 */
    private static final double QUAKE_RADIUS = 7.0D;
    private static final float QUAKE_DAMAGE = 9.0F;
    /** 骨刺齐射：根数、单发伤害、初速、散布。 */
    private static final int VOLLEY_COUNT = 5;
    private static final float VOLLEY_DAMAGE = 5.0F;
    private static final float VOLLEY_SPEED = 2.4F;
    private static final float VOLLEY_SPREAD = 0.06F;
    /** 召唤：一次几只（设计给定 5）、场上最多留几只。 */
    private static final int SUMMON_COUNT = 5;
    /** 场上留存上限 —— 不是平衡数值，是防「召唤把自己埋掉」的粗暴围栏。 */
    private static final int SUMMON_CAP = 12;
    private static final double SUMMON_RADIUS = 5.0D;
    /** 垂死崩解：半径（格）、伤害、召唤数。 */
    private static final double WAIL_RADIUS = 8.0D;
    private static final float WAIL_DAMAGE = 12.0F;

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    /** Boss 血条：只在有玩家看着的时候挂着，走原版的 {@code ServerBossEvent} 同步。 */
    private final ServerBossEvent bossBar = new ServerBossEvent(
            this.getDisplayName(), BossEvent.BossBarColor.RED, BossEvent.BossBarOverlay.NOTCHED_10);

    /** 环境音 / 阶段宣告的节流计数。 */
    private int phaseAnnounceCooldown;

    /** 当前阶段（1..3）。只存在服务端：客户端读的是技能状态，不需要知道阶段。 */
    private int phase = 1;

    /** 阶段入场技 / 亡语这种「一次性插队技能」，非 NONE 时优先于轮转表。 */
    private EliteAbility entryAbility = EliteAbility.NONE;

    /** 血怒是否已挂过（Phase 3 只挂一次，重挂会把增益叠成永动机）。 */
    private boolean rageApplied;

    /** 亡语是否已放（一只 Boss 只放一次）。 */
    private boolean deathWailFired;

    private int rotationIndex;

    public HordeOverlord(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
        this.xpReward = 500;
        this.setCanPickUpLoot(false);
        this.setPersistenceRequired();
    }

    /**
     * Boss 的数值。移速故意压得比普通僵尸低（0.21 < 0.23）：一个 2500 血的怪如果还能追着人跑，
     * 玩家就没有「拉开距离打工」这个解法了。
     *
     * <p>防御 5 / 攻击 15 是设计给定值 —— 它靠 2500 血和三段技能撑硬度，不靠护甲；
     * 护甲给太高会让「堆输出」变成唯一解，防御压到 5 才能让拆解（走位 + 打工）成立。</p>
     */
    public static AttributeSupplier.Builder createAttributes() {
        return eliteAttributes()
                .add(Attributes.MAX_HEALTH, BOSS_MAX_HEALTH)
                .add(Attributes.MOVEMENT_SPEED, 0.21D)
                .add(Attributes.ATTACK_DAMAGE, ATTACK_POWER)
                .add(Attributes.ARMOR, ARMOR_POINTS)
                .add(Attributes.ARMOR_TOUGHNESS, 8.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 0.8D)
                .add(Attributes.FOLLOW_RANGE, 48.0D);
    }

    // ------------------------------------------------------------------ 动画

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }

    /**
     * 两条控制器：{@code movement} 管静置 / 行走，{@code cast} 管技能。
     *
     * <p>整套技能一次只放一个，所以不需要「并行叠一层」那种第三控制器 ——
     * 每段剪辑首尾都归零，切进切出都不会跳变（生成器逐通道验过）。</p>
     */
    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, "movement", 4, HordeOverlord::movementAnimation));
        controllers.add(new AnimationController<>(this, "cast", 1, HordeOverlord::castAnimation));
    }

    /** 静置 / 行走：步子按实际位移缩放，三格高的腿不会打滑。 */
    private static PlayState movementAnimation(AnimationState<HordeOverlord> state) {
        if (state.getAnimatable().isCasting()) {
            return PlayState.STOP;
        }
        state.setControllerSpeed(Mth.clamp(0.6F + 0.9F * state.getLimbSwingAmount(), 0.55F, 2.0F));
        return state.setAndContinue(state.isMoving()
                ? RawAnimation.begin().thenLoop(ANIM_WALK)
                : RawAnimation.begin().thenLoop(ANIM_IDLE));
    }

    /** 施法：轮到哪一套就播哪一段。 */
    private static PlayState castAnimation(AnimationState<HordeOverlord> state) {
        String clip = switch (state.getAnimatable().getAbility()) {
            case BOSS_SWEEP -> ANIM_MELEE;
            case BONE_VOLLEY -> ANIM_RANGED;
            case RAISE_HORDE -> ANIM_SUMMON;
            case GROUND_QUAKE -> ANIM_QUAKE;
            case BLOOD_RAGE -> ANIM_RAGE;
            case DEATH_WAIL -> ANIM_DEATH;
            default -> null;
        };
        if (clip == null) {
            return PlayState.STOP;
        }
        return state.setAndContinue(RawAnimation.begin().thenPlay(clip));
    }

    // ------------------------------------------------------------------ 阶段与轮转

    /** 当前阶段。 */
    public int getPhase() {
        return this.phase;
    }

    /** 按血量算阶段：≥1666 → 1，≥833 → 2，否则 3。 */
    private int phaseFor(float health) {
        if (health > PHASE2_HP) {
            return 1;
        }
        return health > PHASE3_HP ? 2 : 3;
    }

    private static EliteAbility[] rotationFor(int phase) {
        return switch (phase) {
            case 2 -> ROTATION_PHASE_2;
            case 3 -> ROTATION_PHASE_3;
            default -> ROTATION_PHASE_1;
        };
    }

    /** 驱动器的「当前技能」= 插队的入场技优先，否则轮转表里的这一招。 */
    @Override
    protected EliteAbility ability() {
        if (this.entryAbility != EliteAbility.NONE) {
            return this.entryAbility;
        }
        EliteAbility[] table = rotationFor(this.phase);
        return table[this.rotationIndex % table.length];
    }

    @Override
    protected int abilityCooldownTicks() {
        return ABILITY_GAP;
    }

    /**
     * 起手条件 = 距离条件成立。
     *
     * <p>轮转到的这一招够不着时不像美女僵尸那样「数够 tick 就跳过」：
     * Boss 的三阶段本来就是按距离分层的（近战 / 远程 / 范围），
     * 够不着就把这一槽原地等 —— 玩家贴上来自然会放，跑远了会被远程接管。</p>
     */
    @Override
    protected boolean canStartAbility() {
        EliteAbility wanted = this.ability();
        if (wanted == EliteAbility.NONE) {
            return false;
        }
        return switch (wanted) {
            // 近战：贴到 5 格以内才有意义
            case BOSS_SWEEP -> this.hasTargetInRange(1.0D, SWEEP_RADIUS + 1.0D);
            // 远程：4 格内用斧头更划算，40 格外开始收不到
            case BONE_VOLLEY -> this.hasTargetInRange(4.0D, 40.0D);
            // 踏地：等玩家进圈
            case GROUND_QUAKE -> this.hasTargetInRange(1.0D, QUAKE_RADIUS + 1.5D);
            // 召唤：身边有人就放，不要求贴脸
            case RAISE_HORDE -> this.hasTargetInRange(1.0D, 24.0D);
            // 亡语：崩解要有意义，范围比踏地大一格
            case DEATH_WAIL -> this.hasTargetInRange(1.0D, WAIL_RADIUS + 1.0D);
            // 血怒是变身，有人看得见就放
            case BLOOD_RAGE -> true;
            default -> false;
        };
    }

    @Override
    protected void onAbilityStart() {
        switch (this.getAbility()) {
            case BOSS_SWEEP -> this.playSound(SoundEvents.RAVAGER_ATTACK, 1.6F, 0.7F);
            case BONE_VOLLEY -> this.playSound(SoundEvents.WITHER_SHOOT, 1.4F, 1.3F);
            case RAISE_HORDE -> {
                this.playSound(SoundEvents.EVOKER_PREPARE_SUMMON, 1.5F, 0.8F);
                this.ringParticles(ParticleTypes.SOUL, 1.2D, 24);
            }
            case GROUND_QUAKE -> this.playSound(SoundEvents.RAVAGER_ROAR, 1.6F, 0.6F);
            case BLOOD_RAGE -> {
                this.playSound(SoundEvents.WARDEN_ROAR, 2.0F, 0.8F);
                this.ringParticles(ParticleTypes.SOUL_FIRE_FLAME, 2.0D, 40);
            }
            case DEATH_WAIL -> {
                this.playSound(SoundEvents.WITHER_DEATH, 1.8F, 0.7F);
                this.ringParticles(ParticleTypes.SCULK_SOUL, 2.0D, 36);
            }
            default -> {
            }
        }
    }

    @Override
    protected void onAbilityImpact() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        switch (this.getAbility()) {
            case BOSS_SWEEP -> this.castSweep(level);
            case BONE_VOLLEY -> this.castBoneVolley(level);
            case RAISE_HORDE -> this.castRaiseHorde(level, SUMMON_COUNT);
            case GROUND_QUAKE -> this.castQuake(level);
            case BLOOD_RAGE -> this.castBloodRage(level);
            case DEATH_WAIL -> this.castDeathWail(level);
            default -> {
            }
        }
    }

    @Override
    protected void onAbilityEnd() {
        // 插队技能用掉就还回去。轮转表只在「正常轮转」的招上往前走一格 ——
        // 入场技和亡语是额外送的，不该占用轮转的节奏。
        if (this.entryAbility != EliteAbility.NONE) {
            this.entryAbility = EliteAbility.NONE;
            return;
        }
        EliteAbility[] table = rotationFor(this.phase);
        this.rotationIndex = (this.rotationIndex + 1) % table.length;
    }

    /**
     * 阶段推进 + 亡语判定 + 血条。挂在 {@code customServerAiStep} 上：
     * 这里排在 goalSelector 之后、{@code travel()} 之前，改完当 tick 就生效。
     */
    @Override
    protected void customServerAiStep() {
        super.customServerAiStep();
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }

        float health = this.getHealth();
        int next = this.phaseFor(health);
        if (next > this.phase) {
            this.enterPhase(level, next);
        }

        // 垂死崩解：Phase 3 里跌破 15% 时插队一次，之后不再触发
        if (!this.deathWailFired && this.phase == 3 && health <= DEATH_WAIL_HP
                && !this.isCasting()) {
            this.deathWailFired = true;
            this.entryAbility = EliteAbility.DEATH_WAIL;
        }

        this.updateBossBar(level);
    }

    /** 进入新阶段：换轮转表、插一张入场技、给看得见的玩家放标题与音效。 */
    private void enterPhase(ServerLevel level, int next) {
        this.phase = next;
        this.rotationIndex = 0;
        this.bossBar.setColor(switch (next) {
            case 2 -> BossEvent.BossBarColor.YELLOW;
            case 3 -> BossEvent.BossBarColor.PURPLE;
            default -> BossEvent.BossBarColor.RED;
        });

        if (next == 2) {
            this.entryAbility = EliteAbility.GROUND_QUAKE;
        } else if (next == 3 && !this.rageApplied) {
            this.entryAbility = EliteAbility.BLOOD_RAGE;
        }

        for (ServerPlayer player : level.players()) {
            player.connection.send(new ClientboundSetTitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.boss.phase.title", next, PHASE_COUNT)));
            player.connection.send(new ClientboundSetSubtitleTextPacket(
                    Component.translatable("horde.apocalypse_zombies.boss.phase.subtitle")));
            player.playNotifySound(SoundEvents.WARDEN_ROAR, SoundSource.HOSTILE, 1.4F, 0.7F);
        }
        this.phaseAnnounceCooldown = 60;
    }

    /** 血条：名字带阶段与血量，进度条就是血量。每 5 tick 推一次，不必每 tick 发包。 */
    private void updateBossBar(ServerLevel level) {
        // 名单每 2 秒重挂一次就够了：新看到的玩家由 startSeenByPlayer 立刻补上，
        // 每 tick 遍历玩家列表只是白花钱（战斗时这一段在服务端主线程上）。
        if (this.phaseAnnounceCooldown > 0) {
            this.phaseAnnounceCooldown--;
        }
        if (this.phaseAnnounceCooldown <= 0) {
            this.phaseAnnounceCooldown = 40;
            for (ServerPlayer player : level.players()) {
                this.bossBar.addPlayer(player);
            }
        }
        if (this.tickCount % 5 != 0) {
            return;
        }
        this.bossBar.setName(Component.translatable("horde.apocalypse_zombies.boss.bar",
                this.phase, Math.max(0, Math.round(this.getHealth()))));
        this.bossBar.setProgress(Mth.clamp(this.getHealth() / this.getMaxHealth(), 0.0F, 1.0F));
    }

    /** 被玩家看到就挂上血条；第一次被看到时吼一声，让玩家知道碰上的是什么。 */
    @Override
    public void startSeenByPlayer(ServerPlayer player) {
        super.startSeenByPlayer(player);
        this.bossBar.addPlayer(player);
        player.playNotifySound(SoundEvents.WITHER_SPAWN, SoundSource.HOSTILE, 1.0F, 0.6F);
        player.connection.send(new ClientboundSetTitleTextPacket(
                Component.translatable("horde.apocalypse_zombies.boss.spawn.title")));
    }

    @Override
    public void stopSeenByPlayer(ServerPlayer player) {
        super.stopSeenByPlayer(player);
        this.bossBar.removePlayer(player);
    }

    @Override
    public void remove(RemovalReason reason) {
        this.bossBar.removeAllPlayers();
        super.remove(reason);
    }

    // ------------------------------------------------------------------ 技能结算

    /**
     * 巨斧横扫：身前 ±60° / 5 格的扇面重击。
     *
     * <p>角度判定用视线方向与「从自己指向目标」的水平夹角，不做方块射线 ——
     * 三格高的怪站在石头上打脚下的玩家时，射线会被自己的碰撞箱挡住。</p>
     */
    private void castSweep(ServerLevel level) {
        Vec3 look = this.getLookAngle();
        AABB box = this.getBoundingBox().inflate(SWEEP_RADIUS);
        for (LivingEntity victim : level.getEntitiesOfClass(LivingEntity.class, box)) {
            if (victim == this || victim instanceof Zombie) {
                continue;
            }
            Vec3 toVictim = victim.position().subtract(this.position());
            double flat = Math.sqrt(toVictim.x * toVictim.x + toVictim.z * toVictim.z);
            if (flat > SWEEP_RADIUS) {
                continue;
            }
            double dot = (toVictim.x * look.x + toVictim.z * look.z) / Math.max(1.0E-4D, flat);
            if (Math.toDegrees(Math.acos(Mth.clamp(dot, -1.0D, 1.0D))) > SWEEP_HALF_ANGLE) {
                continue;
            }
            victim.hurt(this.damageSources().mobAttack(this), SWEEP_DAMAGE);
            victim.knockback(1.4D, -toVictim.x, -toVictim.z);
        }
        // 斧刃扫过的弧线：沿扇面撒一圈 SWEEP_ATTACK
        for (int i = -3; i <= 3; i++) {
            double angle = this.getYRot() + i * (SWEEP_HALF_ANGLE / 3.5D);
            double radians = Math.toRadians(angle);
            double x = this.getX() - Math.sin(radians) * 2.6D;
            double z = this.getZ() + Math.cos(radians) * 2.6D;
            level.sendParticles(ParticleTypes.SWEEP_ATTACK, x, this.getY() + 1.4D, z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        this.playSound(SoundEvents.PLAYER_ATTACK_SWEEP, 1.8F, 0.6F);
    }

    /** 骨刺齐射：朝目标甩出 5 根带轻微制导的骨刺（复用重箭实体，只是不再放大命中点）。 */
    private void castBoneVolley(ServerLevel level) {
        LivingEntity target = this.getTarget();
        if (target == null) {
            return;
        }
        Vec3 eye = this.getEyePosition();
        Vec3 aim = new Vec3(target.getX(), target.getY(0.5D), target.getZ()).subtract(eye).normalize();
        for (int i = 0; i < VOLLEY_COUNT; i++) {
            double offset = (i - (VOLLEY_COUNT - 1) / 2.0D) * VOLLEY_SPREAD;
            Vec3 direction = aim.yRot((float) offset);
            GiantArrow spike = new GiantArrow(ModEntities.GIANT_ARROW.get(), level);
            spike.setOwner(this);
            spike.setBaseDamage(VOLLEY_DAMAGE);
            spike.setKnockback(1);
            spike.setPos(eye.x, eye.y - 0.4D, eye.z);
            spike.shoot(direction.x, direction.y, direction.z, VOLLEY_SPEED, 0.4F);
            level.addFreshEntity(spike);
        }
        this.playSound(SoundEvents.ARROW_SHOOT, 1.8F, 0.6F);
    }

    /** 召唤尸群：从脚下环状位置召来僵尸，环绕自己的目标冲锋。 */
    private void castRaiseHorde(ServerLevel level, int requested) {
        int alive = this.countNearbyZombies(level);
        int count = Math.max(0, Math.min(requested, SUMMON_CAP - alive));
        LivingEntity target = this.getTarget();
        int tier = Math.min(EvolutionTier.MAX_TIER,
                Math.max(0, MoonEventManager.getEvolutionLevel(level)));
        for (int i = 0; i < count; i++) {
            double angle = 2.0D * Math.PI * i / Math.max(1, count);
            BlockPos pos = BlockPos.containing(this.getX() + Math.cos(angle) * SUMMON_RADIUS,
                    this.getY(), this.getZ() + Math.sin(angle) * SUMMON_RADIUS);
            Zombie minion = EntityType.ZOMBIE.create(level);
            if (minion == null) {
                continue;
            }
            minion.moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D,
                    this.random.nextFloat() * 360.0F, 0.0F);
            minion.finalizeSpawn(level, level.getCurrentDifficultyAt(pos), MobSpawnType.MOB_SUMMONED, null, null);
            minion.setPersistenceRequired();
            ZombieEvolution.setTier(minion, tier, false);
            if (target != null) {
                minion.setTarget(target);
            }
            if (level.addFreshEntity(minion)) {
                level.sendParticles(ParticleTypes.SOUL, minion.getX(), minion.getY() + 1.0D, minion.getZ(),
                        12, 0.3D, 0.5D, 0.3D, 0.02D);
            }
        }
        this.ringParticles(ParticleTypes.SOUL, SUMMON_RADIUS, 32);
        this.playSound(SoundEvents.EVOKER_CAST_SPELL, 1.6F, 0.7F);
    }

    private int countNearbyZombies(ServerLevel level) {
        return level.getEntitiesOfClass(Zombie.class,
                this.getBoundingBox().inflate(SUMMON_RADIUS + 2.0D)).size();
    }

    /** 踏地冲击波：7 格内全部震起 + 重击；玩家还会被短暂减速（腿软）。 */
    private void castQuake(ServerLevel level) {
        AABB box = this.getBoundingBox().inflate(QUAKE_RADIUS);
        for (LivingEntity victim : level.getEntitiesOfClass(LivingEntity.class, box)) {
            if (victim == this || victim instanceof Zombie) {
                continue;
            }
            double distance = Math.max(1.0D, victim.position().distanceTo(this.position()));
            double falloff = 1.0D - Mth.clamp((distance - 1.0D) / QUAKE_RADIUS, 0.0D, 0.75D);
            victim.hurt(this.damageSources().mobAttack(this), (float) (QUAKE_DAMAGE * falloff));
            victim.push(0.0D, 0.85D * falloff, 0.0D);
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, 40, 1));
            victim.hurtMarked = true;
        }
        // 冲击环：贴地撒一圈 EXPLOSION，脚感更重
        for (int i = 0; i < 48; i++) {
            double angle = 2.0D * Math.PI * i / 48.0D;
            level.sendParticles(ParticleTypes.EXPLOSION,
                    this.getX() + Math.cos(angle) * QUAKE_RADIUS, this.getY() + 0.2D,
                    this.getZ() + Math.sin(angle) * QUAKE_RADIUS, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        this.playSound(SoundEvents.GENERIC_EXPLODE, 1.8F, 0.6F);
    }

    /** 血怒（Phase 3 入场）：给自己挂力量 / 迅捷 / 抗性，并把周围推开。 */
    private void castBloodRage(ServerLevel level) {
        this.rageApplied = true;
        this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_BOOST, 12000, 1));
        this.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SPEED, 12000, 0));
        this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_RESISTANCE, 12000, 0));
        this.addEffect(new MobEffectInstance(MobEffects.FIRE_RESISTANCE, 12000, 0));
        this.ringParticles(ParticleTypes.SOUL_FIRE_FLAME, 3.0D, 60);
        AABB box = this.getBoundingBox().inflate(QUAKE_RADIUS);
        for (LivingEntity victim : level.getEntitiesOfClass(LivingEntity.class, box)) {
            if (victim == this || victim instanceof Zombie) {
                continue;
            }
            Vec3 push = victim.position().subtract(this.position());
            victim.knockback(1.2D, -push.x, -push.z);
        }
        this.playSound(SoundEvents.WARDEN_ROAR, 2.0F, 1.2F);
    }

    /** 垂死崩解：8 格范围重击 + 上抛 + 再召一波僵尸，顺便清掉自身的负面效果。 */
    private void castDeathWail(ServerLevel level) {
        AABB box = this.getBoundingBox().inflate(WAIL_RADIUS);
        for (LivingEntity victim : level.getEntitiesOfClass(LivingEntity.class, box)) {
            if (victim == this || victim instanceof Zombie) {
                continue;
            }
            victim.hurt(this.damageSources().mobAttack(this), WAIL_DAMAGE);
            victim.addEffect(new MobEffectInstance(MobEffects.WITHER, 100, 0));
            Vec3 push = victim.position().subtract(this.position()).normalize().scale(1.6D);
            victim.push(push.x, 0.7D, push.z);
            victim.hurtMarked = true;
        }
        this.castRaiseHorde(level, SUMMON_COUNT);
        this.removeAllEffects();
        this.ringParticles(ParticleTypes.SCULK_SOUL, WAIL_RADIUS, 64);
        this.playSound(SoundEvents.WITHER_DEATH, 2.0F, 0.6F);
    }

    /** 环绕自己撒一圈粒子（起手 / 命中都用得上）。 */
    private void ringParticles(net.minecraft.core.particles.SimpleParticleType type, double radius, int count) {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        for (int i = 0; i < count; i++) {
            double angle = 2.0D * Math.PI * i / count;
            level.sendParticles(type, this.getX() + Math.cos(angle) * radius, this.getY() + 1.6D,
                    this.getZ() + Math.sin(angle) * radius, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
    }

    // ------------------------------------------------------------------ 通用性质

    /** Boss 不会被晒成焦炭：2500 血的怪在白天自己烧死，谁都没法打。 */
    @Override
    protected boolean isSunSensitive() {
        return false;
    }

    /** 也不该被水变成溺尸。 */
    @Override
    protected boolean convertsInWater() {
        return false;
    }

    /** 死后掉落 500 经验（{@code xpReward} 已设），并清掉血条。 */
    @Override
    public void die(net.minecraft.world.damagesource.DamageSource source) {
        this.bossBar.removeAllPlayers();
        super.die(source);
    }

    /** 三阶段 Boss 的血条不该因为玩家走远而消失（离得远也看得见进度）。 */
    @Override
    public boolean removeWhenFarAway(double distance) {
        return false;
    }

    /** 供外部（尸潮管理器 / 指令）查询：这只 Boss 现在还能召几只增援。 */
    public int summonHeadroom() {
        if (!(this.level() instanceof ServerLevel level)) {
            return 0;
        }
        return Math.max(0, SUMMON_CAP - this.countNearbyZombies(level));
    }

    /** 阶段标题用得到：把阶段阈值暴露给测试与调试指令。 */
    public static float[] phaseThresholds() {
        return new float[] {PHASE2_HP, PHASE3_HP};
    }

    /** 轮转表快照：自检脚本与日志用得到。 */
    public static List<EliteAbility> rotationSnapshot(int phase) {
        return List.of(rotationFor(phase));
    }
}
