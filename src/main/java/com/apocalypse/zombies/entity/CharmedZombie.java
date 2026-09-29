package com.apocalypse.zombies.entity;

import javax.annotation.Nullable;

import java.util.UUID;

import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;

/**
 * 魅惑召奬 —— 被美女僵尸「策反」过来的僵尸，三套技能的召唤物都是它。
 *
 * <p>它跟普通僵尸的区别只有三条：目标表里没有玩家（只打僵尸）、有存活时限（到点自己散掉）、
 * 带着一个 {@link Variant} 决定贴图和入场 buff。这样三套技能不必各自造一种召唤物，
 * 「召奬」这件事就只有一个出口，调平衡也只改一个地方。</p>
 *
 * <p>存活时限是必须的：三套技能都带召唤，不设时限就是指数级的麻烦，
 * 玩家会被自己没参与过的战斗淹掉。</p>
 */
public class CharmedZombie extends Zombie {

    /** 召奬的三种成色，决定渲染贴图和入场 buff。 */
    public enum Variant {
        /** 亡语魅惑策反来的普通召奬：一眼认得出是被夺过来的僵尸。 */
        CHARMED,
        /** 血月选妃带出来的小队：入场即带速度 + 力量。 */
        CONSORT,
        /** 摄魂尖啸抽出来的幽灵：飘着灵魂粒子，行动更飘。 */
        SPECTER;

        private static final Variant[] BY_ID = values();

        /** 读网络同步来的原始字节；越界退回 {@link #CHARMED}，不让客户端因为脏数据崩。 */
        public static Variant byId(int id) {
            if (id < 0 || id >= BY_ID.length) {
                return CHARMED;
            }
            return BY_ID[id];
        }
    }

    private static final EntityDataAccessor<Byte> DATA_VARIANT =
            SynchedEntityData.defineId(CharmedZombie.class, EntityDataSerializers.BYTE);

    /** 入场时自带的增益时长：比任何一套技能的持续时间都长，免得召奬中途掉 buff。 */
    private static final int ENTRY_BUFF_DURATION = 1200;

    /** 默认存活 tick；{@link #arm} 会按技能覆盖它。 */
    private static final int DEFAULT_LIFETIME = 200;

    /** 剩余存活 tick。到 0 就散。 */
    private int lifetime = DEFAULT_LIFETIME;

    /** 「迅捷」召奬的移速修饰符 id —— 判断某只是不是迅捷，就查这个修饰符在不在。 */
    private static final UUID SWIFT_SPEED_ID =
            UUID.fromString("3c9f1d27-6b4e-4a58-8e2f-7d1a4c0b9e33");

    /** 连续静止多久之后才开始回血（tick）。 */
    private static final int IDLE_REGEN_DELAY = 40;

    /** 静止回血的节奏：每多少 tick 回一格。 */
    private static final int IDLE_REGEN_INTERVAL = 45;

    /** 静止回血每次回多少。 */
    private static final float IDLE_REGEN_AMOUNT = 1.0F;

    /** 已经连续静止了多少 tick。一旦动起来立刻归零。 */
    private int idleTicks;

    public CharmedZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
        // 召奬身上没有经验价值，也不该捡东西或者喊援军
        this.xpReward = 0;
        this.setCanPickUpLoot(false);
        // 不喊原版那套「被打就叫援军」：叫来的援军是普通僵尸，会跟着一起打玩家，
        // 跟「只打僵尸」的设定正好相反
        if (this.getAttribute(Attributes.SPAWN_REINFORCEMENTS_CHANCE) != null) {
            this.getAttribute(Attributes.SPAWN_REINFORCEMENTS_CHANCE).setBaseValue(0.0D);
        }

