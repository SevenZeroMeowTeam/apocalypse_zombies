package com.apocalypse.zombies.entity;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;

/**
 * 技能推进器：冷却计时、起手判定、前摇/命中/收招的时间切分，以及施法期间定身。
 *
 * <p>僵尸系（{@link AbstractEliteZombie}）和骷髅系（{@link MarksmanSkeleton}）分属两条继承链，
 * 没法共用父类，所以把这段逻辑抽成一个组合式的驱动器，两边各持有一个实例。</p>
 *
 * <p>调用点在 {@code customServerAiStep()}：它在 {@code LivingEntity.aiStep} →
 * {@code Mob.serverAiStep} 里排在 goalSelector / navigation 之后、{@code travel()} 之前，
 * 所以在这里清寻路和移动输入，当 tick 就真的钉住不动，不用去动子类的 goal。</p>
 */
public final class EliteAbilityDriver {

    /** 生物自己的那一半：技能是什么、多久冷却、能不能起手、命中干什么。 */
    public interface Hooks {

        EliteAbility ability();

        int cooldownTicks();

        boolean canStart();

        void onStart();

        void onImpact();

        default void onEnd() {
        }
    }

    private final Mob mob;
    private final EliteMob state;
    private final Hooks hooks;

    /** 剩余冷却；<= 0 且 canStart() 为真才起手。 */
    private int cooldown;

    public EliteAbilityDriver(Mob mob, EliteMob state, Hooks hooks) {
        this.mob = mob;
        this.state = state;
        this.hooks = hooks;
    }

    /** 每个服务端 tick 调一次。 */
    public void tick() {
        EliteAbility current = this.state.getAbility();
        if (current.isIdle()) {
            this.tickCooldown();
            return;
        }
        this.advance(current);
    }

    public boolean isOffCooldown() {
        return this.cooldown <= 0;
    }

    private void tickCooldown() {
        if (this.cooldown > 0) {
            this.cooldown--;
        }
        if (this.cooldown <= 0 && this.hooks.canStart()) {
            this.state.setAbility(this.hooks.ability(), 0);
            this.hooks.onStart();
        }
    }

    private void advance(EliteAbility current) {
        int tick = this.state.getAbilityTick() + 1;
        this.state.setAbility(current, tick);
        this.holdStill();

        if (tick == current.getImpactTick()) {
            this.hooks.onImpact();
        }
        if (tick >= current.getDuration()) {
            this.state.setAbility(EliteAbility.NONE, -1);
            this.cooldown = this.hooks.cooldownTicks();
            this.hooks.onEnd();
        }
    }

    /**
     * 施法期间钉在原地，只保留转向。
     *
     * <p>不动 deltaMovement：那样连被打飞的反馈都会被吃掉，清掉寻路路径和两个移动输入就够。</p>
     */
    private void holdStill() {
        this.mob.getNavigation().stop();
        this.mob.xxa = 0.0F;
        this.mob.zza = 0.0F;
        LivingEntity target = this.mob.getTarget();
        if (target != null) {
            this.mob.getLookControl().setLookAt(target, 30.0F, 30.0F);
        }
    }
}
