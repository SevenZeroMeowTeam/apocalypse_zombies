package com.apocalypse.zombies.client.gui;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.network.chat.Component;

/**
 * 末日风石质按钮：深色描边 + 中性灰石面 + 顶面高光 + 几道淡裂纹 + 白字；
 * 悬停 / 键盘聚焦时外圈亮紫、文字转紫白。按钮够高（≥ 34 px）时用 2× 像素字，
 * 与参考图（《末日菜单》）那种分辨率感一致。
 *
 * <p>标题界面与全局菜单主题（{@link DoomMenuTheme}）共用这一个类；
 * 索引只用来让每个按钮的裂纹位置不同。</p>
 */
public class DoomButton extends AbstractWidget {

    private final Runnable action;
    private final int seed;

    public DoomButton(int x, int y, int w, int h, int seed, Component message, Runnable action) {
        super(x, y, w, h, message);
        this.action = action;
        this.seed = seed;
    }

    @Override
    protected void renderWidget(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        int x = getX();
        int y = getY();
        int w = width;
        int h = height;
        boolean hover = isHoveredOrFocused();
        if (hover) {
            graphics.fill(x - 3, y - 3, x + w + 3, y + h + 3, 0x55B44BFF);
            graphics.fill(x - 2, y - 2, x + w + 2, y + h + 2, 0xB0B44BFF);
        }
        // 深色描边 + 石面
        graphics.fill(x, y, x + w, y + h, 0xFF1A1420);
        graphics.fill(x + 1, y + 1, x + w - 1, y + h - 1,
                hover ? 0xFF6E6E6E : 0xFF5E5E5E);
        graphics.fill(x + 1, y + 1, x + w - 1, y + h / 2,
                hover ? 0xFF8A8A8A : 0xFF7C7C7C);
        // 裂纹（每个按钮位置不同，颜色很淡）
        int c = 0x33000000;
        int crackX = x + 16 + seed * 37 % Math.max(1, w - 60);
        graphics.fill(crackX, y + 6, crackX + 22 + seed * 9, y + 7, c);
        graphics.fill(crackX + 14, y + 6, crackX + 15, y + 15, c);
        int crackX2 = x + w - 34 - seed * 23 % 60;
        graphics.fill(crackX2, y + h - 10, crackX2 + 18, y + h - 9, c);
        graphics.fill(crackX2 + 6, y + h - 16, crackX2 + 7, y + h - 10, c);

        // 文字：按钮够大时 2 倍像素字（与参考图的分辨率感一致），否则原尺寸
        Component msg = getMessage();
        int color = hover ? 0xFFE6CCFF : 0xFFFFFFFF;
        int scale = h >= 34 ? 2 : 1;
        var pose = graphics.pose();
        pose.pushPose();
        pose.translate(x + w / 2.0F, y + (h - 8.0F * scale) / 2.0F, 0.0F);
        pose.scale(scale, scale, 1.0F);
        int tw = font().width(msg);
        graphics.drawString(font(), msg, -tw / 2, 0, color, true);
        pose.popPose();
    }

    private static net.minecraft.client.gui.Font font() {
        return Minecraft.getInstance().font;
    }

    @Override
    public void onClick(double mouseX, double mouseY) {
        this.action.run();
    }

    @Override
    protected void updateWidgetNarration(net.minecraft.client.gui.narration.NarrationElementOutput output) {
        this.defaultButtonNarrationText(output);
    }
}
