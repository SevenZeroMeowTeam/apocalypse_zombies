package com.apocalypse.zombies.orbital.terminal;

/**
 * 客户端 → 服务端的终端操作码。全部带终端坐标，服务端逐条校验距离/权限/是否解锁。
 *
 * <p>数值统一用 int 传：倍数类字段是百分比（100 = 1.0×），选择类字段是
 * {@code OrbitalStrikeMode.ordinal()}。不传字符串，避免给客户端留「随便填协议名」的口子。</p>
 */
public final class TerminalAction {

    /** 选中协议：value = 模式 ordinal。 */
    public static final int SELECT = 0;
    /** 半径倍数：value = 百分比 50~200。 */
    public static final int RADIUS = 1;
    /** 威力倍数：value = 百分比 50~200。 */
    public static final int POWER = 2;
    /** 下落段速度倍数：value = 百分比 50~200。 */
    public static final int SPEED = 3;
    /** 过场开关：value = 0/1。 */
    public static final int FILM = 4;
    /** 请求重新同步一次状态（界面打开 / 切页时用）。 */
    public static final int REFRESH = 5;

    private TerminalAction() {
    }

    /** 合法操作码检查（服务端收到脏包时直接丢）。 */
    public static boolean valid(int action) {
        return action >= SELECT && action <= REFRESH;
    }

    /** 把百分比夹到 50~200。 */
    public static int clampPercent(int value) {
        return Math.max(TerminalState.MULTIPLIER_MIN, Math.min(TerminalState.MULTIPLIER_MAX, value));
    }
}
