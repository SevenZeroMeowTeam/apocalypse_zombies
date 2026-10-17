package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Server -> client: 「轨道打击开始了」—— 目标点、选区半径、锁定剩余 tick。
 *
 * <p>客户端只拿它画光柱和地面圆环（纯视觉），不改任何游戏状态；服务端是唯一权威。
 * 锁定/下落/落地的真实进度由服务端 tick 驱动，客户端只根据「开始时刻 + 总时长」推算剩余，
 * 因此包丢失/延迟最多导致视觉少画一条光柱，不会出现「客户端已经把地挖了但服务端没有」。</p>
 */
public class OrbitalStrikePacket {

    private final BlockPos target;
    private final int radius;
    private final int lockTicks;
    private final int fallTicks;

    public OrbitalStrikePacket(BlockPos target, int radius, int lockTicks, int fallTicks) {
        this.target = target;
        this.radius = radius;
        this.lockTicks = lockTicks;
        this.fallTicks = fallTicks;
    }

    public static void encode(OrbitalStrikePacket packet, FriendlyByteBuf buf) {
        buf.writeBlockPos(packet.target);
        buf.writeVarInt(packet.radius);
        buf.writeVarInt(packet.lockTicks);
        buf.writeVarInt(packet.fallTicks);
    }

    public static OrbitalStrikePacket decode(FriendlyByteBuf buf) {
        return new OrbitalStrikePacket(buf.readBlockPos(), buf.readVarInt(), buf.readVarInt(), buf.readVarInt());
    }

    public static void handle(OrbitalStrikePacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> OrbitalStrikeClientState.start(
                packet.target, packet.radius, packet.lockTicks, packet.fallTicks));
        ctx.setPacketHandled(true);
    }
}
