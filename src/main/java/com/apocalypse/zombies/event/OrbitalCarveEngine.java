package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 打击地形改写的「算形 / 落块」两段式引擎（v5.2.0）。
 *
 * <p><b>为什么不能直接在服务端线程里算</b>：一次打击要改写十几万格地形
 * （半径 24 的选区约 11.7 万格）。如果「决定挖哪个格子、挖成什么」也在主线程算，
 * 算出来的每一格都要读一次 chunk —— 读 chunk 会拖慢主线程，打击的瞬间整服卡顿。
 * 现在��做法是：主线程只负责**读快照**和**落块**，中间的纯计算丢给工作线程。</p>
 *
 * <p><b>为什么工作线程不能直接改世界</b>：MC 的区块数据没有并发保护，
 * 工作线程直接 {@code setBlock} 会撕裂区块（参考包 the-shooting-star 也踩过这条线，
 * 它的做法是工作线程只算、落块一律回服务端线程 —— 本模组照抄这个纪律）。</p>
 *
 * <p><b>线程池规模</b>：{@code clamp(可用核数 - 2, 2, 8)}（与参考包一致）。
 * 少留两个核给服务端，8 是上限 —— 再多只会让内存带宽先饱和。</p>
 *
 * <p><b>内存预算</b>：{@code maxMemory / 16}。预计算的「要改哪些格子」列表
 * 会占内存，超预算就少算一点，剩下的下一 tick 继续（宁可慢，不要 OOM）。</p>
 */
public final class OrbitalCarveEngine {

    /** 一次算形任务的产出：一批「坐标 → 新状态」的改动。 */
    public record Plan(long[] packed, BlockState[] states) {
        public static final Plan EMPTY = new Plan(new long[0], new BlockState[0]);

        public int size() {
            return packed.length;
        }
    }

    /** 工作线程算出来的形状描述：一个区域内哪些格子要改成什么。 */
    @FunctionalInterface
    public interface ShapeFn {
        /**
         * 在工作线程上算形。
         *
         * @param region 目标区域（只读）
         * @param out    产出缓冲：把「坐标 + 新状态」写进去
         * @param limit  最多产出多少格（内存预算）
         * @return 实际产出格数
         */
        int apply(Region region, PlanSink out, int limit);
    }

    /** 产出缓冲：把改动写进预分配的数组，避免工作线程上大量分配。 */
    public static final class PlanSink {
        private final long[] packed;
        private final BlockState[] states;
        private int count;

        PlanSink(int capacity) {
            this.packed = new long[capacity];
            this.states = new BlockState[capacity];
        }

        public void add(long key, BlockState state) {
            if (count >= packed.length) {
                return;
            }
            packed[count] = key;
            states[count] = state;
            count++;
        }

        public int count() {
            return count;
        }

        Plan toPlan() {
            Plan plan = new Plan(packed, states);
            count = 0;
            return plan;
        }
    }

    /** 一块待改写的区域（世界坐标 + 尺寸）。 */
    public record Region(ServerLevel level, int minX, int minY, int minZ,
                         int maxX, int maxY, int maxZ) {
        public int volume() {
            return (maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1);
        }
    }

