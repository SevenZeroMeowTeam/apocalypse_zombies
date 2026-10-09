package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.entity.ai.AllySafeHurtByTargetGoal;
import com.apocalypse.zombies.entity.ai.SightFiring;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.tags.TagKey;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.goal.RangedBowAttackGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.item.PrimedTnt;
import net.minecraft.world.entity.SpawnGroupData;
import net.minecraft.world.entity.monster.RangedAttackMob;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.phys.Vec3;

import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

import javax.annotation.Nullable;

import java.util.EnumSet;

/**
 * 残兵 —— 二战军装僵尸士兵（变种僵尸）。
 *
 * <p>形象取自参考图 {@code E:\Administrator\Pictures\R-C-1.jpg}：三只穿军装、戴盔、
 * 眼窝发光的士兵僵尸。几何与贴图由 {@code tools/soldier_v2.py} 生成（{@code art/soldier/}），
 * 动画由 {@code tools/soldier_anim.py} 生成，两侧都带自校验。</p>
 *
 * <p><b>两种兵，各管一门</b>（变种决定贴图、主手物品、能用的技能，三条走同一个开关
 * {@link #getVariant()}）：</p>
 * <ul>
 *   <li><b>弓手</b>（{@link #VARIANT_ARCHER}）—— 直接用原版 {@link RangedBowAttackGoal}
 *       + {@link RangedAttackMob}。主手挂一把 {@code Items.BOW}，但渲染器**故意不挂物品层**：
 *       可见的弓是建模进骨骼树的（{@code bow / bow_limb_up / bow_limb_down / bow_string_up /
 *       bow_string_down}），好处是弓弦能跟着拉弓动作真的拉成 V 形；主手那把原版弓只用来让
 *       原版目标条件 {@code isHoldingBow()} 成立，玩家看不到它。
 *       拉弓动画由 {@code isUsingItem()} 驱动 —— 这个标志在原版实体数据里是同步的，
 *       不用自己加网络字段。</li>
 *   <li><b>爆破兵</b>（{@link #VARIANT_SAPPER}）—— {@link ThrowTntGoal}：1.5 秒的抡臂出手，
 *       第 {@link #THROW_RELEASE_TICK} tick 生成一个原版 {@link PrimedTnt}（引信
 *       {@link #TNT_FUSE} tick，约 2.5 秒），让玩家有躲的余地。手里那包<b>看得见</b>的 TNT
 *       同样是骨骼树里的 {@code tnt / tnt_fuse}（引信画成亮芯），挂在<b>左手</b> ——
 *       {@code throw_tnt} 剪辑抡的就是左臂；起手到出手之间由服务端在引信位置喷火星与烟，
 *       把「点燃」这件事做成看得见的过程，而不是出手瞬间凭空掉出一颗 TNT。</li>
 * </ul>
 *
 * <p>两个变种的装备在渲染时按变种显隐（见 {@code SoldierGeoModel#setCustomAnimations}），
 * 弓手不会背着 TNT、爆破兵也不会举着弓。</p>
 *
 * <p>动画剪辑名与 {@code assets/apocalypse_zombies/animations/soldier_zombie.animation.json}
 * 双向对应：改名字必须两边一起改，否则渲染时静默退回 rest 姿态。</p>
 */
public class SoldierZombie extends Zombie implements GeoEntity, RangedAttackMob, SightFiring {

    // ------------------------------------------------------------ 动画剪辑名（与动画 JSON 一一对应）
    public static final String ANIM_IDLE = "idle";
    public static final String ANIM_WALK = "walk";
    public static final String ANIM_SHOOT = "shoot";
    public static final String ANIM_THROW = "throw_tnt";

    /** 贴图变种：对应参考图里三只兵的不同装具（0 背箭袋 / 1 背工兵铲）。 */
    public static final byte VARIANT_ARCHER = 0;
    public static final byte VARIANT_SAPPER = 1;

    /** 存盘键：变种落盘用（见 addAdditionalSaveData）。 */
    private static final String VARIANT_KEY = "AzVariant";

