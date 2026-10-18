package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;

/**
 * 纯背景图的加载界面。
 *
 * <p>进入单人世界时，原版会连续换三段加载画面：先 {@code GenericDirtMessageScreen}
 * （泥土底 + 「读取世界数据中…」），再 {@code LevelLoadingScreen}（百分比 + 区块网格），
 * 最后 {@code ReceivingLevelScreen}（泥土底 + 「加载地形中…」）。按需求这三段都不该再露原版文字，
 * 统一成同一张末日插画 —— 不画标题、不画进度、不画网格，只留图。</p>
 *
 * <p>本类负责第一段（由 {@code ClientEvents#onScreenOpening} 直接替换原版界面）；
 * {@link #drawCover(GuiGraphics)} 同时供后两段在 {@code ScreenEvent.Render.Post} 整屏覆盖。
 * 铺法与标题界面一致：cover 缩放、超出的部分居中裁掉，任何窗口比例都不留黑边。</p>
 */
public final class ApocalypseLoadingScreen extends Screen {

    /** 读取世界数据 / 加载世界用的背景（1408×768）。 */
    public static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/loading_background.png");
    public static final int TEX_W = 1408;
    public static final int TEX_H = 768;

    public ApocalypseLoadingScreen() {
        super(Component.empty());
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        // 只铺图：父类在这里会画标题/控件，本界面两样都不要。
        drawCover(graphics);
    }

    /** 按 cover 方式把加载背景铺满当前 GUI（不拉伸、不留边）。 */
    public static void drawCover(GuiGraphics graphics) {
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        float scale = Math.max(width / (float) TEX_W, height / (float) TEX_H);
        int w = Math.round(TEX_W * scale);
        int h = Math.round(TEX_H * scale);
        graphics.blit(BACKGROUND, (width - w) / 2, (height - h) / 2, w, h,
                0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }

    @Override
    public boolean shouldCloseOnEsc() {
        return false;
    }
}
