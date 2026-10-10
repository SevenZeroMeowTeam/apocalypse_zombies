package com.apocalypse.zombies.entity;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.function.Predicate;

import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.BaseFireBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LiquidBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;

import com.apocalypse.zombies.Config;

/**
 * 猫耳娘的「全功能工具」：一套共用的掉落 / 可挖判定。
 *
 * <p><b>为什么要有这个类：</b>原版里「砸得下来」和「有产物」是两件事 ——
 * {@code playerDestroy} 卡工具等级，掉落表里的 {@code match_tool} 卡工具**类型**
 * （斧砍树、锹挖土、剪刀剪叶）。她手上只有一把镐，于是「全功能镐」不能只靠高等级兜底，
 * 还得按方块**该用的工具**去取掉落：这就是 {@link #dropTool} 干的事。</p>
 *
 * <p><b>安全边界</b>（沿用 1.1.7x 的约定）：保护名单（基岩 / 屏障 / 命令方块 / 传送门 /
 * 刷怪笼 …，可用 {@code cat_girl.mine_protected} 追加）、带方块实体的（箱子 / 熔炉 /
 * 工作台 / 床）、流体、火、硬度为负的方块 —— 一律不碰。</p>
 */
public final class CatGirlHarvest {

    private CatGirlHarvest() {
    }

    /**
     * 取掉落时的「代理工具」候选，按顺序试第一个对得上这个方块的。
     *
     * <p>顺序有讲究：剪刀放在锄前面 —— 树叶同时属于 {@code mineable/hoe}，
     * 先试剪刀才拿得到树叶本体（用锄只会掉树苗）。</p>
     */
    private static final ItemStack[] PROXIES = {
            new ItemStack(Items.NETHERITE_PICKAXE),
            new ItemStack(Items.NETHERITE_AXE),
            new ItemStack(Items.NETHERITE_SHOVEL),
            new ItemStack(Items.SHEARS),
            new ItemStack(Items.NETHERITE_HOE),
            new ItemStack(Items.NETHERITE_SWORD)
    };

    /** 无论如何都不砸的方块（配置名单之外的内建底线）。 */
    private static final Set<Block> ALWAYS_PROTECTED = Set.of(
            Blocks.BEDROCK,
            Blocks.BARRIER,
            Blocks.LIGHT,
            Blocks.STRUCTURE_VOID,
            Blocks.COMMAND_BLOCK,
            Blocks.CHAIN_COMMAND_BLOCK,
            Blocks.REPEATING_COMMAND_BLOCK,
            Blocks.STRUCTURE_BLOCK,
            Blocks.JIGSAW,
            Blocks.END_PORTAL,
            Blocks.END_PORTAL_FRAME,
            Blocks.END_GATEWAY,
            Blocks.NETHER_PORTAL,
            Blocks.REINFORCED_DEEPSLATE,
            Blocks.SPAWNER);

    /** 配置名单解析缓存：配置内容一变就重建（比每次扫方块都 parse 一遍便宜得多）。 */
    private static String extraKey = "";
    private static Set<Block> extraBlocks = Set.of();

    /** 方块该用的工具（全功能：什么方块都能给出「对口」的那把）。 */
    public static ItemStack proxyFor(BlockState state) {
        for (ItemStack proxy : PROXIES) {
            if (proxy.isCorrectToolForDrops(state)) {
                return proxy;
            }
        }
        return PROXIES[0];
    }

    /**
     * 真正拿去取掉落的那把工具。
     *
     * <ul>
     *   <li>手里那把正好对口 → 就用手里的（保留附魔等行为）；</li>
     *   <li>否则 {@code always_drops} 开着 → 换成对口类型的最高级工具（等级 / 类型都不卡）。</li>
     * </ul>
     */
    public static ItemStack dropTool(BlockState state, ItemStack hand) {
        if (!hand.isEmpty() && hand.isCorrectToolForDrops(state)) {
            return hand;
        }
        if (Config.CAT_GIRL_ALWAYS_DROPS.get()) {
            return proxyFor(state);
        }
        return hand;
    }

    /** 配置里的保护名单（已解析成方块集合）。 */
    public static Set<Block> protectedExtra() {
        List<? extends String> list = Config.CAT_GIRL_MINE_PROTECTED.get();
        String key = String.join(",", list);
        if (!key.equals(extraKey)) {
            Set<Block> parsed = new HashSet<>();
            for (String id : list) {
                ResourceLocation rl = ResourceLocation.tryParse(id.contains(":") ? id : "minecraft:" + id);
                if (rl != null) {
                    BuiltInRegistries.BLOCK.getOptional(rl).ifPresent(parsed::add);
                }
            }
            extraKey = key;
            extraBlocks = Set.copyOf(parsed);
        }
        return extraBlocks;
    }

