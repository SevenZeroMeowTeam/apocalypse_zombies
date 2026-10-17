package com.apocalypse.zombies.client;

import com.apocalypse.zombies.registry.ModParticles;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;

/**
 * 落地之后的余晖：弹坑上方持续 25 秒的悬浮电青碎屑。
 *
 * <p>打击的「结束」不该是 2 秒后粒子全部消失、世界瞬间恢复原样 —— 参考 mod 的余韵感
 * 来自落地后很久还有东西在动。这里每 tick 在弹坑范围内随机撒 1~3 颗慢速上飘的余烬，
 * 全部由客户端本地生成（不发包，只有本机看得到），所以多撒一点也不花服务器带宽。</p>
 *
 * <p>时间基准同样是 {@link OrbitalStrikeClientState}：在落地帧把「落地时刻」锁定下来，
 * 之后 {@code OrbitalStrikeClientState} 本身过期（余晖 40 tick 后收尾）也不会打断这里 ——
 * 余烬要飘 500 tick。</p>
 */
public final class OrbitalAftermath {

    /** 余烬持续时间（25 s）。 */
    private static final int LINGER_TICKS = 500;
    /** 前 6 秒密度高一些（「还在烧」），之后转成稀疏的余烬。 */
    private static final int DENSE_TICKS = 120;

    /** 当前正在余晖的落点；null = 没有。 */
    private static BlockPos target;
    /** 落地时刻的世界时间；-1 = 还没锁定。 */
    private static long impactGameTime = -1L;

    private OrbitalAftermath() {
    }

    /** 每客户端 tick 调用一次。 */
    public static void tick(Minecraft minecraft) {
        ClientLevel level = minecraft.level;
        if (level == null) {
            reset();
            return;
        }
        // 只在「刚落地」的那几 tick 锁定基准 —— 之后状态过期（AFTERGLOW 40 tick）也不影响。
        if (OrbitalStrikeClientState.isActive()) {
            long age = OrbitalStrikeClientState.impactAge();
            BlockPos current = OrbitalStrikeClientState.target();
            if (age >= 0 && age <= 2 && current != null
                    && (!current.equals(target) || impactGameTime < 0)) {
                target = current.immutable();
                impactGameTime = level.getGameTime();
            }
        }
        if (target == null || impactGameTime < 0) {
            return;
        }
        long since = level.getGameTime() - impactGameTime;
        if (since < 0 || since >= LINGER_TICKS) {
            return;
        }

        int radius = OrbitalStrikeClientState.radius();
        double cx = target.getX() + 0.5D;
        double cy = target.getY() + 1.0D;
        double cz = target.getZ() + 0.5D;
        int count = since < DENSE_TICKS ? 3 : 1;
        for (int i = 0; i < count; i++) {
            double angle = level.random.nextDouble() * Math.PI * 2.0D;
            double dist = Math.sqrt(level.random.nextDouble()) * radius * 1.25D;
            double x = cx + Math.cos(angle) * dist;
            double z = cz + Math.sin(angle) * dist;
            double y = cy + 0.4D + level.random.nextDouble() * (radius * 0.55D + 3.0D);
            level.addParticle(ModParticles.ORBITAL_EMBER.get(), true,
                    x, y, z,
                    (level.random.nextDouble() - 0.5D) * 0.02D,
                    0.012D + level.random.nextDouble() * 0.03D,
                    (level.random.nextDouble() - 0.5D) * 0.02D);
        }
    }

    /** 退出世界 / 换服时清空，避免把上一局的落点带过去。 */
    public static void reset() {
        target = null;
        impactGameTime = -1L;
    }
}
