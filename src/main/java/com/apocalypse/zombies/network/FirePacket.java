package com.apocalypse.zombies.network;

import com.apocalypse.zombies.item.GunItem;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Client -> server: the player pressed the fire button (left mouse by default).
 *
 * <p>Same contract as {@link ReloadPacket}: the press is only a request. The client never decides whether
 * a shot happens — the server re-checks the held item, the round count and the action lock, so a packet
 * spammer gets exactly the same cadence as an honest player.</p>
 */
public class FirePacket {

    public static void encode(FirePacket packet, FriendlyByteBuf buf) {
        // no payload: the server reads the sender's held item and look vector itself
    }

    public static FirePacket decode(FriendlyByteBuf buf) {
        return new FirePacket();
    }

    public static void handle(FirePacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> {
            ServerPlayer player = ctx.getSender();
            if (player == null || !(player.level() instanceof ServerLevel level)) {
                return;
            }
            ItemStack stack = player.getMainHandItem();
            if (stack.getItem() instanceof GunItem gun) {
                gun.tryFire(player, stack, level);
            }
        });
        ctx.setPacketHandled(true);
    }
}
