package com.apocalypse.zombies.entity;

import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.goal.RangedBowAttackGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.monster.AbstractSkeleton;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.ai.AllySafeHurtByTargetGoal;
import com.apocalypse.zombies.entity.ai.GiantArrowGoal;

import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

/**
 * 骸骨射手 —— 远程压制。普通射击走原版弓，冷却好了就蓄一发「骨矢锁定」。
 *
 * <p>技能「骨矢锁定」：举弓蓄力 2.1 秒（42 tick），第 1.7 秒（34 tick）放出一发必中骨矢
 * （{@link BoneLockArrow}）—— 转向速率默认 60 度 / tick，甩不掉；伤害是「目标最大血量 ×
 * {@code Config.AI_MARKSMAN_LOCK_RATIO}」，护甲 / 无敌帧 / 抗性都吃不住这一枪。
 * 靠 {@link KeepDistanceGoal} 吊在 7~18 格外，不贴身。</p>
 *
 * <p>和僵尸系那三只分属不同继承链，所以施法状态自己持一份 {@code SynchedEntityData} 访问器
 * （{@code defineId} 按类分 ID 段，跨类复用会撞 ID），推进逻辑复用 {@link EliteAbilityDriver}。</p>
 *
 * <p>外观是 GeckoLib 真骨骼模型（{@code client/model/MarksmanGeoModel}）：主手的原版弓
 * 只留给 {@code RangedBowAttackGoal} 做持物判定，玩家看到的是骨骼树里的 {@code bow}。</p>
 */
public class MarksmanSkeleton extends AbstractSkeleton implements EliteMob, GeoEntity {

    // ------------------------------------------------------------------ 动作剪辑名
    // 值必须与 art/marksman/DESIGN.md 的 clip 表和 animations/marksman_skeleton.animation.json
    // 一致：GeckoLib 找不到剪辑是**静默**的（模型定格在静止姿态），没有任何日志。
    /** 站立。 */
    public static final String ANIM_IDLE = "idle";
    /** 行走。 */
    public static final String ANIM_WALK = "walk";
    /** 拉弓射击：由原版同步标志（{@code isUsingItem()} + 主手弓）驱动，不需要自定义字段。 */
    public static final String ANIM_SHOOT = "shoot";
    /** 骨矢锁定：举弓前摇 → 第 34 tick 放出骨矢 → 收招，整段 42 tick。 */
    public static final String ANIM_LOCK = "skill_bone_lock";

    /**
     * 前摇粒子：眼眶与骨弓上烧起来的灵魂火。
     *
     * <p>具名常量，不把字面量散在调用处 —— 换特效只要改这一行，
     * 也不会出现两处喷的不一样（照 {@code DeathMarkEffect.MARK_PARTICLE} 的写法）。</p>
     */
    private static final ParticleOptions WINDUP_PARTICLE = ParticleTypes.SOUL_FIRE_FLAME;

    /** 前摇粒子间隔（tick）：每 4 tick 一簇，够密但不至于糊满整块屏幕。 */
    private static final int WINDUP_PARTICLE_INTERVAL = 4;

    private static final EntityDataAccessor<Byte> DATA_ABILITY =
            SynchedEntityData.defineId(MarksmanSkeleton.class, EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Integer> DATA_ABILITY_TICK =
            SynchedEntityData.defineId(MarksmanSkeleton.class, EntityDataSerializers.INT);

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    private EliteAbilityDriver driver;

    public MarksmanSkeleton(EntityType<? extends AbstractSkeleton> type, Level level) {
        super(type, level);
        this.xpReward = 14;
    }

    public static AttributeSupplier.Builder createAttributes() {
        return AbstractSkeleton.createAttributes()
                .add(Attributes.MAX_HEALTH, 28.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.26D)
                .add(Attributes.ATTACK_DAMAGE, 3.0D)
                .add(Attributes.ARMOR, 3.0D)
                .add(Attributes.FOLLOW_RANGE, 48.0D);
    }

    // ------------------------------------------------------------------ 同步状态

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        this.getEntityData().define(DATA_ABILITY, (byte) EliteAbility.NONE.ordinal());
        this.getEntityData().define(DATA_ABILITY_TICK, -1);
    }

    @Override
    public EliteAbility getAbility() {
        return EliteAbility.byId(this.getEntityData().get(DATA_ABILITY));
    }

    @Override
    public int getAbilityTick() {
        return this.getEntityData().get(DATA_ABILITY_TICK);
    }

