package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.AcidProjectile;
import com.apocalypse.zombies.entity.BulletProjectile;
import com.apocalypse.zombies.registry.ModEffects;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 死亡标记：远程怪打中谁，谁就被标上，之后被标记期间吃「所有怪」的伤害都更重。
 *
 * <p>一个钩子干两件事，顺序很关键：<b>先按已经挂上的层数加伤，再加新的一层</b>。
 * 这样「第一枪只是标记、第二枪开始才痛」，层数是打出来的而不是一命中就吃满 ——
 * 反过来写的话第一枪就会带上它自己刚打出来的加成。</p>
 *
 * <p>加伤只认 {@link Monster} 打出来的伤害：玩家互殴、摔伤、岩浆不该因为被僵尸打中过一次
 * 就统统变重。命中来源用三个类判定 —— 子弹（{@link BulletProjectile}）、箭
 * （{@link AbstractArrow}，残兵的弓、骸骨射手的弓箭、以及超大跟踪箭都是它的子类）、
 * 腐蚀者的酸弹（{@link AcidProjectile}）。四只远程怪的出口在这一次判定里收口。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID)
public final class DeathMarkHandler {

    private DeathMarkHandler() {
    }

    @SubscribeEvent
    public static void onHurt(LivingHurtEvent event) {
        if (!Config.DEATH_MARK_ENABLED.get()) {
            return;
        }
        LivingEntity victim = event.getEntity();
        DamageSource source = event.getSource();

        // ① 结算：按「已经被打上的层数」放大来自怪的伤害
        int stacks = stacksOf(victim);
        if (stacks > 0 && source.getEntity() instanceof Monster) {
            double bonus = stacks * Config.DEATH_MARK_DAMAGE_BONUS.get();
            event.setAmount((float) (event.getAmount() * (1.0D + bonus)));
        }

        // ② 命中即叠层：只认怪用远程武器打出来的命中
        Entity direct = source.getDirectEntity();
        if (!isRangedHit(direct) || !(source.getEntity() instanceof Monster shooter)) {
            return;
        }
        if (shooter == victim) {
            return;
        }
        applyMark(victim, stacks);
    }

    /** 哪些弹射物算「远程命中」。四只远程怪的出口都在这三个类里。 */
    private static boolean isRangedHit(Entity direct) {
        return direct instanceof BulletProjectile
                || direct instanceof AbstractArrow
                || direct instanceof AcidProjectile;
    }

    /** 标记层数 = amplifier + 1；没挂就是 0。 */
    private static int stacksOf(LivingEntity victim) {
        MobEffectInstance instance = victim.getEffect(ModEffects.DEATH_MARK.get());
        return instance == null ? 0 : instance.getAmplifier() + 1;
    }

    /**
     * 叠一层。vanilla 的 {@code addEffect} 自己会「取更高的 amplifier、更长的 duration」，
     * 所以这里只要把新层数原样递进去，重复命中就自然变成刷新时长。
     */
    private static void applyMark(LivingEntity victim, int currentStacks) {
        int next = Math.min(currentStacks + 1, Config.DEATH_MARK_MAX_STACKS.get());
        victim.addEffect(new MobEffectInstance(ModEffects.DEATH_MARK.get(),
                Config.DEATH_MARK_DURATION.get(), next - 1,
                false, true, true));
    }
}
