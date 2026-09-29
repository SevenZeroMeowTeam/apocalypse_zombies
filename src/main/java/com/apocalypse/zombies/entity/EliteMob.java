package com.apocalypse.zombies.entity;

import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;

/**
 * 施法状态的共同契约。
 *
 * <p>4 只生物分属两条继承链（僵尸系 / 骷髅系），没法再抽公共父类，所以状态用接口暴露：
 * 每个具体实体各自持有 {@code SynchedEntityData} 访问器（{@code defineId} 是按类分 ID 段的，
 * 拿别的类的访问器去 define 会撞 ID 直接抛异常），模型这边只认接口。</p>
 */
public interface EliteMob {

    EliteAbility getAbility();

    /** 当前技能已经走过的 tick；不在施法时为 -1。 */
    int getAbilityTick();

    void setAbility(EliteAbility ability, int tick);

    default boolean isCasting() {
        return !this.getAbility().isIdle();
    }

    /**
     * 客户端摆姿势用的归一化进度。
     *
     * <p>{@code setupAnim} 拿到的 {@code ageInTicks} 已经含了帧插值，直接把它减掉
     * {@code tickCount} 就是这一帧的 partial tick，所以动画能比 20Hz 的同步更顺。</p>
     */
    default float abilityProgress(float ageInTicks, int tickCount) {
        EliteAbility ability = this.getAbility();
        if (ability.isIdle()) {
            return 0.0F;
        }
        int tick = this.getAbilityTick();
        if (tick < 0) {
            return 0.0F;
        }
        float partialTick = ageInTicks - (float) tickCount;
        return Mth.clamp(((float) tick + partialTick) / (float) ability.getDuration(), 0.0F, 1.0F);
    }

    /** 前摇段的进度：0 = 刚起手，1 = 即将命中。命中之后恒为 1。 */
    default float windup(EliteAbility ability, float progress) {
        if (ability.isIdle()) {
            return 0.0F;
        }
        float impact = (float) ability.getImpactTick() / (float) ability.getDuration();
        if (impact <= 0.0F) {
            return 1.0F;
        }
        return Mth.clamp(progress / impact, 0.0F, 1.0F);
    }

    /** 收招段的进度：命中前恒为 0，命中后 0 → 1。 */
    default float recovery(EliteAbility ability, float progress) {
        if (ability.isIdle()) {
            return 0.0F;
        }
        float impact = (float) ability.getImpactTick() / (float) ability.getDuration();
        if (impact >= 1.0F) {
            return 0.0F;
        }
        return Mth.clamp((progress - impact) / (1.0F - impact), 0.0F, 1.0F);
    }

    /**
     * 目标是否在 [min, max] 距离内、看得见、且允许攻击。
     *
     * <p>实现者其实都是 {@link Mob}，但接口本身没法声明这一点，只好在这里做一次受检转换；
     * 僵尸系那边由 {@code AbstractEliteZombie} 包一层同名的实例方法，子类照旧用 {@code this.}。</p>
     */
    static boolean hasTargetInRange(LivingEntity self, double min, double max) {
        if (!(self instanceof Mob mob)) {
            return false;
        }
        LivingEntity target = mob.getTarget();
        if (target == null || !target.isAlive() || !mob.canAttack(target)) {
            return false;
        }
        double distance = mob.distanceTo(target);
        return distance >= min && distance <= max && mob.getSensing().hasLineOfSight(target);
    }
}
