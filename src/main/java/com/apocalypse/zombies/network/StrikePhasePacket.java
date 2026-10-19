package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * 服务端 → 客户端：一次打击进入了新的相位（v4.0 P3）。
 *
 * <p>整场打击只在相位切换时发 6 个包（MARK / ASCENT / DEVICE / FIRE / IMPACT / AFTERMATH），
 * 客户端拿它做两件事：</p>
 * <ul>
 *   <li>校正自己的时间轴（见 {@code OrbitalStrikeClientState.onPhase}）；</li>
 *   <li>HUD 显示权威相位名，而不是本地推算。</li>
 * </ul>
 *
 * <p>{@code serverTick} 是服务端发包时的 {@code gameTime}；客户端只拿它做相位对齐，
 * 不据此改任何游戏状态。</p>
 */
public class StrikePhasePacket {

    private final UUID strikeId;
    private final int phase;
    private final int serverTick;

    public StrikePhasePacket(UUID strikeId, int phase, int serverTick) {
        this.strikeId = strikeId;
        this.phase = phase;
        this.serverTick = serverTick;
    }

    public static void encode(StrikePhasePacket packet, FriendlyByteBuf buf) {
        buf.writeUUID(packet.strikeId);
        buf.writeVarInt(packet.phase);
        buf.writeVarInt(packet.serverTick);
    }

    public static StrikePhasePacket decode(FriendlyByteBuf buf) {
        return new StrikePhasePacket(buf.readUUID(), buf.readVarInt(), buf.readVarInt());
    }

    public static void handle(StrikePhasePacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> OrbitalStrikeClientState.onPhase(packet.strikeId, packet.phase));
        ctx.setPacketHandled(true);
    }
}
