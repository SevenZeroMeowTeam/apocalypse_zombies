package com.apocalypse.zombies.client.sky;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.ClientConfig;
import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.AbstractTexture;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.client.renderer.texture.SimpleTexture;
import net.minecraft.client.renderer.texture.TextureManager;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Unit;
import net.minecraft.util.profiling.ProfilerFiller;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterClientReloadListenersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.config.ModConfigEvent;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;

import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 把本模组的写实天空贴图（太阳 / 八相位月面 / 云层 / 雨 / 雪）强行装进原版
 * {@code minecraft:textures/environment/*} 槽位。
 *
 * <p><b>为什么不能只靠 {@code assets/minecraft/textures/environment/} 覆盖：</b>
 * 资源查找从资源栈<b>尾部</b>往回走（{@code FallbackResourceManager} 倒序），
 * {@code options.txt} 的 {@code resourcePacks} 数组<b>最后一个优先级最高</b>。
 * 本实例实测栈是 {@code mod_resources, vanilla, file/apocalypse_32x, high_contrast,
 * programmer_art} —— {@code vanilla} / {@code programmer_art} 都排在模组之后，
 * 于是 6.1.0 内置的 1024² 太阳、2048×1024 月面、无缝云层被原版 32×32 盖回去，
 * 看起来「日月云又变回原版」；方块贴图没事是因为 {@code file/apocalypse_32x}
 * 排在原版之上、且里面没有天空贴图。</p>
 *
 * <p><b>修法</b>：从 {@code apocalypse_zombies:textures/environment/} 读 PNG，做成
 * {@link DynamicTexture} 注册到原版那五个 {@link ResourceLocation}。
 * {@code TextureManager.getTexture} 命中 {@code byPath} 就直接返回，不再去问资源栈；
 * {@link DynamicTexture#load} 是空的，F3+T 重载时 {@code TextureManager.reload → reset →
 * register(this)} 不会把它冲成原版 {@link SimpleTexture}。资源重载后再 apply 一次兜底。</p>
 *
 * <p>关掉 {@code sky.texture_override} 立刻退回资源栈（原版 / 程序员艺术包 / 用户包）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class SkyTextureOverrides {

    /** 原版 {@code LevelRenderer} 绑的五个槽位，与源码常量逐字相同。 */
    static final ResourceLocation VANILLA_SUN =
            ResourceLocation.withDefaultNamespace("textures/environment/sun.png");
    static final ResourceLocation VANILLA_MOON =
            ResourceLocation.withDefaultNamespace("textures/environment/moon_phases.png");
    static final ResourceLocation VANILLA_CLOUDS =
            ResourceLocation.withDefaultNamespace("textures/environment/clouds.png");
    static final ResourceLocation VANILLA_RAIN =
            ResourceLocation.withDefaultNamespace("textures/environment/rain.png");
    static final ResourceLocation VANILLA_SNOW =
            ResourceLocation.withDefaultNamespace("textures/environment/snow.png");

    /** 本模组资产路径（与 jar 内文件一一对应，不进 minecraft 命名空间，所以不怕资源栈顺序）。 */
    private static final ResourceLocation OURS_SUN = modEnv("sun.png");
    private static final ResourceLocation OURS_MOON = modEnv("moon_phases.png");
    private static final ResourceLocation OURS_CLOUDS = modEnv("clouds.png");
    private static final ResourceLocation OURS_RAIN = modEnv("rain.png");
    private static final ResourceLocation OURS_SNOW = modEnv("snow.png");

    private static boolean applied;

    private SkyTextureOverrides() {
    }

    private static ResourceLocation modEnv(String file) {
        return ResourceLocation.fromNamespaceAndPath(ApocalypseZombies.MOD_ID,
                "textures/environment/" + file);
    }

    @SubscribeEvent
    public static void onClientSetup(FMLClientSetupEvent event) {
        event.enqueueWork(SkyTextureOverrides::apply);
    }

    @SubscribeEvent
    public static void onRegisterReload(RegisterClientReloadListenersEvent event) {
        event.registerReloadListener(new PreparableReloadListener() {
            @Override
            public CompletableFuture<Void> reload(PreparableReloadListener.PreparationBarrier barrier,
                                                  ResourceManager resourceManager,
                                                  ProfilerFiller preparationsProfiler,
                                                  ProfilerFiller reloadProfiler,
                                                  Executor backgroundExecutor,
                                                  Executor gameExecutor) {
                // barrier 之后 TextureManager 已经按资源栈把 SimpleTexture 重装过一遍，
                // 再在主线程把 DynamicTexture 顶回去。
                return barrier.wait(Unit.INSTANCE)
                        .thenRunAsync(SkyTextureOverrides::apply, gameExecutor);
            }
        });
    }

    @SubscribeEvent
    public static void onConfig(ModConfigEvent event) {
        if (event.getConfig().getSpec() != ClientConfig.SPEC) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft != null) {
            minecraft.execute(SkyTextureOverrides::apply);
        }
    }

    /** 按当前配置把五个槽位装成写实贴图，或退回资源栈。任何失败只 warn，不崩客户端。 */
    public static void apply() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            return;
        }
        TextureManager textures = minecraft.getTextureManager();
        boolean want = ClientConfig.SPEC.isLoaded() && ClientConfig.REALISTIC_SKY_EFFECTS.get()
                && ClientConfig.SKY_TEXTURE_OVERRIDE.get();
        try {
            if (want) {
                bindOurs(textures, VANILLA_SUN, OURS_SUN, false);
                bindOurs(textures, VANILLA_MOON, OURS_MOON, false);
                bindOurs(textures, VANILLA_CLOUDS, OURS_CLOUDS, true);
                bindOurs(textures, VANILLA_RAIN, OURS_RAIN, false);
                bindOurs(textures, VANILLA_SNOW, OURS_SNOW, false);
                if (!applied) {
                    ApocalypseZombies.LOGGER.info(
                            "[天空贴图] 已把写实太阳/月面/云层/雨雪装进原版 environment 槽位（不受 vanilla / programmer_art 资源包顺序影响）");
                }
                applied = true;
            } else if (applied) {
                restore(textures, VANILLA_SUN);
                restore(textures, VANILLA_MOON);
                restore(textures, VANILLA_CLOUDS);
                restore(textures, VANILLA_RAIN);
                restore(textures, VANILLA_SNOW);
                applied = false;
                ApocalypseZombies.LOGGER.info("[天空贴图] 已退回资源栈（sky.texture_override=false）");
            }
        } catch (Exception e) {
            ApocalypseZombies.LOGGER.warn("[天空贴图] 应用失败，槽位保持现状。", e);
        }
    }

    /**
     * 已经是本模组 DynamicTexture 就不动（F3+T 时 TextureManager 会 reset 同一实例）；
     * 否则从模组命名空间读 PNG 做成新的 DynamicTexture 顶上去。
     */
    private static void bindOurs(TextureManager textures, ResourceLocation vanilla,
                                 ResourceLocation ours, boolean blur) throws IOException {
        AbstractTexture current = textures.getTexture(vanilla, null);
        if (current instanceof DynamicTexture) {
            return;
        }
        NativeImage image = readPng(ours);
        DynamicTexture texture = new DynamicTexture(image);
        texture.setFilter(blur, false);
        textures.register(vanilla, texture);
    }

    /** 退回 {@link SimpleTexture}：下次 bind 时按资源栈重读（原版 / 程序员艺术包 / 用户包）。 */
    private static void restore(TextureManager textures, ResourceLocation vanilla) {
        textures.register(vanilla, new SimpleTexture(vanilla));
    }

    private static NativeImage readPng(ResourceLocation location) throws IOException {
        ResourceManager resources = Minecraft.getInstance().getResourceManager();
        Resource resource = resources.getResource(location).orElseThrow(
                () -> new IOException("missing sky texture " + location));
        try (InputStream stream = resource.open()) {
            return NativeImage.read(stream);
        }
    }
}
