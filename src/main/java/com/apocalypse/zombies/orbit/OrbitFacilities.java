package com.apocalypse.zombies.orbit;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * 轨道设施平台的程序化搭建（v4.0.8 起改用专用装饰方块）。
 *
 * <p>贴图是程序化原创的 32×32 装甲板/金箔/太阳能电池/抛物面/自发光条（{@code tools/facility_art.py}），
 * 让卫星、炮台、导轨、环站、等离子舰、陨石在轨道维度里更接近参考图的工业质感；
 * 方块本身不可破坏、无物品形态，只服务这个维度。</p>
 *
 * <p>平台 = 49×49 双层甲板 + 玻璃护栏 + 四角灯 + 中央载体 + 玩家落点（z+18）+
 * 角落磁石返回点。只在区块已加载时写方块，不申请无界 ticket。</p>
 */
public final class OrbitFacilities {

    private static final int HALF = 24;

    private OrbitFacilities() {
    }

    public static void ensure(ServerLevel level, OrbitalStrikeMode mode, BlockPos center) {
        if (!level.getBlockState(center.below(1)).isAir()) {
            return;
        }
        int chunkX = center.getX() >> 4;
        int chunkZ = center.getZ() >> 4;
        for (int dx = -2; dx <= 2; dx++) {
            for (int dz = -2; dz <= 2; dz++) {
                level.getChunk(chunkX + dx, chunkZ + dz);
            }
        }

        // 甲板：深灰装甲板 + 深色结构件棋盘格
        for (int x = -HALF; x <= HALF; x++) {
            for (int z = -HALF; z <= HALF; z++) {
                BlockState floor = ((x + z) & 1) == 0 ? hull() : dark();
                set(level, center, x, 0, z, floor);
                set(level, center, x, -1, z, dark());
            }
        }
        for (int i = -HALF; i <= HALF; i++) {
            set(level, center, i, 1, -HALF, Blocks.GLASS.defaultBlockState());
            set(level, center, i, 1, HALF, Blocks.GLASS.defaultBlockState());
            set(level, center, -HALF, 1, i, Blocks.GLASS.defaultBlockState());
            set(level, center, HALF, 1, i, Blocks.GLASS.defaultBlockState());
        }
        for (int sx : new int[]{-HALF, HALF}) {
            for (int sz : new int[]{-HALF, HALF}) {
                set(level, center, sx, 1, sz, glowCyan());
            }
        }
        fill(level, center, -7, 1, -7, 7, 1, 7, hull());

        switch (mode) {
            case CANNON -> cannon(level, center);
            case LANCE -> lance(level, center);
            case GRAVITY -> gravity(level, center);
            case STORM -> storm(level, center);
            case LASER -> laser(level, center);
            case PLANET -> planet(level, center);
        }

        // 返回磁石 + 落点灯带
        BlockPos pad = center.offset(18, 1, 18);
        set(level, pad, 0, 0, 0, Blocks.LODESTONE.defaultBlockState());
        for (int dx = -2; dx <= 2; dx++) {
            for (int dz = -2; dz <= 2; dz++) {
                if (Math.abs(dx) == 2 && Math.abs(dz) == 2) {
                    set(level, pad, dx, 0, dz, glowCyan());
                }
            }
        }
        // 玩家落点（z+18）前方的引导灯
        for (int dx = -2; dx <= 2; dx++) {
            set(level, center, dx, 1, 16, glowCyan());
        }
    }

    // ------------------------------------------------------------------ 六种载体

