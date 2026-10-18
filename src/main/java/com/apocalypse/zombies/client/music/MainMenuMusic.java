package com.apocalypse.zombies.client.music;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.registry.ModSounds;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 主菜单曲《The Last Known Meridian》—— 只在标题界面循环。
 *
 * <p><b>分工</b>：世界里放「朋友的酒」（{@link FriendsWineMusic}），主菜单放这首。
 * 两者同一时刻只有一首：本类在 {@code level == null}（标题界面 / 载入中）时接管，
 * 一进世界立刻停；{@code FriendsWineMusic} 反过来在菜单里让位。</p>
 *
 * <p><b>循环</b>：与「朋友的酒」同一套办法 —— 流式 OGG 不走 {@code AL_LOOPING}，
 * {@code looping=false} + 每 tick 查 {@code SoundManager#isActive}，放完就从开头再来一遍。
 * 曲末到重播之间最多一个 tick（50 ms）。</p>
 *
 * <p><b>原版主菜单曲</b>：开播期间每 tick 调一次 {@code MusicManager#stopPlaying()} 让位
 * （幂等；与原版自己的行为一致）。是否压原版沿用 {@code friends_wine_music.suppress_vanilla}
 * 这条设置 —— 「别放原版背景音乐」是一件事，不按界面区分。</p>
 *
 * <p><b>总开关</b>：F10 / {@code friends_wine_music.enabled} 关掉 = 自研音乐全静音
 * （主菜单曲与朋友的酒一起停）。另有 {@code main_menu_music.enabled} 单独关菜单曲。</p>
 *
 * <p>纯客户端：专用服务器不加载这个类（{@code Dist.CLIENT} + FORGE 总线订阅）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class MainMenuMusic {

    /** 当前正在播的那一个实例（用于 {@code isActive} 查询与精确停止）。 */
    private static SoundInstance current;

    private MainMenuMusic() {
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        // 只接管「没有世界」的界面：标题菜单、载入世界、连接服务器
        if (minecraft.level != null) {
            stop(minecraft);
            return;
        }
        if (!Config.FRIENDS_WINE_MUSIC.get() || !Config.MAIN_MENU_MUSIC.get()) {
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
        if (current != null && minecraft.getSoundManager().isActive(current)) {
            return;
        }
        play(minecraft);
    }

    private static void play(Minecraft minecraft) {
        float volume = Config.MAIN_MENU_MUSIC_VOLUME.get().floatValue();
        current = new SimpleSoundInstance(
                ModSounds.MUSIC_THE_LAST_KNOWN_MERIDIAN.get().getLocation(),
                SoundSource.MUSIC,
                volume,
                1.0F,
                RandomSource.create(),
                false,                                  // 不交给 OpenAL 循环（流式音源接不上，见类注释）
                0,
                SoundInstance.Attenuation.NONE,
                0.0D, 0.0D, 0.0D,
                true);                                  // relative：跟着听者
        minecraft.getSoundManager().play(current);
    }

    private static void stop(Minecraft minecraft) {
        if (current == null) {
            return;
        }
        if (minecraft.getSoundManager() != null) {
            minecraft.getSoundManager().stop(current);
        }
        current = null;
    }
}
