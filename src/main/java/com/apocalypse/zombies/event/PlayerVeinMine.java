package com.apocalypse.zombies.event;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.event.level.BlockEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlHarvest;

/**
 * 玩家一键挖掘：左键砸掉一格，同一种方块跟着一起下来（默认只认矿石 —— 煤 / 铁 / 金 / 钻石…）。
 *
 * <p><b>触发方式是原版破坏事件，不是按键。</b>挂在 {@code BlockEvent.BreakEvent} 上（Forge 事件总线，
 * 这条事件只在服务端 {@code ServerPlayerGameMode.destroyBlock} 里发），所以：</p>
 * <ul>
 *   <li>不需要新按键、不需要网络包、客户端装不装这个 mod 都一样；</li>
 *   <li><b>挖多少 / 挖哪儿 / 给不给产物全部只认服务端读到的配置</b>（{@code [player_mine]} 段），
 *       客户端改自己的 TOML 也影响不了判定；</li>
 *   <li>你砸的那一格交给原版处理（工具等级、掉落、声音都是原版的），我们只补上**多出来的那几格**。</li>
 * </ul>
 *
 * <p><b>安全边界复用 {@link CatGirlHarvest}</b>（1.1.7x 起那套约定，一格不改）：保护名单（基岩 / 屏障 /
 * 命令方块 / 传送门 / 刷怪笼…，{@code cat_girl.mine_protected} 与 {@code player_mine.protected} 都生效）、
 * 带方块实体的（箱子 / 熔炉 / 床 —— 绝不碰容器）、流体、火、硬度为负 —— 一律不碰。</p>
 *
 * <p><b>为什么额外认「深板岩变种」：</b>{@code deepslate_iron_ore} 与 {@code iron_ore} 是两个注册名，
 * 只按方块相等判定的话，你在深层挖铁矿只会下来一格。这里按注册名配对（{@code X_ore} ↔
 * {@code deepslate_X_ore}）算同一簇，其他方块仍严格同名才连带。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class PlayerVeinMine {

    private PlayerVeinMine() {
    }

    /** 配置名单解析缓存：内容一变就重建（照 {@link CatGirlHarvest} 的做法）。 */
    private static String extraKey = "";
    private static Set<Block> extraBlocks = Set.of();

    @SubscribeEvent
    public static void onBreak(BlockEvent.BreakEvent event) {
        if (!Config.PLAYER_MINE_ENABLED.get()) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        if (!(event.getPlayer() instanceof ServerPlayer player)) {
            return;
        }
        BlockPos originPos = event.getPos();
        ItemStack tool = player.getMainHandItem();
        // 潜行不连带这条判定收在 preview 里（单一出口）—— 客户端画高亮/数字时读的是同一份，
        // 所以蹲下的时候框和数字会跟着一起没有，不会「画了却不砸」。
        List<BlockPos> found = preview(level, originPos, tool, player.isShiftKeyDown());
        if (found.size() <= 1) {
            return;   // 就那一格（或在潜行）—— 原版自己会处理，别插手
        }

        Set<Block> extra = protectedExtra();
        BlockState origin = event.getState();
        Block originBlock = origin.getBlock();
        Block twin = deepslateTwin(originBlock);
        boolean toInventory = Config.PLAYER_MINE_TO_INVENTORY.get();
        boolean durability = Config.PLAYER_MINE_DURABILITY.get();
        int budget = clampMax(Config.PLAYER_MINE_MAX_BLOCKS.get()) - 1;   // 你砸的那一格算在 max 里
        int done = 0;
        for (BlockPos pos : found) {
            if (done >= budget) {
                break;
            }
            if (pos.equals(originPos)) {
                continue;
            }
            if (!breakOne(level, player, pos, originBlock, twin, extra, tool, toInventory)) {
                continue;
            }
            done++;
            if (durability && !player.isCreative() && !tool.isEmpty()) {
                tool.hurtAndBreak(1, player, p -> p.broadcastBreakEvent(InteractionHand.MAIN_HAND));
                if (tool.isEmpty()) {
                    break;   // 工具刚好用完 —— 停手，别再凭空挖
                }
            }
        }
    }

    /**
     * 「以 {@code origin} 为种子，左键会连带下来哪些方块」—— 含 {@code origin} 自己，由近及远。
     *
     * <p><b>服务端与客户端共用这一份：</b>服务端据此决定砸哪些（{@link #onBreak}），
     * 客户端据此画高亮与数字（{@code client/renderer/VeinMineHighlighter}）。于是「画出来的框」与
     * 「实际会砸的方块」永远一致 —— 不会画了不砸，也不会砸了没画。</p>
     *
     * <p>凡是<b>会影响砸多少</b>的判断都收在这个方法里，包括「潜行只挖一格」—— 否则客户端那份算不出来，
     * 就会出现「蹲着还给你画一整簇」的谎。所以它要 {@code sneaking} 这个参数。</p>
     */
    public static List<BlockPos> preview(LevelReader level, BlockPos origin, ItemStack tool, boolean sneaking) {
        if (Config.PLAYER_MINE_SNEAK_DISABLES.get() && sneaking) {
            return List.of();
        }
        BlockPos seed = origin.immutable();
        BlockState originState = level.getBlockState(seed);
        Set<Block> extra = protectedExtra();
        if (!isTarget(level, seed, originState, extra)) {
            return List.of();
        }
        if (Config.PLAYER_MINE_REQUIRE_TOOL.get() && !tool.isCorrectToolForDrops(originState)) {
            return List.of();
        }
        int max = clampMax(Config.PLAYER_MINE_MAX_BLOCKS.get());
        int radius = Math.max(1, Config.PLAYER_MINE_RADIUS.get());
        Block originBlock = originState.getBlock();
        Block twin = deepslateTwin(originBlock);
        return Config.PLAYER_MINE_VEIN_ONLY.get()
                ? floodFill(level, seed, originBlock, twin, radius, max, extra)
                : scan(level, seed, originBlock, twin, radius, max, extra);
    }

    /** 一格：取原版该给的掉落 → 销毁 → 产物进背包（塞不下掉在脚下）或留在原地。 */
    private static boolean breakOne(ServerLevel level, ServerPlayer player, BlockPos pos, Block originBlock,
                                    Block twin, Set<Block> extra, ItemStack tool, boolean toInventory) {
        BlockState state = level.getBlockState(pos);
        if (!sameKind(state.getBlock(), originBlock, twin)) {
            return false;
        }
        if (!CatGirlHarvest.isMineable(level, pos, state, extra)) {
            return false;
        }
        BlockEntity be = level.getBlockEntity(pos);
        List<ItemStack> drops = Block.getDrops(state, level, pos, be, player, tool);
        level.destroyBlock(pos, false);
        for (ItemStack drop : drops) {
            if (drop.isEmpty()) {
                continue;
            }
            if (toInventory && player.getInventory().add(drop)) {
                continue;
            }
            if (toInventory) {
                player.drop(drop, false);   // 背包满了 —— 掉在你脚下，别丢进虚空
            } else {
                Block.popResource(level, pos, drop);
            }
        }
        return true;
    }

    /** 连通矿脉：6 面 flood fill，BFS 天然由近及远，拿满上限就停。 */
    private static List<BlockPos> floodFill(LevelReader level, BlockPos origin, Block originBlock, Block twin,
                                            int radius, int max, Set<Block> extra) {
        List<BlockPos> out = new ArrayList<>();
        Set<BlockPos> seen = new HashSet<>();
        Deque<BlockPos> queue = new ArrayDeque<>();
        seen.add(origin);
        queue.add(origin);
        out.add(origin);
        int r2 = radius * radius;
        while (!queue.isEmpty() && out.size() < max) {
            BlockPos cur = queue.poll();
            for (BlockPos next : neighbours(cur)) {
                if (!seen.add(next)) {
                    continue;
                }
                if (next.distSqr(origin) > r2) {
                    continue;
                }
                BlockState state = level.getBlockState(next);
                if (!sameKind(state.getBlock(), originBlock, twin) || !isTarget(level, next, state, extra)) {
                    continue;
                }
                out.add(next);
                queue.add(next);
                if (out.size() >= max) {
                    break;
                }
            }
        }
        return out;
    }

    /** 半径内所有同类方块（不要求连通），由近及远取到上限。 */
    private static List<BlockPos> scan(LevelReader level, BlockPos origin, Block originBlock, Block twin,
                                       int radius, int max, Set<Block> extra) {
        List<BlockPos> out = new ArrayList<>();
        for (BlockPos pos : BlockPos.betweenClosed(origin.offset(-radius, -radius, -radius),
                origin.offset(radius, radius, radius))) {
            if (pos.distSqr(origin) > (double) radius * radius) {
                continue;
            }
            BlockState state = level.getBlockState(pos);
            if (!sameKind(state.getBlock(), originBlock, twin)) {
                continue;
            }
            if (!isTarget(level, pos, state, extra)) {
                continue;
            }
            out.add(pos.immutable());
        }
        out.sort(Comparator.comparingDouble((BlockPos p) -> p.distSqr(origin)));
        if (out.size() > max) {
            out = new ArrayList<>(out.subList(0, max));
        }
        return out;
    }

    private static BlockPos[] neighbours(BlockPos pos) {
        return new BlockPos[] {
                pos.above(), pos.below(), pos.north(), pos.south(), pos.east(), pos.west()
        };
    }

    /** 这一格算不算「一键挖掘的目标」：先过 targets 档位，再过那套共用安全判定。 */
    private static boolean isTarget(LevelReader level, BlockPos pos, BlockState state, Set<Block> extra) {
        if (!CatGirlHarvest.isMineable(level, pos, state, extra)) {
            return false;
        }
        int mode = Config.PLAYER_MINE_TARGETS.get();
        if (mode <= 0) {
            return CatGirlHarvest.isOre(state);
        }
        if (mode == 1) {
            return CatGirlHarvest.isNaturalTarget(state);
        }
        return true;   // 2 = 任何能挖的方块（自己房子也会被连带）
    }

    /** 同名，或「深板岩变种」算同一簇（{@code iron_ore} ↔ {@code deepslate_iron_ore}）。 */
    private static boolean sameKind(Block block, Block originBlock, Block twin) {
        return block == originBlock || (twin != null && block == twin);
    }

    /** {@code X_ore} 的另一半，认不出来就 null。 */
    private static Block deepslateTwin(Block block) {
        ResourceLocation id = BuiltInRegistries.BLOCK.getKey(block);
        String path = id.getPath();
        if (!path.endsWith("_ore")) {
            return null;
        }
        String twin = path.startsWith("deepslate_")
                ? path.substring("deepslate_".length())
                : "deepslate_" + path;
        if (!twin.endsWith("_ore")) {
            return null;
        }
        return BuiltInRegistries.BLOCK.getOptional(new ResourceLocation(id.getNamespace(), twin)).orElse(null);
    }

    private static int clampMax(int value) {
        return Math.max(1, Math.min(value, 64));
    }

    /** 她那份名单 + 玩家自己那份，合并解析（两份都改也无所谓）。 */
    private static Set<Block> protectedExtra() {
        List<? extends String> list = Config.PLAYER_MINE_PROTECTED.get();
        String key = String.join(",", list);
        if (!key.equals(extraKey)) {
            Set<Block> parsed = new HashSet<>(CatGirlHarvest.protectedExtra());
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
}
