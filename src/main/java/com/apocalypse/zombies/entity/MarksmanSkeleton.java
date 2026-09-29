package com.apocalypse.zombies.entity;

import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
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
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.ai.AllySafeHurtByTargetGoal;
import com.apocalypse.zombies.entity.ai.GiantArrowGoal;

/**
 * 骸骨射手 —— 远程压制。普通射击走原版弓，偶尔蓄一发穿透箭。
 *
 * <p>技能「穿透射击」：拉满 1.7 秒，命中瞬间射出穿透 3 层的暴击箭（基础伤害 6）。
 * 靠 {@link KeepDistanceGoal} 吊在 7~18 格外，不贴身。</p>
 *
 * <p>和僵尸系那三只分属不同继承链，所以施法状态自己持一份 {@code SynchedEntityData} 访问器
 * （{@code defineId} 按类分 ID 段，跨类复用会撞 ID），推进逻辑复用 {@link EliteAbilityDriver}。</p>
 */
public class MarksmanSkeleton extends AbstractSkeleton implements EliteMob {

    private static final EntityDataAccessor<Byte> DATA_ABILITY =
            SynchedEntityData.defineId(MarksmanSkeleton.class, EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Integer> DATA_ABILITY_TICK =
            SynchedEntityData.defineId(MarksmanSkeleton.class, EntityDataSerializers.INT);

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
        }
    }

    private final class MarksmanHooks implements EliteAbilityDriver.Hooks {

        @Override
        public EliteAbility ability() {
            return EliteAbility.SNIPE;
        }

        @Override
        public int cooldownTicks() {
            return 160;
        }

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
            MarksmanSkeleton.this.firePiercingShot();
        }
    }

    /** 穿透 3 层、必暴击的一箭。速度给高一点，弹道才够平直。 */
    private void firePiercingShot() {
        LivingEntity target = this.getTarget();
        if (target == null) {
            return;
        }
        Arrow arrow = new Arrow(this.level(), this);
        arrow.setPierceLevel((byte) 3);
        arrow.setBaseDamage(6.0D);
        arrow.setKnockback(2);
        arrow.setCritArrow(true);

        double dx = target.getX() - this.getX();
        double dy = target.getY(0.5D) - arrow.getY();
        double dz = target.getZ() - this.getZ();
        double horizontal = Math.sqrt(dx * dx + dz * dz);
        arrow.shoot(dx, dy + horizontal * 0.05D, dz, 3.0F, 0.5F);
        this.playSound(SoundEvents.ARROW_SHOOT, 1.6F, 0.6F);
        this.level().addFreshEntity(arrow);
    }

    // ------------------------------------------------------------------ AI

    /**
     * 全部重写：不要原版的「怕阳光 / 躲狼」，改成远程站位 + 弓 + 偶尔穿透箭。
     * 注意 {@link #canStart} 已经由技能自己管，这里只负责走位和普通射击。
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

    /** 父类是 AbstractSkeleton 不是 Skeleton，默认装备槽是空的，弓得自己发。 */
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
