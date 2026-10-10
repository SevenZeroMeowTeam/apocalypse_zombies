package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;
import java.util.List;
import java.util.function.Predicate;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlEntity.Job;

/**
 * 猫耳娘的劳作目标：找到最近的匹配方块 → 走过去 → 抡起来砸碎，产物进她的库存。
 *
 * <p>伐木与挖矿共用一套实现，差别只在构造参数：模式（{@link Job}）、方块过滤器
 * （原木 / 矿石）、动作通道（chop / mine）。加一种新工种不用再写一个 Goal。</p>
 *
 * <p><b>几个刻意的设计</b>：</p>
 * <ul>
 *   <li>索敌扫描有冷却（{@link #SCAN_INTERVAL}）—— Goal 在没运行时每 tick 都会被
 *       {@code canUse()} 问一次，全量扫 12 格半径的立体区域每 tick 都扫一遍，
 *       十几只猫耳娘就能把服务端按住。</li>
 *   <li>够不着会放弃并把该方块拉黑一小段时间（{@link #UNREACHABLE_COOLDOWN}）——
 *       否则「导航走不到 → 目标作废 → 重新选中同一个方块」会形成死循环，
 *       她会在原地反复起步，看起来像卡住了。</li>
 *   <li>破坏耗时按手持工具打折（斧对原木、镐对矿石减半）—— 让「给她一把好工具」
 *       这件事在体感上有回报，而不是只有动画好看。</li>
 * </ul>
 */
public class WorkBlockGoal extends Goal {

    /** 索敌扫描的间隔（tick）。 */
    private static final int SCAN_INTERVAL = 25;

    /** 够不到就把方块拉黑这么多 tick，防止原地打转。 */
    private static final int UNREACHABLE_COOLDOWN = 200;

    /** 导航完成却离目标还差的容忍距离（格）。 */
    private static final double REACH = 3.0D;

    /** 导航走不动超过这么多 tick 就放弃。 */
    private static final int STUCK_TICKS = 60;

    private final CatGirlEntity cat;
    private final Job job;
    private final Predicate<BlockState> filter;
    private final int action;

    private int scanCooldown;
    private BlockPos target;
    private BlockPos blacklisted;
    private int blacklistTicks;
    private int stuckTicks;
    private int workTicks;

    public WorkBlockGoal(CatGirlEntity cat, Job job, Predicate<BlockState> filter, int action) {
        this.cat = cat;
        this.job = job;
        this.filter = filter;
        this.action = action;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (this.cat.getJob() != this.job) {
            return false;
        }
        if (this.blacklistTicks > 0) {
            this.blacklistTicks--;
        }
        if (this.scanCooldown > 0) {
            this.scanCooldown--;
            return false;
        }
        this.scanCooldown = SCAN_INTERVAL;
        this.target = this.findBlock();
        return this.target != null;
    }

    @Override
    public boolean canContinueToUse() {
        if (this.cat.getJob() != this.job || this.target == null) {
            return false;
        }
        BlockState state = this.cat.level().getBlockState(this.target);
        return this.filter.test(state) && this.cat.isAlive();
    }

    @Override
    public void start() {
        this.workTicks = 0;
        this.stuckTicks = 0;
        this.cat.getNavigation().moveTo(this.target.getX() + 0.5D, this.target.getY(), this.target.getZ() + 0.5D, 1.0D);
        this.cat.setTarget(null);
    }

    @Override
    public void stop() {
        this.cat.getNavigation().stop();
        this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
        this.target = null;
    }

