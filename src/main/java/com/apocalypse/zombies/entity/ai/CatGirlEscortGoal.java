package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

import java.util.EnumSet;

/**
 * 护卫：主人挨打时贴过去挡在中间。
 *
 * <p>「谁打主人就打谁」由目标选择器（{@code OwnerHurtByTargetGoal}）负责，这条只管<b>站位</b>。
 * 因为原版 {@code FollowOwnerGoal} 只在主人离得远（&gt;10 格）时才动，主人被贴脸时她是站着不动的 ——
 * 看起来就像在看戏。这里补上「挨打 → 立刻靠过去」。</p>
 *
 * <ul>
 *   <li>条件：主人的记仇对象还活着、在 {@link #RANGE} 格内；她与主人还差 {@link #STANDOFF} 格以上。</li>
 *   <li>到位就停，不围着主人转圈（主人被围时原地打转最碍事）。</li>
 * </ul>
 */
public class CatGirlEscortGoal extends Goal {

    /** 认账的半径（格）：主人被打的地点太远就交给跟随逻辑，不追到天边。 */
    private static final double RANGE = 24.0D;

    /** 贴到这么近就算到位（格）。 */
    private static final double STANDOFF = 2.5D;

    private static final double SPEED = 1.35D;

    private final CatGirlEntity cat;

    public CatGirlEscortGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (!Config.CAT_GIRL_ESCORT.get()) {
            return false;
        }
        LivingEntity owner = this.cat.getOwner();
        LivingEntity attacker = owner == null ? null : owner.getLastHurtByMob();
        if (attacker == null || !attacker.isAlive() || !owner.isAlive()) {
            return false;
        }
        if (this.cat.distanceToSqr(owner) > RANGE * RANGE) {
            return false;
        }
        return this.cat.distanceToSqr(owner) > STANDOFF * STANDOFF;
    }

    @Override
    public boolean canContinueToUse() {
        return this.canUse();
    }

    @Override
    public void start() {
        this.cat.setTarget(null);   // 让她自己选目标，这条只管走位
    }

    @Override
    public void tick() {
        LivingEntity owner = this.cat.getOwner();
        if (owner == null) {
            return;
        }
        // 站到主人与攻击者之间：先看主人，再往攻击者那边偏一点点
        LivingEntity attacker = owner.getLastHurtByMob();
        Vec3 aim = owner.position();
        if (attacker != null) {
            Vec3 toAttacker = attacker.position().subtract(owner.position()).normalize().scale(1.2D);
            aim = owner.position().add(toAttacker);
        }
        this.cat.getNavigation().moveTo(aim.x, aim.y, aim.z, SPEED);
        if (attacker != null) {
            this.cat.getLookControl().setLookAt(attacker, 30.0F, 30.0F);
        }
    }

    @Override
    public void stop() {
        this.cat.getNavigation().stop();
    }
}
