package com.apocalypse.zombies.entity.ai;

import java.util.List;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.phys.AABB;

/**
 * 村民的日常杂活：随手关门、白天开门、收成熟的庄稼并补种。
 *
 * <p><b>为什么是静态工具、不是 Goal</b>：村民的日程走 {@code Brain} 的活动系统
 * （{@code WORK} / {@code IDLE} / {@code PANIC} …），移动由 {@code MoveToTargetSink} 下发，
 * 自己挂的 {@code Goal} 会和它抢 {@code Flag.MOVE}。而这两件事都<b>不需要移动</b> ——
 * 站在原地看着附近就能干完。所以走 {@link com.apocalypse.zombies.event.MobAiEnhanced}
 * 里村民 tick 那一支，与「恐慌 + 呼救铁傀儡」同一节奏，顺便复用它的节流与相位打散。</p>
 *
 * <p><b>开销</b>：一轮是一条 {@code radius × 5 × radius} 的方块带（y 只上下探 2 格 ——
 * 门与庄稼都在地面附近，扫整个立方体纯属浪费）。按 {@code ai_enhance.villager_interval}
 * （默认 20 tick）跑一次、并按实体 id 打散相位，所以同屏 N 个村民摊到每 tick 上是 N/20 轮；
 * 默认半径 6 时单轮约 845 格。</p>
 */
public final class VillagerChores {

    /** 门被「夹住」的距离：这个范围内有活物就不动手，免得把谁夹在门里。 */
    private static final double DOOR_CLEARANCE = 1.5D;

    private VillagerChores() {
    }

    /**
     * 跑一轮杂活。调用方（村民 tick）已经做过开关判断、节流与相位打散。
     *
     * @param radius 作用半径（格）
     * @param doors  是否管门（白天开 / 夜里关）
     * @param farm   是否管庄稼（收成熟 + 补种）
     */
    public static void run(Villager villager, int radius, boolean doors, boolean farm) {
        if (!(villager.level() instanceof ServerLevel level) || !villager.isAlive()) {
            return;
        }
        BlockPos center = villager.blockPosition();
        BlockPos from = center.offset(-radius, -2, -radius);
        BlockPos to = center.offset(radius, 2, radius);
        for (BlockPos pos : BlockPos.betweenClosed(from, to)) {
            BlockState state = level.getBlockState(pos);
            if (doors && state.getBlock() instanceof DoorBlock) {
                tendDoor(level, pos, state);
            } else if (farm && state.getBlock() instanceof CropBlock crop) {
                harvest(level, pos, state, crop, villager);
            }
        }
    }

    /**
     * 白天把门打开、夜里关上；门边有活物时这一轮不动它。
     *
     * <p>只碰木门 —— 铁门是玩家上锁用的，村民本来也开不了，替它开等于绕过门禁。</p>
     */
    private static void tendDoor(ServerLevel level, BlockPos pos, BlockState state) {
        if (state.getBlock() == Blocks.IRON_DOOR) {
            return;
        }
        boolean wantOpen = level.isDay();
        if (state.getValue(DoorBlock.OPEN) == wantOpen) {
            return;
        }
        if (!level.getEntities((Entity) null, new AABB(pos).inflate(DOOR_CLEARANCE)).isEmpty()) {
            return;
        }
        setDoor(level, pos, state, wantOpen);
    }

    /**
     * 门是上下两半，而 {@code setBlock} <b>不会</b>像玩家交互那样联动另一半 ——
     * 只改一半会得到一扇错开的门，所以这里手动同步。
     */
    private static void setDoor(ServerLevel level, BlockPos pos, BlockState state, boolean open) {
        level.setBlock(pos, state.setValue(DoorBlock.OPEN, open), 10);
        BlockPos other = state.getValue(DoorBlock.HALF) == DoubleBlockHalf.LOWER
                ? pos.above() : pos.below();
        BlockState otherState = level.getBlockState(other);
        if (otherState.getBlock() == state.getBlock()
                && otherState.getValue(DoorBlock.OPEN) != open) {
            level.setBlock(other, otherState.setValue(DoorBlock.OPEN, open), 10);
        }
    }

    /**
     * 收成熟的那一格：<b>先用一颗当种子补上</b>，其余进村民背包（背包装不下就丢在脚边）。
     *
     * <p>顺序与原版农民一致 —— 先补种再收走，所以不会出现「收完了地空着」。</p>
     */
    private static void harvest(ServerLevel level, BlockPos pos, BlockState state,
                                CropBlock crop, Villager villager) {
        if (!crop.isMaxAge(state)) {
            return;
        }
        Item seed = seedOf(state.getBlock());
        List<ItemStack> drops = Block.getDrops(state, level, pos, null, villager,
                villager.getMainHandItem());
        level.destroyBlock(pos, false, villager);      // false：掉落我们自己发，免得发两份
        boolean replanted = false;
        for (ItemStack drop : drops) {
            if (drop.isEmpty()) {
                continue;
            }
            if (!replanted && drop.getItem() == seed) {
                ItemStack rest = drop.copy();
                rest.shrink(1);                        // 留一颗当种子
                level.setBlock(pos, crop.defaultBlockState(), 3);
                replanted = true;
                if (!rest.isEmpty()) {
                    store(villager, rest);
                }
                continue;
            }
            store(villager, drop);
        }
        if (!replanted) {
            // 没掉出种子（例如满熟时被别的模组拦了掉落）也得补上，不然这块地就废了
            level.setBlock(pos, crop.defaultBlockState(), 3);
        }
    }

    /** 收进村民背包；满了就丢在脚边 —— 别让作物凭空蒸发。 */
    private static void store(Villager villager, ItemStack stack) {
        ItemStack left = villager.getInventory().addItem(stack.copy());
        if (!left.isEmpty()) {
            Block.popResource(villager.level(), villager.blockPosition().above(), left);
        }
    }

    /**
     * 这四种原版作物「能再种下去的东西」是什么。
     *
     * <p>小麦与甜菜收上来的是种子，胡萝卜与马铃薯收上来的是自己 —— 写死这四种而不是去问
     * {@code CropBlock}，是因为它的 {@code getBaseSeedId()} 在 1.20.1 上不对外，而本模组
     * 也没有自己注册的作物。</p>
     */
    private static Item seedOf(Block block) {
        if (block == Blocks.WHEAT) {
            return Items.WHEAT_SEEDS;
        }
        if (block == Blocks.CARROTS) {
            return Items.CARROT;
        }
        if (block == Blocks.POTATOES) {
            return Items.POTATO;
        }
        if (block == Blocks.BEETROOTS) {
            return Items.BEETROOT_SEEDS;
        }
        return null;
    }
}
