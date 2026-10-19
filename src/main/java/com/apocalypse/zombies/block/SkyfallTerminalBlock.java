package com.apocalypse.zombies.block;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.orbital.terminal.ProtocolCoreItem;
import com.apocalypse.zombies.orbital.terminal.SkyfallTerminalManager;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.BaseEntityBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import org.jetbrains.annotations.Nullable;

/**
 * 天陨指挥终端（方块）。
 *
 * <p>两种交互：</p>
 * <ul>
 *   <li>手里拿着<b>协议核心</b>右键：把核心装进终端（一次性消耗，解锁对应模式并自动选中）；</li>
 *   <li>空手 / 拿其它东西右键：把终端状态发给该玩家，客户端打开六边形协议面板。</li>
 * </ul>
 *
 * <p>它自己不做任何判定之外的事情 —— 充能、参数、权限分别在
 * {@link SkyfallTerminalBlockEntity} 与 {@link SkyfallTerminalManager}。这样把「方块」这一层
 * 压到最薄，出问题时一眼能看出是哪一层。</p>
 */
public class SkyfallTerminalBlock extends BaseEntityBlock {

    public SkyfallTerminalBlock(Properties properties) {
        super(properties);
    }

    @Override
    public RenderShape getRenderShape(BlockState state) {
        return RenderShape.MODEL;
    }

    @Nullable
    @Override
    public BlockEntity newBlockEntity(BlockPos pos, BlockState state) {
        return new SkyfallTerminalBlockEntity(pos, state);
    }

    @Override
    public void setPlacedBy(Level level, BlockPos pos, BlockState state,
                            @Nullable LivingEntity placer, ItemStack stack) {
        super.setPlacedBy(level, pos, state, placer, stack);
        if (!level.isClientSide() && placer instanceof Player player
                && level.getBlockEntity(pos) instanceof SkyfallTerminalBlockEntity terminal) {
            terminal.setOwner(player);
        }
    }

    @Override
    public InteractionResult use(BlockState state, Level level, BlockPos pos, Player player,
                                 InteractionHand hand, BlockHitResult hit) {
        if (!(level.getBlockEntity(pos) instanceof SkyfallTerminalBlockEntity terminal)) {
            return InteractionResult.PASS;
        }
        ItemStack stack = player.getItemInHand(hand);
        // 客户端不做任何判定，只给一个「已处理」的预测，避免手臂反复摆动。
        if (level.isClientSide()) {
            return InteractionResult.SUCCESS;
        }
        if (!(player instanceof ServerPlayer serverPlayer)) {
            return InteractionResult.PASS;
        }

        // —— 装核心
        if (stack.getItem() instanceof ProtocolCoreItem core) {
            if (terminal.install(core.mode())) {
                if (!serverPlayer.isCreative()) {
                    stack.shrink(1);
                }
                serverPlayer.displayClientMessage(Component.translatable(
                                "skyfall.terminal.installed", core.mode().display())
                        .withStyle(ChatFormatting.AQUA), false);
                level.playSound(null, pos, SoundEvents.BEACON_ACTIVATE, SoundSource.BLOCKS, 0.9F, 1.55F);
            } else {
                serverPlayer.displayClientMessage(Component.translatable(
                                "skyfall.terminal.already", core.mode().display())
                        .withStyle(ChatFormatting.GRAY), true);
            }
            SkyfallTerminalManager.sendState(serverPlayer, terminal, false);
            return InteractionResult.CONSUME;
        }

        // —— 快速充能（默认红石块）：放在「装核心」之后，核心右键永远优先。
        if (Config.TERMINAL_QUICK_CHARGE_ENABLED.get() && isQuickChargeItem(stack)) {
            int seconds = terminal.quickCharge(Config.TERMINAL_QUICK_CHARGE_SECONDS.get());
            if (seconds <= 0) {
                serverPlayer.displayClientMessage(Component.translatable("skyfall.terminal.ready_now")
                        .withStyle(ChatFormatting.GRAY), true);
            } else {
                if (!serverPlayer.isCreative()) {
                    stack.shrink(1);
                }
                serverPlayer.displayClientMessage(Component.translatable(
                                "skyfall.terminal.quick_charge", seconds)
                        .withStyle(ChatFormatting.GREEN), false);
                level.playSound(null, pos, SoundEvents.AMETHYST_BLOCK_CHIME,
                        SoundSource.BLOCKS, 0.9F, 1.4F);
            }
            SkyfallTerminalManager.sendState(serverPlayer, terminal, false);
            return InteractionResult.CONSUME;
        }

        // —— 打开协议面板
        if (!SkyfallTerminalManager.canOperate(serverPlayer, terminal)) {
            serverPlayer.displayClientMessage(Component.translatable("skyfall.terminal.locked")
                    .withStyle(ChatFormatting.RED), true);
            return InteractionResult.CONSUME;
        }
        SkyfallTerminalManager.sendState(serverPlayer, terminal, true);
        level.playSound(null, pos, SoundEvents.UI_BUTTON_CLICK.get(), SoundSource.BLOCKS, 0.7F, 1.2F);
        return InteractionResult.CONSUME;
    }

    /** 保留给以后的朝向/连接状态：目前终端是个立方体，不需要 {@link BlockPlaceContext}。 */
    @Nullable
    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context) {
        return defaultBlockState();
    }

    /**
     * v4.0 P3：玩家拆掉终端时，把它授权的、还没结算的打击一并中止（配置可关）。
     *
     * <p>只在服务端执行；退款由打击管理器按相位判断（FIRE 前才退）。</p>
     */
    @Override
    public void playerWillDestroy(Level level, BlockPos pos, BlockState state, Player player) {
        if (!level.isClientSide() && Config.TERMINAL_CANCEL_ON_BREAK.get()) {
            SkyfallTerminalManager.cancelForTerminal(level, pos);
        }
        super.playerWillDestroy(level, pos, state, player);
    }

    /** 手里这个物品是不是配置里的快速充能道具。 */
    private static boolean isQuickChargeItem(ItemStack stack) {
        if (stack.isEmpty()) {
            return false;
        }
        var key = net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(stack.getItem());
        return key != null && key.toString().equals(Config.TERMINAL_QUICK_CHARGE_ITEM.get().trim());
    }
}
