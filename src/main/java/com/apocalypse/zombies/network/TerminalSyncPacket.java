package com.apocalypse.zombies.network;

import com.apocalypse.zombies.orbital.terminal.TerminalState;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Server → client：终端状态的一份快照。
 *
 * <p>{@code open = true} 表示「玩家刚右键了终端，把界面打开」；之后的每一次修改都回
 * {@code open = false}，由已经打开的界面就地刷新。这样不需要单独的 OpenScreen 包。</p>
 *
 * <p>客户端只把它交给 {@code SkyfallClientHooks} 画界面，不据此改任何游戏状态。</p>
 */
public class TerminalSyncPacket {

    private final TerminalState state;
    private final boolean open;

    public TerminalSyncPacket(TerminalState state, boolean open) {
        this.state = state;
        this.open = open;
    }

    public static void encode(TerminalSyncPacket packet, FriendlyByteBuf buf) {
        packet.state.encode(buf);
        buf.writeBoolean(packet.open);
    }

    public static TerminalSyncPacket decode(FriendlyByteBuf buf) {
        return new TerminalSyncPacket(TerminalState.decode(buf), buf.readBoolean());
    }

    public static void handle(TerminalSyncPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.apocalypse.zombies.client.SkyfallClientHooks.onSync(packet.state, packet.open)));
        ctx.setPacketHandled(true);
    }
}
