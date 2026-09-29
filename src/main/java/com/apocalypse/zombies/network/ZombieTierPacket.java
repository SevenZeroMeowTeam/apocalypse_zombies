package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.ClientZombieTiers;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Server -> client: the evolution tier of one zombie.
 *
 * <p>Entity persistent data is not synced, so the client cannot work out how big a zombie should be
 * drawn without being told. Sent when a zombie starts being tracked and again whenever it evolves.</p>
 */
public class ZombieTierPacket {

    private final int entityId;
    private final int tier;

    public ZombieTierPacket(int entityId, int tier) {
        this.entityId = entityId;
        this.tier = tier;
    }

    public static void encode(ZombieTierPacket packet, FriendlyByteBuf buf) {
        buf.writeVarInt(packet.entityId);
        buf.writeVarInt(packet.tier);
    }

    public static ZombieTierPacket decode(FriendlyByteBuf buf) {
        return new ZombieTierPacket(buf.readVarInt(), buf.readVarInt());
    }

    public static void handle(ZombieTierPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> ClientZombieTiers.set(packet.entityId, packet.tier));
        ctx.setPacketHandled(true);
    }
}
