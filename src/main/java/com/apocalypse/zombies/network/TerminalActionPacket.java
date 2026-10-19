package com.apocalypse.zombies.network;

import com.apocalypse.zombies.orbital.terminal.SkyfallTerminalManager;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Client → server：玩家在终端界面里动了一下（选协议 / 拖滑条 / 切过场）。
 *
 * <p>服务端只认一个东西：**当前这个玩家、这个坐标上真的有一台终端，且他有权限**。
 * 数值一律由服务端夹紧后再写进 BlockEntity；客户端说什么都不算数。</p>
 */
public class TerminalActionPacket {

    private final BlockPos pos;
    private final int action;
    private final int value;

    public TerminalActionPacket(BlockPos pos, int action, int value) {
        this.pos = pos;
        this.action = action;
        this.value = value;
    }

    public static void encode(TerminalActionPacket packet, FriendlyByteBuf buf) {
        buf.writeBlockPos(packet.pos);
        buf.writeVarInt(packet.action);
        buf.writeVarInt(packet.value);
    }

    public static TerminalActionPacket decode(FriendlyByteBuf buf) {
        return new TerminalActionPacket(buf.readBlockPos(), buf.readVarInt(), buf.readVarInt());
    }

    public static void handle(TerminalActionPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> {
            ServerPlayer player = ctx.getSender();
            if (player != null) {
                SkyfallTerminalManager.handleAction(player, packet.pos, packet.action, packet.value);
            }
        });
        ctx.setPacketHandled(true);
    }
}
