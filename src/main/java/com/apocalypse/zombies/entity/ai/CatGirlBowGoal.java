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
 * 「给她一张弓，她就远程打怪」—— **完整蓄力**版。
 *
 * <p>弓：拉满 20 tick（原版弓的满弦时间）才放，箭速按满蓄力 3.0 出手；
 * 弩：装填 25 tick（原版弩的装填时间）才放，箭速 3.15。放完歇 6 tick 再来一轮。
 * 也就是说她的节奏和玩家拉弓/装弩一致，不是「无脑连发」。</p>
 *
 * <p>成立条件：工种是打怪、主手拿着弓/弩、目标活着、有视线、距离 &gt; 3 格，
 * 并且**她自己的库存里有箭**（{@code goods}；玩家把箭交给她即入袋）。缺任一条件就轮不到它，
 * 贴脸与没箭时自动退回同层的近战目标。</p>
 */
public class CatGirlBowGoal extends Goal {

    /** 弓：满弦时间（tick），与原版一致。 */
    private static final int BOW_DRAW = 20;
    /** 弩：装填时间（tick），与原版一致。 */
    private static final int CROSSBOW_LOAD = 25;
    /** 放完这一轮后歇几 tick 再开始下一轮。 */
    private static final int RELOAD_GAP = 6;

    /** 满蓄力箭速（原版弓满弦是 3.0，弩是 3.15）。 */
    private static final float BOW_SPEED = 3.0F;
    private static final float CROSSBOW_SPEED = 3.15F;

    private final CatGirlEntity cat;
    /** 本轮蓄力剩余 tick；<=0 表示该出手了。 */
    private int charge;
    private boolean crossbow;

    public CatGirlBowGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    private boolean isCrossbow() {
        return this.cat.getMainHandItem().is(Items.CROSSBOW);
    }

    private boolean holdingRanged() {
        ItemStack held = this.cat.getMainHandItem();
        return held.is(Items.BOW) || held.is(Items.CROSSBOW);
    }

    /** 蓄力时长：弩 25 tick，弓 20 tick。 */
    private int drawTime() {
        return this.crossbow ? CROSSBOW_LOAD : BOW_DRAW;
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
        if (this.cat.getJob() != CatGirlEntity.Job.FIGHT || !this.holdingRanged()) {
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
        this.crossbow = this.isCrossbow();
        this.charge = this.drawTime();
        // 蓄力期间抬臂：用攻击动作占位，看起来就是在拉弓/端弩
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, this.charge);
    }

    @Override
    public void stop() {
        this.charge = 0;
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
        this.cat.getNavigation().stop(); // 站定蓄力，别边走边放

        if (this.charge > 0) {
            this.charge--;
            return;
        }
        this.fire(target);
        this.charge = RELOAD_GAP + this.drawTime();
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, this.drawTime());
    }

    /** 满蓄力出手：扣一支箭，按弓/弩各自的满蓄力箭速射出去。 */
    private void fire(LivingEntity target) {
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
        // 满蓄力：抬一点点补偿重力，散布按满弦收紧（弓 1.0 / 弩 0.6）
        float speed = this.crossbow ? CROSSBOW_SPEED : BOW_SPEED;
        float spread = this.crossbow ? 0.6F : 1.0F;
        shot.shoot(dx, dy + flat * 0.12D, dz, speed, spread);
        level.addFreshEntity(shot);

        this.cat.playSound(this.crossbow ? SoundEvents.CROSSBOW_SHOOT : SoundEvents.ARROW_SHOOT,
                1.0F, 1.0F / (this.cat.getRandom().nextFloat() * 0.4F + 0.8F));
    }
}
