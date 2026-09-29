package com.apocalypse.zombies.entity.ai;

import javax.annotation.Nullable;

import com.apocalypse.zombies.Config;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal;

/**
 * 回击之前先过阵营的 {@code HurtByTargetGoal}。
 *
 * <p>原版这条 Goal 只问「看得见吗、够得着吗」，不问「打我的这个是不是自己人」。正常玩法里
 * 它没问题（原版怪之间几乎不会互相造成伤害），但只要有一次范围伤害擦到同伴 —— TNT 爆炸、
 * 流弹、腐蚀液、抛花刺 —— {@code LastHurtByMob} 就记上了，同伴立刻掉头互咬。</p>
 *
 * <p>这条子类把「打我的家伙是不是同阵营」插在原版判定<b>之前</b>：是同伴就清掉那条记录并
 * 放弃（留着记录等于每 tick 重试一次）。清记录这一下很关键 —— {@code LastHurtByMob}
 * 同时也是别的判定（例如「被打过」的成就与仇恨扩散）会读的字段，留着它等于埋一颗随时
 * 复发的雷。</p>
 *
 * <p>它只挡「同阵营回击」，不挡任何主动仇恨：玩家、村民、铁傀儡照旧。</p>
 */
public class AllySafeHurtByTargetGoal extends HurtByTargetGoal {

    public AllySafeHurtByTargetGoal(PathfinderMob mob, Class<?>... toIgnoreDamage) {
        super(mob, toIgnoreDamage);
    }

    @Override
    public boolean canUse() {
        if (Config.NO_INFIGHTING.get() && this.ignoreAllyAttacker()) {
            return false;
        }
        return super.canUse();
    }

    @Override
    public boolean canContinueToUse() {
        if (Config.NO_INFIGHTING.get() && this.ignoreAllyAttacker()) {
            return false;
        }
        return super.canContinueToUse();
    }

    /** 打我的那个是不是同伴；是就顺手把账销了，免得每 tick 再判一遍。 */
    private boolean ignoreAllyAttacker() {
        @Nullable LivingEntity attacker = this.mob.getLastHurtByMob();
        if (attacker == null || !AllyJudge.isAlly(this.mob, attacker)) {
            return false;
        }
        this.mob.setLastHurtByMob(null);
        return true;
    }
}