    public static boolean isProtected(BlockState state, Set<Block> extra) {
        Block block = state.getBlock();
        return ALWAYS_PROTECTED.contains(block) || extra.contains(block);
    }

    /**
     * 「什么都能挖」的判定：一次性排除掉她不该碰的东西。
     *
     * <p>这里挡的是四类：空气 / 流体 / 火（没产物）、保护名单、带方块实体的
     * （箱子·熔炉·工作台·床 —— 她的约定是绝不碰容器）、以及硬度为负的方块。</p>
     */
    public static boolean isMineable(LevelReader level, BlockPos pos, BlockState state, Set<Block> extra) {
        if (state.isAir() || state.is(BlockTags.FIRE)) {
            return false;
        }
        if (!state.getFluidState().isEmpty() || state.getBlock() instanceof LiquidBlock) {
            return false;
        }
        if (state.getBlock() instanceof BaseFireBlock) {
            return false;
        }
        if (isProtected(state, extra)) {
            return false;
        }
        if (state.hasBlockEntity()) {
            return false;
        }
        return state.getDestroySpeed(level, pos) >= 0.0F;
    }

    /** 矿石标签走 {@code forge:ores}（1.20.1 的通用约定；原版没有 {@code minecraft:ores}）。 */
    private static final net.minecraft.tags.TagKey<net.minecraft.world.level.block.Block> ORES_TAG =
            net.minecraft.tags.BlockTags.create(new net.minecraft.resources.ResourceLocation("forge", "ores"));

    /**
     * 自主挖矿（没人下单时她自己的活）的目标集合：自然方块。
     *
     * <p>原版只有矿石算「矿」；{@code mine_all} 打开后把土 / 沙 / 砾 / 树叶 / 石头类
     * 也算进来 —— 但仍然**只认自然方块**，免得她把主人的房子当成矿脉。</p>
     */
    public static boolean isNaturalTarget(BlockState state) {
        return state.is(BlockTags.LOGS)
                || state.is(BlockTags.LEAVES)
                || state.is(BlockTags.DIRT)
                || state.is(BlockTags.SAND)
                || state.is(BlockTags.BASE_STONE_OVERWORLD)
                || state.is(BlockTags.BASE_STONE_NETHER)
                || state.is(ORES_TAG)
                || state.is(BlockTags.REPLACEABLE_BY_TREES)
                || state.is(BlockTags.SMALL_FLOWERS)
                || state.is(BlockTags.TALL_FLOWERS)
                || state.is(Blocks.GRAVEL)
                || state.is(Blocks.CLAY)
                || state.is(Blocks.SNOW)
                || state.is(Blocks.SNOW_BLOCK)
                || state.is(Blocks.POWDER_SNOW);
    }

    /** 按方块该用的工具，把她库存里对口的那把换到手上（没有就不动）。 */
    public static void equipFor(CatGirlEntity cat, BlockState state) {
        ItemStack held = cat.getMainHandItem();
        if (!held.isEmpty() && held.isCorrectToolForDrops(state)) {
            return;
        }
        ItemStack want = cat.takeBestFor(stack -> stack.isCorrectToolForDrops(state));
        if (want.isEmpty()) {
            return;
        }
        if (!held.isEmpty()) {
            cat.getGoods().addItem(held.copy());
        }
        cat.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, ItemStack.EMPTY);
        cat.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, want);
    }

    /** 她要的那类工具在不在库存里（不动库存，只判断）？ */
    public static boolean hasToolFor(CatGirlEntity cat, BlockState state) {
        ItemStack held = cat.getMainHandItem();
        if (!held.isEmpty() && held.isCorrectToolForDrops(state)) {
            return true;
        }
        return cat.hasGoodsMatching(stack -> stack.isCorrectToolForDrops(state));
    }

    /** 破坏并收走产物（全功能工具的唯一出口：伐木 / 挖矿 / 开路 / 一键挖掘都走这里）。 */
    public static boolean breakAndCollect(CatGirlEntity cat, BlockPos pos, Predicate<BlockState> stillValid) {
        if (!(cat.level() instanceof ServerLevel server)) {
            return false;
        }
        BlockState state = server.getBlockState(pos);
        if (!stillValid.test(state)) {
            return false;
        }
        equipFor(cat, state);
        BlockEntity be = server.getBlockEntity(pos);
        List<ItemStack> drops = Block.getDrops(state, server, pos, be, cat, dropTool(state, cat.getMainHandItem()));
        server.destroyBlock(pos, false);
        cat.storeOrDrop(drops, pos);
        cat.playSound(net.minecraft.sounds.SoundEvents.ITEM_PICKUP, 0.5F, 1.6F);
        return true;
    }
}
