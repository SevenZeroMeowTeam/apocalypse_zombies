package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

import java.util.EnumSet;

/**
 * 开路：挡路就砸掉。
 *
 * <p>没有这一步，她的表现是「撞墙 3 秒后把目标拉黑换下一个」—— 看起来像她在挑活儿，
 * 其实是导航过不去。玩家的做法很朴素：挡路的挖掉。这里就照着做。</p>
 *
 * <h2>边界（这条决定她会不会拆家）</h2>
 * <ul>
 *   <li>只砸<b>白名单里的自然方块</b>：原木 / 树叶 / 土 / 沙 / 圆石类岩石 / 砂砾。
 *       石头建筑也是石头，判断不了「这是玩家盖的」，所以白名单之外一律不碰。</li>
 *   <li>不碰任何<b>带方块实体</b>的方块（箱子 / 熔炉 / 工作台 / 告示牌 …），也不碰门。</li>
 *   <li>硬度上限 {@link #MAX_HARDNESS}：黑曜石/远古残骸这类她砸不动，别浪费她时间。</li>
 *   <li>只在<b>她确实卡住</b>（水平碰撞持续 {@link #STUCK_TICKS} tick 以上、且正在导航）时才动手，
 *       不是见树就砍 —— 那归 {@link WorkBlockGoal}。</li>
 * </ul>
 *
 * <p>产出照旧走 {@link CatGirlEntity#harvestBlockHard}：和伐木/挖矿同一套掉落规则
 * （含 {@code always_drops}），所以「她挖什么都有产物」这条不会被开路行为绕过去。</p>
 */
public class CatGirlClearWayGoal extends Goal {

    /** 水平碰撞持续这么多 tick 才算卡住（太短会和正常走路时的贴墙摩擦混淆）。 */
    private static final int STUCK_TICKS = 25;

    /** 单次开路行为的间隔，避免在同一个门口反复起手。 */
    private static final int COOLDOWN = 20;

    /** 硬度上限：超过就不砸（黑曜石 50 / 远古残骸 30 都在这之上）。 */
    private static final float MAX_HARDNESS = 3.0F;

    private final CatGirlEntity cat;
    private int stuckTicks;
    private int cooldown;
    private BlockPos breaking;
    private int breakTicks;

    public CatGirlClearWayGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (!Config.CAT_GIRL_CLEAR_WAY.get() || this.cooldown > 0) {
            if (this.cooldown > 0) {
                this.cooldown--;
            }
            this.stuckTicks = 0;
            return false;
        }
        // 只在「她有个想去的地方、但走不动」时介入
        if (this.cat.getNavigation().isDone()) {
            this.stuckTicks = 0;
            return false;
        }
        if (this.cat.horizontalCollision) {
            this.stuckTicks++;
        } else {
            this.stuckTicks = 0;
        }
        if (this.stuckTicks < STUCK_TICKS) {
            return false;
        }
        this.breaking = this.findBlocker();
        return this.breaking != null;
    }

    @Override
    public boolean canContinueToUse() {
        return this.breaking != null && Config.CAT_GIRL_CLEAR_WAY.get()
                && breakable(this.cat.level().getBlockState(this.breaking));
    }

    @Override
    public void start() {
        this.breakTicks = 0;
        this.cat.getNavigation().stop();
    }

    @Override
    public void stop() {
        this.breaking = null;
        this.stuckTicks = 0;
        this.cooldown = COOLDOWN;
        this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
    }

    @Override
    public void tick() {
        if (this.breaking == null) {
            return;
        }
        var center = net.minecraft.world.phys.Vec3.atCenterOf(this.breaking);
        this.cat.getLookControl().setLookAt(center.x, center.y, center.z, 30.0F, 30.0F);
        this.cat.holdAction(this.cat.getJob() == CatGirlEntity.Job.LUMBER
                ? CatGirlEntity.ACTION_CHOP : CatGirlEntity.ACTION_MINE);

        if (++this.breakTicks >= this.breakTicksNeeded()) {
            BlockPos pos = this.breaking;
            this.cat.getNavigation().stop();
            this.cat.harvestBlockHard(pos, this.cat.getMainHandItem().is(net.minecraft.tags.ItemTags.AXES));
            this.breaking = null;
            this.cat.setAction(CatGirlEntity.ACTION_NONE, 0);
        }
    }

    /** 挡路方块用对口工具砸得快一点，和伐木/挖矿同一套「给好工具有回报」的直觉。 */
    private int breakTicksNeeded() {
        boolean tool = this.cat.getMainHandItem().is(net.minecraft.tags.ItemTags.PICKAXES)
                || this.cat.getMainHandItem().is(net.minecraft.tags.ItemTags.AXES);
        return tool ? 20 : 45;
    }

    /** 她正前方（含头上一格）的第一个可砸方块。 */
    private BlockPos findBlocker() {
        Direction dir = this.cat.getDirection();
        BlockPos feet = this.cat.blockPosition();
        BlockPos[] candidates = {
                feet.relative(dir),            // 脚那层的正前方
                feet.relative(dir).above(),    // 头那层的正前方
                feet.above().relative(dir),
        };
        for (BlockPos pos : candidates) {
            if (breakable(this.cat.level().getBlockState(pos))) {
                return pos.immutable();
            }
        }
        return null;
    }

    /** 白名单 + 无方块实体 + 硬度上限。 */
    private static boolean breakable(BlockState state) {
        if (state.isAir() || state.hasBlockEntity()) {
            return false;
        }
        if (state.getBlock().defaultDestroyTime() < 0.0F
                || state.getBlock().defaultDestroyTime() > MAX_HARDNESS) {
            return false;
        }
        return state.is(BlockTags.LOGS)
                || state.is(BlockTags.LEAVES)
                || state.is(BlockTags.DIRT)
                || state.is(BlockTags.SAND)
                || state.is(BlockTags.BASE_STONE_OVERWORLD)
                || state.is(Blocks.GRAVEL)
                || state.is(Blocks.CLAY)
                || state.is(BlockTags.REPLACEABLE_BY_TREES)
                || state.is(BlockTags.TALL_FLOWERS)
                || state.is(BlockTags.SMALL_FLOWERS)
                || state.is(Blocks.SNOW_BLOCK)
                || state.is(Blocks.SNOW);
    }
}
