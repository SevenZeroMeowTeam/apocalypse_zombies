package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.ChatScreen;
import net.minecraft.client.gui.screens.DeathScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.gui.components.events.GuiEventListener;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ScreenEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.ArrayList;
import java.util.List;

/**
 * 全局菜单的末日主题：所有「菜单类」界面统一换成末日背景 + 暗紫压暗，原生按钮统一换成
 * {@link DoomButton} 的末日石质外观（点击、可用状态、文字全部沿用原按钮）。
 *
 * <p><b>覆盖面</b>：暂停菜单、选项及其所有子页、选择世界、多人、资源包、语言、模组列表、
 * 载入界面……凡是 {@code Screen} 都在内；<b>排除</b>：标题界面（{@link ApocalypseTitleScreen}
 * 自己画）、本模组自己的配置/交易界面、物品容器界面（背包/箱子/合成台等，
 * {@link AbstractContainerScreen}）、聊天与死亡界面。</p>
 *
 * <p><b>实现</b>：背景挂在 {@code ScreenEvent.BackgroundRendered}（原版背景画完后整体覆盖，
 * 保证盖住泥土底图与模糊背景）；按钮换肤挂在 {@code ScreenEvent.Init.Post}，只替换
 * <b>类就是 {@code Button}</b> 的实例（图标按钮、自绘子类、滑块、复选框一律不动，避免破坏
 * 它们自己的渲染与交互）。列表行里由 Entry 自建的按钮不在 Screen 的 children 里，保持原样。</p>
 *
 * <p>纯客户端：专用服务器不加载。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class DoomMenuTheme {

    /** 与标题界面同一张《末日菜单》背景（1408×768）。 */
    private static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/apocalypse_title.png");
    private static final int TEX_W = 1408;
    private static final int TEX_H = 768;

    private DoomMenuTheme() {
    }

    @SubscribeEvent
    public static void onBackgroundRendered(ScreenEvent.BackgroundRendered event) {
        Screen screen = event.getScreen();
        if (!isThemed(screen)) {
            return;
        }
        GuiGraphics graphics = event.getGuiGraphics();
        int w = screen.width;
        int h = screen.height;
        // cover 铺满（与标题界面同一套算法）
        float scale = Math.max(w / (float) TEX_W, h / (float) TEX_H);
        int bw = Math.round(TEX_W * scale);
        int bh = Math.round(TEX_H * scale);
        int x = (w - bw) / 2;
        int y = (h - bh) / 2;
        graphics.blit(BACKGROUND, x, y, bw, bh, 0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
        // 压暗 + 冷紫调：菜单文字/列表压在图上也要读得清
        graphics.fill(0, 0, w, h, 0x99000000);
        graphics.fill(0, 0, w, h, 0x2A1A0A28);
    }

    @SubscribeEvent
    public static void onScreenInit(ScreenEvent.Init.Post event) {
        Screen screen = event.getScreen();
        if (!isThemed(screen)) {
            return;
        }
        // 先收集再替换：一边迭代 children 一边 addRenderableWidget 会 CME
        List<Button> vanilla = new ArrayList<>();
        for (GuiEventListener listener : new ArrayList<>(screen.children())) {
            if (listener.getClass() == Button.class) {
                vanilla.add((Button) listener);
            }
        }
        int seed = 0;
        for (Button original : vanilla) {
            WrappedDoomButton wrapped = new WrappedDoomButton(original, seed++);
            // 从屏幕原有的渲染/事件列表里摘掉原按钮，再走 Forge 的正规通道加外壳
            // （Screen#addRenderableWidget 是 protected，ScreenEvent.Init#addListener 就是给它开的门）
            screen.children().remove(original);
            screen.renderables.remove(original);
            event.addListener(wrapped);
        }
    }

    /** 哪些界面吃这套主题。 */
    private static boolean isThemed(Screen screen) {
        if (screen instanceof TitleScreen) {
            return false;                                   // 原版标题（正常会被换成 ApocalypseTitleScreen）
        }
        if (screen instanceof ApocalypseTitleScreen
                || screen instanceof ApocalypseConfigScreen
                || screen instanceof CatGirlTradeScreen) {
            return false;                                   // 本模组自绘界面
        }
        if (screen instanceof AbstractContainerScreen) {
            return false;                                   // 背包/箱子/合成台等容器
        }
        if (screen instanceof ChatScreen || screen instanceof DeathScreen) {
            return false;                                   // 聊天 / 死亡：不该被背景图干扰
        }
        return true;
    }

    /**
     * 包住一个原版 {@code Button}：外观换成末日石质，点击转交原按钮的 {@code onPress()}；
     * 原按钮的可用/可见状态每帧同步过来（有些界面会根据选择实时置灰按钮）。
     */
    private static final class WrappedDoomButton extends DoomButton {
        private final Button original;

        private WrappedDoomButton(Button original, int seed) {
            super(original.getX(), original.getY(), original.getWidth(), original.getHeight(), seed,
                    original.getMessage(), original::onPress);
            this.original = original;
            this.active = original.active;
            this.visible = original.visible;
        }

        @Override
        public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
            this.active = this.original.active;
            this.visible = this.original.visible;
            super.render(graphics, mouseX, mouseY, partialTick);
        }
    }
}