    /**
     * 坐标打包：一个 long 存三个 int（x/y/z 各 21 位有符号）。
     *
     * <p>位布局：x 占高 21 位（42..62）、y 占中 21 位（21..41）、z 占低 21 位（0..20）。</p>
     *
     * <p><b>解包必须先取掩码再补符号</b>：直接写 {@code (int)(key << 42) >> 42} 是错的 ——
     * {@code key << 42} 是 long 的左移，x 那 21 位会从 42 挪到 84，越过 64 位被丢掉，
     * 取到的是别的分量。正确做法是先把该分量<b>右移</b>到低位、掩掉多余的位，
     * 再用 {@link #signExtend21} 把 21 位当有符号数补回符号。</p>
     *
     * <p><b>21 位够不够</b>：21 位有符号的范围只有 −1048576..1048575（约 ±100 万格），
     * 而 Minecraft 的世界边界是 ±3000 万格 —— <b>绝对坐标装不下</b>。</p>
     *
     * <p>所以这里存的是<b>相对坐标</b>：弹坑永远以打击点为中心，
     * 半径最大也就几百格，21 位绰绰有余。
     * 打包用 {@link #packRelative}，解包用 {@link #unpackRelativeX}/{@link #unpackRelativeY}/
     * {@link #unpackRelativeZ}，原点由调用方（区域中心）提供。</p>
     */
    public static long pack(int x, int y, int z) {
        return ((long) (x & 0x1FFFFF) << 42)
                | ((long) (y & 0x1FFFFF) << 21)
                | (z & 0x1FFFFF);
    }

    /** 把低 21 位当有符号数补回符号位。 */
    private static int signExtend21(int value) {
        return (value << (32 - 21)) >> (32 - 21);
    }

    public static int unpackX(long key) {
        return signExtend21((int) ((key >> 42) & 0x1FFFFF));
    }

    public static int unpackY(long key) {
        return signExtend21((int) ((key >> 21) & 0x1FFFFF));
    }

    public static int unpackZ(long key) {
        return signExtend21((int) (key & 0x1FFFFF));
    }

    /** 相对坐标打包（相对打击点）。见类注释：绝对坐标装不进 21 位。 */
    public static long packRelative(int dx, int dy, int dz) {
        return pack(dx, dy, dz);
    }

    /** 相对坐标解包：加回区域原点。 */
    public static int unpackRelativeX(long key, int originX) {
        return originX + unpackX(key);
    }

    public static int unpackRelativeY(long key, int originY) {
        return originY + unpackY(key);
    }

    public static int unpackRelativeZ(long key, int originZ) {
        return originZ + unpackZ(key);
    }

