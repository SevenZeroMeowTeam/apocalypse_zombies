package com.apocalypse.zombies.entity;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.MoveThroughVillageGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;

import com.apocalypse.zombies.entity.ai.AllySafeHurtByTargetGoal;
import com.apocalypse.zombies.registry.ModEntities;

/**
 * 腐蚀者 —— 远程软控。不近战，靠 {@link KeepDistanceGoal} 吊在 6~14 格外吐酸液。
 *
 * <p>技能「酸液喷射」：后仰蓄酸 0.75 秒，命中瞬间射出一发 {@link AcidProjectile}，
 * 落点留一片腐蚀云（毒 + 虚弱，8 秒）。</p>
 */
public class CorroderZombie extends AbstractEliteZombie {

    public CorroderZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return eliteAttributes()
                .add(Attributes.MAX_HEALTH, 26.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.24D)
                .add(Attributes.ATTACK_DAMAGE, 3.0D)
                .add(Attributes.ARMOR, 1.0D)
                .add(Attributes.FOLLOW_RANGE, 40.0D);
    }

    @Override
    protected EliteAbility ability() {
        return EliteAbility.SPIT;
    }

    @Override
    protected int abilityCooldownTicks() {
        return 100;
    }

    @Override
    protected boolean canStartAbility() {
        return this.hasTargetInRange(3.0D, 18.0D);
    }

    @Override
    protected void onAbilityStart() {
        this.playSound(SoundEvents.SLIME_ATTACK, 1.2F, 0.6F);
    }

    @Override
    protected void onAbilityImpact() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        LivingEntity target = this.getTarget();
        if (target == null) {
            return;
        }

        double dx = target.getX() - this.getX();
        double dy = target.getY(0.5D) - this.getEyeY();
        double dz = target.getZ() - this.getZ();
        double horizontal = Math.sqrt(dx * dx + dz * dz);

        AcidProjectile acid = new AcidProjectile(ModEntities.ACID_PROJECTILE.get(), this, level);
        acid.setPos(this.getX(), this.getEyeY() - 0.25D, this.getZ());
        // 抛物线补偿：水平距离越远，抬得越高
        acid.shoot(dx, dy + horizontal * 0.14D, dz, 1.1F, 2.0F);
        level.addFreshEntity(acid);
        this.playSound(SoundEvents.LLAMA_SPIT, 1.4F, 0.5F);
    }

    /**
     * 不挂近战 goal：远程单位贴脸不是它的活。
     * 用 {@link KeepDistanceGoal} 顶掉原版僵尸的冲锋。
     */
    @Override
    protected void addBehaviourGoals() {
        this.goalSelector.addGoal(2, new KeepDistanceGoal(this, 1.0D, 6.0D, 14.0D));
        this.goalSelector.addGoal(6, new MoveThroughVillageGoal(this, 1.0D, true, 4, this::canBreakDoors));
        this.goalSelector.addGoal(7, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.targetSelector.addGoal(1, new AllySafeHurtByTargetGoal(this));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
        this.targetSelector.addGoal(3, new NearestAttackableTargetGoal<>(this, IronGolem.class, true));
    }

    @Override
    protected SoundEvent getAmbientSound() {
        return SoundEvents.SLIME_SQUISH_SMALL;
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) {
        return SoundEvents.SLIME_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.SLIME_DEATH;
    }
}