    /** 轨道炮：桁架炮台 + 长炮管 + 侧面太阳能翼，炮口带制动环。 */
    private static void cannon(ServerLevel level, BlockPos c) {
        fill(level, c, -8, 2, -8, 8, 2, 8, hull());
        fill(level, c, -5, 3, -5, 5, 3, 5, dark());
        fill(level, c, -4, 4, -4, 4, 10, 4, hull());
        fill(level, c, -5, 10, -5, 5, 10, 5, hull());
        // 金色加强环
        ringXZ(level, c, 6, 4, gold());
        ringXZ(level, c, 6, 7, gold());
        // 炮管（沿 +X）：3×3，每 6 格一个金环
        for (int x = 4; x <= 30; x++) {
            if (x % 6 == 0) {
                fill(level, c, x, 6, -2, x, 8, 2, gold());
            } else {
                fill(level, c, x, 6, -1, x, 8, 1, hull());
            }
        }
        fill(level, c, 31, 5, -3, 33, 9, 3, dark());
        set(level, c, 33, 7, 0, glowCyan());
        // 炮口冷却片
        for (int z = -3; z <= 3; z += 2) {
            set(level, c, 32, 4, z, gold());
            set(level, c, 32, 10, z, gold());
        }
        // 后座散热片
        fill(level, c, -10, 5, -1, -10, 7, 1, dark());
        // 太阳能翼
        for (int side : new int[]{-1, 1}) {
            fill(level, c, -12, 6, side * 4, -6, 6, side * 6, hull());
            fill(level, c, -18, 6, side * 7, -4, 6, side * 13, solar());
            fill(level, c, -18, 7, side * 7, -18, 7, side * 13, gold());
        }
        // 尾部推进器
        for (int z : new int[]{-2, 2}) {
            fill(level, c, -9, 2, z, -9, 4, z, dark());
            set(level, c, -10, 3, z, glowOrange());
        }
    }

    /** 天基矛：双导轨 + 支撑塔 + 金属矛体，导轨带青色能量线。 */
    private static void lance(ServerLevel level, BlockPos c) {
        fill(level, c, -8, 2, -8, 8, 2, 8, hull());
        for (int side : new int[]{-1, 1}) {
            for (int x = -20; x <= 20; x++) {
                set(level, c, x, 3, side * 4, hull());
                set(level, c, x, 4, side * 5, gold());
                if (x % 9 == 0) {
                    fill(level, c, x, 1, side * 4, x, 2, side * 6, dark());
                }
            }
            set(level, c, -20, 4, side * 4, glowCyan());
            set(level, c, 20, 4, side * 4, glowCyan());
        }
        // 矛体
        fill(level, c, -7, 5, -1, 6, 7, 1, panel());
        fill(level, c, 7, 5, -1, 8, 7, 1, dark());
        fill(level, c, 9, 6, 0, 11, 6, 0, dark());
        // 尾翼
        for (int side : new int[]{-1, 1}) {
            fill(level, c, -8, 5, side * 2, -8, 7, side * 3, gold());
        }
        // 支撑塔
        fill(level, c, 0, 3, -3, 0, 4, 3, hull());
    }

    /** 引力奇点：三向外环 + 金色内环 + 黑球核心 + 青色奇点。 */
    private static void gravity(ServerLevel level, BlockPos c) {
        ringXZ(level, c, 15, 5, hull());
        ringXZ(level, c, 11, 5, gold());
        ringXY(level, c, 10, 6, 0, hull());
        ringXY(level, c, 7, 6, 0, dark());
        // 辐条
        for (int i = 0; i < 8; i++) {
            double a = Math.PI * 2.0D * i / 8.0D;
            for (int r = 4; r <= 14; r++) {
                int x = (int) Math.round(Math.cos(a) * r);
                int z = (int) Math.round(Math.sin(a) * r);
                set(level, c, x, 5, z, dark());
            }
        }
        sphere(level, c, 0, 7, 0, 4, dark());
        set(level, c, 0, 7, 0, glowCyan());
        set(level, c, 0, 6, 0, glowCyan());
        set(level, c, 0, 8, 0, glowCyan());
    }

