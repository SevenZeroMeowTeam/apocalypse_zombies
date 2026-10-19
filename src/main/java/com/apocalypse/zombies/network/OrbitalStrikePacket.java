package com.apocalypse.zombies.network;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * Server -> client: 「轨道打击开始了」—— 目标点、实际半径、锁定/下落 tick、打击模式。
 *
 * <p>客户端只拿它画光柱和地面圆环（纯视觉），不改任何游戏状态；服务端是唯一权威。
 * 全部时长都<b>由服务端算好再发</b>（模式倍率在服务端乘过），客户端不重算 ——
 * 避免两端口径漂移导致光柱和挖地不同步。</p>
 *
 * <p>v4.0 P3 起多带三个字段：</p>
 * <ul>
 *   <li>{@code strikeId}：同一次打击的唯一标识，后续的相位/取消包都带同一个；</li>
 *   <li>{@code spectator}：true 表示「我不是施放者，只是被广播的旁观者」；</li>
 *   <li>{@code serverGameTime}：服务端发包时的 gameTime（首次对齐用）。</li>
 * </ul>
 *
 * <p>旧包（没有 id）仍然可解析 —— 自由开火路径暂时还走旧构造器，id 为 null。</p>
 */
public class OrbitalStrikePacket {

    private final BlockPos target;
    private final int radius;
    private final int lockTicks;
    private final int fallTicks;
    private final OrbitalStrikeMode mode;
    /** 玩家触发时的朝向（度）：断层裂谷沿这个方向展开。 */
    private final float yaw;
    /** 本次打击的标识；null = 旧路径（没有后续相位包）。 */
    private final UUID strikeId;
    /** true = 观众视角（被广播的旁观者）。 */
    private final boolean spectator;
    /** 服务端发包时的 gameTime。 */
    private final long serverGameTime;

    /** 旧构造器：自由开火路径用，不带 id/观众标记。 */
    public OrbitalStrikePacket(BlockPos target, int radius, int lockTicks, int fallTicks,
                               OrbitalStrikeMode mode, float yaw) {
        this(target, radius, lockTicks, fallTicks, mode, yaw, null, false, 0L);
    }

    public OrbitalStrikePacket(BlockPos target, int radius, int lockTicks, int fallTicks,
                               OrbitalStrikeMode mode, float yaw, UUID strikeId,
                               boolean spectator, long serverGameTime) {
        this.target = target;
        this.radius = radius;
        this.lockTicks = lockTicks;
        this.fallTicks = fallTicks;
        this.mode = mode;
        this.yaw = yaw;
        this.strikeId = strikeId;
        this.spectator = spectator;
        this.serverGameTime = serverGameTime;
    }

    public static void encode(OrbitalStrikePacket packet, FriendlyByteBuf buf) {
        buf.writeBlockPos(packet.target);
        buf.writeVarInt(packet.radius);
        buf.writeVarInt(packet.lockTicks);
        buf.writeVarInt(packet.fallTicks);
        buf.writeUtf(packet.mode.id());
        buf.writeFloat(packet.yaw);
        buf.writeBoolean(packet.strikeId != null);
        if (packet.strikeId != null) {
            buf.writeUUID(packet.strikeId);
        }
        buf.writeBoolean(packet.spectator);
        buf.writeLong(packet.serverGameTime);
    }

    public static OrbitalStrikePacket decode(FriendlyByteBuf buf) {
        BlockPos target = buf.readBlockPos();
        int radius = buf.readVarInt();
        int lockTicks = buf.readVarInt();
        int fallTicks = buf.readVarInt();
        OrbitalStrikeMode mode = OrbitalStrikeMode.byId(buf.readUtf());
        float yaw = buf.readFloat();
        UUID strikeId = buf.readBoolean() ? buf.readUUID() : null;
        boolean spectator = buf.readBoolean();
        long serverGameTime = buf.readLong();
        return new OrbitalStrikePacket(target, radius, lockTicks, fallTicks, mode, yaw,
                strikeId, spectator, serverGameTime);
    }

    public static void handle(OrbitalStrikePacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> OrbitalStrikeClientState.start(
                packet.target, packet.radius, packet.lockTicks, packet.fallTicks, packet.mode,
                packet.yaw, packet.strikeId, packet.spectator));
        ctx.setPacketHandled(true);
    }
}