    /** 投掷剪辑 1.5s；0.62s 出手 ⇒ 第 13 tick 生成 TNT（留 1 tick 给状态同步的延迟）。 */
    public static final int THROW_RELEASE_TICK = 13;
    /** 整个投掷动作的占据时长（= 剪辑时长 1.5s），这期间移动/floating 一律让位。 */
    public static final int THROW_CLIP_TICKS = 30;
    /** 两次投掷之间的间隔。 */
    public static final int THROW_COOLDOWN_TICKS = 130;
    /** TNT 引信：2.5 秒，够玩家跑开。 */
    public static final int TNT_FUSE = 50;
    /** 投掷射程带：近了砸自己、远了白扔。 */
    public static final double THROW_MIN_RANGE = 4.0D;
    public static final double THROW_MAX_RANGE = 14.0D;

    /**
     * 弓的射程（格）—— {@code RangedBowAttackGoal} 的 {@code attackRadiusSqr} 入参。
     *
     * <p>写成常量而不是把 {@code 15.0F} 散在调用处：{@link #sightFiringRange()} 必须与它
     * <b>同源</b>，两处各写一个字面量迟早会漂开（那是「看得见却报不出射程、又退回走不到就不打」的老病）。</p>
     */
    private static final double BOW_RANGE = 15.0D;

    /**
     * 弓手贴到这个距离以内就把 MOVE/LOOK 交给近战出口（格）。
     *
     * <p>弓 Goal 的「站定 + strafe」区间下限是 {@code sqrt(0.25) * 15 ≈ 7.5} 格，那时 MOVE 归它，
     * 近战出口根本抢不到旗子；贴脸的目标它又只能原地乱射。所以在这个距离上主动交旗。</p>
     */
    private static final double BOW_MELEE_HANDOFF = 3.5D;
    /** MC 里抛体的有效重力（0.04 是标称值，加一点补偿空气阻力）。 */
    private static final double THROW_GRAVITY = 0.05D;

    private static final byte ACTION_NONE = 0;
    private static final byte ACTION_THROW = 1;

    private static final EntityDataAccessor<Byte> DATA_ACTION =
            SynchedEntityData.defineId(SoldierZombie.class, EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Byte> DATA_VARIANT =
            SynchedEntityData.defineId(SoldierZombie.class, EntityDataSerializers.BYTE);

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    public SoldierZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
        this.xpReward = 12;
        // 主手挂一件"看不见的"原版物品：只服务原版 AI 的持物判定，渲染器不画物品层。
        // 拿什么由变种决定（见 applyVariantEquipment），这里先按默认变种给上。
        this.applyVariantEquipment();
        this.setDropChance(EquipmentSlot.MAINHAND, 0.085F);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return Zombie.createAttributes()
                .add(Attributes.MAX_HEALTH, 26.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.24D)
                .add(Attributes.ATTACK_DAMAGE, 4.0D)
                .add(Attributes.ARMOR, 3.0D)
                .add(Attributes.FOLLOW_RANGE, 40.0D);
    }

