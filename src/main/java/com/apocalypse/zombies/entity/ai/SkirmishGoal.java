package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

/**
 * 被贴脸就往后退，退开之后把移动通道交还射击 Goal。
 *
 * <p>骷髅系的痛点是「站桩挨打」：原版 {@code RangedBowAttackGoal} 在近距离只会侧移，
 * 不会拉开距离，于是玩家一步冲上去就能把它锁在脸上打。这条 Goal 只在
 * <b>距离小于 {@code engage}</b> 时介入，把距离重新拉回 {@code disengage} 之外就退出 ——
 * 关键在于「退出」：退到位之后弓 Goal 重新拿到 MOVE，射击立刻恢复。</p>
 *
 * <p>这也是它不能直接用 {@code KeepDistanceGoal} 的原因：那一条只要目标存在就一直占着 MOVE
 * （它的 {@code canUse} 不看距离），会把弓的射击 Goal 永久堵死 —— 怪会一直退、一箭都不放。
 * 站位类 Goal 的 {@code canUse} 必须以距离为条件，这是同一件事上的硬约束。</p>
 */
public class SkirmishGoal extends Goal {

    private final Mob mob;
    private final double speed;
    private final double engage;
    private final double disengage;

    private int refresh;

    public SkirmishGoal(Mob mob, double speed, double engage, double disengage) {
        this.mob = mob;
        this.speed = speed;
        this.engage = engage;
        this.disengage = disengage;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE));
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.mob.getTarget();
        return target != null && target.isAlive() && this.mob.distanceTo(target) < this.engage;
    }

    @Override
    public boolean canContinueToUse() {
        LivingEntity target = this.mob.getTarget();
        return target != null && target.isAlive() && this.mob.distanceTo(target) < this.disengage;
    }

    @Override
    public void start() {
        this.refresh = 0;
    }

    @Override
    public void stop() {
        this.mob.getNavigation().stop();
    }

    @Override
    public void tick() {
        if (--this.refresh > 0) {
            return;
        }
        this.refresh = 10;
        LivingEntity target = this.mob.getTarget();
        if (target == null) {
            return;
        }
        Vec3 away = this.mob.position().subtract(target.position());
        Vec3 flat = new Vec3(away.x, 0.0D, away.z);
        if (flat.horizontalDistanceSqr() < 1.0E-4D) {
            flat = new Vec3(1.0D, 0.0D, 0.0D);
        }
        flat = flat.normalize();
        double step = this.disengage - this.engage + 3.0D;
        this.mob.getNavigation().moveTo(this.mob.getX() + flat.x * step,
                this.mob.getY(), this.mob.getZ() + flat.z * step, this.speed);
    }
}
