package com.apocalypse.zombies.network;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.network.NetworkRegistry;
import net.minecraftforge.network.simple.SimpleChannel;

/**
 * Single channel carrying everything the client and server have to tell each other: night-sky state,
 * zombie tiers, and the player's request to reload a weapon.
 */
public final class NetworkHandler {

    private static final String PROTOCOL = "1";

    public static final SimpleChannel CHANNEL = NetworkRegistry.newSimpleChannel(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "main"),
            () -> PROTOCOL,
            PROTOCOL::equals,
            PROTOCOL::equals);

    private NetworkHandler() {
    }

    public static void register() {
        int id = 0;
        CHANNEL.registerMessage(id++, MoonSyncPacket.class,
                MoonSyncPacket::encode, MoonSyncPacket::decode, MoonSyncPacket::handle);
        CHANNEL.registerMessage(id++, ZombieTierPacket.class,
                ZombieTierPacket::encode, ZombieTierPacket::decode, ZombieTierPacket::handle);
        CHANNEL.registerMessage(id++, ReloadPacket.class,
                ReloadPacket::encode, ReloadPacket::decode, ReloadPacket::handle);
        CHANNEL.registerMessage(id++, FirePacket.class,
                FirePacket::encode, FirePacket::decode, FirePacket::handle);
        CHANNEL.registerMessage(id++, CollectPacket.class,
                CollectPacket::encode, CollectPacket::decode, CollectPacket::handle);
    }
}
