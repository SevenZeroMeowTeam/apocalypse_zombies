package com.apocalypse.zombies.orbital.terminal;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;

/**
 * 天陨指挥终端的一份完整状态快照：客户端 GUI 只读它，服务端 BlockEntity 写它。
 *
 * <p><b>为什么用一个 record 而不是让客户端直接读 BlockEntity：</b>终端是方块实体，
 * 客户端拿不到权威数据（也绝不能让客户端改）。所有改动都走「C2S 动作包 → 服务端校验 →
 * S2C 同步包」这一条路，{@code TerminalState} 就是这条路上的唯一载荷 —— 打开界面、
 * 改滑条、装核心之后，服务端都回一份新的它，界面照着重画即可。</p>
 *
 * <p>字段全部是原始类型 + 一个字符串，编码固定、长度可控，多人服务器上不构成负担。</p>
 *
 * @param pos            终端方块坐标
 * @param unlockedMask   已安装核心的位图，第 i 位对应 {@link OrbitalStrikeMode#values()}[i]
 * @param selected       当前选中的模式 id（{@link OrbitalStrikeMode#id()}）
 * @param radiusPercent  半径倍率百分比（50~200，100 = 协议默认）
 * @param powerPercent   伤害倍率百分比（50~200）
 * @param speedPercent   下落段速度百分比（50~200，越大越快）
 * @param filmOn         是否播放过场电影
 * @param readyAt        终端充能完成的服务端 gameTime；≤ 当前时间表示可用
 * @param chargeTicks    一次完整充能需要的 tick 数（用于进度条）
 * @param ownerName      放置者名字（空字符串 = 无主）
 * @param gameTime       服务端打包时的 gameTime（客户端用它算倒计时，避免两端时钟漂移）
 */
public record TerminalState(
        BlockPos pos,
        int unlockedMask,
        String selected,
        int radiusPercent,
        int powerPercent,
        int speedPercent,
        boolean filmOn,
        long readyAt,
        int chargeTicks,
        String ownerName,
        long gameTime) {

    public static final int MULTIPLIER_MIN = 50;
    public static final int MULTIPLIER_MAX = 200;

    /** 是否已经装过这种模式的核心。 */
    public boolean unlocked(OrbitalStrikeMode mode) {
        return mode != null && (unlockedMask & (1 << mode.ordinal())) != 0;
    }

    /** 当前选中模式；id 坏掉时回落到轨道炮（和遥控器同一套容错）。 */
    public OrbitalStrikeMode selectedMode() {
        return OrbitalStrikeMode.byId(selected);
    }

    /** 终端是否已经充能完毕。 */
    public boolean ready() {
        return gameTime >= readyAt;
    }

    /** 距离可用还有多少秒（向上取整，0 = 可用）。 */
    public int secondsLeft() {
        long ticks = Math.max(0L, readyAt - gameTime);
        return (int) ((ticks + 19L) / 20L);
    }

    /** 充能进度 0→1（1 = 可用）。 */
    public float chargeProgress() {
        if (chargeTicks <= 0 || ready()) {
            return 1.0F;
        }
        float remaining = (float) Math.max(0L, readyAt - gameTime) / (float) chargeTicks;
        return net.minecraft.util.Mth.clamp(1.0F - remaining, 0.0F, 1.0F);
    }

    public float radiusMul() {
        return radiusPercent / 100.0F;
    }

    public float powerMul() {
        return powerPercent / 100.0F;
    }

    public float speedMul() {
        return speedPercent / 100.0F;
    }

    /** 已安装核心数量（GUI 的 "x/6"）。 */
    public int unlockedCount() {
        return Integer.bitCount(unlockedMask & 0x3F);
    }

    // ------------------------------------------------------------------ 编解码

    public void encode(FriendlyByteBuf buf) {
        buf.writeBlockPos(pos);
        buf.writeVarInt(unlockedMask);
        buf.writeUtf(selected, 32);
        buf.writeVarInt(radiusPercent);
        buf.writeVarInt(powerPercent);
        buf.writeVarInt(speedPercent);
        buf.writeBoolean(filmOn);
        buf.writeLong(readyAt);
        buf.writeVarInt(chargeTicks);
        buf.writeUtf(ownerName, 64);
        buf.writeLong(gameTime);
    }

    public static TerminalState decode(FriendlyByteBuf buf) {
        return new TerminalState(
                buf.readBlockPos(),
                buf.readVarInt(),
                buf.readUtf(32),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readBoolean(),
                buf.readLong(),
                buf.readVarInt(),
                buf.readUtf(64),
                buf.readLong());
    }
}
