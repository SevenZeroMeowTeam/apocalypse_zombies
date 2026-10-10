package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;
import java.util.function.BooleanSupplier;
import java.util.function.Predicate;

import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlEntity.Job;
import com.apocalypse.zombies.entity.CatGirlHarvest;

/**
 * 猫耳娘的劳作目标：找到最近的匹配方块 → 走过去 → 抡起来砸碎，产物进她的库存。
 *
 * <p>伐木、挖矿、以及主人点名的「一键挖掘」共用这一套实现，差别只在构造参数：
 * 模式（{@link Job}）、方块过滤器、动作通道（chop / mine）、以及一个可选的额外门槛
 * （{@code gate}，一键挖掘用它兜住「订单还在不在」）。加一种新工种不用再写一个 Goal。</p>
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
    private final Predicate<BlockPos> filter;
    private final int action;
    /** 额外门槛：返回 false 时这个目标整个不成立（默认没有门槛）。 */
    private final BooleanSupplier gate;
    /** 是不是「一键挖掘」订单目标（决定产出记账）。 */
    private final boolean orderMode;

    private int scanCooldown;
    private BlockPos target;
    private BlockPos blacklisted;
    private int blacklistTicks;
    private int stuckTicks;
    private int workTicks;

    public WorkBlockGoal(CatGirlEntity cat, Job job, Predicate<BlockPos> filter, int action) {
        this(cat, job, filter, action, () -> true, false);
    }

    public WorkBlockGoal(CatGirlEntity cat, Job job, Predicate<BlockPos> filter, int action, BooleanSupplier gate) {
        this(cat, job, filter, action, gate, false);
    }

    private WorkBlockGoal(CatGirlEntity cat, Job job, Predicate<BlockPos> filter, int action,
            BooleanSupplier gate, boolean orderMode) {
        this.cat = cat;
        this.job = job;
        this.filter = filter;
        this.action = action;
        this.gate = gate;
        this.orderMode = orderMode;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    /**
     * 一键挖掘订单专用的构造：订单挖满或被撤掉，这个目标立刻不成立
     * —— 订单没了就该回到自主挖矿 / 别的活，而不是继续扫方块。
     */
    public static WorkBlockGoal forOrder(CatGirlEntity cat, Predicate<BlockPos> filter, int action) {
        return new WorkBlockGoal(cat, Job.MINE, filter, action, cat::hasMineOrder, true);
    }

    @Override
    public boolean canUse() {
        if (this.cat.getJob() != this.job || !this.gate.getAsBoolean()) {
            return false;
        }
        // 主人跑远了先跟人：她是随从，不该为了砍树把主人丢在地图另一头。
        net.minecraft.world.entity.LivingEntity owner = this.cat.getOwner();
        if (owner != null) {
            double leash = Config.CAT_GIRL_AUTONOMY_RADIUS.get();
            if (this.cat.distanceToSqr(owner) > leash * leash) {
                return false;
            }
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
        if (this.cat.getJob() != this.job || this.target == null || !this.gate.getAsBoolean()) {
            return false;
        }
        return this.filter.test(this.target) && this.cat.isAlive();
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
            this.breakBlock();
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

    private void breakBlock() {
        BlockPos pos = this.target;
        BlockState state = this.cat.level().getBlockState(pos);
        // 掉落 + 换对口工具 + 收进库存，统一在 CatGirlHarvest 里做（全功能工具的唯一出口）。
        // 注意：破坏后方块已变空气，filter 会立刻失败，所以记账必须在这里、破坏之前判断。
        if (!CatGirlHarvest.breakAndCollect(this.cat, pos, state2 -> this.filter.test(pos))) {
            return;
        }
        if (this.orderMode) {
            this.cat.minedOne(state);
        }
    }

    private void blacklistAndStop() {
        this.blacklisted = this.target;
        this.blacklistTicks = UNREACHABLE_COOLDOWN;
        this.target = null;
        this.cat.getNavigation().stop();
    }

    /** 在半径内找最近的匹配方块：以她所在位置为中心扫一个立方体，向下多扫一点（矿洞场景）。 */
    private BlockPos findBlock() {
        // 取两者较大的那个：老存档里 work_radius 还是 12，光靠它她走不出院子。
        // mine_radius（配置里的「范围」）既管自主挖矿也管一键挖掘订单。
        int radius = Math.max(Config.CAT_GIRL_MINE_RADIUS.get(), Config.CAT_GIRL_WORK_RADIUS.get());
        BlockPos origin = this.cat.blockPosition();
        BlockPos best = null;
        double bestDistance = Double.MAX_VALUE;
        for (BlockPos pos : BlockPos.betweenClosed(
                origin.offset(-radius, -Math.min(radius, 8), -radius),
                origin.offset(radius, Math.min(radius, 6), radius))) {
            if (this.blacklistTicks > 0 && pos.equals(this.blacklisted)) {
                continue;
            }
            if (!this.filter.test(pos)) {
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
