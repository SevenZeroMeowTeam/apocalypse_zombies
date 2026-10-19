package com.apocalypse.zombies.orbit;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * 轨道设施平台的程序化搭建：只用原版方块，第一次传送到某个平台时一次性搭出来。
 *
 * <p>每个平台 = 49×49 双层甲板 + 玻璃护栏 + 四角海晶灯 + 一台对应协议的“载体”轮廓 +
 * 角落的磁石返回点。没有结构文件、没有维度专属方块，存档删掉维度也不会伤到主世界。</p>
 *
 * <p>只在区块已加载时写方块：传送前由 {@link #ensure} 先取周围 7×7 区块，
 * 不额外申请无界 ticket；平台之间相隔很远，所以玩家只会加载当前这一座。</p>
 */
public final class OrbitFacilities {

    private static final int HALF = 24;

    private OrbitFacilities() {
    }

    public static void ensure(ServerLevel level, OrbitalStrikeMode mode, BlockPos center) {
        if (!level.getBlockState(center.below(2)).isAir()) {
            return; // 已经搭过
        }
        int chunkX = center.getX() >> 4;
        int chunkZ = center.getZ() >> 4;
        for (int dx = -2; dx <= 2; dx++) {
            for (int dz = -2; dz <= 2; dz++) {
                level.getChunk(chunkX + dx, chunkZ + dz);
            }
        }

        // —— 甲板：两层，棋盘格
        for (int x = -HALF; x <= HALF; x++) {
            for (int z = -HALF; z <= HALF; z++) {
                BlockState floor = ((x + z) & 1) == 0 ? Blocks.SMOOTH_STONE.defaultBlockState()
                        : Blocks.DEEPSLATE_TILES.defaultBlockState();
                set(level, center, x, 0, z, floor);
                set(level, center, x, -1, z, Blocks.DEEPSLATE_TILES.defaultBlockState());
            }
        }
        // 玻璃护栏 + 四角灯
        for (int i = -HALF; i <= HALF; i++) {
            set(level, center, i, 1, -HALF, Blocks.GLASS.defaultBlockState());
            set(level, center, i, 1, HALF, Blocks.GLASS.defaultBlockState());
            set(level, center, -HALF, 1, i, Blocks.GLASS.defaultBlockState());
            set(level, center, HALF, 1, i, Blocks.GLASS.defaultBlockState());
        }
        for (int sx : new int[]{-HALF, HALF}) {
            for (int sz : new int[]{-HALF, HALF}) {
                set(level, center, sx, 1, sz, Blocks.SEA_LANTERN.defaultBlockState());
            }
        }
        // 中央基座
        fill(level, center, -6, 1, -6, 6, 1, 6, Blocks.POLISHED_DEEPSLATE.defaultBlockState());

        switch (mode) {
            case CANNON -> cannon(level, center);
            case LANCE -> lance(level, center);
            case GRAVITY -> gravity(level, center);
            case STORM -> storm(level, center);
            case LASER -> laser(level, center);
            case PLANET -> planet(level, center);
        }

        // 返回磁石（右上角）
        BlockPos pad = center.offset(18, 1, 18);
        set(level, pad, 0, 0, 0, Blocks.LODESTONE.defaultBlockState());
        set(level, pad, 1, 0, 0, Blocks.SEA_LANTERN.defaultBlockState());
        set(level, pad, -1, 0, 0, Blocks.SEA_LANTERN.defaultBlockState());
        set(level, pad, 0, 0, 1, Blocks.SEA_LANTERN.defaultBlockState());
        set(level, pad, 0, 0, -1, Blocks.SEA_LANTERN.defaultBlockState());
    }

    // ------------------------------------------------------------------ 六种载体

    private static void cannon(ServerLevel level, BlockPos c) {
        fill(level, c, -5, 2, -5, 5, 3, 5, Blocks.IRON_BLOCK.defaultBlockState());
        fill(level, c, -3, 4, -3, 3, 8, 3, Blocks.SMOOTH_STONE.defaultBlockState());
        fill(level, c, -4, 9, -4, 4, 9, 4, Blocks.DEEPSLATE_TILES.defaultBlockState());
        // 炮管（沿 +X）
        fill(level, c, 3, 6, -1, 23, 7, 1, Blocks.COPPER_BLOCK.defaultBlockState());
        fill(level, c, 23, 6, -2, 23, 7, 2, Blocks.COPPER_BLOCK.defaultBlockState());
        set(level, c, 23, 7, 0, Blocks.SEA_LANTERN.defaultBlockState());
        // 后座支架
        fill(level, c, 5, 4, -2, 8, 5, 2, Blocks.COPPER_BLOCK.defaultBlockState());
    }

    private static void lance(ServerLevel level, BlockPos c) {
        for (int side : new int[]{-3, 3}) {
            for (int x = -14; x <= 14; x++) {
                set(level, c, x, 2, side, Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                if (x % 7 == 0) {
                    fill(level, c, x, 0, side, x, 1, side, Blocks.DEEPSLATE_TILES.defaultBlockState());
                }
            }
        }
        fill(level, c, -6, 4, 0, 6, 5, 0, Blocks.QUARTZ_BLOCK.defaultBlockState());
        set(level, c, 7, 4, 0, Blocks.SEA_LANTERN.defaultBlockState());
        set(level, c, 7, 5, 0, Blocks.SEA_LANTERN.defaultBlockState());
        // 弹头
        fill(level, c, -7, 4, 0, -6, 5, 0, Blocks.IRON_BLOCK.defaultBlockState());
    }

    private static void gravity(ServerLevel level, BlockPos c) {
        ringXZ(level, c, 10, 2, Blocks.OBSIDIAN.defaultBlockState());
        ringXZ(level, c, 14, 2, Blocks.BLACKSTONE.defaultBlockState());
        ringXY(level, c, 8, 0, 2, Blocks.OBSIDIAN.defaultBlockState());
        fill(level, c, -1, 3, -1, 1, 6, 1, Blocks.MAGMA_BLOCK.defaultBlockState());
        set(level, c, 0, 7, 0, Blocks.SEA_LANTERN.defaultBlockState());
    }

    private static void storm(ServerLevel level, BlockPos c) {
        for (int i = 0; i < 7; i++) {
            double angle = Math.PI * 2.0D * i / 7.0D;
            int x = (int) Math.round(Math.cos(angle) * 13.0D);
            int z = (int) Math.round(Math.sin(angle) * 13.0D);
            fill(level, c, x, 1, z, x, 6, z, Blocks.PURPLE_CONCRETE.defaultBlockState());
            set(level, c, x, 7, z, Blocks.SEA_LANTERN.defaultBlockState());
        }
        ringXZ(level, c, 13, 1, Blocks.GLOWSTONE.defaultBlockState());
        fill(level, c, -1, 1, -1, 1, 4, 1, Blocks.OBSIDIAN.defaultBlockState());
        set(level, c, 0, 5, 0, Blocks.SEA_LANTERN.defaultBlockState());
    }

    private static void laser(ServerLevel level, BlockPos c) {
        // 卫星本体
        fill(level, c, -3, 5, -3, 3, 11, 3, Blocks.GOLD_BLOCK.defaultBlockState());
        // 两侧太阳翼
        for (int side : new int[]{-1, 1}) {
            int inner = side * 5;
            int outer = side * 15;
            int x0 = Math.min(inner, outer);
            int x1 = Math.max(inner, outer);
            fill(level, c, x0, 7, -2, x1, 7, 2, Blocks.BLUE_CONCRETE.defaultBlockState());
            fill(level, c, x0, 8, -2, x1, 8, 2, Blocks.GLASS.defaultBlockState());
        }
        // 天线
        fill(level, c, 0, 12, 0, 0, 15, 0, Blocks.END_ROD.defaultBlockState());
        // 抛物面（XY 平面的环 + 中心）
        ringXY(level, c, 5, 0, 8, Blocks.QUARTZ_BLOCK.defaultBlockState());
        set(level, c, 0, 9, 8, Blocks.SEA_LANTERN.defaultBlockState());
    }

    private static void planet(ServerLevel level, BlockPos c) {
        int r = 7;
        for (int x = -r; x <= r; x++) {
            for (int y = -r; y <= r; y++) {
                for (int z = -r; z <= r; z++) {
                    if (x * x + y * y + z * z > r * r) {
                        continue;
                    }
                    long hash = (long) (x + 31) * 341873128712L ^ (long) (y + 31) * 132897987541L
                            ^ (long) (z + 31) * 17L;
                    BlockState state = (hash & 7L) == 0L ? Blocks.MAGMA_BLOCK.defaultBlockState()
                            : ((hash & 1L) == 0L ? Blocks.BLACKSTONE.defaultBlockState()
                            : Blocks.DEEPSLATE.defaultBlockState());
                    set(level, c, x, 8 + y, z, state);
                }
            }
        }
        ringXZ(level, c, 12, 2, Blocks.BASALT.defaultBlockState());
        ringXZ(level, c, 15, 2, Blocks.BASALT.defaultBlockState());
    }

    // ------------------------------------------------------------------ 画图工具

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
        int steps = Math.max(24, radius * 8);
        for (int i = 0; i < steps; i++) {
            double a = Math.PI * 2.0D * i / steps;
            set(level, c, (int) Math.round(Math.cos(a) * radius), y, (int) Math.round(Math.sin(a) * radius), state);
        }
    }

    private static void ringXY(ServerLevel level, BlockPos c, int radius, int yCenter, int z, BlockState state) {
        int steps = Math.max(24, radius * 8);
        for (int i = 0; i < steps; i++) {
            double a = Math.PI * 2.0D * i / steps;
            set(level, c, (int) Math.round(Math.cos(a) * radius), yCenter + (int) Math.round(Math.sin(a) * radius), z, state);
        }
    }

    private static void set(ServerLevel level, BlockPos c, int dx, int dy, int dz, BlockState state) {
        level.setBlock(c.offset(dx, dy, dz), state, 2);
    }
}
