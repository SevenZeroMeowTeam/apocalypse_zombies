package com.apocalypse.zombies.network;

import com.apocalypse.zombies.item.AmmoType;
import com.apocalypse.zombies.item.GunItem;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.network.NetworkEvent;

import java.util.function.Supplier;

/**
 * Client -> server: the player released the reload key ({@code R} by default), carrying whichever round the
 * wheel was pointing at.
 *
 * <p>A key release is only a request — the client holds no authority over the gun. The server re-checks that
 * one of our guns is really in the main hand, records the chosen round, and only then lets the gun decide
 * whether the reload can happen at all (mid-action, already full, a dry trigger's fold still running).</p>
 *
 * <p>The round is written <em>before</em> {@code beginReload} so that the fill the player asked for is what
 * gets chambered, even though the animation runs for another second or two. It also means an old client that
 * sends no round at all lands on {@link AmmoType#STANDARD} and behaves exactly as it always did.</p>
 */
public class ReloadPacket {

    /** True when the player held sneak: ask for the single-round top-up instead of a magazine change. */
    public final boolean single;

    /** 轮盘选中的弹种（{@link AmmoType#id()}）；{@code standard} = 装普通弹。 */
    public final String ammo;

    public ReloadPacket() {
        this(false, AmmoType.STANDARD.id());
    }

    public ReloadPacket(boolean single) {
        this(single, AmmoType.STANDARD.id());
    }

    public ReloadPacket(boolean single, String ammo) {
        this.single = single;
        this.ammo = ammo;
    }

    public static void encode(ReloadPacket packet, FriendlyByteBuf buf) {
        buf.writeBoolean(packet.single);
        buf.writeUtf(packet.ammo, 24);
    }

    public static ReloadPacket decode(FriendlyByteBuf buf) {
        return new ReloadPacket(buf.readBoolean(), buf.readUtf(24));
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
                gun.selectAmmo(stack, AmmoType.byId(packet.ammo));
                gun.beginReload(player, stack, level, packet.single);
            }
        });
        ctx.setPacketHandled(true);
    }
}
