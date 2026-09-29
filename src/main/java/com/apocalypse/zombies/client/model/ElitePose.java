package com.apocalypse.zombies.client.model;

import net.minecraft.util.Mth;

import com.apocalypse.zombies.entity.EliteAbility;
import com.apocalypse.zombies.entity.EliteMob;

/**
 * 4 只精英的攻击姿态共用的缓动与分段工具。
 *
 * <p>技能的时间轴是「前摇 → 命中 → 收招」，姿态这边只要三个量就能摆出任意一段动作：
 * {@link #hold} 是蓄力保持量、{@link #strike} 是命中后那一下的完成度、
 * {@link #pulse} 是命中瞬间的冲击脉冲。三个量都由同一份网络同步状态算出来，
 * 所以服务端改 {@code impactTick} / {@code duration}，客户端动画会自动跟着变。</p>
 */
public final class ElitePose {

    /** 脉冲的半宽（占整段时间轴的比例）。 */
    private static final float PULSE_HALF_WIDTH = 0.18F;

    private ElitePose() {
    }

    /** 蓄力到位后的保持量：前摇爬到 1，收招松回 0。 */
    public static float hold(EliteMob mob, EliteAbility ability, float ageInTicks, int tickCount) {
        float progress = mob.abilityProgress(ageInTicks, tickCount);
        return mob.windup(ability, progress) * (1.0F - mob.recovery(ability, progress));
    }

    /** 命中后立刻完成的那一下（下砸 / 释放）：收招前三分之一内从 0 跑到 1。 */
    public static float strike(EliteMob mob, EliteAbility ability, float ageInTicks, int tickCount) {
        float progress = mob.abilityProgress(ageInTicks, tickCount);
        return Mth.clamp(mob.recovery(ability, progress) * 3.0F, 0.0F, 1.0F);
    }

    /** 以命中 tick 为中心的三角脉冲：0 → 1 → 0，给「顿」那一下。 */
    public static float pulse(EliteMob mob, EliteAbility ability, float ageInTicks, int tickCount) {
        float progress = mob.abilityProgress(ageInTicks, tickCount);
        float impact = (float) ability.getImpactTick() / (float) ability.getDuration();
        float delta = Math.abs(progress - impact);
        return Math.max(0.0F, 1.0F - delta / PULSE_HALF_WIDTH);
    }

    /** 施法期间的高频抖动，用来做「绷住了」的细节。 */
    public static float tremble(float ageInTicks, float speed, float amplitude) {
        return Mth.sin(ageInTicks * speed) * amplitude;
    }
}
