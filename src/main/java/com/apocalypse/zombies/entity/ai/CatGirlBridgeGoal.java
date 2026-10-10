package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.state.BlockState;

import java.util.EnumSet;

/**
 * 搭桥：前方是坑（深谷 / 水 / 岩浆）就用手里的方块铺一格落脚点。
 *
 * <p>这是玩家过沟最朴素的那一招，也是她的寻路唯一「算不出路」的典型场景：
 * 目标在坑对面，导航直接返回空路径，她就会原地站着。</p>
 *
 * <h2>规矩</h2>
 * <ul>
 *   <li>只用<b>她自己背包里已有的实心方块</b>，不凭空生成 —— 背包里没有就放弃（玩家也得带砖）。</li>
 *   <li>落点只铺在<b>她正前方一格的下一层</b>，不会在她脚下乱放，也不会围着她盖墙。</li>
 *   <li>不放流体/非实心/带方块实体的东西（免得她把箱子当砖垫）。</li>
 *   <li>触发条件和她卡住一致：正在导航 + 水平碰撞持续 —— 正常走路时不会乱铺路。</li>
 * </ul>
 */
public class CatGirlBridgeGoal extends Goal {

    /** 卡住多久才开始铺（比开路略短：过沟比砸墙更常见）。 */
    private static final int STUCK_TICKS = 18;

    /** 铺一格的间隔。 */
    private static final int COOLDOWN = 25;

    private final CatGirlEntity cat;
    private int stuckTicks;
    private int cooldown;

    public CatGirlBridgeGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (!Config.CAT_GIRL_BRIDGE.get() || this.cooldown > 0) {
            if (this.cooldown > 0) {
                this.cooldown--;
            }
            this.stuckTicks = 0;
            return false;
        }
        if (this.cat.getNavigation().isDone()) {
            this.stuckTicks = 0;
            return false;
        }
        if (this.cat.horizontalCollision || this.cat.getNavigation().getPath() == null) {
            this.stuckTicks++;
        } else {
            this.stuckTicks = 0;
        }
        if (this.stuckTicks < STUCK_TICKS) {
            return false;
        }
        return this.findSpot() != null && this.findBlockItem() >= 0;
    }

    @Override
    public boolean canContinueToUse() {
        return false;   // 一次性动作：铺完就退，让导航重新算路
    }

    @Override
    public void start() {
        BlockPos spot = this.findSpot();
        int slot = this.findBlockItem();
        if (spot == null || slot < 0 || !(this.cat.level() instanceof net.minecraft.server.level.ServerLevel server)) {
            this.cooldown = COOLDOWN;
            return;
        }
        ItemStack stack = this.cat.getGoods().getItem(slot);
        BlockState state = ((BlockItem) stack.getItem()).getBlock().defaultBlockState();
        if (!state.canSurvive(server, spot)) {
            this.cooldown = COOLDOWN;
            return;
        }
        server.setBlockAndUpdate(spot, state);
        server.playSound(null, spot, state.getSoundType().getPlaceSound(), SoundSource.BLOCKS, 1.0F, 0.85F);
        this.cat.swing(net.minecraft.world.InteractionHand.MAIN_HAND, true);
        stack.shrink(1);
        this.cat.getGoods().setChanged();
        this.cat.getNavigation().stop();
        // 记住这一格，别在同一处反复铺（导航可能仍旧算不出路）
        this.cooldown = COOLDOWN;
        this.stuckTicks = 0;
    }

    @Override
    public void stop() {
        this.stuckTicks = 0;
    }

    /** 正前方那一格的下一层：空的（或流体）就值得铺。 */
    private BlockPos findSpot() {
        Direction dir = this.cat.getDirection();
        BlockPos feet = this.cat.blockPosition();
        BlockPos frontFeet = feet.relative(dir);
        BlockPos frontHead = frontFeet.above();
        var level = this.cat.level();
        // 前方两格得是她能过的地方，否则那是「墙」，归开路管
        if (!level.getBlockState(frontFeet).canBeReplaced() || !level.getBlockState(frontHead).canBeReplaced()) {
            return null;
        }
        BlockPos spot = frontFeet.below();
        BlockState there = level.getBlockState(spot);
        boolean hasFloor = there.isSolid() && there.getFluidState().isEmpty()
                && there.getCollisionShape(level, spot).isEmpty() == false
                && !there.canBeReplaced();
        return hasFloor ? null : spot.immutable();
    }

    /** 背包里第一个「实心、非方块实体」的方块物品槽位，没有回 -1。 */
    private int findBlockItem() {
        var goods = this.cat.getGoods();
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (stack.isEmpty() || !(stack.getItem() instanceof BlockItem blockItem)) {
                continue;
            }
            BlockState state = blockItem.getBlock().defaultBlockState();
            if (state.hasBlockEntity() || !state.isSolid() || state.canBeReplaced()) {
                continue;
            }
            return i;
        }
        return -1;
    }
}
