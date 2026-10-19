package com.apocalypse.zombies.block;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.terminal.SkyfallTerminalManager;
import com.apocalypse.zombies.orbital.terminal.TerminalState;
import com.apocalypse.zombies.registry.ModBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import org.jetbrains.annotations.Nullable;

import java.util.UUID;

/**
 * 天陨指挥终端的数据核心：装过哪些协议核心、当前选哪份、三个倍率、过场开关、充能进度、主人。
 *
 * <p><b>权威只在这里。</b>客户端 GUI 拿到的永远是 {@link #state()} 打出来的只读快照；
 * 任何修改都必须走 {@code TerminalActionPacket} → {@link SkyfallTerminalManager#handleAction} →
 * {@link #applyAction}，服务端夹紧数值后再回一份 `TerminalState`。</p>
 *
 * <p>终端不 tick：充能是一个 {@code readyAt} 时间戳，进度按需算。这样一百台终端同时加载也不会
 * 多出一百条 tick 回调。</p>
 */
public class SkyfallTerminalBlockEntity extends BlockEntity {

    private static final String TAG_UNLOCKED = "Unlocked";
    private static final String TAG_SELECTED = "Selected";
    private static final String TAG_RADIUS = "RadiusPercent";
    private static final String TAG_POWER = "PowerPercent";
    private static final String TAG_SPEED = "SpeedPercent";
    private static final String TAG_FILM = "Film";
    private static final String TAG_READY_AT = "ReadyAt";
    private static final String TAG_CHARGE = "ChargeTicks";
    private static final String TAG_OWNER = "Owner";
    private static final String TAG_OWNER_NAME = "OwnerName";

    /** 已安装核心的位图：第 i 位 = {@link OrbitalStrikeMode#values()}[i]。 */
    private int unlockedMask;
    private String selected = OrbitalStrikeMode.CANNON.id();
    private int radiusPercent = 100;
    private int powerPercent = 100;
    private int speedPercent = 100;
    private boolean filmOn = true;
    /** 充能完成的服务端 gameTime；0 = 从一开始就是充满的。 */
    private long readyAt;
    /** 上一次充能的总 tick 数（进度条分母）。 */
    private int chargeTicks;
    @Nullable
    private UUID owner;
    private String ownerName = "";

    public SkyfallTerminalBlockEntity(BlockPos pos, BlockState state) {
        super(ModBlockEntities.SKYFALL_TERMINAL.get(), pos, state);
    }

    // ------------------------------------------------------------------ 生命周期

    @Override
    public void setLevel(Level level) {
        super.setLevel(level);
        if (level != null && !level.isClientSide()) {
            SkyfallTerminalManager.register(this);
        }
    }

    @Override
    public void setRemoved() {
        super.setRemoved();
        SkyfallTerminalManager.unregister(this);
    }

    @Override
    public void onChunkUnloaded() {
        super.onChunkUnloaded();
        SkyfallTerminalManager.unregister(this);
    }

    // ------------------------------------------------------------------ 查询

    public boolean unlocked(OrbitalStrikeMode mode) {
        return mode != null && (unlockedMask & (1 << mode.ordinal())) != 0;
    }

    public OrbitalStrikeMode selectedMode() {
        return OrbitalStrikeMode.byId(selected);
    }

