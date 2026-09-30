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

        default void onEnd(EliteAbility finished) {
        }

        /**
         * 一个槽位最多干等多少 tick 才认它是死槽位，见 {@code tickIdle()}。默认 2 秒。
         */
        default int starvationTicks() {
            return 40;
        }

        /**
         * 当前槽位等够了 {@link #starvationTicks()} 却依然起不了手。实现者应当换一招，别原地卡死。
         */
        default void onStarved() {
        }
    }

    private final Mob mob;
    private final EliteMob state;
    private final Hooks hooks;

    /** 剩余冷却；<= 0 且 canStart() 为真才起手。 */
    private int cooldown;

    /** 当前槽位已经白等了几个 tick。命中即起手的招永远是 0，不会误触发换槽。 */
    private int starvedTicks;

    public EliteAbilityDriver(Mob mob, EliteMob state, Hooks hooks) {
        this.mob = mob;
        this.state = state;
        this.hooks = hooks;
    }

    /** 每个服务端 tick 调一次。 */
    public void tick() {
        EliteAbility current = this.state.getAbility();
        if (current.isIdle()) {
            this.tickIdle();
            return;
        }
        this.starvedTicks = 0;
        this.advance(current);
    }

    public boolean isOffCooldown() {
        return this.cooldown <= 0;
    }

    /** 当前槽位白等了多少 tick —— 调试指令直接读它。 */
    public int getStarvedTicks() {
        return this.starvedTicks;
    }

    /**
     * 冷却 + 起手 + <b>死槽位兜底</b>。
     *
     * <p>兜底这一段是必须的：起手条件由子类定（距离、视线、目标存活），而这些条件随时可能
     * 长时间不成立 —— 玩家贴脸肉搏时，「目标 ≥ 4 格才能放」的远程招就永远起不了手。
     * 轮转索引只在技能<b>结束</b>时前进，所以一个起不了手的槽位会把整张轮转表锁死，
     * 表现是 Boss 站着不动、一招都不放（看着像「这个阶段没有技能」）。
     * 干等到 {@link Hooks#starvationTicks()} 就通知子类换槽，让轮转重新流动起来。</p>
     */
    private void tickIdle() {
        if (this.cooldown > 0) {
            this.cooldown--;
        }
        if (this.cooldown > 0) {
            return;
        }
        if (this.hooks.canStart()) {
            this.starvedTicks = 0;
            this.state.setAbility(this.hooks.ability(), 0);
            this.hooks.onStart();
            return;
        }
        this.starvedTicks++;
        if (this.starvedTicks >= Math.max(1, this.hooks.starvationTicks())) {
            this.starvedTicks = 0;
            this.hooks.onStarved();
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
            this.hooks.onEnd(current);
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