    /** 等离子风暴：舰体 + 七座发射塔 + 前端发射环。 */
    private static void storm(ServerLevel level, BlockPos c) {
        fill(level, c, -12, 3, -6, 12, 8, 6, hull());
        fill(level, c, -12, 8, -6, 12, 8, 6, dark());
        fill(level, c, -10, 4, -7, 10, 7, -7, panel());
        fill(level, c, -10, 4, 7, 10, 7, 7, panel());
        // 金色腰线
        fill(level, c, -12, 6, -6, 12, 6, -6, gold());
        fill(level, c, -12, 6, 6, 12, 6, 6, gold());
        // 七座发射塔（半圆排列，朝前）
        for (int i = 0; i < 7; i++) {
            double a = Math.PI * 0.15D + Math.PI * 0.70D * i / 6.0D;
            int x = (int) Math.round(Math.cos(a) * 9.0D);
            int z = (int) Math.round(Math.sin(a) * 9.0D) + 2;
            fill(level, c, x, 9, z, x, 13, z, dark());
            set(level, c, x, 14, z, glowOrange());
        }
        // 发射环（XY 前方）
        ringXY(level, c, 7, 7, 11, glowCyan());
        ringXY(level, c, 8, 7, 11, dark());
        fill(level, c, -1, 7, 11, 1, 7, 11, glowOrange());
        // 侧翼
        for (int side : new int[]{-1, 1}) {
            fill(level, c, -6, 5, side * 12, 6, 5, side * 16, solar());
            fill(level, c, -6, 6, side * 12, -6, 6, side * 16, gold());
        }
    }

    /** 卫星（v4.1.0 起改由 GeckoLib 实体展示；这里只保留基座与引导灯）。 */
    private static void laser(ServerLevel level, BlockPos c) {
        fill(level, c, -8, 2, -8, 8, 2, 8, hull());
        // 支撑基座：方块卫星已换成 OrbitSatellite 实体，甲板中央留空给模型
        fill(level, c, -3, 3, -3, 3, 3, 3, dark());
        fill(level, c, -5, 3, -5, 5, 3, -4, panel());
        for (int x : new int[]{-5, 5}) {
            for (int z : new int[]{-5, 5}) {
                set(level, c, x, 4, z, glowCyan());
            }
        }
        // 服务端只做一次：家里没有卫星实体才生成（OrbitFacilities.ensure 本身去重）
        spawnSatellite(level, c);
    }

    /**
     * 在平台中央生成轨道卫星展示实体（无 AI、不可推动、贴回出生点）。
     * 重复进入维度不会重复生成：先查附近是否已有。
     */
    private static void spawnSatellite(ServerLevel level, BlockPos c) {
        net.minecraft.world.phys.AABB box = new net.minecraft.world.phys.AABB(
                c.getX() - 6, c.getY() + 2, c.getZ() - 6,
                c.getX() + 6, c.getY() + 10, c.getZ() + 6);
        java.util.List<com.apocalypse.zombies.entity.OrbitSatellite> existing =
                level.getEntitiesOfClass(com.apocalypse.zombies.entity.OrbitSatellite.class, box);
        if (!existing.isEmpty()) {
            return;
        }
        com.apocalypse.zombies.entity.OrbitSatellite satellite =
                com.apocalypse.zombies.registry.ModEntities.ORBIT_SATELLITE.get()
                        .create(level);
        if (satellite == null) {
            return;
        }
        // 模型约 7 格高，甲板 Y+4 起算，落在基座上方；朝向让天线朝向平台边缘
        satellite.setup(com.apocalypse.zombies.orbital.OrbitalStrikeMode.LASER,
                c.getX() + 0.5D, c.getY() + 6.0D, c.getZ() + 0.5D);
        level.addFreshEntity(satellite);
    }

    /** 行星陨落：大颗岩质球体 + 熔岩裂纹 + 双层碎屑环。 */
    private static void planet(ServerLevel level, BlockPos c) {
        fill(level, c, -8, 2, -8, 8, 2, 8, hull());
        sphereMixed(level, c, 0, 10, 0, 9);
        ringXZ(level, c, 13, 3, dish());
        ringXZ(level, c, 16, 3, hull());
        ringXZ(level, c, 19, 3, dark());
        // 环上的金/橙点
        for (int i = 0; i < 28; i++) {
            double a = Math.PI * 2.0D * i / 28.0D;
            set(level, c, (int) Math.round(Math.cos(a) * 16.0D), 3,
                    (int) Math.round(Math.sin(a) * 16.0D), i % 3 == 0 ? glowOrange() : gold());
        }
    }

