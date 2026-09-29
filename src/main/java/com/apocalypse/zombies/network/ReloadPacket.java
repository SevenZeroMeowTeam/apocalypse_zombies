package com.apocalypse.zombies.network;

import com.apocalypse.zombies.item.GunItem;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Client -> server: the player pressed the reload key (R by default).
 *
 * <p>A key press is only a request — the client holds no authority over the gun. The server re-checks
 * that an AWM is really in the main hand and that the weapon is not mid-action, then picks the clip
 * (tactical when there is still a round chambered, empty when there is not) and drives it.</p>
 */
public class ReloadPacket {

    public static void encode(ReloadPacket packet, FriendlyByteBuf buf) {
        // no payload: the server reads the sender's held item
    }

    public static ReloadPacket decode(FriendlyByteBuf buf) {
        return new ReloadPacket();
    }

    public static void handle(ReloadPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> {
            ServerPlayer player = ctx.getSender();
            if (player == null || !(player.level() instanceof ServerLevel level)) {
                return;
            }
            ItemStack stack = player.getMainHandItem();
            if (stack.getItem() instanceof GunItem gun) {
                gun.beginReload(player, stack, level);
            }
        });
        ctx.setPacketHandled(true);
    }
}
