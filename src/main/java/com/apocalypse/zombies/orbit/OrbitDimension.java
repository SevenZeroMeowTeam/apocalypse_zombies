package com.apocalypse.zombies.orbit;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

/**
 * 可传送的「轨道设施」维度（v5-P5）：六个平台，每个平台放一台对应协议的载体。
 *
 * <p>维度数据在 {@code data/apocalypse_zombies/dimension(_type)/orbit.json}：
 * void 超平坦 + 无自然生成 + 末地天空。平台不是结构文件，而是首次传送时由
 * {@link OrbitFacilities} 用原版方块一次性搭出来（只在对应区块已加载时搭，不强制加载无界区块）。</p>
 *
 * <p>返回点存在玩家持久化 NBT 的 {@code apocalypse_orbit_*} 里：
 * 进入时记录原维度 + 坐标，右键返回信标 / 掉出平台 / 在轨道维度重生时回到原处。</p>
 */
public final class OrbitDimension {

    public static final ResourceKey<Level> LEVEL = ResourceKey.create(
            Registries.DIMENSION, new ResourceLocation("apocalypse_zombies", "orbit"));

    /** 平台甲板顶面高度（玩家站在 Y+1）。 */
    public static final int DECK_Y = 128;
    /** 六个平台在轨道维度里的中心（正六边形，半径 512）。 */
    private static final int RADIUS = 512;

    private OrbitDimension() {
    }

    public static BlockPos platform(OrbitalStrikeMode mode) {
        int index = Math.max(0, mode.ordinal());
        double angle = Math.PI * 2.0D * index / 6.0D;
        return new BlockPos((int) Math.round(Math.cos(angle) * RADIUS), DECK_Y,
                (int) Math.round(Math.sin(angle) * RADIUS));
    }

    /** 传送到某个协议的设施平台；返回是否成功。已在轨道维度时只换平台，不覆盖返回点。 */
    public static boolean enter(ServerPlayer player, OrbitalStrikeMode mode) {
        ServerLevel level = player.server.getLevel(LEVEL);
        if (level == null) {
            player.sendSystemMessage(Component.literal("轨道维度没有加载（检查 data/apocalypse_zombies/dimension/orbit.json）。"));
            return false;
        }
        BlockPos center = platform(mode);
        OrbitFacilities.ensure(level, mode, center);
        if (!inOrbit(player)) {
            rememberReturn(player);
        }
        player.teleportTo(level, center.getX() + 0.5D, DECK_Y + 1.0D, center.getZ() + 18.5D,
                player.getYRot(), 0.0F);
        player.sendSystemMessage(Component.literal(
                "轨道设施 // " + mode.codename() + " —— 参观区，不能在这里发射打击；右键平台角的磁石返回。"));
        return true;
    }

    /** 从轨道维度返回进入前的位置；没有记录就回主世界出生点。 */
    public static boolean leave(ServerPlayer player) {
        if (!player.level().dimension().equals(LEVEL)) {
            return false;
        }
        CompoundTag tag = player.getPersistentData();
        ServerLevel target = player.server.overworld();
        double x;
        double y;
        double z;
        if (tag.contains("apocalypse_orbit_dim")) {
            ResourceKey<Level> key = ResourceKey.create(Registries.DIMENSION,
                    new ResourceLocation(tag.getString("apocalypse_orbit_dim")));
            ServerLevel candidate = player.server.getLevel(key);
            if (candidate != null) {
                target = candidate;
            }
            x = tag.getDouble("apocalypse_orbit_x");
            y = tag.getDouble("apocalypse_orbit_y");
            z = tag.getDouble("apocalypse_orbit_z");
        } else {
            Vec3 spawn = Vec3.atBottomCenterOf(target.getSharedSpawnPos());
            x = spawn.x;
            y = spawn.y;
            z = spawn.z;
        }
        tag.remove("apocalypse_orbit_dim");
        tag.remove("apocalypse_orbit_x");
        tag.remove("apocalypse_orbit_y");
        tag.remove("apocalypse_orbit_z");
        player.teleportTo(target, x, y, z, player.getYRot(), player.getXRot());
        player.sendSystemMessage(Component.literal("已返回进入轨道前的位置。"));
        return true;
    }

    public static boolean inOrbit(ServerPlayer player) {
        return player.level().dimension().equals(LEVEL);
    }

    private static void rememberReturn(ServerPlayer player) {
        CompoundTag tag = player.getPersistentData();
        tag.putString("apocalypse_orbit_dim", player.level().dimension().location().toString());
        tag.putDouble("apocalypse_orbit_x", player.getX());
        tag.putDouble("apocalypse_orbit_y", player.getY());
        tag.putDouble("apocalypse_orbit_z", player.getZ());
    }
}
