package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.orbit.OrbitDimension;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.Blocks;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 轨道设施维度的安全出口：右键磁石返回、掉出平台自动返回、在轨道维度重生也返回。
 *
 * <p>这三条是“可传送维度”的必要兜底：玩家进去以后不能因为迷路/掉落/死亡被困在虚空。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class OrbitEvents {

    private OrbitEvents() {
    }

    @SubscribeEvent
    public static void onRightClickBlock(PlayerInteractEvent.RightClickBlock event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level) || !level.dimension().equals(OrbitDimension.LEVEL)) {
            return;
        }
        if (!level.getBlockState(event.getPos()).is(Blocks.LODESTONE)) {
            return;
        }
        event.setCanceled(true);
        OrbitDimension.leave(player);
    }

    @SubscribeEvent
    public static void onPlayerTick(TickEvent.PlayerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || !(event.player instanceof ServerPlayer player)) {
            return;
        }
        if (player.level().dimension().equals(OrbitDimension.LEVEL) && player.getY() < 40.0D) {
            OrbitDimension.leave(player);
        }
    }

    @SubscribeEvent
    public static void onRespawn(PlayerEvent.PlayerRespawnEvent event) {
        if (event.getEntity() instanceof ServerPlayer player
                && player.level().dimension().equals(OrbitDimension.LEVEL)) {
            OrbitDimension.leave(player);
        }
    }
}
