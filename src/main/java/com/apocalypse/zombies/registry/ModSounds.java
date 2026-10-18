package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * Sound events for the weapon layer.
 *
 * <p><b>音源换成项目自备的了（1.1.93）</b>：这 22 条以前指向 TaCZ 的 AWM 录音（借用，
 * CC BY-NC-ND 4.0），现在全部指向 {@code assets/apocalypse_zombies/sounds/guns/} 里项目自带的
 * 17 个枪械音效。因此 {@code build.gradle} 的 {@code borrowedEntries} <b>不再排除音效</b> ——
 * 纯净包（{@code -clean}）从这一版起也有声音了；还留在借用清单里的只剩转录动画
 * {@code animations/awm.animation.json} 一项。</p>
 *
 * <p>Most ids below kept their names on purpose: the sounds.json key, the Java constant and the
 * per-gun {@code tick → cue} tables are one contract, so swapping the recordings meant re-pointing
 * files and nothing else. Two ids are new — {@link #UZI_SHOOT} and {@link #CROSSBOW_SHOOT} give
 * those two weapons their own takes (four and three respectively, one drawn at random per shot),
 * which a single shared AWM recording could not express.</p>
 *
 * <p>机械声沿用旧的事件名，但现在放的是 {@code akm_*} / {@code bolt_1} / {@code awp_reload_1}：
 * 拉栓、推栓、闭锁、卸匣、插匣、弃匣。时刻表不在这里 —— 它在各枪的
 * {@code tick → SoundEvent} 表里（见 {@code UziItem}、{@code CrossbowItem} 等），
 * 与动画片段的关键帧对齐。</p>
 */
public final class ModSounds {

    public static final DeferredRegister<SoundEvent> SOUNDS =
            DeferredRegister.create(ForgeRegistries.SOUND_EVENTS, ApocalypseZombies.MOD_ID);

    /**
     * 枪声：射击者听近场版，旁人听远场版。
     *
     * <p>素材是一支 .338 狙击枪的录音，栓动那几把（AWM / 莫辛纳甘）与拿它当通用枪声的半自动
     * 步枪都用这一条。{@link #UZI_SHOOT} 与 {@link #CROSSBOW_SHOOT} 各自另有专属录音。</p>
     */
    public static final RegistryObject<SoundEvent> AWM_SHOOT = sound("awm_shoot");
    public static final RegistryObject<SoundEvent> AWM_SHOOT_3P = sound("awm_shoot_3p");

    /** Uzi 的枪声：四支录音，每发随机挑一支 —— 连发时不至于像同一发子弹在复读。 */
    public static final RegistryObject<SoundEvent> UZI_SHOOT = sound("uzi_shoot");

    /** 十字弩的弦声：三支录音，每发随机。 */
    public static final RegistryObject<SoundEvent> CROSSBOW_SHOOT = sound("crossbow_shoot");

    /**
     * 弩箭命中（弦停下来的那一下）。
     *
     * <p>素材已就位，但当前没有调用点 —— 弩命中沿用原版箭矢的命中声。留着这条是为了
     * 以后接「命中反馈」时不必再动 sounds.json。</p>
     */
    public static final RegistryObject<SoundEvent> CROSSBOW_HIT = sound("crossbow_hit");

    /** Bolt cycle — the 打一发拉一下栓 sequence. */
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_OUT = sound("awm_rechamber_out");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_EJECT = sound("awm_rechamber_ejectclick");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_IN = sound("awm_rechamber_in");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_END = sound("awm_rechamber_end");

    /** Magazine swap with a round still chambered — no bolt, so no rechamber sounds. */
    public static final RegistryObject<SoundEvent> AWM_RELOAD_RAISE = sound("awm_reload_raise");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_RATTLE = sound("awm_reload_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EJECT = sound("awm_reload_ejectclick");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGOUT = sound("awm_reload_magout");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_FAST_RATTLE = sound("awm_reload_fast_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGHIT = sound("awm_reload_maghit");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGIN = sound("awm_reload_magin");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_END = sound("awm_reload_end");

    /** Empty-magazine reload — the long one, with the bolt cycle on the end. */
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_RAISE = sound("awm_reload_empty_raise");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGOUT = sound("awm_reload_empty_magout");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAG_DROP = sound("awm_reload_empty_mag_drop");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_RATTLE = sound("awm_reload_empty_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGHIT = sound("awm_reload_empty_maghit");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGIN = sound("awm_reload_empty_magin");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_BOLTCLOSE = sound("awm_reload_empty_boltclose");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_END = sound("awm_reload_empty_end");

    /** 弹夹弹出时的金属碰撞声"叮"。 */
    public static final RegistryObject<SoundEvent> AMMO_CLIP_POP = sound("ammo_clip_pop");

    /**
     * 「朋友的酒」—— 常驻背景音乐，客户端循环播放，见 {@code client/music/FriendsWineMusic}。
     *
     * <p>音频由玩家自备、随本模组分发，与枪械音效同一来源。1.1.93 起 {@code cleanJar} 不再排除
     * {@code sounds/**}，所以这首音乐现在也随纯净包分发。</p>
     */
    public static final RegistryObject<SoundEvent> MUSIC_FRIENDS_WINE = sound("music_friends_wine");

    /**
     * 主菜单曲（The Last Known Meridian）—— 只在标题界面循环，见
     * {@code client/music/MainMenuMusic}。流式 OGG（2 分 37 秒），进世界后让位给「朋友的酒」。
     */
    public static final RegistryObject<SoundEvent> MUSIC_THE_LAST_KNOWN_MERIDIAN =
            sound("music_the_last_known_meridian");

    /** 情境音乐：地表探索（The Quiet Latitude）。 */
    public static final RegistryObject<SoundEvent> MUSIC_THE_QUIET_LATITUDE =
            sound("music_the_quiet_latitude");
    /** 情境音乐：石之重（The Weight Of Stone）—— 备选矿洞曲，默认未挂载，可在配置里指定。 */
    public static final RegistryObject<SoundEvent> MUSIC_THE_WEIGHT_OF_STONE =
            sound("music_the_weight_of_stone");
    /** 情境音乐：血月升起（Crimson Countdown）。 */
    public static final RegistryObject<SoundEvent> MUSIC_CRIMSON_COUNTDOWN =
            sound("music_crimson_countdown");

    private ModSounds() {
    }

    /** Wires the sound registry onto the mod event bus. */
    public static void register(IEventBus modBus) {
        SOUNDS.register(modBus);
    }

    private static RegistryObject<SoundEvent> sound(String name) {
        return SOUNDS.register(name, () -> SoundEvent.createVariableRangeEvent(
                new ResourceLocation(ApocalypseZombies.MOD_ID, name)));
    }
}
