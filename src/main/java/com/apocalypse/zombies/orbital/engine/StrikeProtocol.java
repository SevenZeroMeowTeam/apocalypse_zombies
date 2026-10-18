package com.apocalypse.zombies.orbital.engine;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;

/**
 * 一份打击协议（数据定义）。
 *
 * <p>它是 v2 引擎的“内容单元”：代号、颜色、相位时长、地形参数。服务端和客户端读同一份，
 * 避免两边对“什么时候该发射/什么时候该裂开”产生分歧。</p>
 *
 * <p>相位切分：
 * <ul>
 *   <li>{@code mark + ascent + device} = 开火前的总时长（服务端 lock）；</li>
 *   <li>{@code fire} = 服务端的 fallTicks（弹体/光束飞行）；</li>
 *   <li>{@code impact} / {@code aftermath} = 命中与余波。</li>
 * </ul>
 * 火山口/裂谷的长度、宽度、深度等参数放在 {@link Terrain} 里；不在地形里的协议留空。</p>
 */
public record StrikeProtocol(
        String id,
        OrbitalStrikeMode mode,
        String display,
        String codename,
        int color,
        int markTicks,
        int ascentTicks,
        int deviceTicks,
        int impactTicks,
        int aftermathTicks,
        Terrain terrain) {

    /** 地形签名参数。shape 是协议自己的形状名（rift/column/cordon/brood/purge/rain）。 */
    public record Terrain(String shape, int riftLength, int riftWidth, int riftDepth) {
        public static final Terrain NONE = new Terrain("", 0, 0, 0);

        public boolean rift() {
            return "rift".equalsIgnoreCase(shape);
        }
    }

    /** 开火前总时长（服务端 lock）。 */
    public int preFireTicks() {
        return markTicks + ascentTicks + deviceTicks;
    }

    /** 是否是 v2 已经迁移的断层协议。 */
    public boolean fault() {
        return "fault".equals(id);
    }

    /** 相位在整场打击里的开始 tick（impact/aftermath 需要 lock+fall）。 */
    public int phaseStart(StrikePhase phase, int lockTicks, int fallTicks) {
        return switch (phase) {
            case MARK -> 0;
            case ASCENT -> Math.min(markTicks, lockTicks);
            case DEVICE -> Math.min(markTicks + ascentTicks, lockTicks);
            case FIRE -> lockTicks;
            case IMPACT -> lockTicks + fallTicks;
            case AFTERMATH -> lockTicks + fallTicks + impactTicks;
        };
    }

    /** 相位结束 tick；未到达的边界用 lock/fall 夹住。 */
    public int phaseEnd(StrikePhase phase, int lockTicks, int fallTicks) {
        return switch (phase) {
            case MARK -> Math.min(markTicks, lockTicks);
            case ASCENT -> Math.min(markTicks + ascentTicks, lockTicks);
            case DEVICE -> lockTicks;
            case FIRE -> lockTicks + fallTicks;
            case IMPACT -> lockTicks + fallTicks + impactTicks;
            case AFTERMATH -> lockTicks + fallTicks + impactTicks + aftermathTicks;
        };
    }

    public StrikePhase phaseAt(long elapsed, int lockTicks, int fallTicks) {
        int t = (int) Math.max(0L, elapsed);
        if (t < phaseEnd(StrikePhase.MARK, lockTicks, fallTicks)) {
            return StrikePhase.MARK;
        }
        if (t < phaseEnd(StrikePhase.ASCENT, lockTicks, fallTicks)) {
            return StrikePhase.ASCENT;
        }
        if (t < phaseEnd(StrikePhase.DEVICE, lockTicks, fallTicks)) {
            return StrikePhase.DEVICE;
        }
        if (t < phaseEnd(StrikePhase.FIRE, lockTicks, fallTicks)) {
            return StrikePhase.FIRE;
        }
        if (t < phaseEnd(StrikePhase.IMPACT, lockTicks, fallTicks)) {
            return StrikePhase.IMPACT;
        }
        return StrikePhase.AFTERMATH;
    }

    public String phaseLabel(StrikePhase phase) {
        return switch (phase) {
            case MARK -> "MARK // 标记";
            case ASCENT -> "ASCENT // 升空";
            case DEVICE -> "DEVICE // 装填";
            case FIRE -> "FIRE // 发射";
            case IMPACT -> "IMPACT // 命中";
            case AFTERMATH -> "AFTERMATH // 余波";
        };
    }
}