    @Override
    protected void registerGoals() {
        super.registerGoals();
        // 投掷排在近战之前：不这样，近战 Goal 只要贴脸就永远压着投掷不放。
        // 两个远程 Goal 各自只对一种兵生效 —— 原来它们不判变种，于是弓手也在丢 TNT、
        // 爆破兵也在射箭，和设计里的两种兵完全对不上。
        this.goalSelector.addGoal(1, new ThrowTntGoal());
        // 弓手也必须是 1 号位，理由和投掷同源，但更隐蔽：{@code Zombie.registerGoals()} 已经在
        // 2 号位挂了一个原版近战 {@code ZombieAttackGoal}，而 GoalSelector 里「同优先级不能抢占」
        // （WrappedGoal.canBeReplacedBy 要求 challenger 的号更小），所以弓 Goal 挂 2 就等于
        // 和原版近战抢 MOVE/LOOK：近战的 navigation 一空就把旗子让出去、弓一开火近战又抢回来。
        // 实测就是这样：弓手在 7.5~13 格之间以恒定速度来回踱步（弓 Goal 的 strafe 阈值
        // 0.25/0.75 × 15² 正好是 7.5 / 13），16 秒只放 7 箭、靶子掉 0 血 —— 「走路不对 + 不打人」。
        // 放到 1 号位后弓 Goal 能压住原版近战，离开 3.5 格才交旗给近战出口。
        this.goalSelector.addGoal(1, new RangedBowAttackGoal<SoldierZombie>(this, 1.0D, 20, (float) BOW_RANGE) {
            @Override
            public boolean canUse() {
                LivingEntity target = SoldierZombie.this.getTarget();
                return SoldierZombie.this.getVariant() == VARIANT_ARCHER
                        && target != null
                        && SoldierZombie.this.distanceToSqr(target) > BOW_MELEE_HANDOFF * BOW_MELEE_HANDOFF
                        && super.canUse();
            }

            // 必须一起写：原版 canContinueToUse 是 (canUse() || !navigation.isDone()) && 手持弓，
            // 只看「目标还在」就返回 true —— 贴脸之后 MOVE 会被它钉死，近战出口永远等不到旗子。
            @Override
            public boolean canContinueToUse() {
                LivingEntity target = SoldierZombie.this.getTarget();
                return SoldierZombie.this.getVariant() == VARIANT_ARCHER
                        && target != null
                        && SoldierZombie.this.distanceToSqr(target) > BOW_MELEE_HANDOFF * BOW_MELEE_HANDOFF
                        && super.canContinueToUse();
            }
        });
        this.goalSelector.addGoal(3, new MeleeAttackGoal(this, 1.0D, false));
        this.goalSelector.addGoal(7, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.goalSelector.addGoal(8, new LookAtPlayerGoal(this, Player.class, 12.0F));
        this.goalSelector.addGoal(8, new RandomLookAroundGoal(this));
        this.targetSelector.addGoal(1, new AllySafeHurtByTargetGoal(this));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    /**
     * 「看得见就能打」的射程上限（格）—— 见 {@link SightFiring}。
     *
     * <p>残兵是远程兵种（弓 / TNT），但这一条一直只有 {@code MarksmanSkeleton} 实现了，
     * 于是 {@link com.apocalypse.zombies.entity.ai.PreyJudge} 对残兵退回默认判据「走得到」：
     * 玩家躲到塔顶、船上、柱顶、栏杆后面这类<b>看得见却走不到</b>的地方，残兵就锁不上、
     * 站着发呆 —— 玩家那边看到的就是「怪物不会攻击」（死过一次躲起来之后尤其明显）。</p>
     *
     * <p>取最远那件武器，即弓的 {@link #BOW_RANGE}（15 格 &gt; TNT 的 {@link #THROW_MAX_RANGE} 14）。
     * 报小了会对着够得着的目标发呆，报大了会锁上一个真打不到的目标 —— 两件武器的射程入参都从
     * 常量来，改武器射程时这一条自动跟随。</p>
     */
    @Override
    public double sightFiringRange() {
        return Math.max(BOW_RANGE, THROW_MAX_RANGE);
    }

    /** 参考图里这三位大白天站在院子里 ⇒ 不烧。 */
    @Override
    public boolean isSunSensitive() {
        return false;
    }

    /**
     * 日光伤害的第二道门，一起关掉。
     *
     * <p>1.20.1 里「会不会被太阳点着」要过 {@code isSunSensitive()} 与 {@code isSunBurnTick()} 两道判定，
     * 而哪一道在 {@code Zombie#aiStep} 里起决定作用、是否被父类提前短路，光看字节码不足以断定；
     * 两个都返回 false，就等于把入口全部封死，行为不依赖对某个版本实现的猜测。</p>
     */
    @Override
    protected boolean isSunBurnTick() {
        return false;
    }

    /**
     * 爆炸免伤：写成有名字的常量而不是内联 {@code DamageTypeTags.IS_EXPLOSION}。
     *
     * <p>一是「免哪一类伤害」这个决定只出现在一处，将来要改成「只免疫自己丢的 TNT」只改这里；
     * 二是出货门禁要能钉在一个属于本模组的名字上 —— 生产 jar 会被 SRG 重映射，
     * 原版字段名在 jar 里搜不到，拿它当证据会永远判失败。</p>
     */
    private static final TagKey<DamageType> EXPLOSION_IMMUNITY = DamageTypeTags.IS_EXPLOSION;

    /**
     * 免疫爆炸伤害。
     *
     * <p>它自己丢的 TNT 就落在脚边（{@link ThrowTntGoal} 按抛物线解初速往目标脚下扔）—— 不做这道
     * 免伤，投掷型僵尸会被自己的手雷炸死，玩家只要站在旁边看戏就行。走
     * {@code isInvulnerableTo} 而不是覆写 {@code hurt}：这一层在伤害计算之前就被
     * {@code LivingEntity#hurt} 查过，击退、着火、仇恨全都一并免掉，也不必再判「是不是我丢的那颗」。
     * 父类判定必须保留 —— 无敌帧、抗火之类都长在这里。</p>
     */
    @Override
    public boolean isInvulnerableTo(DamageSource source) {
        return super.isInvulnerableTo(source) || source.is(EXPLOSION_IMMUNITY);
    }

    // ------------------------------------------------------------ 投掷状态（同步给客户端驱动动画）
    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        this.entityData.define(DATA_ACTION, ACTION_NONE);
        this.entityData.define(DATA_VARIANT, VARIANT_ARCHER);
    }

    /**
     * 变种号必须在服务端抽签后再同步：实体构造函数两侧都会跑，各抽一次会得到两张不同的皮。
     */
    @Override
    public SpawnGroupData finalizeSpawn(ServerLevelAccessor level, DifficultyInstance difficulty,
                                        MobSpawnType reason, @Nullable SpawnGroupData spawnData,
                                        @Nullable CompoundTag dataTag) {
        SpawnGroupData data = super.finalizeSpawn(level, difficulty, reason, spawnData, dataTag);
        this.setVariant(this.getRandom().nextBoolean() ? VARIANT_SAPPER : VARIANT_ARCHER);
        return data;
    }

    public byte getVariant() {
        return this.entityData.get(DATA_VARIANT);
    }

    private void setVariant(byte variant) {
        this.entityData.set(DATA_VARIANT, variant);
        this.applyVariantEquipment();
    }

    /**
     * 变种决定主手拿什么。这条链顺手把两个远程 Goal 各自锁在一种兵身上：原版
     * {@code RangedBowAttackGoal} 起手要求手里是弓，爆破兵手里是 TNT，自然不再射箭。
     */
    private void applyVariantEquipment() {
        this.setItemSlot(EquipmentSlot.MAINHAND,
                new ItemStack(this.getVariant() == VARIANT_SAPPER ? Items.TNT : Items.BOW));
    }

    /**
     * 变种必须存盘。
     *
     * <p>{@code defineSynchedData} 给的默认值是弓手，而随机抽签只发生在 {@code finalizeSpawn}
     * 那一刻 —— 区块卸载重载后，存盘里没有变种的爆破兵会全部退回弓手（贴图、装备、技能一起
     * 变回另一种兵）。这是「同一只怪前后不是一只兵」的根因，不是显示问题。</p>
     */
    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putByte(VARIANT_KEY, this.getVariant());
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        if (tag.contains(VARIANT_KEY)) {
            this.setVariant(tag.getByte(VARIANT_KEY));
        }
    }

