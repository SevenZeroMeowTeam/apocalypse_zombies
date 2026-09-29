package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;
import java.util.List;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.ai.goal.Goal;

/**
 * 自动锁敌：同类挨打，附近的同伴一起围上来。
 *
 * <p>原版每只怪各锁各的目标，于是「打一只僵尸」只招来那一只 —— 玩家可以逐个点杀，
 * 尸群读起来是一堆互不相干的个体。这条 Goal 让仇恨在同类之间传播：只要半径内有一只同伴
 * 已经锁定了玩家（或正在被玩家打），自己就接下同一个目标。</p>
 *
 * <p>三条刻意的设计：</p>
 * <ul>
 *   <li><b>只认「非怪物」当目标</b> —— 同伴锁着一只狼、一只铁傀儡、一个村民，都值得跟；
 *       但如果目标本身是怪物（两个模组的怪互殴），跟上去只会把场面搅乱。</li>
 *   <li><b>冷却而不是每 tick 扫描</b> —— 反正是「附近有人喊」级别的判断，每 {@code interval}
 *       tick 看一次足够，几百只怪同屏时这一条决定了它能不能用。</li>
 *   <li><b>只传「用得上」的仇恨</b> —— 接过同伴的目标之后，{@link PreyJudge} 每 tick 复核一次：
 *       看得见却走不到的目标（石壳里的村民、柱顶上的村民、飞在天上的玩家）立刻放掉。
 *       这一条是踩出来的：原来「锁上就不放手」的写法会把 TARGET 通道占死，她站在够不着的
 *       东西旁边一动不动，连原版那三条目标都起不来（详见 {@link PreyTargetGoal} 的类注释）。</li>
 * </ul>
 */
public class SharedAggroGoal extends Goal {

    private final Mob mob;
    private final PreyJudge judge;
    private final double radius;
    private final int interval;

    private int cooldown;
    private LivingEntity shared;

    public SharedAggroGoal(Mob mob, double radius, int interval) {
        this.mob = mob;
        this.judge = new PreyJudge(mob);
        this.radius = radius;
        this.interval = Math.max(1, interval);
        this.setFlags(EnumSet.of(Goal.Flag.TARGET));
    }

    @Override
    public boolean canUse() {
        LivingEntity current = this.mob.getTarget();
        if (current != null && current.isAlive()) {
            return false;
        }
        if (this.cooldown > 0) {
            this.cooldown--;
            return false;
        }
        this.cooldown = this.interval;
        this.shared = this.findSharedTarget();
        return this.shared != null;
    }

    @Override
    public boolean canContinueToUse() {
        return this.shared != null && this.shared.isAlive() && this.mob.getTarget() == this.shared
                && this.judge.usable(this.shared);
    }

    @Override
    public void start() {
        this.mob.setTarget(this.shared);
    }

    @Override
    public void stop() {
        // 清掉自己的引用，但不动实体的目标 —— GoalSelector 换人时会紧接着 start 新的 owner，
        // 清空会把对方的设置抹掉。（目标「该不该一直留着」由 PreyJudge 每 tick 复核。）
        this.shared = null;
    }

    @SuppressWarnings("unchecked")
    private LivingEntity findSharedTarget() {
        Class<? extends Mob> same = (Class<? extends Mob>) this.mob.getClass();
        List<? extends Mob> allies = this.mob.level().getEntitiesOfClass(same,
                this.mob.getBoundingBox().inflate(this.radius));
        for (Mob ally : allies) {
            if (ally == this.mob || !ally.isAlive()) {
                continue;
            }
            LivingEntity candidate = ally.getTarget();
            if (candidate != null && candidate.isAlive() && this.acceptable(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    /** 非怪物目标才算「该一起打的敌人」；怪物之间的争斗不掺和。而且必须是「用得上」的。 */
    private boolean acceptable(LivingEntity candidate) {
        return !(candidate instanceof Monster) && this.mob.canAttack(candidate)
                && this.judge.usable(candidate);
    }
}
