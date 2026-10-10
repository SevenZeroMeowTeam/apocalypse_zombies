package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.EnumSet;

/**
 * 「给她一张弓，她就远程打怪」。
 *
 * <p>成立条件：工种是打怪、主手拿着弓/弩、目标活着、有视线、距离 &gt; 3 格，
 * 并且**她自己的库存里有箭**（{@code goods} 容器，砍伐/挖矿的产出也进这里；玩家把箭交给她即入袋）。
 * 缺任一条件就轮不到它，贴脸与没箭时自动退回同层的近战目标。
 *
 * <p>箭从她库存里扣，射完为止 —— 想让她持续输出，记得给她补箭。
 */
public class CatGirlBowGoal extends Goal {

    /** 两发之间的冷却：约 1.4 秒，比玩家拉满弓略慢。 */
    private static final int COOLDOWN = 28;

    private final CatGirlEntity cat;
    private int cooldown;

    public CatGirlBowGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    private boolean holdingBow() {
        ItemStack held = this.cat.getMainHandItem();
        return held.is(Items.BOW) || held.is(Items.CROSSBOW);
    }

    private ItemStack findArrow() {
        for (int i = 0; i < this.cat.getGoods().getContainerSize(); i++) {
            ItemStack s = this.cat.getGoods().getItem(i);
            if (s.is(Items.ARROW) || s.is(Items.SPECTRAL_ARROW) || s.is(Items.TIPPED_ARROW)) {
                return s;
            }
        }
        return ItemStack.EMPTY;
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.cat.getTarget();
        if (this.cat.getJob() != CatGirlEntity.Job.FIGHT || !this.holdingBow()) {
            return false;
        }
        if (target == null || !target.isAlive() || this.cat.distanceToSqr(target) <= 9.0D) {
            return false;
        }
        return !this.findArrow().isEmpty() && this.cat.getSensing().hasLineOfSight(target);
    }

    @Override
    public boolean canContinueToUse() {
        return this.canUse();
    }

    @Override
    public void start() {
        this.cooldown = 10; // 起手稍快，之后按 COOLDOWN 走
    }

    @Override
    public boolean requiresUpdateEveryTick() {
        return true;
    }

    @Override
    public void tick() {
        LivingEntity target = this.cat.getTarget();
        if (target == null) {
            return;
        }
        this.cat.getLookControl().setLookAt(target, 30.0F, 30.0F);
        if (this.cooldown > 0) {
            this.cooldown--;
            return;
        }
        this.cooldown = COOLDOWN;

        ItemStack arrow = this.findArrow();
        if (arrow.isEmpty() || !(this.cat.level() instanceof ServerLevel level)) {
            return;
        }
        arrow.shrink(1);
        this.cat.getGoods().setChanged();

        Arrow shot = new Arrow(level, this.cat);
        double dx = target.getX() - this.cat.getX();
        double dy = target.getEyeY() - this.cat.getEyeY();
        double dz = target.getZ() - this.cat.getZ();
        double flat = Math.sqrt(dx * dx + dz * dz);
        // 抬高一点补偿重力，剩下的交给 6.0 的散布
        shot.shoot(dx, dy + flat * 0.12D, dz, 1.6F, 6.0F);
        level.addFreshEntity(shot);

        this.cat.playSound(SoundEvents.SKELETON_SHOOT, 1.0F,
                1.0F / (this.cat.getRandom().nextFloat() * 0.4F + 0.8F));
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, 9);
    }
}