    // ------------------------------------------------------------------ 画图工具

    private static void sphere(ServerLevel level, BlockPos c, int cx, int cy, int cz, int r, BlockState state) {
        for (int x = -r; x <= r; x++) {
            for (int y = -r; y <= r; y++) {
                for (int z = -r; z <= r; z++) {
                    if (x * x + y * y + z * z <= r * r) {
                        set(level, c, cx + x, cy + y, cz + z, state);
                    }
                }
            }
        }
    }

    private static void sphereMixed(ServerLevel level, BlockPos c, int cx, int cy, int cz, int r) {
        for (int x = -r; x <= r; x++) {
            for (int y = -r; y <= r; y++) {
                for (int z = -r; z <= r; z++) {
                    int d = x * x + y * y + z * z;
                    if (d > r * r) {
                        continue;
                    }
                    long hash = (long) (x + 31) * 341873128712L ^ (long) (y + 31) * 132897987541L
                            ^ (long) (z + 31) * 17L;
                    BlockState state;
                    if ((hash % 19L) == 0L) {
                        state = glowOrange();
                    } else if ((hash & 3L) == 0L) {
                        state = gold();
                    } else if ((hash & 1L) == 0L) {
                        state = dark();
                    } else {
                        state = hull();
                    }
                    set(level, c, cx + x, cy + y, cz + z, state);
                }
            }
        }
    }

    private static void fill(ServerLevel level, BlockPos c, int x0, int y0, int z0,
                             int x1, int y1, int z1, BlockState state) {
        for (int x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) {
            for (int y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) {
                for (int z = Math.min(z0, z1); z <= Math.max(z0, z1); z++) {
                    set(level, c, x, y, z, state);
                }
            }
        }
    }

    private static void ringXZ(ServerLevel level, BlockPos c, int radius, int y, BlockState state) {
        int steps = Math.max(32, radius * 8);
        for (int i = 0; i < steps; i++) {
            double a = Math.PI * 2.0D * i / steps;
            set(level, c, (int) Math.round(Math.cos(a) * radius), y, (int) Math.round(Math.sin(a) * radius), state);
        }
    }

    private static void ringXY(ServerLevel level, BlockPos c, int radius, int yCenter, int z, BlockState state) {
        int steps = Math.max(32, radius * 8);
        for (int i = 0; i < steps; i++) {
            double a = Math.PI * 2.0D * i / steps;
            set(level, c, (int) Math.round(Math.cos(a) * radius),
                    yCenter + (int) Math.round(Math.sin(a) * radius), z, state);
        }
    }

    private static void set(ServerLevel level, BlockPos c, int dx, int dy, int dz, BlockState state) {
        level.setBlock(c.offset(dx, dy, dz), state, 2);
    }

    private static BlockState hull() {
        return ModBlocks.FACILITY_HULL.get().defaultBlockState();
    }

    private static BlockState gold() {
        return ModBlocks.FACILITY_GOLD.get().defaultBlockState();
    }

    private static BlockState panel() {
        return ModBlocks.FACILITY_PANEL.get().defaultBlockState();
    }

    private static BlockState solar() {
        return ModBlocks.FACILITY_SOLAR.get().defaultBlockState();
    }

    private static BlockState dish() {
        return ModBlocks.FACILITY_DISH.get().defaultBlockState();
    }

    private static BlockState glowCyan() {
        return ModBlocks.FACILITY_GLOW_CYAN.get().defaultBlockState();
    }

    private static BlockState glowOrange() {
        return ModBlocks.FACILITY_GLOW_ORANGE.get().defaultBlockState();
    }

    private static BlockState dark() {
        return ModBlocks.FACILITY_DARK.get().defaultBlockState();
    }
}
