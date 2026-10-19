package com.apocalypse.zombies.orbital.terminal;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.level.Level;
import org.jetbrains.annotations.Nullable;

import java.util.List;

/**
 * 协议核心：一次性消耗品，右键天陨终端把对应模式「装进」终端。
 *
 * <p>六个核心一一对应六种打击模式（焚城/断层/隔离/蜂群/黎明/黑雨）。核心只负责回答
 * 「我是哪种模式」，安装判定与消耗都在 {@link com.apocalypse.zombies.block.SkyfallTerminalBlock#use}
 * 里做 —— 物品本身不持有任何状态，堆叠/掉落的语义才不会变复杂。</p>
 */
public class ProtocolCoreItem extends Item {

    private final OrbitalStrikeMode mode;

    public ProtocolCoreItem(OrbitalStrikeMode mode, Properties properties) {
        super(properties);
        this.mode = mode;
    }

    /** 这个核心能解锁哪种打击模式。 */
    public OrbitalStrikeMode mode() {
        return mode;
    }

    @Override
    public void appendHoverText(ItemStack stack, @Nullable Level level,
                                List<Component> tooltip, TooltipFlag flag) {
        tooltip.add(Component.translatable("orbital_mode." + mode.id()).withStyle(ChatFormatting.AQUA));
        tooltip.add(Component.translatable("skyfall.core.hint").withStyle(ChatFormatting.DARK_GRAY));
    }
}

