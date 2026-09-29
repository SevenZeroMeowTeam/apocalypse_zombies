package com.apocalypse.zombies.entity;

import java.util.EnumSet;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

/**
 * 把持有者锁在离目标一定距离的环带里：太近就退，太远就靠，刚好就交还移动通道。
 *
 * <p>腐蚀者和骸骨射手都靠它实现「主动拉开距离」。它只在<b>目标存在且自己不在环带里</b>时
 * 占据 MOVE/LOOK：进到环带内就退出，把 MOVE 让给同实体上优先级更低、但同样要 MOVE 的攻击
 * Goal（弓箭 Goal 就在它之后）。这条「让位」不是优化而是必需 —— 只要 {@code canUse} 只看
 * 目标存在，本 Goal 就会永久占住 MOVE，同一只怪身上的远程攻击 Goal 一箭都放不出来。</p>
 *
 * <p>施法定身（{@code customServerAiStep} 里清寻路）依然能盖住它——那一 tick 的顺序是
 * goalSelector → navigation → customServerAiStep。</p>
 */
public class KeepDistanceGoal extends Goal {

    private final PathfinderMob mob;
    private final double speedModifier;
    /** 比这更近就往后退。 */
    private final double tooClose;
    /** 后退时一次撤这么远。 */
    private final double retreatStep;
    /** 比这更远就往前压。 */
    private final double tooFar;

    private int recalcCooldown;

    public KeepDistanceGoal(PathfinderMob mob, double speedModifier, double tooClose, double tooFar) {
        this.mob = mob;
        this.speedModifier = speedModifier;
        this.tooClose = tooClose;
        this.tooFar = tooFar;
        this.retreatStep = Math.max(4.0D, tooFar - tooClose);
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        return this.outOfBand();
    }

    @Override
    public boolean canContinueToUse() {
        return this.outOfBand();
    }

    /**
     * 「现在需要我动」= 目标有效且不在环带里。
     *
     * <p>刻意<b>不</b>写成「只要目标有效」：那会让本 Goal 永久霸占 MOVE，
     * 同实体上优先级更低的弓箭 Goal 永远开不了火（弓箭 Goal 也需要 MOVE）。</p>
     */
    private boolean outOfBand() {
        LivingEntity target = this.mob.getTarget();
        if (target == null || !target.isAlive()) {
            return false;
        }
        double distance = this.mob.distanceTo(target);
        return distance < this.tooClose || distance > this.tooFar;
    }

    @Override
    public void start() {
        this.recalcCooldown = 0;
    }

    @Override
    public void stop() {
        this.mob.getNavigation().stop();
    }

    @Override
    public void tick() {
        LivingEntity target = this.mob.getTarget();
        if (target == null) {
            return;
        }
        this.mob.getLookControl().setLookAt(target, 30.0F, 30.0F);

        if (--this.recalcCooldown > 0) {
            return;
        }
        this.recalcCooldown = 8;

        double distance = this.mob.distanceTo(target);
        if (distance < this.tooClose) {
            Vec3 away = this.mob.position().subtract(target.position());
            Vec3 direction = away.horizontalDistanceSqr() < 1.0E-4D
                    ? new Vec3(this.mob.getRandom().nextDouble() - 0.5D, 0.0D,
                            this.mob.getRandom().nextDouble() - 0.5D).normalize()
                    : away.normalize();
            Vec3 retreat = this.mob.position().add(direction.x * this.retreatStep, 0.0D,
                    direction.z * this.retreatStep);
            this.mob.getNavigation().moveTo(retreat.x, retreat.y, retreat.z, this.speedModifier);
        } else if (distance > this.tooFar) {
            this.mob.getNavigation().moveTo(target, this.speedModifier);
        } else {
            this.mob.getNavigation().stop();
        }
    }
}