    public byte getAction() {
        return this.entityData.get(DATA_ACTION);
    }

    private void setAction(byte action) {
        this.entityData.set(DATA_ACTION, action);
    }

    // ------------------------------------------------------------ 射箭
    @Override
    public void performRangedAttack(LivingEntity target, float velocity) {
        Arrow arrow = new Arrow(this.level(), this);
        double dx = target.getX() - this.getX();
        double dy = target.getEyeY() - arrow.getY();
        double dz = target.getZ() - this.getZ();
        double horizontal = Math.sqrt(dx * dx + dz * dz);
        // 抬高一点抵消重力：骷髅系同款手感（1.6 初速 + 14 的散布上限）
        arrow.shoot(dx, dy + horizontal * 0.2D, dz, 1.6F, (float) (14 - this.level().getDifficulty().getId() * 4));
        arrow.setBaseDamage(3.0D);
        this.playSound(SoundEvents.SKELETON_SHOOT, 1.0F, 1.0F / (this.getRandom().nextFloat() * 0.4F + 0.8F));
        this.level().addFreshEntity(arrow);
    }

    @Override
    public SoundEvent getAmbientSound() {
        return SoundEvents.ZOMBIE_AMBIENT;
    }

    @Override
    protected SoundEvent getHurtSound(net.minecraft.world.damagesource.DamageSource source) {
        return SoundEvents.ZOMBIE_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.ZOMBIE_DEATH;
    }

