package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Server -> client: 「轨道打击开始了」—— 目标点、实际半径、锁定/下落 tick、打击模式。
 *
 * <p>客户端只拿它画光柱和地面圆环（纯视觉），不改任何游戏状态；服务端是唯一权威。
 * 全部时长都<b>由服务端算好再发</b>（模式倍率在服务端乘过），客户端不重算 ——
 * 避免两端口径漂移导致光柱和挖地不同步。</p>
 */
public class OrbitalStrikePacket {

    private final BlockPos target;
    private final int radius;
    private final int lockTicks;
    private final int fallTicks;
    private final OrbitalStrikeMode mode;
    /** 玩家触发时的朝向（度）：断层裂谷沿这个方向展开。 */
    private final float yaw;

    public OrbitalStrikePacket(BlockPos target, int radius, int lockTicks, int fallTicks,
                               OrbitalStrikeMode mode, float yaw) {
        this.target = target;
        this.radius = radius;
        this.lockTicks = lockTicks;
        this.fallTicks = fallTicks;
        this.mode = mode;
        this.yaw = yaw;
    }

    public static void encode(OrbitalStrikePacket packet, FriendlyByteBuf buf) {
        buf.writeBlockPos(packet.target);
        buf.writeVarInt(packet.radius);
        buf.writeVarInt(packet.lockTicks);
        buf.writeVarInt(packet.fallTicks);
        buf.writeUtf(packet.mode.id());
        buf.writeFloat(packet.yaw);
    }

    public static OrbitalStrikePacket decode(FriendlyByteBuf buf) {
        return new OrbitalStrikePacket(buf.readBlockPos(), buf.readVarInt(), buf.readVarInt(),
                buf.readVarInt(), OrbitalStrikeMode.byId(buf.readUtf()), buf.readFloat());
    }

    public static void handle(OrbitalStrikePacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> OrbitalStrikeClientState.start(
                packet.target, packet.radius, packet.lockTicks, packet.fallTicks, packet.mode,
                packet.yaw));
        ctx.setPacketHandled(true);
    }
}