    @Override
    public void tick() {
        if (this.target == null) {
            return;
        }
        Vec3 center = Vec3.atCenterOf(this.target);
        this.cat.getLookControl().setLookAt(center.x, center.y, center.z, 30.0F, 30.0F);

        double distance = this.cat.position().distanceTo(center);
        if (distance > REACH) {
            // 走路阶段：让移动动画自己说话，动作通道留空
            if (this.cat.getAction() != CatGirlEntity.ACTION_NONE) {
                this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
            }
            if (this.cat.getNavigation().isDone() || this.cat.horizontalCollision) {
                this.stuckTicks++;
                // 走不动就重发一次导航（可能被卡在坎边），再不行就拉黑换目标
                if (this.stuckTicks % 20 == 0) {
                    this.cat.getNavigation().moveTo(center.x, center.y, center.z, 1.0D);
                }
                if (this.stuckTicks > STUCK_TICKS) {
                    this.blacklistAndStop();
                }
            } else {
                this.stuckTicks = 0;
            }
            return;
        }

        // 到位：停下，开砸
        this.stuckTicks = 0;
        this.cat.getNavigation().stop();
        this.cat.holdAction(this.action);
        this.workTicks++;

        if (this.workTicks >= this.breakTicks()) {
            this.breakBlock(center);
            this.workTicks = 0;
            this.target = null;
            this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
            this.scanCooldown = 6;
        }
    }

    /** 破坏耗时：基础值来自 Config，拿着对口工具打对折。 */
    private int breakTicks() {
        boolean tool = switch (this.job) {
            case LUMBER -> this.cat.getMainHandItem().is(net.minecraft.tags.ItemTags.AXES);
            case MINE -> this.cat.getMainHandItem().is(net.minecraft.tags.ItemTags.PICKAXES);
            default -> false;
        };
        int base = this.job == Job.MINE ? Config.CAT_GIRL_MINE_TICKS.get() : Config.CAT_GIRL_CHOP_TICKS.get();
        return tool ? Math.max(4, (int) (base * Config.CAT_GIRL_TOOL_SPEEDUP.get())) : base;
    }

    private void breakBlock(Vec3 center) {
        ServerLevel server = (ServerLevel) this.cat.level();
        BlockPos pos = this.target;
        BlockState state = server.getBlockState(pos);
        BlockEntity entity = server.getBlockEntity(pos);
        List<ItemStack> drops = Block.getDrops(state, server, pos, entity, this.cat, this.cat.getMainHandItem());
        if (drops.isEmpty() && state.requiresCorrectToolForDrops()
                && Config.CAT_GIRL_ALWAYS_DROPS.get()) {
            // 「无视原版规则限制」：原版卡掉落的是 playerDestroy 里的 canHarvestBlock（工具等级），
            // 不是掉落表本身 —— 这里用最高等级工具再取一次，保证她砸什么都有产物。
            ItemStack cheat = new ItemStack(this.job == Job.LUMBER
                    ? net.minecraft.world.item.Items.NETHERITE_AXE
                    : net.minecraft.world.item.Items.NETHERITE_PICKAXE);
            drops = Block.getDrops(state, server, pos, entity, this.cat, cheat);
        }
        server.destroyBlock(pos, false);
        this.cat.storeOrDrop(drops, pos);
        this.cat.playSound(net.minecraft.sounds.SoundEvents.ITEM_PICKUP, 0.5F, 1.6F);
    }

    private void blacklistAndStop() {
        this.blacklisted = this.target;
        this.blacklistTicks = UNREACHABLE_COOLDOWN;
        this.target = null;
        this.cat.getNavigation().stop();
    }

    /** 在半径内找最近的匹配方块：以她所在位置为中心扫一个立方体，向下多扫一点（矿洞场景）。 */
    private BlockPos findBlock() {
        int radius = Config.CAT_GIRL_WORK_RADIUS.get();
        BlockPos origin = this.cat.blockPosition();
        BlockPos best = null;
        double bestDistance = Double.MAX_VALUE;
        for (BlockPos pos : BlockPos.betweenClosed(
                origin.offset(-radius, -Math.min(radius, 8), -radius),
                origin.offset(radius, Math.min(radius, 6), radius))) {
            if (this.blacklistTicks > 0 && pos.equals(this.blacklisted)) {
                continue;
            }
            if (!this.filter.test(this.cat.level().getBlockState(pos))) {
                continue;
            }
            double distance = pos.distToCenterSqr(this.cat.position());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = pos.immutable();
            }
        }
        return best;
    }
}
