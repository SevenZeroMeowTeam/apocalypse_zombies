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

    /** v4.0 P3：新增相位/取消包，协议号从 1 升到 2（新旧客户端不允许混连）。 */
    private static final String PROTOCOL = "2";

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
        CHANNEL.registerMessage(id++, OrbitalStrikePacket.class,
                OrbitalStrikePacket::encode, OrbitalStrikePacket::decode, OrbitalStrikePacket::handle);
        // v4.0 天陨指挥终端：S2C 状态快照 + C2S 操作
        CHANNEL.registerMessage(id++, TerminalSyncPacket.class,
                TerminalSyncPacket::encode, TerminalSyncPacket::decode, TerminalSyncPacket::handle);
        CHANNEL.registerMessage(id++, TerminalActionPacket.class,
                TerminalActionPacket::encode, TerminalActionPacket::decode, TerminalActionPacket::handle);
        // v4.0 P3：相位同步 + 中止
        CHANNEL.registerMessage(id++, StrikePhasePacket.class,
                StrikePhasePacket::encode, StrikePhasePacket::decode, StrikePhasePacket::handle);
        CHANNEL.registerMessage(id++, StrikeCancelPacket.class,
                StrikeCancelPacket::encode, StrikeCancelPacket::decode, StrikeCancelPacket::handle);
    }
}
