package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.ai.AllyJudge;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 敌对生物之间不互相攻击 —— 一刀切在伤害入口上。
 *
 * <p>为什么必须在伤害这一步拦，而不是只改目标表：内斗的<b>因果是反的</b>。不是「它们想打
 * 对方」，而是「它们被对方擦到了，原版就自动记仇」。所以只改目标表（谁该被打）治不了本，
 * 得让同伴的伤害<b>根本没发生</b>：伤害不发生 ⇒ {@code LastHurtByMob} 不会被写 ⇒
 * 原版所有回击 Goal（{@code HurtByTargetGoal}）都无从下手。这一层同时覆盖了本模组与
 * 原版的全部伤害路径（近战、投射物、爆炸都走 {@code LivingEntity#hurt}）。</p>
 *
 * <p>两个档位，对应两个配置项：</p>
 * <ul>
 *   <li>{@code ai_enhance.no_infighting}（默认开）—— <b>任一侧是本模组的怪</b>就不许互殴。
 *       这是「本模组不内斗」的兜底：别的模组/原版怪之间怎么打不管。</li>
 *   <li>{@code ai_enhance.no_infighting_global}（默认关）—— 连原版怪之间也不许互殴。
 *       会改到原版行为（凋灵、掠夺者与僵尸之类原本会打起来的组合也会安静下来），
 *       所以默认不开，留给玩家自己决定。</li>
 * </ul>
 *
 * <p>豁免（{@link AllyJudge} 里写着）：美女僵尸的策反物/召唤物整类不算「自己人」，
 * 它们与僵尸的撕咬是技能设计；玩家阵营的驯服生物与召唤物也不算敌对生物。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID)
public final class NoInfighting {

    private NoInfighting() {
    }

    @SubscribeEvent
    public static void onLivingAttack(LivingAttackEvent event) {
        LivingEntity victim = event.getEntity();
        Entity source = event.getSource().getEntity();
        if (!(source instanceof LivingEntity attacker) || attacker == victim) {
            return;
        }
        // 双方都得是天然敌对生物；任何一侧是策反物/玩家阵营，这条规则就不适用。
        if (!AllyJudge.isAlly(attacker, victim)) {
            return;
        }
        if (!Config.NO_INFIGHTING_GLOBAL.get()
                && !(Config.NO_INFIGHTING.get()
                        && (AllyJudge.isModMob(attacker) || AllyJudge.isModMob(victim)))) {
            return;
        }
        event.setCanceled(true);
    }
}
