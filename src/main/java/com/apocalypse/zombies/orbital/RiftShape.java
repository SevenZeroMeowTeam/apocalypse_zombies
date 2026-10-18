package com.apocalypse.zombies.orbital;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;

import java.util.ArrayList;
import java.util.List;

/**
 * 断层 FAULT 的裂谷形状（服务端挖地与客户端预览共用）。
 *
 * <p>从目标点沿玩家朝向拉一条长约 {@code length} 的折线；每 3 格取一个点，点在中轴两侧
 * 做随机游走，形成一条不规则的裂缝。随机种子只由目标坐标和朝向决定 —— 服务端和客户端
 * 各自算出完全相同的折线，预览与真正挖开的位置不会错位。</p>
 */
public final class RiftShape {

    /** 一个裂谷节点（世界 x/z；y 由地形高度决定）。 */
    public record Point(int x, int z) {
    }

    private RiftShape() {
    }

    public static List<Point> points(BlockPos target, float yawDegrees, int length) {
        int len = Math.max(16, Math.min(256, length));
        double yaw = Math.toRadians(yawDegrees);
        // Minecraft yaw：0 = +Z，90 = -X（与相机 forward 的水平分量一致）。
        double dx = -Math.sin(yaw);
        double dz = Math.cos(yaw);
        // 垂直方向：把方向顺时针转 90°。
        double px = -dz;
        double pz = dx;

        long seed = target.asLong() * 0x9E3779B97F4A7C15L
                ^ ((long) Math.round(yawDegrees * 100.0F) * 0x632BE59BD9B4E019L);
        RandomSource random = RandomSource.create(seed);

        double startX = target.getX() - dx * (len / 2.0D);
        double startZ = target.getZ() - dz * (len / 2.0D);
        int steps = Math.max(5, len / 3);
        List<Point> points = new ArrayList<>(steps + 1);
        double offset = 0.0D;
        for (int i = 0; i <= steps; i++) {
            double t = i / (double) steps;
            // 折线主干 + 侧向随机游走 + 每点抖动；两端收一点，避免裂口突然断头。
            double taper = Math.sin(Math.PI * Math.min(1.0D, Math.max(0.05D, t)));
            offset = Math.max(-4.0D, Math.min(4.0D, offset + (random.nextDouble() - 0.5D) * 1.9D));
            double wobble = offset * taper + (random.nextDouble() - 0.5D) * 1.2D;
            double jitter = (random.nextDouble() - 0.5D) * 1.4D;
            double x = startX + dx * len * t + px * wobble + dx * jitter;
            double z = startZ + dz * len * t + pz * wobble + dz * jitter;
            Point point = new Point((int) Math.floor(x), (int) Math.floor(z));
            if (points.isEmpty() || !points.get(points.size() - 1).equals(point)) {
                points.add(point);
            }
        }
        return points;
    }

    /** 点到折线的最小水平距离（用于裂谷伤害）。 */
    public static double distanceTo(List<Point> points, double x, double z) {
        double best = Double.MAX_VALUE;
        for (Point p : points) {
            double ddx = x - (p.x() + 0.5D);
            double ddz = z - (p.z() + 0.5D);
            best = Math.min(best, Math.sqrt(ddx * ddx + ddz * ddz));
        }
        return best;
    }
}