        // 撤掉原版僵尸那套「打玩家 / 村民 / 铁傀儡」的目标表，只留「打其他僵尸」。
        // 把自己人和女主人从目标里排掉：配枪之后，误伤会从「挠一下」变成「点射」。
        this.targetSelector.removeAllGoals(goal -> true);
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, Zombie.class, true,
                target -> !(target instanceof CharmedZombie) && !(target instanceof BrideZombie)));
    }

    /**
     * 手里有枪就开枪，而不是凑上去挠。
     *
     * <p>挂在 <b>1 号位</b>（原版僵尸的近战在 2 号位）：远程 Goal 一旦占住 MOVE 标记，
     * 近战那个就抢不到执行权 —— 这就是「发射而不是近战」在引擎层的实现方式。枪打空了、
     * 或者没有视线时它自己失效，近战自然接手，所以不用去禁用原版那套。</p>
     */
    @Override
    protected void registerGoals() {
        super.registerGoals();
        this.goalSelector.addGoal(1, new GunAttackGoal(this));
    }

    public static AttributeSupplier.Builder createAttributes() {
        return Zombie.createAttributes();
    }

    /**
     * 上线配置：存活多久、是哪种成色、继承谁的目标、带什么入场 buff。
     * 三套技能的召唤路径都只调这一个方法。
     */
    public void arm(int lifetimeTicks, Variant variant, @Nullable LivingEntity target) {
        this.lifetime = Math.max(1, lifetimeTicks);
        this.setVariant(variant);
        if (target != null) {
            this.setTarget(target);
        }
        this.setPersistenceRequired();
        switch (variant) {
            case CONSORT -> {
                this.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SPEED, ENTRY_BUFF_DURATION, 0));
                this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_BOOST, ENTRY_BUFF_DURATION, 0));
            }
            case SPECTER -> {
                this.addEffect(new MobEffectInstance(MobEffects.SLOW_FALLING, ENTRY_BUFF_DURATION, 0));
                this.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SPEED, ENTRY_BUFF_DURATION, 0));
            }
            case CHARMED -> {
            }
        }
    }

    /**
     * 出生时抽到「迅捷」：把移速加成挂成永久修饰符。
     *
     * <p>用永久（而非临时）修饰符是有意的：召奬 {@code setPersistenceRequired()} 且不随距离消失，
     * 存档重载后如果移速加成丢了、而别的线索还在，就会出现「同一只兵前后速度不一样」。
     * 永久修饰符跟着实体一起存，行为一致。</p>
     */
    public void makeSwift(double bonus) {
        AttributeInstance speed = this.getAttribute(Attributes.MOVEMENT_SPEED);
        if (speed != null && speed.getModifier(SWIFT_SPEED_ID) == null) {
            speed.addPermanentModifier(new AttributeModifier(SWIFT_SPEED_ID, "bride_swift",
                    bonus, AttributeModifier.Operation.MULTIPLY_BASE));
        }
    }

    /** 是不是出生就抽到「迅捷」的那只。服务端判据，不需要额外的同步字段。 */
    public boolean isSwift() {
        AttributeInstance speed = this.getAttribute(Attributes.MOVEMENT_SPEED);
        return speed != null && speed.getModifier(SWIFT_SPEED_ID) != null;
    }

    // ------------------------------------------------------------------ 同步状态

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        this.getEntityData().define(DATA_VARIANT, (byte) Variant.CHARMED.ordinal());
    }

    public Variant getVariant() {
        return Variant.byId(this.getEntityData().get(DATA_VARIANT));
    }

    public void setVariant(Variant variant) {
        this.getEntityData().set(DATA_VARIANT, (byte) variant.ordinal());
    }

    public int getLifetime() {
        return this.lifetime;
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putInt("CharmedLifetime", this.lifetime);
        tag.putByte("CharmedVariant", (byte) this.getVariant().ordinal());
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        if (tag.contains("CharmedLifetime")) {
            this.lifetime = tag.getInt("CharmedLifetime");
        }
        this.setVariant(Variant.byId(tag.getByte("CharmedVariant")));
    }

    // ------------------------------------------------------------------ 生命周期

    @Override
    public void tick() {
        super.tick();
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        this.emitVariantParticles(level);
        if (!this.isAlive() || this.isRemoved()) {
            return;
        }
        this.tickIdleRegen(level);
        if (--this.lifetime <= 0) {
            this.dispel(level);
        }
    }

    /**
     * 静止时缓慢回血。
     *
     * <p>「静止」按水平位移判定，而不是「手上有没有目标」：召奬被击退、或者目标隔着一堵墙
     * 过不去时也会站着不动，那种时候让它回一点血正是想要的效果，所以判据取更朴素的「真的没在动」。</p>
     *
     * <p>先要连续静止 {@link #IDLE_REGEN_DELAY} tick 才起步，之后每 {@link #IDLE_REGEN_INTERVAL}
     * tick 回 {@link #IDLE_REGEN_AMOUNT} 格 —— 慢到打不赢一场遭遇战，只够让活下来的召奬慢慢补齐。</p>
     */
    private void tickIdleRegen(ServerLevel level) {
        boolean still = this.onGround()
                && !this.isInWater()
                && this.getDeltaMovement().horizontalDistanceSqr() < 1.0E-4D;
        if (!still) {
            this.idleTicks = 0;
            return;
        }
        if (++this.idleTicks < IDLE_REGEN_DELAY) {
            return;
        }
        if (this.getHealth() >= this.getMaxHealth() || this.tickCount % IDLE_REGEN_INTERVAL != 0) {
            return;
        }
        this.heal(IDLE_REGEN_AMOUNT);
        level.sendParticles(ParticleTypes.HEART,
                this.getX(), this.getY() + 1.4D, this.getZ(), 1, 0.2D, 0.1D, 0.2D, 0.0D);
    }

    /** 灵魂 / 爱心 / 绿星粒子：让三种召奬在贴图相同的地方也读得出来。 */
    private void emitVariantParticles(ServerLevel level) {
        // 迅捷的那只跑到哪儿都拖一串脚底火星：不用看着它出生，也能认出队伍里谁是快的
        if (this.isSwift() && this.tickCount % 10 == 0
                && this.getDeltaMovement().horizontalDistanceSqr() > 1.0E-4D) {
            level.sendParticles(ParticleTypes.CRIT,
                    this.getX(), this.getY() + 0.15D, this.getZ(), 1, 0.2D, 0.05D, 0.2D, 0.01D);
        }
        switch (this.getVariant()) {
            case SPECTER -> {
                if (this.tickCount % 5 == 0) {
                    level.sendParticles(ParticleTypes.SOUL, this.getX(), this.getY() + 1.0D, this.getZ(),
                            1, 0.18D, 0.30D, 0.18D, 0.01D);
                }
            }
            case CHARMED -> {
                if (this.tickCount % 40 == 0) {
                    level.sendParticles(ParticleTypes.HEART, this.getX(), this.getY() + 1.6D, this.getZ(),
                            1, 0.25D, 0.20D, 0.25D, 0.0D);
                }
            }
            case CONSORT -> {
                if (this.tickCount % 20 == 0) {
                    level.sendParticles(ParticleTypes.HAPPY_VILLAGER, this.getX(), this.getY() + 1.2D, this.getZ(),
                            2, 0.25D, 0.25D, 0.25D, 0.0D);
                }
            }
        }
    }

    /** 时限到了：散场粒子 + 轻声，不留尸体、不掉经验。 */
    private void dispel(ServerLevel level) {
        level.sendParticles(ParticleTypes.SOUL, this.getX(), this.getY() + 1.0D, this.getZ(),
                8, 0.3D, 0.5D, 0.3D, 0.02D);
        this.playSound(SoundEvents.ZOMBIE_DEATH, 0.6F, 1.5F);
        this.discard();
    }

    // ------------------------------------------------------------------ 行为约束

    /** 只打其他僵尸：玩家、别的召奬、女主人本体都不在攻击名单里。 */
    @Override
    public boolean canAttack(LivingEntity target) {
        if (target instanceof Player || target instanceof CharmedZombie || target instanceof BrideZombie) {
            return false;
        }
        return super.canAttack(target);
    }

    /** 召奬不该因为天亮烧死，也不该在水里变溺尸。 */
    @Override
    protected boolean isSunSensitive() {
        return false;
    }

    @Override
    protected boolean convertsInWater() {
        return false;
    }

    /** 只刷成年体：幼年体的尺寸和速度修饰符会跟入场 buff 打架。 */
    @Override
    public boolean isBaby() {
        return false;
    }

    @Override
    public void setBaby(boolean baby) {
        // 召奬恒为成年体
    }

    @Override
    public boolean removeWhenFarAway(double distance) {
        return false;
    }
}