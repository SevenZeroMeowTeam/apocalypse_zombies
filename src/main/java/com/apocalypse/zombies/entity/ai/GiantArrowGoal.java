package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;

import com.apocalypse.zombies.entity.GiantArrow;

import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.goal.Goal;

/**
 * 「蓄一发超大号跟踪箭」——骷髅的重击。
 *
 * <p>概率、伤害、弹速、追踪速率、大小、冷却全部由调用方（也就是 {@code Config}）传进来，
 * 本类不含任何魔数 —— 普通骷髅与精英骸骨射手共用这一段，差别只在两套参数。</p>
 *
 * <p><b>前摇是刻意的</b>：{@code windupTicks} 期间站定、面向目标、脚下冒粒子并拉出低音。
 * 没有前摇的话，玩家只会觉得自己莫名其妙掉了半管血；有了前摇，这是一次「看得见、可以打断或走开」
 * 的攻击，跟美女僵尸的技能线是同一条设计纪律。</p>
 *
 * <p>抢占 MOVE 与 LOOK：站定才能瞄，也顺手压住同优先级之下的走位 Goal（弓 Goal 在它之后，
 * 前摇结束、本 Goal 退出，射击立刻恢复）。</p>
 */
public class GiantArrowGoal extends Goal {

    private final Mob mob;
    private final double minRange;
    private final double maxRange;
    private final float chance;
    private final float damage;
    private final float speed;
    private final int knockback;
    private final double turnDegrees;
    private final int cooldownTicks;
    private final int windupTicks;
    private final int lifeTicks;

    private int cooldown;
    private int windup = -1;

    public GiantArrowGoal(Mob mob, double minRange, double maxRange, float chance, float damage,
                          float speed, int knockback, double turnDegrees,
                          int cooldownTicks, int windupTicks, int lifeTicks) {
        this.mob = mob;
        this.minRange = minRange;
        this.maxRange = maxRange;
        this.chance = chance;
        this.damage = damage;
        this.speed = speed;
        this.knockback = knockback;
        this.turnDegrees = turnDegrees;
        this.cooldownTicks = cooldownTicks;
        this.windupTicks = windupTicks;
        this.lifeTicks = lifeTicks;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        // 冷却在这里递减：本 Goal 不占 TARGET 之外的调度槽，canUse 每 tick 都会被问到
        if (this.cooldown > 0) {
            this.cooldown--;
            return false;
        }
        LivingEntity target = this.mob.getTarget();
        if (target == null || !target.isAlive()) {
            return false;
        }
        double distance = this.mob.distanceTo(target);
        if (distance < this.minRange || distance > this.maxRange) {
            return false;
        }
        return this.mob.getSensing().hasLineOfSight(target);
    }

    @Override
    public boolean canContinueToUse() {
        LivingEntity target = this.mob.getTarget();
        return this.windup >= 0 && target != null && target.isAlive();
    }

    @Override
    public void start() {
        this.windup = this.windupTicks;
        this.mob.getNavigation().stop();
        // 低音 = 这一发比普通箭重，玩家听得出区别
        this.mob.playSound(SoundEvents.SKELETON_SHOOT, 1.4F, 0.55F);
    }

    @Override
    public void tick() {
        LivingEntity target = this.mob.getTarget();
        if (target != null) {
            this.mob.getLookControl().setLookAt(target, 30.0F, 30.0F);
        }
        if (this.windup > 0 && this.windup % 4 == 0
                && this.mob.level() instanceof ServerLevel level) {
            level.sendParticles(ParticleTypes.CRIT,
                    this.mob.getX(), this.mob.getY() + this.mob.getBbHeight() * 0.8D, this.mob.getZ(),
                    3, 0.3D, 0.2D, 0.3D, 0.02D);
        }
        if (--this.windup > 0) {
            return;
        }
        this.windup = -1;
        this.cooldown = this.cooldownTicks + this.windupTicks;
        if (this.mob.getRandom().nextFloat() < this.chance) {
            this.fire(target);
        }
    }

    @Override
    public void stop() {
        this.windup = -1;
    }

    private void fire(LivingEntity target) {
        if (target == null || !(this.mob.level() instanceof ServerLevel level)) {
            return;
        }
        GiantArrow.launch(level, this.mob, target, this.damage, this.speed, this.knockback,
                this.turnDegrees, this.lifeTicks);
    }
}
