package com.apocalypse.zombies.client.music;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.ClientMoonState;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.registry.ModSounds;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.Level;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.registries.ForgeRegistries;

import java.util.Locale;

/**
 * 情境音乐导演：世界内的 BGM 按「此刻在干什么」自动换曲。
 *
 * <p><b>优先级</b>（高 → 低）：
 * <ol>
 *   <li><b>血月升起的夜晚</b>（含超级血月）→ {@code crimson_countdown}；</li>
 *   <li><b>蓝月升起的夜晚</b>（含超级蓝月）→ {@code the_last_known_meridian}；</li>
 *   <li><b>矿洞探索</b>（主世界、头顶看不到天空）→ {@code the_last_known_meridian}；</li>
 *   <li><b>地表探索</b>（其余情况，含下界/末地）→ {@code the_quiet_latitude}。</li>
 * </ol>
 * 曲目名全部走配置（{@code [context_music]}）：把 {@code cave_track} 改成
 * {@code the_weight_of_stone} 就换成《石之重》，不用改代码。</p>
 *
 * <p><b>防抖</b>：月亮状态立即切换（事件是明确的状态变化）；探索 ↔ 矿洞之间要
 * {@link #HYSTERESIS_TICKS}（3 s）稳定才切 —— 不然在洞口来回走会疯狂切歌。
 * 切曲从新曲的开头开始（情境音乐的惯例）。</p>
 *
 * <p><b>循环</b>：与另外两套音乐同一方案 —— 流式 OGG 不走 {@code AL_LOOPING}，
 * {@code looping=false} + 每 tick 查 {@code isActive}，播完重播。</p>
 *
 * <p><b>与其它两套的关系</b>：主菜单由 {@link MainMenuMusic} 接管（{@code level == null}）；
 * 本类开着时 {@link FriendsWineMusic} 在世界里让位 —— 关掉 {@code context_music.enabled}
 * 就回到「朋友的酒」全局播放的旧行为。F10 / {@code friends_wine_music.enabled} 仍是总开关。</p>
 *
 * <p>纯客户端：专用服务器不加载（{@code Dist.CLIENT} + FORGE 总线订阅）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ContextMusic {

    /** 探索 / 矿洞之间切换需要的稳定时长（tick）：3 s。 */
    private static final int HYSTERESIS_TICKS = 60;

    /** 当前情境槽位。 */
    private enum Slot {
        EXPLORATION, CAVE, BLOOD_MOON, BLUE_MOON
    }

    private static SoundInstance current;
    private static Slot currentSlot;
    /** 当前曲子解析出来的 sound id（配置改曲名时据此判断要不要重启）。 */
    private static net.minecraft.resources.ResourceLocation currentTrackId;
    private static Slot pendingSlot;
    private static int pendingTicks;

    private ContextMusic() {
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        // 世界外（标题/载入/连接中）交给 MainMenuMusic
        if (minecraft.level == null || minecraft.player == null) {
            stop(minecraft);
            return;
        }
        if (!Config.FRIENDS_WINE_MUSIC.get() || !Config.CONTEXT_MUSIC.get()) {
            stop(minecraft);
            return;
        }
        if (minecraft.getSoundManager() == null) {
            return;
        }
        if (minecraft.options.getSoundSourceVolume(SoundSource.MUSIC) <= 0.0F) {
            stop(minecraft);
            return;
        }
        if (Config.FRIENDS_WINE_SUPPRESS_VANILLA.get() && minecraft.getMusicManager() != null) {
            minecraft.getMusicManager().stopPlaying();
        }

        Slot desired = decide(minecraft);
        if (current == null || currentSlot == null) {
            switchTo(minecraft, desired);
        } else if (desired != currentSlot) {
            boolean immediate = desired == Slot.BLOOD_MOON || desired == Slot.BLUE_MOON
                    || currentSlot == Slot.BLOOD_MOON || currentSlot == Slot.BLUE_MOON;
            if (immediate) {
                pendingTicks = 0;
                switchTo(minecraft, desired);
            } else if (pendingSlot == desired) {
                if (++pendingTicks >= HYSTERESIS_TICKS) {
                    pendingTicks = 0;
                    switchTo(minecraft, desired);
                }
            } else {
                pendingSlot = desired;
                pendingTicks = 0;
            }
        } else {
            pendingTicks = 0;
        }

        // 配置里改了曲名 → 立刻按新曲重启（不用等这一遍放完）
        if (current != null && !trackId(currentSlot).equals(currentTrackId)) {
            switchTo(minecraft, currentSlot);
            return;
        }
        // 播完重播 = 循环
        if (current != null && !minecraft.getSoundManager().isActive(current)) {
            play(minecraft, currentSlot);
        }
    }

    /** 决策：血月 > 蓝月 > 矿洞 > 地表。 */
    private static Slot decide(Minecraft minecraft) {
        MoonEvent moon = ClientMoonState.getMoonEvent();
        if (moon == MoonEvent.BLOOD_MOON || moon == MoonEvent.SUPER_BLOOD_MOON) {
            return Slot.BLOOD_MOON;
        }
        if (moon == MoonEvent.BLUE_MOON || moon == MoonEvent.SUPER_BLUE_MOON) {
            return Slot.BLUE_MOON;
        }
        boolean overworld = minecraft.level != null && minecraft.level.dimension().equals(Level.OVERWORLD);
        if (overworld && minecraft.player != null
                && !minecraft.level.canSeeSky(minecraft.player.blockPosition())) {
            return Slot.CAVE;
        }
        return Slot.EXPLORATION;
    }

    private static void switchTo(Minecraft minecraft, Slot slot) {
        stop(minecraft);
        currentSlot = slot;
        play(minecraft, slot);
    }

    private static void play(Minecraft minecraft, Slot slot) {
        SoundEvent sound = resolve(trackName(slot), fallbackFor(slot));
        currentTrackId = sound.getLocation();
        current = new SimpleSoundInstance(
                sound.getLocation(),
                SoundSource.MUSIC,
                Config.CONTEXT_MUSIC_VOLUME.get().floatValue(),
                1.0F,
                RandomSource.create(),
                false,                                  // 流式音源不交给 OpenAL 循环
                0,
                SoundInstance.Attenuation.NONE,
                0.0D, 0.0D, 0.0D,
                true);
        minecraft.getSoundManager().play(current);
    }

    private static void stop(Minecraft minecraft) {
        if (current != null && minecraft.getSoundManager() != null) {
            minecraft.getSoundManager().stop(current);
        }
        current = null;
        currentSlot = null;
        currentTrackId = null;
        pendingSlot = null;
        pendingTicks = 0;
    }

    // ---------------------------------------------------------------- 曲目解析

    private static String trackName(Slot slot) {
        return switch (slot) {
            case EXPLORATION -> Config.CONTEXT_EXPLORATION_TRACK.get();
            case CAVE -> Config.CONTEXT_CAVE_TRACK.get();
            case BLOOD_MOON -> Config.CONTEXT_BLOOD_MOON_TRACK.get();
            case BLUE_MOON -> Config.CONTEXT_BLUE_MOON_TRACK.get();
        };
    }

    private static SoundEvent fallbackFor(Slot slot) {
        return switch (slot) {
            case EXPLORATION -> ModSounds.MUSIC_THE_QUIET_LATITUDE.get();
            case CAVE, BLUE_MOON -> ModSounds.MUSIC_THE_LAST_KNOWN_MERIDIAN.get();
            case BLOOD_MOON -> ModSounds.MUSIC_CRIMSON_COUNTDOWN.get();
        };
    }

    /** 解析到的实际 sound id（配置里的名字无效时落到默认曲）。 */
    private static net.minecraft.resources.ResourceLocation trackId(Slot slot) {
        return resolve(trackName(slot), fallbackFor(slot)).getLocation();
    }

    /**
     * 把配置里的曲名解析成 sound event：接受 {@code the_quiet_latitude}、
     * {@code music_the_quiet_latitude} 或完整 id {@code apocalypse_zombies:music_...}。
     */
    private static SoundEvent resolve(String raw, SoundEvent fallback) {
        if (raw == null || raw.isBlank()) {
            return fallback;
        }
        String name = raw.trim().toLowerCase(Locale.ROOT);
        net.minecraft.resources.ResourceLocation id;
        if (name.contains(":")) {
            id = net.minecraft.resources.ResourceLocation.tryParse(name);
        } else if (name.startsWith("music_")) {
            id = new net.minecraft.resources.ResourceLocation(ApocalypseZombies.MOD_ID, name);
        } else {
            id = new net.minecraft.resources.ResourceLocation(ApocalypseZombies.MOD_ID, "music_" + name);
        }
        if (id == null) {
            return fallback;
        }
        SoundEvent sound = ForgeRegistries.SOUND_EVENTS.getValue(id);
        return sound != null ? sound : fallback;
    }
}
