package com.apocalypse.zombies.client.music;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.registry.ModSounds;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 「朋友的酒」—— 常驻背景音乐。
 *
 * <p>玩家要的是「进游戏就一直循环放」，所以这里不走原版那套「隔几分钟随机挑一首」的节奏，
 * 而是把它挂成一个常驻的 {@link SoundInstance}，一直放到离开世界或关掉开关为止。</p>
 *
 * <h2>循环为什么不交给 SoundEngine</h2>
 * 这首音频在 {@code sounds.json} 里标了 {@code "stream": true}（5.5 MB，必须流式解码，否则整曲进内存），
 * 而 OpenAL 的 {@code AL_LOOPING} 只对<b>整段一次性入队</b>的缓冲有效 —— 流式音源是边解边喂 buffer，
 * 到曲末那条路不一定接得上。所以这里用原版 {@code MusicManager} 用了几十年的办法：
 * {@code looping = false}，每 tick 查一次 {@code SoundManager#isActive}，播放结束就重新起一首。
 * 代价只是曲末到重播之间最多一个 tick（50 ms），换来的是「一定会循环」。</p>
 *
 * <h2>为什么要压原版音乐</h2>
 * Forge 1.20.1 <b>没有</b> {@code SelectMusicEvent}（那个是更高版本才有的），所以没有「把
 * 场景音乐换成我的」这条正规途径。原版 {@code MusicManager} 每 tick 自己判断要不要开一首，
 * 于是只能反着来：只要我们的音乐在放，就每 tick 调一次 {@code MusicManager#stopPlaying()} 让它
 * 让位。这个调用本身是幂等的（没有正在播的音乐时什么都不做），原版在没有音乐时也一直在做同一件事，
 * 所以反复调用没有副作用。开关在 {@code [friends_wine_music] suppress_vanilla}。</p>
 *
 * <p>纯客户端：专用服务器不加载这个类（{@code Dist.CLIENT} + 事件总线订阅）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class FriendsWineMusic {

    /** 当前正在播的那一个实例。持有它是为了能查 {@code isActive} 与在需要时精确停掉。 */
    private static SoundInstance current;

    private FriendsWineMusic() {
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (!Config.FRIENDS_WINE_MUSIC.get()) {
            stop(minecraft);
            return;
        }
        if (minecraft.level == null || minecraft.player == null) {
            stop(minecraft);
            return;
        }
        // 玩家把「音乐」音量拉到 0 就别占着解码线程了 —— SoundEngine 会把它静音，但流式解码照跑
        if (minecraft.options.getSoundSourceVolume(SoundSource.MUSIC) <= 0.0F) {
            stop(minecraft);
            return;
        }

        if (Config.FRIENDS_WINE_SUPPRESS_VANILLA.get()) {
            minecraft.getMusicManager().stopPlaying();
        }
        // 还在放就什么都不做；放完了（或从没开始）就起一首 —— 这就是「循环」的全部实现
        if (current != null && minecraft.getSoundManager().isActive(current)) {
            return;
        }
        play(minecraft);
    }

    /** 退出世界时收干净：实例没了，但下次进来要重新起。 */
    @SubscribeEvent
    public static void onLoggingOut(ClientPlayerNetworkEvent.LoggingOut event) {
        stop(Minecraft.getInstance());
    }

    private static void play(Minecraft minecraft) {
        SoundEvent event = ModSounds.MUSIC_FRIENDS_WINE.get();
        float volume = Config.FRIENDS_WINE_VOLUME.get().floatValue();
        current = new SimpleSoundInstance(
                event.getLocation(),
                SoundSource.MUSIC,
                volume,
                1.0F,
                RandomSource.create(),
                false,                                  // 不交给 OpenAL 循环，见类注释
                0,                                      // delay
                SoundInstance.Attenuation.NONE,         // 不随距离衰减
                0.0D, 0.0D, 0.0D,
                true);                                  // relative：跟随听者，走到哪都在耳边
        minecraft.getSoundManager().play(current);
    }

    private static void stop(Minecraft minecraft) {
        if (current == null) {
            return;
        }
        minecraft.getSoundManager().stop(current);
        current = null;
    }
}
