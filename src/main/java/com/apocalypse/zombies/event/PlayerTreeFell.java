package com.apocalypse.zombies.event;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.AxeItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.level.BlockEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlHarvest;

/**
 * 斧子一键砍伐：拿着斧头砍倒一格原木，同一棵树（同类原木连成的那一棵）跟着整棵下来。
 *
 * <p><b>触发方式是原版破坏事件，不是按键。</b>挂在 {@code BlockEvent.BreakEvent} 上，所以不需要
 * 新按键、不需要网络包；你砍的那一根交给原版处理（耐久 / 声音 / 进度都是原版的），我们只补上
 * 「跟下来的那一部分」：</p>
 * <ul>
 *   <li><b>原木</b>：从你砍的那一格出发，6 邻连通、只认同一种原木方块 —— 橡树 / 白桦 / 云杉
 *       一根直杆也好，黑橡树 2×2 也好，带枝杈的橡木也好，连得上的同种原木全算这一棵；
 *       <b>树与树之间没有原木相连就互不影响</b>，砍一棵只下一棵。</li>
 *   <li><b>树叶</b>（{@code player_fell.take_leaves}，默认开）：原木收完从这些原木的边界向外
 *       走树叶（任何树种都算 —— 藤蔓交错的树冠不该剩半截），树苗 / 苹果 / 树枝照常按掉落表出。
 *       树叶<b>不扣耐久</b>：树冠动辄几十格，都扣的话一把斧头撑不完整棵树。</li>
 * </ul>
 *
 * <p><b>为什么不再走 {@link PlayerVeinMine}</b>：矿脉贴地横向铺开，「半径 + 64 格上限」罩得住；
 * 树是竖着长的一长串（大云杉几十格高），半径圈罩不住树顶。两套一起触发还会对着同一批方块重复
 * 结算 —— 所以原木 + 斧头的目标归本类，一键挖掘在 {@code preview} 里自动让路（没有斧头、或本
 * 功能关着时，一键挖掘照旧管原木）。</p>
 *
 * <p><b>产物一律进背包</b>（{@code to_inventory}，默认开），包括你亲手砍的那一根：连带出来的格子
 * 在 {@link #breakOne} 里直接塞进背包；种子根由原版挖、原版掉 —— 它的掉落物在砍之前登记一下
 * （{@link #awaitSeedDrops}），生成的那一瞬（{@link EntityJoinLevelEvent}）捞进背包。背包塞不下
 * 就掉在脚下，找不到主人（离线）就让原版照常掉。</p>
 *
 * <p><b>安全边界复用 {@link CatGirlHarvest}</b>：带方块实体的（箱子 / 熔炉 / 床 —— 绝不碰容器）、
 * 流体、火、硬度为负 —— 一律不碰。原木与树叶本来也不在这些名单里，这层只是兜底。</p>
 *
 * <p><b>服务端与客户端共用 {@link #preview}</b>：服务端据此决定砍哪些，客户端
 * （{@code TreeFellHighlighter}）据此画描边与数字 —— 「画出来的」与「实际会砍的」永远一致。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class PlayerTreeFell {

    private PlayerTreeFell() {
    }

    /**
     * 种子根（你砍的那一格）的掉落物登记：维度 → 位置 → 「谁砍的 / 到哪一 tick 为止算数」。
     * 与 {@link PlayerVeinMine} 各管各的表（两边同时开着也互不串门）。
     */
    private static final Map<ResourceKey<Level>, Map<BlockPos, SeedDrop>> seedDrops = new HashMap<>();

    /** 一条种子根掉落登记。{@code deadline} 用 {@code level.getGameTime()} 同一时间轴。 */
    private record SeedDrop(UUID owner, long deadline) {
    }

    @SubscribeEvent
    public static void onBreak(BlockEvent.BreakEvent event) {
        if (!Config.PLAYER_FELL_ENABLED.get()) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        if (!(event.getPlayer() instanceof ServerPlayer player)) {
            return;
        }
        ItemStack tool = player.getMainHandItem();
        if (!(tool.getItem() instanceof AxeItem)) {
            return;   // 「斧子一键砍伐」—— 手里不是斧头就只是普通的砍
        }
        Block originLog = event.getState().getBlock();
        if (!event.getState().is(BlockTags.LOGS)) {
            return;
        }
        BlockPos originPos = event.getPos();
        // 潜行只砍一格这条判定收在 preview 里（单一出口）—— 客户端画描边 / 数字时读的是同一份，
        // 所以蹲下的时候框和数字会跟着一起没有，不会「画了却不砍」。
        List<BlockPos> found = preview(level, originPos, tool, player.isShiftKeyDown());
        if (found.size() <= 1) {
            return;   // 就那一格（孤零零的原木桩，或在潜行）—— 原版自己会处理
        }

        boolean toInventory = Config.PLAYER_FELL_TO_INVENTORY.get();
        if (toInventory) {
            // 种子根留给原版砍（耐久 / 声音 / 进度都按原版走），产物在这条登记里领回背包。
            awaitSeedDrops(level, player, originPos);
        }
        int budget = clampMax(Config.PLAYER_FELL_MAX_BLOCKS.get()) - 1;   // 你砍的那一根算在 max 里
        boolean durability = Config.PLAYER_FELL_DURABILITY.get();
        int done = 0;
        for (BlockPos pos : found) {
            if (done >= budget) {
                break;
            }
            if (pos.equals(originPos)) {
                continue;
            }
            boolean wasLog = level.getBlockState(pos).is(originLog);   // 树叶不扣耐久，先记下它是什么
            if (!breakOne(level, player, pos, originLog, tool, toInventory)) {
                continue;
            }
            done++;
            if (durability && wasLog && !player.isCreative() && !tool.isEmpty()) {
                tool.hurtAndBreak(1, player, p -> p.broadcastBreakEvent(InteractionHand.MAIN_HAND));
                if (tool.isEmpty()) {
                    break;   // 斧头刚好用坏 —— 停手，剩下的树干还立着，别凭空拆树
                }
            }
        }
    }

    /**
     * 种子根的掉落物进场时，直接领进砍树人的背包（{@code to_inventory} 关着就一个字节都不碰）。
     * 认人的三条线索缺一不可：同一维度、同一格、同一个 tick 前后 —— 与 {@link PlayerVeinMine}
     * 的同名机制一致（那边管矿石这边管原木，两张表互不重叠，一件掉落物只会被一边领走）。
     */
    @SubscribeEvent
    public static void onItemJoin(EntityJoinLevelEvent event) {
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        if (!(event.getEntity() instanceof ItemEntity item)) {
            return;
        }
        if (!Config.PLAYER_FELL_TO_INVENTORY.get()) {
            return;
        }
        Map<BlockPos, SeedDrop> pending = seedDrops.get(level.dimension());
        if (pending == null || pending.isEmpty()) {
            return;
        }
        BlockPos pos = item.blockPosition();
        SeedDrop seeded = pending.get(pos);
        if (seeded == null) {
            return;
        }
        if (level.getGameTime() > seeded.deadline()) {
            pending.remove(pos);   // 过期的登记 —— 这一格是别的来源
            return;
        }
        ServerPlayer owner = level.getServer() == null
                ? null
                : level.getServer().getPlayerList().getPlayer(seeded.owner());
        if (owner == null) {
            pending.remove(pos);   // 人走了 —— 让原版照常掉在地上
            return;
        }
        // 不删登记：同一格一次可以掉好几件（树叶掉俩树苗这种），都在同一个时间窗里，一起领走。
        ItemStack drop = item.getItem().copy();
        event.setCanceled(true);
        if (drop.isEmpty()) {
            return;
        }
        if (!owner.getInventory().add(drop)) {
            owner.drop(drop, false);   // 背包满了 —— 掉在他脚下
        }
    }

    /** 砍种子根之前登记一次：这一格接下来生成的原版掉落物归这个玩家。 */
    private static void awaitSeedDrops(ServerLevel level, ServerPlayer player, BlockPos pos) {
        long now = level.getGameTime();
        Map<BlockPos, SeedDrop> pending = seedDrops.computeIfAbsent(level.dimension(), k -> new HashMap<>());
        pending.values().removeIf(drop -> now > drop.deadline());   // 顺手清过期，表不会越攒越大
        pending.put(pos.immutable(), new SeedDrop(player.getUUID(), now + 1));
    }

    /**
     * 「以 {@code origin} 为种子，这一斧头会跟着下来哪些方块」—— 含 {@code origin} 自己，
     * 原木在前、树叶在后。
     *
     * <p><b>服务端与客户端共用这一份：</b>服务端据此决定砍哪些（{@link #onBreak}），客户端据此
     * 画描边与数字（{@code client/renderer/TreeFellHighlighter}）。</p>
     *
     * <p>凡是<b>会影响砍多少</b>的判断都收在这个方法里，包括「潜行只砍一格」—— 否则客户端那份
     * 算不出来，就会出现「蹲着还给你画一棵树」的谎。</p>
     */
    public static List<BlockPos> preview(LevelReader level, BlockPos origin, ItemStack tool, boolean sneaking) {
        if (Config.PLAYER_FELL_SNEAK_DISABLES.get() && sneaking) {
            return List.of();
        }
        if (!(tool.getItem() instanceof AxeItem)) {
            return List.of();   // 手里不是斧头 —— 「斧子一键砍伐」不生效，客户端也就不画（单一出口）
        }
        BlockPos seed = origin.immutable();
        BlockState originState = level.getBlockState(seed);
        if (!originState.is(BlockTags.LOGS)) {
            return List.of();   // 目标不是原木 —— 这不是砍树，原版自己处理
        }
        int max = clampMax(Config.PLAYER_FELL_MAX_BLOCKS.get());
        List<BlockPos> logs = floodLogs(level, seed, originState.getBlock(), max);
        if (!Config.PLAYER_FELL_LEAVES.get()) {
            return logs;
        }
        int budget = max - logs.size();   // 树叶排在前面的原木后面，吃剩下的名额
        if (budget <= 0) {
            return logs;
        }
        List<BlockPos> leaves = floodLeaves(level, logs, budget);
        if (leaves.isEmpty()) {
            return logs;
        }
        List<BlockPos> out = new ArrayList<>(logs.size() + leaves.size());
        out.addAll(logs);
        out.addAll(leaves);
        return out;
    }

    /** 一格：取原版该给的掉落 → 销毁 → 产物进背包（塞不下掉在脚下）或留在原地。 */
    private static boolean breakOne(ServerLevel level, ServerPlayer player, BlockPos pos,
                                    Block originLog, ItemStack tool, boolean toInventory) {
        BlockState state = level.getBlockState(pos);
        if (!state.is(originLog) && !state.is(BlockTags.LEAVES)) {
            return false;   // 位置上的东西变了（同 tick 内不该发生，兜底）
        }
        if (!CatGirlHarvest.isMineable(level, pos, state, Set.of())) {
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
                player.drop(drop, false);   // 背包满了 —— 掉在你脚下
            } else {
                Block.popResource(level, pos, drop);
            }
        }
        return true;
    }

    /** 同种原木的连通体：6 邻 BFS，天然由近及远，拿满上限就停（砍到上限就停手）。 */
    private static List<BlockPos> floodLogs(LevelReader level, BlockPos origin, Block originLog, int max) {
        List<BlockPos> out = new ArrayList<>();
        Set<BlockPos> seen = new HashSet<>();
        Deque<BlockPos> queue = new ArrayDeque<>();
        seen.add(origin);
        queue.add(origin);
        out.add(origin);
        while (!queue.isEmpty() && out.size() < max) {
            BlockPos cur = queue.poll();
            for (BlockPos next : new BlockPos[] {
                    cur.above(), cur.below(), cur.north(), cur.south(), cur.east(), cur.west()}) {
                if (!seen.add(next)) {
                    continue;
                }
                if (level.getBlockState(next).is(originLog)) {
                    out.add(next);
                    queue.add(next);
                    if (out.size() >= max) {
                        break;
                    }
                }
            }
        }
        return out;
    }

    /** 树冠：从已砍的原木边界向外走树叶（任何树种都算），吃 {@code budget} 个名额就停。 */
    private static List<BlockPos> floodLeaves(LevelReader level, List<BlockPos> logs, int budget) {
        List<BlockPos> out = new ArrayList<>();
        Set<BlockPos> seen = new HashSet<>();
        Deque<BlockPos> queue = new ArrayDeque<>();
        for (BlockPos log : logs) {
            for (BlockPos next : new BlockPos[] {
                    log.above(), log.below(), log.north(), log.south(), log.east(), log.west()}) {
                if (seen.add(next) && level.getBlockState(next).is(BlockTags.LEAVES)) {
                    queue.add(next);
                }
            }
        }
        while (!queue.isEmpty() && out.size() < budget) {
            BlockPos cur = queue.poll();   // 进队的都验过是树叶（前沿一圈当场验的）
            out.add(cur);
            for (BlockPos next : new BlockPos[] {
                    cur.above(), cur.below(), cur.north(), cur.south(), cur.east(), cur.west()}) {
                if (seen.add(next) && level.getBlockState(next).is(BlockTags.LEAVES)) {
                    queue.add(next);
                }
            }
        }
        return out;
    }

    private static int clampMax(int value) {
        return Math.max(1, Math.min(value, 256));
    }
}