    public boolean ready() {
        return gameTime() >= readyAt;
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

    public boolean filmOn() {
        return filmOn;
    }

    /** 选中协议在当前配置半径下实际打多大（格）。 */
    public int radius() {
        int base = Math.max(1, Math.min(96, Config.ORBITAL_STRIKE_RADIUS.get()));
        int scaled = Math.round(selectedMode().radius(base) * radiusMul());
        int cap = Math.max(1, Math.min(96, Config.TERMINAL_RADIUS_MAX.get()));
        // 半径上限取「终端滑条上限」与「引擎 96」的较小者；协议自身倍率仍会放大，
        // 所以这里不对倍率后的值再乘一遍，只做最终夹紧。
        return net.minecraft.util.Mth.clamp(scaled, 1, Math.max(cap, 1));
    }

    @Nullable
    public UUID owner() {
        return owner;
    }

    public String ownerName() {
        return ownerName == null ? "" : ownerName;
    }

    /** 给 GUI 的只读快照。 */
    public TerminalState state() {
        return new TerminalState(
                getBlockPos(),
                unlockedMask,
                selected,
                radiusPercent,
                powerPercent,
                speedPercent,
                filmOn,
                readyAt,
                chargeTicks,
                ownerName(),
                gameTime());
    }

    private long gameTime() {
        return level == null ? 0L : level.getGameTime();
    }

    // ------------------------------------------------------------------ 修改

    public void setOwner(Player player) {
        this.owner = player.getUUID();
        this.ownerName = player.getName().getString();
        setChanged();
    }

    /** 装一个协议核心；已经装过返回 false。装完自动选中它。 */
    public boolean install(OrbitalStrikeMode mode) {
        if (mode == null || unlocked(mode)) {
            return false;
        }
        unlockedMask |= 1 << mode.ordinal();
        selected = mode.id();
        setChanged();
        return true;
    }

    /**
     * 打击授权成功：终端进入充能。
     *
     * <p>充能时长 = {@link Config#TERMINAL_CHARGE_SECONDS} 按该模式的冷却倍率缩放
     * （和遥控器旧的冷却算法同一套，玩家不用学两套数）。</p>
     */
    public void onStrike() {
        int seconds = Math.max(0, Config.TERMINAL_CHARGE_SECONDS.get());
        chargeTicks = selectedMode().cooldownSeconds(seconds) * 20;
        readyAt = gameTime() + Math.max(0, chargeTicks);
        setChanged();
    }

    /**
     * v4.0 P3：打击在 FIRE 之前被中止时把充能退回来（可以立刻再打）。
     *
     * <p>只应由服务端的取消路径调用；已经进入 FIRE 的打击不退款 —— 那时候弹已经出去了。</p>
     */
    public void refundCharge() {
        readyAt = 0L;
        chargeTicks = 0;
        setChanged();
    }

    /** 距离充满还差多少 tick（0 = 已就绪）。 */
    public int chargeRemainingTicks() {
        return (int) Math.max(0L, readyAt - gameTime());
    }

    /**
     * 快速充能：把冷却往前推 {@code seconds} 秒（不会超过「立刻就绪」）。
     *
     * @return 实际缩短的秒数（向上取整）；0 = 本来就充满 / 参数无效
     */
    public int quickCharge(int seconds) {
        int remaining = chargeRemainingTicks();
        if (remaining <= 0 || seconds <= 0) {
            return 0;
        }
        int cut = Math.min(remaining, seconds * 20);
        readyAt -= cut;
        setChanged();
        return (cut + 19) / 20;
    }

    /**
     * 应用一次 GUI 操作。返回是否真的改了东西（没改就不用回包）。
     *
     * <p>所有数值都在这里夹紧 —— 即使客户端被改包，也写不进越界值。</p>
     */
    public boolean applyAction(int action, int value) {
        boolean changed = false;
        switch (action) {
            case com.apocalypse.zombies.orbital.terminal.TerminalAction.SELECT -> {
                OrbitalStrikeMode[] modes = OrbitalStrikeMode.values();
                if (value >= 0 && value < modes.length && unlocked(modes[value]) && !modes[value].id().equals(selected)) {
                    selected = modes[value].id();
                    changed = true;
                }
            }
            case com.apocalypse.zombies.orbital.terminal.TerminalAction.RADIUS -> {
                int v = com.apocalypse.zombies.orbital.terminal.TerminalAction.clampPercent(value);
                if (v != radiusPercent) {
                    radiusPercent = v;
                    changed = true;
                }
            }
            case com.apocalypse.zombies.orbital.terminal.TerminalAction.POWER -> {
                int v = com.apocalypse.zombies.orbital.terminal.TerminalAction.clampPercent(value);
                if (v != powerPercent) {
                    powerPercent = v;
                    changed = true;
                }
            }
            case com.apocalypse.zombies.orbital.terminal.TerminalAction.SPEED -> {
                int v = com.apocalypse.zombies.orbital.terminal.TerminalAction.clampPercent(value);
                if (v != speedPercent) {
                    speedPercent = v;
                    changed = true;
                }
            }
            case com.apocalypse.zombies.orbital.terminal.TerminalAction.FILM -> {
                boolean v = value != 0;
                if (v != filmOn) {
                    filmOn = v;
                    changed = true;
                }
            }
            default -> {
                // REFRESH 与未知操作码：不改数据，调用方负责回一份最新快照。
            }
        }
        if (changed) {
            setChanged();
        }
        return changed;
    }

    // ------------------------------------------------------------------ NBT

    @Override
    protected void saveAdditional(CompoundTag tag) {
        super.saveAdditional(tag);
        tag.putInt(TAG_UNLOCKED, unlockedMask);
        tag.putString(TAG_SELECTED, selected);
        tag.putInt(TAG_RADIUS, radiusPercent);
        tag.putInt(TAG_POWER, powerPercent);
        tag.putInt(TAG_SPEED, speedPercent);
        tag.putBoolean(TAG_FILM, filmOn);
        tag.putLong(TAG_READY_AT, readyAt);
        tag.putInt(TAG_CHARGE, chargeTicks);
        if (owner != null) {
            tag.putUUID(TAG_OWNER, owner);
        }
        tag.putString(TAG_OWNER_NAME, ownerName());
    }

    @Override
    public void load(CompoundTag tag) {
        super.load(tag);
        unlockedMask = tag.getInt(TAG_UNLOCKED);
        selected = tag.contains(TAG_SELECTED) ? tag.getString(TAG_SELECTED) : OrbitalStrikeMode.CANNON.id();
        radiusPercent = clampPercent(tag.getInt(TAG_RADIUS));
        powerPercent = clampPercent(tag.getInt(TAG_POWER));
        speedPercent = clampPercent(tag.getInt(TAG_SPEED));
        filmOn = !tag.contains(TAG_FILM) || tag.getBoolean(TAG_FILM);
        readyAt = tag.getLong(TAG_READY_AT);
        chargeTicks = tag.getInt(TAG_CHARGE);
        owner = tag.hasUUID(TAG_OWNER) ? tag.getUUID(TAG_OWNER) : null;
        ownerName = tag.getString(TAG_OWNER_NAME);
    }

    private static int clampPercent(int value) {
        if (value <= 0) {
            return 100;
        }
        return com.apocalypse.zombies.orbital.terminal.TerminalAction.clampPercent(value);
    }
}
