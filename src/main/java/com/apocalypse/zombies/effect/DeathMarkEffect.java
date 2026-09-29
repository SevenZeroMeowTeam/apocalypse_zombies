package com.apocalypse.zombies.effect;

import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.effect.MobEffect;
import net.minecraft.world.effect.MobEffectCategory;
import net.minecraft.world.entity.LivingEntity;

/**
 * 死亡标记：被远程怪打中的人身上挂的印记。
 *
 * <p>它自己<b>不改任何伤害</b> —— 伤害在 {@code DeathMarkHandler} 里加。这里只负责两件事：
 * 让玩家在 HUD 上看见（图标 + 名字），以及在世界上看得见（每 0.5 秒冒一点飞溅粒子）。
 * 把「表现」和「数值」分在两个地方，是为了让改数值不必碰效果类，改表现也不必碰伤害钩子。</p>
 *
 * <p>层数用 vanilla 的 amplifier 表示：1 层 = amplifier 0，最多到配置里的上限。
 * 重复命中时 vanilla 自己会「取更高的 amplifier、更长的 duration」，所以叠层与刷新时长
 * 都不需要额外记状态。图标按注册名去 {@code textures/mob_effect/death_mark.png} 找，
 * 尺寸必须是 18×18（HUD 原样 blit）。</p>
 */
public class DeathMarkEffect extends MobEffect {

    /** 冒粒子的间隔（tick）：每 tick 刷粒子既费又糊。 */
    private static final int PULSE_INTERVAL = 10;

    /**
     * 标记的视觉：被打的人身上冒的粒子。
     *
     * <p>写成有名字的常量而不是内联 {@code ParticleTypes.DAMAGE_INDICATOR}：一是换视觉只改一处，
     * 二是出货门禁要能<b>钉在一个属于本模组的名字上</b> —— 生产 jar 会被 SRG 重映射，
     * 原版名（{@code DAMAGE_INDICATOR} 之类）在 jar 里根本搜不到，拿它当「新代码进没进包」的证据
     * 会永远判失败。</p>
     */
    private static final ParticleOptions MARK_PARTICLE = ParticleTypes.DAMAGE_INDICATOR;

    public DeathMarkEffect() {
        // 深红：与图标主色同源，HUD 上「有害」那栏的边框颜色也取这个
        super(MobEffectCategory.HARMFUL, 0xB01E1E);
    }

    @Override
    public void applyEffectTick(LivingEntity entity, int amplifier) {
        if (!(entity.level() instanceof ServerLevel level)) {
            return;
        }
        // 绕半身高打一点飞溅，扫一眼就知道谁被标了，不用盯 HUD
        level.sendParticles(MARK_PARTICLE,
                entity.getX(), entity.getY() + entity.getBbHeight() * 0.7D, entity.getZ(),
                1, 0.25D, 0.25D, 0.25D, 0.0D);
    }

    @Override
    public boolean isDurationEffectTick(int duration, int amplifier) {
        return duration % PULSE_INTERVAL == 0;
    }
}
