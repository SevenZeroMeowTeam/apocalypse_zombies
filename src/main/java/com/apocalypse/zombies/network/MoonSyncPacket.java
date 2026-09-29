package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.ClientMoonState;
import com.apocalypse.zombies.moon.MoonEvent;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/** Server -> client: the moon currently overhead plus the global evolution stage. */
public class MoonSyncPacket {

    private final MoonEvent moonEvent;
    private final int evolutionLevel;

    public MoonSyncPacket(MoonEvent moonEvent, int evolutionLevel) {
        this.moonEvent = moonEvent;
        this.evolutionLevel = evolutionLevel;
    }

    public static void encode(MoonSyncPacket packet, FriendlyByteBuf buf) {
        buf.writeByte(packet.moonEvent.ordinal());
        buf.writeVarInt(packet.evolutionLevel);
    }

    public static MoonSyncPacket decode(FriendlyByteBuf buf) {
        int ordinal = buf.readByte();
        MoonEvent[] values = MoonEvent.values();
        MoonEvent event = ordinal >= 0 && ordinal < values.length ? values[ordinal] : MoonEvent.NONE;
        return new MoonSyncPacket(event, buf.readVarInt());
    }

    public static void handle(MoonSyncPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> ClientMoonState.set(packet.moonEvent, packet.evolutionLevel));
        ctx.setPacketHandled(true);
    }
}
