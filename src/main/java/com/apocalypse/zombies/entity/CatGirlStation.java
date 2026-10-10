package com.apocalypse.zombies.entity;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * 猫耳娘的「工作方块」：合成去合成台、熔炼去熔炉。
 *
 * <p>三种能力：<b>找</b>（就近扫描，带缓存，见 {@link CatGirlEntity#stationNear}）、
 * <b>做</b>（她真缺材料时按配方自己做，走 {@code CatGirlCrafting}）、
 * <b>放</b>（放到她脚边，只认可替换的位置）。</p>
 *
 * <p><b>放置的安全边界</b>（和开路/垫脚同一套约定）：只放在
 * {@code canBeReplaced()} 的位置（草 / 雪 / 空气），下面必须有实心支撑，
 * 位置本身不能有方块实体，也绝不放流体 —— 她不会为了一个工作台拆主人的房子。</p>
 */
public final class CatGirlStation {

    public enum Kind {
        NONE,
        CRAFTING_TABLE,
        FURNACE
    }

    private CatGirlStation() {
    }

    /** 这个方块是不是她要找的工作方块（熔炉类含高炉 / 烟熏炉）。 */
    public static Kind of(BlockState state) {
        if (state.is(Blocks.CRAFTING_TABLE)) {
            return Kind.CRAFTING_TABLE;
        }
        if (state.is(Blocks.FURNACE) || state.is(Blocks.BLAST_FURNACE) || state.is(Blocks.SMOKER)) {
            return Kind.FURNACE;
        }
        return Kind.NONE;
    }

    /** 这一类工作方块的「物品形态」（她放下去用的东西）。 */
    public static ItemStack itemFor(Kind kind) {
        return switch (kind) {
            case CRAFTING_TABLE -> new ItemStack(Items.CRAFTING_TABLE);
            case FURNACE -> new ItemStack(Items.FURNACE);
            default -> ItemStack.EMPTY;
        };
    }

    public static boolean matches(LevelReader level, BlockPos pos, Kind kind) {
        return kind != Kind.NONE && of(level.getBlockState(pos)) == kind;
    }

    /**
     * 就近扫一个工作方块（以她为中心的立方体，上下各放宽一点，因为她可能站在矿洞里）。
     *
     * <p>这个方法每次调用都是全量扫描，所以调用方一律走
     * {@link CatGirlEntity#stationNear}（带 60 tick 缓存）—— Goal 的 {@code canUse}
     * 是每 tick 都会被问的，直接扫会出事。</p>
     */
    public static BlockPos findNear(CatGirlEntity cat, Kind kind, int radius) {
        if (kind == Kind.NONE) {
            return null;
        }
        LevelReader level = cat.level();
        BlockPos origin = cat.blockPosition();
        int ry = Math.min(radius, 8);
        BlockPos best = null;
        double bestDistance = Double.MAX_VALUE;
        for (BlockPos pos : BlockPos.betweenClosed(
                origin.offset(-radius, -ry, -radius), origin.offset(radius, ry, radius))) {
            if (!matches(level, pos, kind)) {
                continue;
            }
            double distance = pos.distToCenterSqr(cat.position());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = pos.immutable();
            }
        }
        return best;
    }

    /**
     * 把工作方块放到她脚边 —— 只认可替换位置 + 实心支撑，放成功返回放下的坐标。
     *
     * <p>就地放而不是「找地方放」：她刚做完合成台就该能用上，多一段导航只会多一段失败。</p>
     */
    public static BlockPos placeNear(CatGirlEntity cat, Kind kind) {
        if (!(cat.level() instanceof ServerLevel level)) {
            return null;
        }
        ItemStack item = itemFor(kind);
        if (item.isEmpty() || !cat.hasGoodsMatching(stack -> stack.is(item.getItem()))) {
            return null;
        }
        BlockState place = kind == Kind.CRAFTING_TABLE
                ? Blocks.CRAFTING_TABLE.defaultBlockState()
                : Blocks.FURNACE.defaultBlockState();
        BlockPos base = cat.blockPosition();
        for (int dy : new int[]{0, -1}) {
            for (Direction side : Direction.Plane.HORIZONTAL) {
                BlockPos pos = base.relative(side).offset(0, dy, 0);
                BlockState at = level.getBlockState(pos);
                if (!at.canBeReplaced() || at.hasBlockEntity()) {
                    continue;
                }
                if (!level.getFluidState(pos).isEmpty()) {
                    continue;
                }
                BlockPos below = pos.below();
                if (!level.getBlockState(below).isFaceSturdy(level, below, Direction.UP)) {
                    continue;
                }
                if (!cat.consumeOneMatching(stack -> stack.is(item.getItem()))) {
                    return null;
                }
                level.setBlockAndUpdate(pos, place);
                cat.playSound(SoundEvents.WOOD_PLACE, 0.8F, 1.0F);
                return pos.immutable();
            }
        }
        return null;
    }
}
