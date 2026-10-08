package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;

import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.npc.Villager;

/**
 * 武装村民的近战行为。
 *
 * <p><b>为什么不用 {@link net.minecraft.world.entity.ai.goal.MeleeAttackGoal}</b>：村民的
 * {@code createAttributes()} 里<b>没有</b> {@code ATTACK_DAMAGE}（它只有移动速度与跟随范围），
 * 而那个 Goal 的攻击路径 {@code Mob.doHurtTarget} 第一步就去读这个属性 ——
 * {@code AttributeSupplier.getValue} 找不到属性时直接抛 {@code IllegalArgumentException}。
 * 实测结果就是「放置武装村民 → 服务端 tick 到它 → 崩溃」：</p>
 *
 * <pre>
 * Can't find attribute minecraft:generic.attack_damage
 *   at AttributeSupplier.getValue
 *   at LivingEntity.getAttribute
 *   at Mob.doHurtTarget
 *   at MeleeAttackGoal.checkAndPerformAttack
 * </pre>
 *
 * <p>而 {@code AttributeMap} 没有公开的"添加属性"接口，没法凭空把 {@code ATTACK_DAMAGE} 补给村民，
 * 所以这里自己走一遍：贴到攻击距离就直接 {@code hurt()}，伤害值由本模组给定、不经过属性系统，
 * 再让村民挥手做动作。等价于把 {@code MeleeAttackGoal} 里唯一需要属性的那一步替换掉。</p>
 */
public class VillagerDefendGoal extends Goal {

    /** 两次挥击之间的间隔（tick）。村民不是战斗单位，给得比僵尸慢一档。 */
    private static final int ATTACK_INTERVAL = 20;

    private final Villager villager;
    private final double speed;
    private final float damage;
    private final double reachSqr;
    private int cooldown;

    public VillagerDefendGoal(Villager villager, double speed, float damage, double reach) {
        this.villager = villager;
        this.speed = speed;
        this.damage = damage;
        this.reachSqr = reach * reach;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.villager.getTarget();
        return target != null && target.isAlive();
    }

    @Override
    public boolean canContinueToUse() {
        return this.canUse();
    }

    @Override
    public void start() {
        this.cooldown = 0;
    }

    @Override
    public void stop() {
        this.villager.getNavigation().stop();
        this.cooldown = 0;
    }

    @Override
    public void tick() {
        LivingEntity target = this.villager.getTarget();
        if (target == null) {
            return;
        }
        this.villager.getLookControl().setLookAt(target, 30.0F, 30.0F);
        if (this.villager.distanceToSqr(target) > this.reachSqr) {
            // 够不着就自己追：这条支线不归 Brain 管，没人会替它寻路
            if (this.villager.getNavigation().isDone()) {
                this.villager.getNavigation().moveTo(target, this.speed);
            }
            return;
        }
        this.villager.getNavigation().stop();
        if (this.cooldown > 0) {
            this.cooldown--;
            return;
        }
        this.cooldown = ATTACK_INTERVAL;
        this.villager.swing(InteractionHand.MAIN_HAND);
        target.hurt(this.villager.damageSources().mobAttack(this.villager), this.damage);
    }
}
