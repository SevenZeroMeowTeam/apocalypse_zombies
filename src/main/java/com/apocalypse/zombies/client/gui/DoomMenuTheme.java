package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.ChatScreen;
import net.minecraft.client.gui.screens.DeathScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.gui.screens.worldselection.SelectWorldScreen;
import net.minecraft.client.gui.screens.worldselection.WorldSelectionList;
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

    /**
     * 菜单通用背景：干净的末日紫调废墟插画（1408×768）。
     *
     * <p><b>为什么不用 apocalypse_title.png</b>：那张《末日菜单》原图里烤死了标题字和
     * 四个石质按钮，只适合标题界面自己用（真实按钮正好盖住图里的按钮）。铺到断开连接/
     * 选项/多人等界面时，烤死的字和按钮会从对话框后面透出来，像重影 UI。
     * 这张由 {@code tools/menu_background.py} 从 pause_background.png 派生，本身没有任何文字/按钮。</p>
     */
    private static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/menu_background.png");
    /** 选择世界：用户指定的《废土城市》插画（与 ESC 暂停同一张）。 */
    private static final ResourceLocation SELECT_WORLD_BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/pause_background.png");
    private static final int TEX_W = 1408;
    private static final int TEX_H = 768;

    private DoomMenuTheme() {
    }

    /**
     * 选择世界界面：铺《废土城市》插画。
     *
     * <p><b>为什么必须挂在 Render.Pre</b>：{@code SelectWorldScreen.render} 自己不调用
     * {@code renderBackground}，所以 {@code BackgroundRendered} 根本不会触发；而
     * {@code WorldSelectionList} 会在列表区域自绘原版泥土。这里在屏幕绘制前先铺图，
     * 同时在 {@link #onScreenInit} 里把列表的 {@code renderBackground} 关掉 —— 泥土才不会盖住插画。</p>
     */
    @SubscribeEvent
    public static void onScreenRenderPre(ScreenEvent.Render.Pre event) {
        Screen screen = event.getScreen();
        if (screen instanceof SelectWorldScreen) {
            drawCover(event.getGuiGraphics(), screen.width, screen.height,
                    SELECT_WORLD_BACKGROUND, 0x80000000);
        }
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
        if (screen instanceof SelectWorldScreen) {
            // 若这个版本仍走了 renderBackground（先画了泥土），这里补铺一次插画把它盖掉。
            drawCover(graphics, w, h, SELECT_WORLD_BACKGROUND, 0x80000000);
            return;
        }
        drawCover(graphics, w, h, BACKGROUND, 0x99000000);
    }

    /** cover 铺满 + 压暗 + 冷紫调。 */
    private static void drawCover(GuiGraphics graphics, int w, int h,
                                  ResourceLocation background, int dim) {
        float scale = Math.max(w / (float) TEX_W, h / (float) TEX_H);
        int bw = Math.round(TEX_W * scale);
        int bh = Math.round(TEX_H * scale);
        int x = (w - bw) / 2;
        int y = (h - bh) / 2;
        graphics.blit(background, x, y, bw, bh, 0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
        graphics.fill(0, 0, w, h, dim);
        graphics.fill(0, 0, w, h, 0x2A1A0A28);
    }

    @SubscribeEvent
    public static void onScreenInit(ScreenEvent.Init.Post event) {
        Screen screen = event.getScreen();
        if (!isThemed(screen)) {
            return;
        }
        // 选择世界的世界列表会自绘一层原版泥土（SelectWorldScreen 自己不调用 renderBackground）；
        // 关掉它，Render.Pre 铺的插画才能透出来。列表行、搜索框、按钮仍照常画。
        if (screen instanceof SelectWorldScreen) {
            for (GuiEventListener listener : screen.children()) {
                if (listener instanceof WorldSelectionList list) {
                    list.setRenderBackground(false);
                    break;
                }
            }
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
                || screen instanceof ApocalypsePauseScreen
                || screen instanceof ApocalypseLoadingScreen
                || screen instanceof ApocalypseConfigScreen
                || screen instanceof CatGirlTradeScreen) {
            return false;                                   // 本模组自绘界面（自己铺背景/按钮）
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
