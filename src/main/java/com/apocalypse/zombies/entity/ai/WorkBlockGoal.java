package com.apocalypse.zombies.entity.ai;

import java.util.ArrayDeque;
import java.util.EnumSet;
import java.util.function.BooleanSupplier;
import java.util.function.Predicate;

import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
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
 *   <li><b>不垂直下挖</b>：目标只在「她的脚层上下各一小段」里找（向下 {@code mine_depth}，
 *       默认 1 格），而且**她站着那一格的正下方永远不选** —— 她不会挖穿自己的地板掉进自挖竖井。
 *       想看老行为（一路往下钻）就把 {@code mine_depth} 调到 8。</li>
 *   <li><b>探矿</b>：附近一时没矿可挖时，她按 {@link #PROSPECT_INTERVAL} 的节奏走到周围
 *       没探过的位置转一圈（{@code prospect} 开关 + {@code prospect_tries} 次数上限），
 *       而不是原地刨地或往下打洞；连着几个探点都空手就回主人身边待命，过一会儿再出门。</li>
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

    /** 目标最多比她高几格（树冠 / 头顶的矿脉；再高导航也上不去）。 */
    private static final int SCAN_UP = 4;

    /** 探矿：记住多少个探点防打转。 */
    private static final int VISITED_KEEP = 12;

    /** 探矿：两个探点之间至少隔这么多 tick 再选下一个。 */
    private static final int PROSPECT_INTERVAL = 40;

    /** 空手太久（tick）就把探矿次数清零，允许她再出去转一圈。 */
    private static final int DRY_RESET_TICKS = 1200;

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

    /** 当前目标是探点（走过去看看）而不是待砸的方块。 */
    private boolean prospecting;
    /** 这一轮已经走了几个探点（找到活就清零）。 */
    private int prospectTries;
    /** 这一轮第一次空手是什么时候（过 {@link #DRY_RESET_TICKS} 再允许探矿）。 */
    private long drySince;
    /** 最近探过的位置（先进先出，防在同一片地来回走）。 */
    private final ArrayDeque<BlockPos> visited = new ArrayDeque<>();

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
        LivingEntity owner = this.cat.getOwner();
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
        if (this.target != null) {
            // 找到活了：空手的账清掉，探矿次数归零
            this.prospecting = false;
            this.prospectTries = 0;
            this.drySince = 0L;
            return true;
        }
        this.target = this.pickProspect();
        this.prospecting = this.target != null;
        return this.target != null;
    }

    @Override
    public boolean canContinueToUse() {
        if (this.cat.getJob() != this.job || this.target == null || !this.gate.getAsBoolean()) {
            return false;
        }
        if (this.prospecting) {
            // 探点不是方块，别拿 filter 去验它
            return this.cat.isAlive();
        }
        return this.filter.test(this.target) && this.cat.isAlive();
    }

    @Override
    public void start() {
        this.workTicks = 0;
        this.stuckTicks = 0;
        this.cat.getNavigation().moveTo(this.target.getX() + 0.5D, this.target.getY(), this.target.getZ() + 0.5D, 1.0D);
        this.cat.setTarget(null);
        if (this.prospecting) {
            // 探矿不砸方块：动作通道留空，让走路动画自己说话
            this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
        }
    }

    @Override
    public void stop() {
        this.cat.getNavigation().stop();
        this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
        this.target = null;
        this.prospecting = false;
    }

    @Override
    public void tick() {
        if (this.target == null) {
            return;
        }
        Vec3 center = Vec3.atCenterOf(this.target);
        this.cat.getLookControl().setLookAt(center.x, center.y, center.z, 30.0F, 30.0F);

        if (this.prospecting) {
            this.tickProspect(center);
            return;
        }

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

    /**
     * 在半径内找最近的匹配方块。
     *
     * <p>垂直窗口 = 向下 {@code mine_depth}（订单用 {@code mine_order_depth}）、向上 {@link #SCAN_UP}。
     * 向下收得这么窄是刻意的：原来向下扫 8 格，她会一路挖脚下的土/矿往下钻、掉进自己挖的竖井里继续挖。
     * 另外**她站着那一格的正下方永远跳过** —— 那是她的地板，砸了就是自己给自己挖坑。</p>
     */
    private BlockPos findBlock() {
        // 取两者较大的那个：老存档里 work_radius 还是 12，光靠它她走不出院子。
        // mine_radius（配置里的「范围」）既管自主挖矿也管一键挖掘订单。
        int radius = Math.max(Config.CAT_GIRL_MINE_RADIUS.get(), Config.CAT_GIRL_WORK_RADIUS.get());
        int down = this.orderMode ? Config.CAT_GIRL_MINE_ORDER_DEPTH.get() : Config.CAT_GIRL_MINE_DEPTH.get();
        down = Mth.clamp(down, 0, radius);
        int up = Math.min(SCAN_UP, radius);
        BlockPos origin = this.cat.blockPosition();
        BlockPos floor = origin.below();
        BlockPos best = null;
        double bestDistance = Double.MAX_VALUE;
        for (BlockPos pos : BlockPos.betweenClosed(
                origin.offset(-radius, -down, -radius),
                origin.offset(radius, up, radius))) {
            if (pos.equals(floor)) {
                continue; // 绝不砸自己脚下那一格：那是唯一会让她掉下去的方块
            }
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

    /**
     * 选一个探点：在她 {@code mine_radius} 内随机取一个方向 + 距离，落到地表，
     * 且不离开主人超过 {@code autonomy_radius}；最近探过的位置跳过（防原地打转）。
     *
     * <p>返回 null = 这轮不探了（开关关了 / 是订单 / 已经探够 {@code prospect_tries} 次）。</p>
     */
    private BlockPos pickProspect() {
        if (this.orderMode || !Config.CAT_GIRL_PROSPECT.get()) {
            return null;
        }
        int maxTries = Config.CAT_GIRL_PROSPECT_TRIES.get();
        long now = this.cat.level().getGameTime();
        if (this.prospectTries >= maxTries) {
            if (this.drySince == 0L || now - this.drySince < DRY_RESET_TICKS) {
                return null; // 探够了：先回主人身边待命，过一会儿再出门
            }
            this.prospectTries = 0;
            this.drySince = 0L;
            this.visited.clear();
        }
        int radius = Math.max(Config.CAT_GIRL_MINE_RADIUS.get(), Config.CAT_GIRL_WORK_RADIUS.get());
        int step = Math.min(Config.CAT_GIRL_PROSPECT_STEP.get(), radius);
        LivingEntity owner = this.cat.getOwner();
        double leash = Config.CAT_GIRL_AUTONOMY_RADIUS.get();
        int here = this.cat.blockPosition().getY();
        for (int attempt = 0; attempt < 16; attempt++) {
            double angle = this.cat.getRandom().nextDouble() * Math.PI * 2.0D;
            double dist = step + this.cat.getRandom().nextDouble() * Math.max(1, radius - step);
            int x = Mth.floor(this.cat.getX() + Math.cos(angle) * dist);
            int z = Mth.floor(this.cat.getZ() + Math.sin(angle) * dist);
            if (owner != null && owner.distanceToSqr(x + 0.5D, owner.getY(), z + 0.5D) > leash * leash) {
                continue; // 不许为了探矿走离主人太远
            }
            BlockPos spot = this.cat.level().getHeightmapPos(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    new BlockPos(x, 0, z));
            if (Math.abs(spot.getY() - here) > 6) {
                continue; // 山顶 / 悬崖底够不着，别浪费这一趟
            }
            if (!this.cat.level().getBlockState(spot).isAir()) {
                continue; // 地表不是空的（水 / 树叶 / 岩浆），站不住
            }
            if (this.visited.contains(spot)) {
                continue;
            }
            this.visited.addFirst(spot);
            while (this.visited.size() > VISITED_KEEP) {
                this.visited.removeLast();
            }
            this.prospectTries++;
            if (this.drySince == 0L) {
                this.drySince = now;
            }
            return spot;
        }
        return null;
    }

    /** 探点：只走过去，不砸方块；到了 / 走不动了就记一笔，回去重扫。 */
    private void tickProspect(Vec3 center) {
        double distance = this.cat.position().distanceTo(center);
        boolean walking = !this.cat.getNavigation().isDone() && distance > REACH;
        if (walking && this.cat.horizontalCollision) {
            this.stuckTicks++;
        } else if (walking) {
            this.stuckTicks = 0;
        }
        if (distance <= REACH || this.cat.getNavigation().isDone() || this.stuckTicks > STUCK_TICKS) {
            this.cat.getNavigation().stop();
            this.target = null;
            this.prospecting = false;
            this.stuckTicks = 0;
            this.scanCooldown = PROSPECT_INTERVAL;
        }
    }
}
