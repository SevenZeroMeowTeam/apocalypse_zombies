package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.common.Tags;

/**
 * 需求驱动：她自己决定该干什么。
 *
 * <p>1.1.74 之前她的工种只能被玩家改（给工具 / 空手右键循环）。这一条让她「像玩家一样」
 * 看着自己的背包和周围环境挑活干：</p>
 *
 * <ol>
 *   <li><b>有敌人</b>且在主人身边 → 打（她看到僵尸会抄家伙，而不是继续砍树）。</li>
 *   <li><b>缺木头</b>（背包里原木不足 {@link #WANT_LOGS}）→ 伐木。</li>
 *   <li><b>缺矿</b>（背包里矿石不足 {@link #WANT_ORES}）→ 挖矿（挖到的矿石会走已有的内部熔炉）。</li>
 *   <li>都不缺 → 跟着主人。</li>
 * </ol>
 *
 * <h2>为什么它不抢执行权</h2>
 * <p>这个 Goal 不带 MOVE / LOOK 标记 —— 它只改 {@link CatGirlEntity#getJob()}，
 * 真正干活的是 {@link WorkBlockGoal} / 战斗那几条。所以「让它自己选题」和
 * 「让它去执行」是两件事，互不干扰。</p>
 *
 * <h2>手动优先</h2>
 * <p>玩家一旦自己切过工种（给工具 / 空手右键），{@code isAutoJob()} 就变成 false，
 * 这里立刻闭嘴 —— 你要它砍树时它不会自作主张跑去挖矿。用
 * {@code /apocalypse catgirl auto} 把自动模式开回来。</p>
 */
public class CatGirlNeedGoal extends Goal {

    /** 评估间隔（tick）。40 = 2 秒，够快也够安静。 */
    private static final int INTERVAL = 40;

    /** 背包里少于这么多原木就算「缺木头」。 */
    private static final int WANT_LOGS = 8;

    /** 背包里少于这么多矿石就算「缺矿」。 */
    private static final int WANT_ORES = 8;

    /** 视为「有敌人」的半径（格）。 */
    private static final double THREAT_RADIUS = 12.0D;

    private final CatGirlEntity cat;
    private int cooldown;

    public CatGirlNeedGoal(CatGirlEntity cat) {
        this.cat = cat;
        // 刻意不取 MOVE / LOOK：它只做决策，不占执行权。
    }

    @Override
    public boolean canUse() {
        return Config.CAT_GIRL_AUTO_JOB.get() && this.cat.isTame() && this.cat.isAutoJob();
    }

    @Override
    public boolean canContinueToUse() {
        return this.canUse();
    }

    @Override
    public void tick() {
        if (--this.cooldown > 0) {
            return;
        }
        this.cooldown = INTERVAL;
        this.decide();
    }

    private void decide() {
        LivingEntity owner = this.cat.getOwner();
        // 正在打人就别插手（战斗决策交给目标选择器与战斗 Goal）
        if (this.cat.getTarget() != null && this.cat.getTarget().isAlive()) {
            return;
        }
        if (owner != null && this.cat.distanceToSqr(owner) < 48.0D * 48.0D && this.threatNearby()) {
            this.cat.setJob(CatGirlEntity.Job.FIGHT);
            return;
        }
        if (this.countTag(ItemTags.LOGS) < WANT_LOGS) {
            this.cat.setJob(CatGirlEntity.Job.LUMBER);
            return;
        }
        if (this.countTag(Tags.Items.ORES) < WANT_ORES) {
            this.cat.setJob(CatGirlEntity.Job.MINE);
            return;
        }
        this.cat.setJob(CatGirlEntity.Job.FOLLOW);
    }

    /** 周围有没有敌对生物（复用她认敌的那套判据，不会把友军算进来）。 */
    private boolean threatNearby() {
        var box = this.cat.getBoundingBox().inflate(THREAT_RADIUS);
        for (LivingEntity other : this.cat.level().getEntitiesOfClass(LivingEntity.class, box)) {
            if (other.isAlive() && AllyJudge.isHorde(other)) {
                return true;
            }
        }
        return false;
    }

    private int countTag(net.minecraft.tags.TagKey<net.minecraft.world.item.Item> tag) {
        int total = 0;
        var goods = this.cat.getGoods();
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (!stack.isEmpty() && stack.is(tag)) {
                total += stack.getCount();
            }
        }
        return total;
    }
}
