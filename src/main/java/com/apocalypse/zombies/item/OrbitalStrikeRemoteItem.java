package com.apocalypse.zombies.item;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.event.OrbitalStrikeManager;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.terminal.SkyfallTerminalManager;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import org.jetbrains.annotations.Nullable;

import java.util.List;

/**
 * 轨道打击遥控器：手持时准星处显示选区框，右键呼叫一次天基打击。
 *
 * <p><b>四种弹种</b>（{@link OrbitalStrikeMode}）：轨道炮 / 天基长矛 / 引力奇点 / 等离子风暴。
 * 选择存在物品 NBT（{@code StrikeMode}）里 —— 服务端权威、随物品栈自动同步，
 * 不需要额外的切换包。潜行 + 右键在服务端切换并回一条 action bar 提示。</p>
 *
 * <p>权限、冷却、保护名单都在 {@link OrbitalStrikeManager} 一处收口，物品本身只负责
 * 「选模式 + 把准星点传给 manager + 扣冷却」三件。客户端描边由
 * {@code OrbitalStrikeHighlighter} 单独读 {@code minecraft.hitResult}，不依赖这里。</p>
 */
public class OrbitalStrikeRemoteItem extends Item {

    /** 模式在物品 NBT 里的键（值是 {@link OrbitalStrikeMode#id()}）。 */
    public static final String MODE_KEY = "StrikeMode";
    /** 服务器侧最大瞄准距离。超过这个距离直接对空地打（仍以射线终点为方块中心）。 */
    private static final double PICK_REACH = 160.0D;

    public OrbitalStrikeRemoteItem(Properties properties) {
        super(properties);
    }

    /** 读这件遥控器当前选的模式；没写过就用配置里的默认值。 */
    public static OrbitalStrikeMode getMode(ItemStack stack) {
        CompoundTag tag = stack.getTag();
        if (tag != null && tag.contains(MODE_KEY)) {
            return OrbitalStrikeMode.byId(tag.getString(MODE_KEY));
        }
        return OrbitalStrikeMode.byId(Config.ORBITAL_STRIKE_DEFAULT_MODE.get());
    }

    private static void setMode(ItemStack stack, OrbitalStrikeMode mode) {
        stack.getOrCreateTag().putString(MODE_KEY, mode.id());
    }

    @Override
    public InteractionResultHolder<ItemStack> use(Level level, Player player, InteractionHand hand) {
        ItemStack stack = player.getItemInHand(hand);
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            return InteractionResultHolder.pass(stack);
        }

        // —— 潜行右键：切换打击模式（不消耗冷却，两侧都 consume 防止连点重复触发）
        if (player.isShiftKeyDown()) {
            if (!Config.ORBITAL_STRIKE_ALLOW_MODE_SWITCH.get()) {
                return InteractionResultHolder.pass(stack);
            }
            if (!level.isClientSide() && player instanceof ServerPlayer serverPlayer) {
                OrbitalStrikeMode next = getMode(stack).next();
                setMode(stack, next);
                // 直接改 NBT 不会自己下发：显式广播一次容器槽位，客户端手里的遥控器
                // （以及 HUD 上的模式名）才会立刻变成新模式。
                serverPlayer.containerMenu.broadcastChanges();
                serverPlayer.displayClientMessage(
                        Component.literal("天陨-01 · " + next.display() + "  [" + next.codename() + "]")
                                .withStyle(ChatFormatting.AQUA), true);
                serverPlayer.level().playSound(null, serverPlayer.blockPosition(),
                        SoundEvents.UI_BUTTON_CLICK.get(), SoundSource.PLAYERS, 0.8F, 1.5F);
            }
            return InteractionResultHolder.consume(stack);
        }

        // 客户端：use 也要 consume，否则连按右键会反复跑「长按 + 松手」的预测逻辑。
        if (level.isClientSide()) {
            return InteractionResultHolder.consume(stack);
        }
        if (!(player instanceof ServerPlayer serverPlayer)) {
            return InteractionResultHolder.pass(stack);
        }
        OrbitalStrikeMode mode = getMode(stack);
        // 准星取点：射线末端必须是 BLOCK 才算「瞄到地」—— 瞄到空气就让玩家自己再想想。
        HitResult hit = player.pick(PICK_REACH, 0.0F, false);
        if (!(hit instanceof BlockHitResult blockHit) || blockHit.getType() != HitResult.Type.BLOCK) {
            return InteractionResultHolder.fail(stack);
        }
        BlockPos target = blockHit.getBlockPos().immutable();

        // —— 终端路径优先：附近有一台已解锁、充能完毕、玩家有权限的终端时，
        //    打击参数（半径/威力/下落速度）全由终端决定，遥控器只负责瞄哪儿。
        //    这里放在物品冷却检查**之前**：终端的充能由终端自己管，不该再被遥控器的
        //    旧冷却（自由开火留下的）二次卡住。
        SkyfallTerminalManager.Authorization authorization =
                SkyfallTerminalManager.authorize(serverPlayer, target);
        if (authorization == SkyfallTerminalManager.Authorization.AUTHORISED) {
            // 授权失败/充能中的提示都由 manager 发，这里只给一个身体上的反馈。
            player.swing(hand, true);
            return InteractionResultHolder.consume(stack);
        }
        if (authorization == SkyfallTerminalManager.Authorization.BLOCKED) {
            return InteractionResultHolder.fail(stack);
        }
        // NO_TERMINAL：终端是可选门槛。配置要求终端时拒绝（并提示），否则回退到 3.x 的自由开火。
        if (Config.TERMINAL_REQUIRED.get()) {
            serverPlayer.displayClientMessage(
                    Component.translatable("skyfall.terminal.required").withStyle(ChatFormatting.YELLOW), true);
            return InteractionResultHolder.fail(stack);
        }

        // —— 自由开火（3.x 旧路径）：冷却作用在物品上。
        // 冷却为 0 表示「完全无冷却」：跳过 isOnCooldown 检查，也不写冷却。
        int cooldownSeconds = mode.cooldownSeconds(Config.ORBITAL_STRIKE_COOLDOWN.get());
        if (cooldownSeconds > 0 && player.getCooldowns().isOnCooldown(this)) {
            return InteractionResultHolder.fail(stack);
        }
        if (OrbitalStrikeManager.schedule(serverPlayer, target, mode) == null) {
            return InteractionResultHolder.fail(stack);
        }
        // 手臂挥一下：给「按下了开关」一个身体上的反馈（纯表现，不影响任何判定）
        player.swing(hand, true);
        if (cooldownSeconds > 0) {
            player.getCooldowns().addCooldown(this, cooldownSeconds * 20);
        }
        return InteractionResultHolder.consume(stack);
    }

    @Override
    public void appendHoverText(ItemStack stack, @Nullable Level level,
                                List<Component> tooltip, TooltipFlag flag) {
        OrbitalStrikeMode mode = getMode(stack);
        tooltip.add(Component.translatable("orbital_mode." + mode.id()).withStyle(ChatFormatting.AQUA));
        tooltip.add(Component.translatable("item.apocalypse_zombies.orbital_strike_remote.hint")
                .withStyle(ChatFormatting.DARK_GRAY));
        if (Config.ORBITAL_STRIKE_BREAK_BEDROCK.get()) {
            tooltip.add(Component.translatable("item.apocalypse_zombies.orbital_strike_remote.bedrock")
                    .withStyle(ChatFormatting.DARK_PURPLE));
        }
    }
}
