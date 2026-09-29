package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;
import java.util.List;

import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.npc.Villager;

/**
 * 铁傀儡的「护民」优先权：谁在威胁村民，先打谁。
 *
 * <p>原版铁傀儡对付村民被袭的路子只有两条，都有缺口：{@code DefendVillageTargetGoal}
 * 只认<b>玩家</b>凶手（僵尸在它眼里不算「袭击村庄」），而它自己那条 {@code NearestAttackableTargetGoal}
 * 只锁 35 格内最近的怪 —— 于是「隔着半个村子、正朝村民走过去的僵尸」不会被优先处理，
 * 铁傀儡可能在原地发呆或者去打一只无关的怪。</p>
 *
 * <p>这条 Goal 补的正是这个缺口：每 {@code interval} tick 扫一遍附近村民，
 * 把<b>正在锁定村民、或已经贴到村民身边</b>的怪挑出来做目标。它只管「立目标」，
 * 追上去打由原版 {@code MeleeAttackGoal} 负责。</p>
 *
 * <p>只在铁傀儡自己没有活目标时介入（{@code getTarget() == null}）—— 不让它半途丢掉正在打的怪。</p>
 */
public class GolemGuardGoal extends Goal {

    private final Mob guard;
    private final double villagerRadius;
    private final double threatRadius;
    private final int interval;

    private int cooldown;

    public GolemGuardGoal(Mob guard, double villagerRadius, double threatRadius, int interval) {
        this.guard = guard;
        this.villagerRadius = villagerRadius;
        this.threatRadius = threatRadius;
        this.interval = Math.max(1, interval);
        this.setFlags(EnumSet.of(Goal.Flag.TARGET));
    }

    @Override
    public boolean canUse() {
        if (this.guard.getTarget() != null && this.guard.getTarget().isAlive()) {
            return false;
        }
        if (this.cooldown > 0) {
            this.cooldown--;
            return false;
        }
        this.cooldown = this.interval;
        return this.findThreat() != null;
    }

    @Override
    public boolean canContinueToUse() {
        return false;
    }

    @Override
    public void start() {
        Monster threat = this.findThreat();
        if (threat != null) {
            this.guard.setTarget(threat);
        }
    }

    @Override
    public void stop() {
        // 目标交给近战 Goal 去用，这里不清
    }

    /** 挑最近的一个「正威胁村民」的怪：已锁定该村民，或已经贴到村民身边。 */
    private Monster findThreat() {
        List<Villager> villagers = this.guard.level().getEntitiesOfClass(Villager.class,
                this.guard.getBoundingBox().inflate(this.villagerRadius), Villager::isAlive);
        Monster best = null;
        double bestDistance = Double.MAX_VALUE;
        for (Villager villager : villagers) {
            List<Monster> nearby = this.guard.level().getEntitiesOfClass(Monster.class,
                    villager.getBoundingBox().inflate(this.threatRadius), Monster::isAlive);
            for (Monster monster : nearby) {
                if (monster.getTarget() != villager) {
                    continue;
                }
                double distance = this.guard.distanceToSqr(monster);
                if (distance < bestDistance) {
                    bestDistance = distance;
                    best = monster;
                }
            }
        }
        return best;
    }
}
