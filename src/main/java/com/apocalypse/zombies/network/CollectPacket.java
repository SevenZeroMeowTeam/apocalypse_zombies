package com.apocalypse.zombies.network;

import java.util.Comparator;
import java.util.List;
import java.util.function.Supplier;

import com.apocalypse.zombies.Config;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.network.NetworkEvent;

/**
 * Client -> server: the player pressed the collect key.
 *
 * <p>跟别的包同一条规矩：按键只是请求，真正收什么由服务端说了算 —— 范围、上限、要不要「只收与手上相同的」
 * 全部在服务端重新读配置、重新判定。客户端版本与配置不一致时不会出现两边理解不同的情况。</p>
 *
 * <p>收集本身走 {@code Inventory.add}：塞得下就 {@code discard} 掉那个掉落物，塞不下一部分就把它余下的
 * 数量写回去（原版捡东西就是这个语义），背包满了直接停下 —— 继续试只是白跑一圈。</p>
 */
public class CollectPacket {

    public CollectPacket() {
    }

    public static void encode(CollectPacket packet, FriendlyByteBuf buf) {
        // 无载荷
    }

    public static CollectPacket decode(FriendlyByteBuf buf) {
        return new CollectPacket();
    }

    public static void handle(CollectPacket packet, Supplier<NetworkEvent.Context> context) {
        NetworkEvent.Context ctx = context.get();
        ctx.enqueueWork(() -> {
            ServerPlayer player = ctx.getSender();
            if (player == null || !Config.COLLECT_ENABLED.get()) {
                return;
            }
            if (!(player.level() instanceof ServerLevel level)) {
                return;
            }

            double radius = Config.COLLECT_RADIUS.get();
            int max = Config.COLLECT_MAX.get();
            boolean matchHand = Config.COLLECT_MATCH_HAND.get();
            ItemStack hand = player.getMainHandItem();

            List<ItemEntity> found = level.getEntitiesOfClass(ItemEntity.class,
                    player.getBoundingBox().inflate(radius),
                    drop -> drop.isAlive() && !drop.getItem().isEmpty());
            found.sort(Comparator.comparingDouble(drop -> drop.distanceToSqr(player)));

            int taken = 0;
            for (ItemEntity drop : found) {
                if (taken >= max) {
                    break;
                }
                ItemStack stack = drop.getItem();
                // 「相同物品」比的是物品本身，不比 NBT —— 耐久/附魔不同的同种东西也算同一种
                if (matchHand && !hand.isEmpty() && !ItemStack.isSameItem(stack, hand)) {
                    continue;
                }
                ItemStack moving = stack.copy();
                if (!player.getInventory().add(moving)) {
                    break;      // 背包满了
                }
                taken++;
                if (moving.isEmpty()) {
                    drop.discard();
                } else {
                    drop.setItem(moving);   // 只收进去一部分，余下的留在原地
                }
            }

            if (taken > 0) {
                player.containerMenu.broadcastChanges();
                level.playSound(null, player.getX(), player.getY(), player.getZ(),
                        SoundEvents.ITEM_PICKUP, SoundSource.PLAYERS, 0.6F, 1.2F);
            }
        });
        ctx.setPacketHandled(true);
    }
}