    @Override
    public void setAbility(EliteAbility ability, int tick) {
        this.getEntityData().set(DATA_ABILITY, (byte) ability.ordinal());
        this.getEntityData().set(DATA_ABILITY_TICK, tick);
    }

    // ------------------------------------------------------------------ 技能推进

    @Override
    protected void customServerAiStep() {
        super.customServerAiStep();
        if (this.level() instanceof ServerLevel) {
            if (this.driver == null) {
                this.driver = new EliteAbilityDriver(this, this, new MarksmanHooks());
            }
            this.driver.tick();
            this.spawnWindupParticles();
        }
    }

    private final class MarksmanHooks implements EliteAbilityDriver.Hooks {

        @Override
        public EliteAbility ability() {
            return EliteAbility.BONE_LOCK;
        }

        @Override
        public int cooldownTicks() {
            return Config.AI_MARKSMAN_LOCK_COOLDOWN.get();
        }

        /**
         * 起手条件：目标在 6~26 格内。
         *
         * <p>比原版弓的 24 格稍远一点：这是精英的「叫杀」手段，贴脸时反而不该放
         * （那种距离该用重箭 / 近身乱射，而不是一条必中弹道）。</p>
         */
        @Override
        public boolean canStart() {
            return EliteMob.hasTargetInRange(MarksmanSkeleton.this, 6.0D, 26.0D);
        }

        @Override
        public void onStart() {
            MarksmanSkeleton.this.playSound(SoundEvents.SKELETON_SHOOT, 1.0F, 0.6F);
        }

        @Override
        public void onImpact() {
            MarksmanSkeleton.this.fireBoneLock();
        }
    }

    /**
     * 射出一发必中骨矢。
     *
     * <p>转向、速度、寿命全部走 Config，伤害在 {@link BoneLockArrow} 里按目标最大血量算
     * —— 这里只负责「把箭放出去」。</p>
     */
    private void fireBoneLock() {
        LivingEntity target = this.getTarget();
        if (!(this.level() instanceof ServerLevel level) || target == null || !target.isAlive()) {
            return;
        }
        BoneLockArrow.launch(level, this, target,
                Config.AI_MARKSMAN_LOCK_SPEED.get().floatValue(),
                Config.AI_MARKSMAN_LOCK_TURN.get(),
                Config.AI_MARKSMAN_LOCK_LIFE.get());
    }

    /**
     * 前摇粒子：每 {@value #WINDUP_PARTICLE_INTERVAL} tick 在眼眶与骨弓上各烧一簇灵魂火。
     *
     * <p>命中 tick 之后不再喷 —— 那时候箭已经在路上了。释放瞬间的粒子由骨矢自己负责
     * （{@code BoneLockArrow#spawnMuzzleParticles}），两处特效才各自落在真实的位置上。</p>
     */
    private void spawnWindupParticles() {
        if (this.getAbility() != EliteAbility.BONE_LOCK) {
            return;
        }
        int tick = this.getAbilityTick();
        if (tick < 0 || tick >= EliteAbility.BONE_LOCK.getImpactTick()
                || tick % WINDUP_PARTICLE_INTERVAL != 0) {
            return;
        }
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        // 眼眶：抬一点点，免得粒子糊在颈椎上
        level.sendParticles(WINDUP_PARTICLE, this.getX(), this.getEyeY() + 0.05D, this.getZ(),
                2, 0.12D, 0.08D, 0.12D, 0.0D);
        // 骨弓：主手前方 —— 弓是模型里的一根骨头，只能按手的位置近似
        Vec3 bow = this.bowPosition();
        level.sendParticles(WINDUP_PARTICLE, bow.x, bow.y, bow.z, 3, 0.15D, 0.15D, 0.15D, 0.01D);
    }

    /** 骨弓在世界里的近似位置：胸口高度往前 0.7 格。 */
    private Vec3 bowPosition() {
        Vec3 facing = Vec3.directionFromRotation(this.getXRot(), this.getYRot());
        return this.position().add(0.0D, 1.15D, 0.0D).add(facing.scale(0.7D));
    }

