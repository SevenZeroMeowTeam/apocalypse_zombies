package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * 服务端 → 客户端：这次打击中止了（v4.0 P3）。
 *
 * <p>拆终端、管理员命令、关服、维度卸载都会发它。客户端收到后立刻清掉画面状态并交还镜头 ——
 * 否则会出现「镜头挂在太空、光柱还在、地面却不再继续塌」的僵死观感。</p>
 *
 * <p>reason 只是给 HUD 文案用的，不参与任何判定。</p>
 */
public class StrikeCancelPacket {

    /** 终端被拆。 */
    public static final int REASON_TERMINAL_BROKEN = 0;
    /** 管理员命令。 */
    public static final int REASON_ADMIN = 1;
    /** 配置总开关被关掉。 */
    public static final int REASON_CONFIG_OFF = 2;
    /** 世界/维度卸载或关服。 */
    public static final int REASON_WORLD_UNLOAD = 3;

    private final UUID strikeId;
    private final int reason;

    public StrikeCancelPacket(UUID strikeId, int reason) {
        this.strikeId = strikeId;
        this.reason = reason;
    }

    public static void encode(StrikeCancelPacket packet, FriendlyByteBuf buf) {
        buf.writeUUID(packet.strikeId);
        buf.writeVarInt(packet.reason);
    }

    public static StrikeCancelPacket decode(FriendlyByteBuf buf) {
        return new StrikeCancelPacket(buf.readUUID(), buf.readVarInt());
    }

    public static void handle(StrikeCancelPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> OrbitalStrikeClientState.cancel(packet.strikeId, packet.reason));
        ctx.setPacketHandled(true);
    }
}