    // ------------------------------------------------------------ GeckoLib
    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        // 顺序有意义：后注册的控制器在后一帧写入同一根骨头时覆盖前一个。
        // 投掷期间把 movement 停掉（投掷剪辑自己管住 root 和腿），
        // 拉弓期间不停 —— 原版弓 Goal 会边走边拉，腿得留给行走控制器。
        controllers.add(new AnimationController<>(this, "movement", 3, SoldierZombie::movementAnimation));
        controllers.add(new AnimationController<>(this, "action", 0, SoldierZombie::actionAnimation));
    }

    private static PlayState movementAnimation(AnimationState<SoldierZombie> state) {
        if (state.getAnimatable().getAction() == ACTION_THROW) {
            return PlayState.STOP;
        }
        state.setControllerSpeed(Mth.clamp(0.6F + 0.9F * state.getLimbSwingAmount(), 0.6F, 2.0F));
        return state.setAndContinue(state.isMoving()
                ? RawAnimation.begin().thenLoop(ANIM_WALK)
                : RawAnimation.begin().thenLoop(ANIM_IDLE));
    }

    private static PlayState actionAnimation(AnimationState<SoldierZombie> state) {
        SoldierZombie mob = state.getAnimatable();
        if (mob.getAction() == ACTION_THROW) {
            return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_THROW));
        }
        // 拉弓走原版同步标志，不需要自定义字段
        if (mob.isUsingItem() && mob.getMainHandItem().is(Items.BOW)) {
            return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_SHOOT));
        }
        return PlayState.STOP;
    }

    // ------------------------------------------------------------ 投掷点燃的 TNT
    /**
     * 抡臂投掷：蓄力 → 出手（生成 {@link PrimedTnt}）→ 收招。
     *
     * <p>出手点必须和动画剪辑里 0.62s 那一帧对上，所以用 tick 计数而不是"随时丢"；
     * 生成时按抛物线解初速，让 TNT 落在目标脚下附近。</p>
     */
    private class ThrowTntGoal extends Goal {

        private int tick;
        private int cooldown;
        private LivingEntity target;

        ThrowTntGoal() {
            // 接管移动 = 投掷期间站定，不追不跑
            this.setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
        }

        @Override
        public boolean canUse() {
            // 只有爆破兵有 TNT；弓手走 RangedBowAttackGoal。
            if (SoldierZombie.this.getVariant() != VARIANT_SAPPER) {
                return false;
            }
            if (this.cooldown > 0) {
                this.cooldown--;
                return false;
            }
            LivingEntity candidate = SoldierZombie.this.getTarget();
            if (candidate == null || !candidate.isAlive()) {
                return false;
            }
            if (SoldierZombie.this.getAction() != ACTION_NONE) {
                return false;
            }
            double distance = SoldierZombie.this.distanceTo(candidate);
            return distance >= THROW_MIN_RANGE && distance <= THROW_MAX_RANGE;
        }

        @Override
        public boolean canContinueToUse() {
            return this.target != null && this.target.isAlive() && this.tick < THROW_CLIP_TICKS;
        }

        @Override
        public void start() {
            this.target = SoldierZombie.this.getTarget();
            this.tick = 0;
            SoldierZombie.this.setAction(ACTION_THROW);
            SoldierZombie.this.setAggressive(true);
            // 点燃那一下要听得见：原版打火石的声音就是「点引信」这件事的音效
            SoldierZombie.this.playSound(SoundEvents.FLINTANDSTEEL_USE, 0.9F, 1.0F);
        }

        @Override
        public void stop() {
            SoldierZombie.this.setAction(ACTION_NONE);
            SoldierZombie.this.setAggressive(false);
            this.cooldown = THROW_COOLDOWN_TICKS;
            this.target = null;
        }

        @Override
        public void tick() {
            if (this.target != null) {
                SoldierZombie.this.getLookControl().setLookAt(this.target, 30.0F, 30.0F);
            }
            this.fuseParticles();
            if (this.tick++ == THROW_RELEASE_TICK) {
                this.release();
            }
        }

        /**
         * 引信火星：从起手就开始冒，出手前加密。
         *
         * <p>位置是<b>近似</b>的：拿的是静置姿态下左手的位置（左偏 0.42 格、脚上 0.86 格），
         * 不是被动画驱动的那根手骨的世界坐标 —— 动画只在客户端算，服务端不知道这一帧的姿势。
         * 火星是粒子，偏几像素看不出来；而把姿势同步回服务端只为放几个粒子，代价不成比例。</p>
         */
        private void fuseParticles() {
            if (!(SoldierZombie.this.level() instanceof net.minecraft.server.level.ServerLevel level)) {
                return;
            }
            float yaw = SoldierZombie.this.yBodyRot * ((float) Math.PI / 180.0F);
            double leftX = -Math.cos(yaw) * 0.42D;
            double leftZ = -Math.sin(yaw) * 0.42D;
            double x = SoldierZombie.this.getX() + leftX;
            double y = SoldierZombie.this.getY() + 0.86D;
            double z = SoldierZombie.this.getZ() + leftZ;
            double heat = Math.min(1.0D, this.tick / (double) THROW_RELEASE_TICK);
            level.sendParticles(net.minecraft.core.particles.ParticleTypes.SMOKE,
                    x, y, z, heat > 0.55D ? 2 : 1, 0.03D, 0.03D, 0.03D, 0.004D);
            if (this.tick % 3 == 0) {
                level.sendParticles(net.minecraft.core.particles.ParticleTypes.FLAME,
                        x, y, z, 1, 0.015D, 0.015D, 0.015D, 0.0D);
            }
        }

        private void release() {
            if (!(SoldierZombie.this.level() instanceof net.minecraft.server.level.ServerLevel level)) {
                return;
            }
            if (this.target == null) {
                return;
            }
            Vec3 look = SoldierZombie.this.getViewVector(1.0F);
            double sx = SoldierZombie.this.getX() + look.x * 0.6D;
            double sy = SoldierZombie.this.getEyeY() - 0.15D;
            double sz = SoldierZombie.this.getZ() + look.z * 0.6D;

            PrimedTnt tnt = new PrimedTnt(level, sx, sy, sz, SoldierZombie.this);
            tnt.setFuse(TNT_FUSE);

            // 抛物线解：给定飞行时间 T，横竖两个分量各自配平，重力项补 0.5·g·T
            double dx = this.target.getX() - sx;
            double dz = this.target.getZ() - sz;
            double dy = this.target.getEyeY() - 0.4D - sy;
            double distance = Math.sqrt(dx * dx + dz * dz);
            double flight = Mth.clamp(12.0D + distance * 1.1D, 12.0D, 34.0D);
            tnt.setDeltaMovement(dx / flight,
                    dy / flight + 0.5D * THROW_GRAVITY * flight,
                    dz / flight);
            level.addFreshEntity(tnt);
            SoldierZombie.this.playSound(SoundEvents.TNT_PRIMED, 1.0F, 1.0F);
        }
    }
}