    private static final ThreadFactory FACTORY = new ThreadFactory() {
        private final AtomicInteger counter = new AtomicInteger();

        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, "Skyfall carver #" + counter.incrementAndGet());
            // 守护线程：服务器关服时它跟着走，不会把 JVM 吊住。
            t.setDaemon(true);
            // 优先级 4（低于普通线程）：算形是后台工作，不该跟主线程抢时间片。
            t.setPriority(4);
            return t;
        }
    };

    private static volatile ExecutorService pool;
    private static volatile int poolSize;

    /** 内存预算：预计算列表最多能占多少。 */
    private static long memoryBudget() {
        return Runtime.getRuntime().maxMemory() / 16L;
    }

    /** 一次最多预计算多少格（与预算挂钩，避免极端配置下分配过大）。 */
    public static int maxPlanCells() {
        long budget = memoryBudget();
        // 每个格子：long 8 字节 + 状态引用 8 字节 ≈ 16 字节。
        long cap = budget / 16L;
        return (int) Math.max(1024L, Math.min(cap, 4_000_000L));
    }

    private static synchronized ExecutorService pool() {
        ExecutorService p = pool;
        if (p != null) {
            return p;
        }
        int size = Math.max(2, Math.min(8, Runtime.getRuntime().availableProcessors() - 2));
        p = Executors.newFixedThreadPool(size, FACTORY);
        pool = p;
        poolSize = size;
        ApocalypseZombies.LOGGER.info("[天陨] 地形算形线程池启动：{} 线程（可用核 {}）",
                size, Runtime.getRuntime().availableProcessors());
        return p;
    }

    /** 当前线程池大小（诊断用）。 */
    public static int poolSize() {
        return poolSize;
    }

    /**
     * 并行算形是否打开。
     *
     * <p>配置还没加载时（模组刚起来、或单元测试环境）读配置会抛
     * {@code IllegalStateException: Cannot get config value before config is loaded}。
     * 这里读失败就当「开」—— 算形只是把计算挪个地方，行为一样，
     * 不该因为配置没就绪就让整个打击路径炸掉。</p>
     */
    private static boolean parallelEnabled() {
        try {
            return Config.ORBITAL_STRIKE_PARALLEL_CARVE.get();
        } catch (Throwable t) {
            return true;
        }
    }

    /**
     * 提交一块区域去算形。
     *
     * @param region 区域
     * @param fn     算形逻辑（必须在工作线程上跑，且不得碰世界）
     * @param limit  产出上限
     * @return 未来的完成句柄
     */
    public static CompletableFuture<Plan> submit(Region region, ShapeFn fn, int limit) {
        if (!parallelEnabled()) {
            // 关掉并行时，退化成「主线程同步算」，行为等价只是慢一点。
            PlanSink sink = new PlanSink(Math.max(1, limit));
            fn.apply(region, sink, limit);
            return CompletableFuture.completedFuture(sink.toPlan());
        }
        int cap = Math.max(1, Math.min(limit, maxPlanCells()));
        PlanSink sink = new PlanSink(cap);
        return CompletableFuture.supplyAsync(() -> {
            try {
                fn.apply(region, sink, cap);
            } catch (Throwable t) {
                ApocalypseZombies.LOGGER.warn("[天陨] 算形任务异常，放弃这块区域", t);
                return Plan.EMPTY;
            }
            return sink.toPlan();
        }, pool());
    }

    /**
     * 把算好的形状**落到世界里**。
     *
     * <p>这一步必须在服务端线程：它要读写区块、触发光照更新、跑方块更新事件。
     * 参考包也是这么分的（它的 {@code m.java} 里写块一律回服务端线程）。</p>
     */
    public static int apply(ServerLevel level, Plan plan) {
        int applied = 0;
        int n = plan.size();
        for (int i = 0; i < n; i++) {
            long key = plan.packed()[i];
            BlockState state = plan.states()[i];
            if (state == null) {
                continue;
            }
            BlockPos pos = new BlockPos(unpackX(key), unpackY(key), unpackZ(key));
            if (!level.isLoaded(pos)) {
                continue;
            }
            BlockState current = level.getBlockState(pos);
            if (current == state) {
                continue;
            }
            if (current.isAir() && state.isAir()) {
                continue;
            }
            level.setBlock(pos, state, Block.UPDATE_ALL);
            applied++;
        }
        return applied;
    }

    /** 把一批区域按预算切成若干块，分给工作线程并行算形。 */
    public static List<Region> split(Region region, int cellsPerChunk) {
        List<Region> out = new ArrayList<>();
        int cells = Math.max(1, cellsPerChunk);
        int ySize = region.maxY() - region.minY() + 1;
        int zSize = region.maxZ() - region.minZ() + 1;
        for (int x = region.minX(); x <= region.maxX(); x += cells) {
            for (int z = region.minZ(); z <= region.maxZ(); z += cells) {
                out.add(new Region(region.level(),
                        x, region.minY(), z,
                        Math.min(region.maxX(), x + cells - 1),
                        region.maxY(),
                        Math.min(region.maxZ(), z + cells - 1)));
            }
        }
        // 每块的体量受 y 高度限制，按块计
        if (ySize > 1 && out.size() > 1) {
            int perLayer = Math.max(1, (int) Math.ceil(out.size() / (double) Math.max(1, ySize)));
            List<Region> layered = new ArrayList<>();
            for (int x = region.minX(); x <= region.maxX(); x += cells) {
                for (int z = region.minZ(); z <= region.maxZ(); z += cells) {
                    for (int y = region.minY(); y <= region.maxY(); y += 32) {
                        layered.add(new Region(region.level(),
                                x, y, z,
                                Math.min(region.maxX(), x + cells - 1),
                                Math.min(region.maxY(), y + 31),
                                Math.min(region.maxZ(), z + cells - 1)));
                    }
                }
            }
            return layered;
        }
        return out;
    }

    private OrbitalCarveEngine() {
    }
}