    // ------------------------------------------------------------------ GeckoLib
    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        // 顺序有意义：后注册的控制器在后一帧写入同一根骨头时覆盖前一个。
        // 施法期间把 movement 停掉（骨矢锁定的剪辑自己管住 root 和腿），
        // 拉弓期间不停 —— 原版弓 Goal 会边走边拉，腿得留给行走控制器。
        controllers.add(new AnimationController<>(this, "movement", 3, MarksmanSkeleton::movementAnimation));
        controllers.add(new AnimationController<>(this, "cast", 0, MarksmanSkeleton::castAnimation));
    }

    private static PlayState movementAnimation(AnimationState<MarksmanSkeleton> state) {
        if (state.getAnimatable().getAbility() == EliteAbility.BONE_LOCK) {
            return PlayState.STOP;
        }
        state.setControllerSpeed(Mth.clamp(0.6F + 0.9F * state.getLimbSwingAmount(), 0.6F, 2.0F));
        return state.setAndContinue(state.isMoving()
                ? RawAnimation.begin().thenLoop(ANIM_WALK)
                : RawAnimation.begin().thenLoop(ANIM_IDLE));
    }

    /**
     * 施法 / 射击动作控制器。
     *
     * <p>技能优先：骨矢锁定期间哪怕弓还拉着，也只播锁定剪辑 —— 前摇姿态本身就是举弓，
     * 两个剪辑叠着播会出现两条胳膊。</p>
     *
     * <p>没有技能时，拉弓走原版同步标志（{@code isUsingItem()} + 主手弓），
     * 和 {@code SoldierZombie} 的 action 控制器是同一套写法，不需要自定义同步字段。</p>
     */
    private static PlayState castAnimation(AnimationState<MarksmanSkeleton> state) {
        MarksmanSkeleton mob = state.getAnimatable();
        if (mob.getAbility() == EliteAbility.BONE_LOCK) {
            return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_LOCK));
        }
        // 拉弓走原版同步标志，不需要自定义字段
        if (mob.isUsingItem() && mob.getMainHandItem().is(Items.BOW)) {
            return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_SHOOT));
        }
        return PlayState.STOP;
    }

    // ------------------------------------------------------------------ AI

    /**
     * 全部重写：不要原版的「怕阳光 / 躲狼」，改成远程站位 + 弓 + 偶尔重箭。
     * 技能起手由 {@code MarksmanHooks#canStart} 管，这里只负责走位和普通射击。
     */
    @Override
    protected void registerGoals() {
        // 精英重箭：同一段逻辑，概率与伤害高一档（普通骷髅由 event/MobAiEnhanced 挂上）
        this.goalSelector.addGoal(1, new GiantArrowGoal(this, 6.0D, 32.0D,
                Config.AI_MARKSMAN_GIANT_CHANCE.get().floatValue(),
                Config.AI_MARKSMAN_GIANT_DAMAGE.get().floatValue(),
                Config.AI_GIANT_ARROW_SPEED.get().floatValue(), 3,
                Config.AI_GIANT_ARROW_TURN.get(), Config.AI_SKELETON_GIANT_COOLDOWN.get(),
                Config.AI_GIANT_ARROW_WINDUP.get(), Config.AI_GIANT_ARROW_LIFE.get()));
        this.goalSelector.addGoal(2, new KeepDistanceGoal(this, 1.0D, 7.0D, 18.0D));
        this.goalSelector.addGoal(4, new RangedBowAttackGoal<>(this, 1.0D, 20, 24.0F));
        this.goalSelector.addGoal(7, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.goalSelector.addGoal(8, new LookAtPlayerGoal(this, Player.class, 8.0F));
        this.goalSelector.addGoal(8, new RandomLookAroundGoal(this));
        this.targetSelector.addGoal(1, new AllySafeHurtByTargetGoal(this));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
        this.targetSelector.addGoal(3, new NearestAttackableTargetGoal<>(this, IronGolem.class, true));
    }

    /**
     * 父类是 AbstractSkeleton 不是 Skeleton，默认装备槽是空的，弓得自己发。
     *
     * <p>这把弓是<b>给 AI 用的</b>：{@code RangedBowAttackGoal} 靠它判断能不能射击，
     * 玩家看到的弓在骨骼树里（{@code bow}）。别想着把它去掉。</p>
     */
    @Override
    protected void populateDefaultEquipmentSlots(RandomSource random, DifficultyInstance difficulty) {
        this.setItemSlot(EquipmentSlot.MAINHAND, new ItemStack(Items.BOW));
    }

    /** 精英无视阳光。 */
    @Override
    protected boolean isSunBurnTick() {
        return false;
    }

    @Override
    protected SoundEvent getStepSound() {
        return SoundEvents.SKELETON_STEP;
    }
}
