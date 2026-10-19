package com.apocalypse.zombies.orbital.terminal;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.block.SkyfallTerminalBlockEntity;
import com.apocalypse.zombies.event.OrbitalStrikeManager;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.TerminalSyncPacket;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.network.PacketDistributor;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * 服务端索引：哪台终端在哪、谁最近、一次打击该不该放行。
 *
 * <p>之所以要一个索引，是因为 {@link OrbitalStrikeManager#schedule} 的入口在遥控器手里，
 * 而遥控器需要「附近有没有一台充能完毕、已解锁、且我有权限的终端」。按区块扫方块实体
 * 会碰到未加载区块；所以终端自己在 {@code setLevel / setRemoved / onChunkUnloaded} 里
 * 登记/注销，这里只维护一张按维度分组的表。</p>
 *
 * <p>所有入口都在服务端线程（方块交互 / 包处理都在主线程队列里），不需要加锁。</p>
 */
public final class SkyfallTerminalManager {

    /** 打开界面 / 改参数要求玩家离终端多近（格）。 */
    private static final double INTERACT_DISTANCE = 8.0D;

    private static final Map<ResourceKey<Level>, Map<BlockPos, SkyfallTerminalBlockEntity>> BY_DIMENSION =
            new HashMap<>();

    private SkyfallTerminalManager() {
    }

    /** 挂到 Forge 事件总线（由 {@code ApocalypseZombies} 在构造时调用一次）。 */
    public static void register() {
        MinecraftForge.EVENT_BUS.register(SkyfallTerminalManager.class);
    }

    /** 关服/退世界：索引里的 BlockEntity 全部属于旧世界，必须清空。 */
    @SubscribeEvent
    public static void onServerStopping(ServerStoppingEvent event) {
        BY_DIMENSION.clear();
    }

    // ------------------------------------------------------------------ 索引

    public static void register(SkyfallTerminalBlockEntity terminal) {
        Level level = terminal.getLevel();
        if (level == null) {
            return;
        }
        BY_DIMENSION.computeIfAbsent(level.dimension(), key -> new HashMap<>())
                .put(terminal.getBlockPos(), terminal);
    }

    public static void unregister(SkyfallTerminalBlockEntity terminal) {
        Level level = terminal.getLevel();
        if (level == null) {
            return;
        }
        Map<BlockPos, SkyfallTerminalBlockEntity> terminals = BY_DIMENSION.get(level.dimension());
        if (terminals != null) {
            terminals.remove(terminal.getBlockPos(), terminal);
        }
    }

    /**
     * 找玩家附近最近的可用终端；顺手清掉已经卸载的条目。
     *
     * @param range 最大距离（格）
     */
    public static SkyfallTerminalBlockEntity findNearest(ServerPlayer player, double range) {
        Map<BlockPos, SkyfallTerminalBlockEntity> terminals = BY_DIMENSION.get(player.level().dimension());
        if (terminals == null || terminals.isEmpty()) {
            return null;
        }
        double best = range * range;
        SkyfallTerminalBlockEntity found = null;
        Iterator<Map.Entry<BlockPos, SkyfallTerminalBlockEntity>> it = terminals.entrySet().iterator();
        while (it.hasNext()) {
            SkyfallTerminalBlockEntity terminal = it.next().getValue();
            if (terminal.isRemoved() || terminal.getLevel() != player.level()) {
                it.remove();
                continue;
            }
            double distance = terminal.getBlockPos().distSqr(player.blockPosition());
            if (distance <= best) {
                best = distance;
                found = terminal;
            }
        }
        return found;
    }

    // ------------------------------------------------------------------ 网络

    /** 把终端当前状态发给一个玩家；{@code open = true} 时客户端会顺手打开界面。 */
    public static void sendState(ServerPlayer player, SkyfallTerminalBlockEntity terminal, boolean open) {
        NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new TerminalSyncPacket(terminal.state(), open));
    }

    /** GUI 操作：距离、权限、合法操作码三重校验后才写进 BlockEntity，然后回一份新状态。 */
    public static void handleAction(ServerPlayer player, BlockPos pos, int action, int value) {
        if (!TerminalAction.valid(action)) {
            return;
        }
        if (!(player.level().getBlockEntity(pos) instanceof SkyfallTerminalBlockEntity terminal)) {
            return;
        }
        if (player.distanceToSqr(Vec3.atCenterOf(pos)) > INTERACT_DISTANCE * INTERACT_DISTANCE) {
            return;
        }
        if (!canOperate(player, terminal)) {
            player.displayClientMessage(Component.translatable("skyfall.terminal.locked")
                    .withStyle(ChatFormatting.RED), true);
            return;
        }
        terminal.applyAction(action, value);
        sendState(player, terminal, false);
    }

    // ------------------------------------------------------------------ 授权

    /** 一次打击请求的判定结果。遥控器据此决定「照常放行 / 回退旧逻辑 / 拒绝并提示」。 */
    public enum Authorization {
        /** 终端授权通过，打击已经排进服务端队列。 */
        AUTHORISED,
        /** 附近没有终端（调用方按 {@code terminal_required} 决定是自由开火还是拒绝）。 */
        NO_TERMINAL,
        /** 有终端但条件不满足（未解锁/充能中/无权限），提示已经发给玩家。 */
        BLOCKED
    }

    /**
     * 遥控器右键的终端路径：校验 → 用终端参数排一次打击 → 终端进入充能。
     *
     * <p>半径/伤害/下落速度全部取自服务端 BlockEntity；客户端手里的遥控器只负责「瞄哪儿」。</p>
     */
    public static Authorization authorize(ServerPlayer player, BlockPos target) {
        SkyfallTerminalBlockEntity terminal = findNearest(player, Config.TERMINAL_RANGE.get());
        if (terminal == null) {
            return Authorization.NO_TERMINAL;
        }
        if (!canOperate(player, terminal)) {
            player.displayClientMessage(Component.translatable("skyfall.terminal.locked")
                    .withStyle(ChatFormatting.RED), true);
            return Authorization.BLOCKED;
        }
        OrbitalStrikeMode mode = terminal.selectedMode();
        if (!terminal.unlocked(mode)) {
            player.displayClientMessage(Component.translatable("skyfall.terminal.no_core",
                    Component.translatable("orbital_mode." + mode.id())).withStyle(ChatFormatting.RED), true);
            return Authorization.BLOCKED;
        }
        if (!terminal.ready()) {
            player.displayClientMessage(Component.translatable("skyfall.terminal.charging",
                    terminal.state().secondsLeft()).withStyle(ChatFormatting.YELLOW), true);
            return Authorization.BLOCKED;
        }
        java.util.UUID strikeId = OrbitalStrikeManager.schedule(player, target, mode, terminal.radius(),
                terminal.powerMul(), terminal.speedMul(), terminal.getBlockPos());
        if (strikeId == null) {
            // 并发上限拒绝：提示已经由 schedule 发给玩家，终端不扣充能。
            return Authorization.BLOCKED;
        }
        terminal.onStrike();
        player.displayClientMessage(Component.translatable("skyfall.terminal.authorised",
                        Component.translatable("orbital_mode." + mode.id()))
                .withStyle(ChatFormatting.AQUA), true);
        player.level().playSound(null, terminal.getBlockPos(), SoundEvents.BEACON_ACTIVATE,
                SoundSource.BLOCKS, 0.9F, 1.35F);
        return Authorization.AUTHORISED;
    }

    /** 玩家是否有权操作这台终端（默认配置下所有人都有权）。 */
    public static boolean canOperate(ServerPlayer player, SkyfallTerminalBlockEntity terminal) {
        if (!Config.TERMINAL_OWNER_ONLY.get()) {
            return true;
        }
        if (player.hasPermissions(2)) {
            return true;
        }
        return terminal.owner() != null && terminal.owner().equals(player.getUUID());
    }

    /**
     * 方块被拆：取消这台终端授权的、还没结算完的打击（退款判定在 {@code OrbitalStrikeManager}）。
     *
     * @return 取消了几发
     */
    public static int cancelForTerminal(Level level, BlockPos pos) {
        return OrbitalStrikeManager.cancelForTerminal(level.dimension(), pos);
    }
}
