package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.Util;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.screens.ConfirmLinkScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.OptionsScreen;
import net.minecraft.client.gui.screens.worldselection.SelectWorldScreen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.fml.ModList;

/**
 * 末日风的标题界面。
 *
 * <p><b>背景与菜单一体</b>：背景图 {@code textures/gui/apocalypse_title.png}（1408×768 的
 * 《末日菜单》原图：紫电、末地废墟、标题字与四个石质按钮全都画在图里）。屏幕把自己那四个
 * 按钮<b>按图里那四个按钮的像素位置铺上去</b>（cover 变换同一套缩放），面是实心的，
 * 正好把图里烤死的按钮盖住 —— 逐像素重影没了，而布局、标题、底部版本行全部沿用参考图。</p>
 *
 * <p>按钮样式对齐参考图：中性灰石面 + 顶面高光 + 深色描边 + 白字；悬停/键盘聚焦时外圈亮紫、
 * 文字转紫白（第一项在打开时默认聚焦，和参考图里「SINGLEPLAYER 亮紫框」一致）。
 * 底部左侧的版本/玩家名是动态绘制的（图上那行是占位符），只盖住文字那一段，
 * 右侧的 MOJANG 标志保持可见；中间两个链接（GitHub / 团队站）点击前走原版
 * {@link ConfirmLinkScreen} 确认。</p>
 *
 * <p>替换入口在 {@code ClientEvents#onScreenOpening}：原版要打开 {@link TitleScreen} 时换成本类。
 * 纯客户端，专用服务器不加载。</p>
 */
public final class ApocalypseTitleScreen extends Screen {

    private static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/apocalypse_title.png");
    /** 背景图的原始尺寸（cover 缩放用；与参考图一致）。 */
    private static final int TEX_W = 1408;
    private static final int TEX_H = 768;

    // ---- 参考图里四个按钮的像素矩形（用 PIL 从 末日菜单.png 量出来的）----
    /** 按钮左/右边界（图内像素）。 */
    private static final int BTN_X0 = 486;
    private static final int BTN_X1 = 921;
    /** 第一行顶边、行距、行高（向外各放 2~4 px，把图里的紫框一起盖住）。 */
    private static final int BTN_TOP = 344;
    private static final int BTN_PITCH = 70;
    private static final int BTN_H = 60;

    /** 参考图底部版本占位文字的右边界（图内像素）—— 只盖到这里，让右下 MOJANG 标志留着。 */
    private static final int BOTTOM_TEXT_RIGHT = 640;

    private static final String GITHUB_URL = "https://github.com/SevenZeroMeowTeam/apocalypse_zombies";
    private static final String TEAM_URL = "https://team.qlm.org.cn";

    private static final int LINK_COLOR = 0xFFB9A8D0;
    private static final int LINK_HOVER = 0xFFE6CCFF;
    private static final int LINK_UNDERLINE = 0xFFB44BFF;

    public ApocalypseTitleScreen() {
        super(Component.empty());
    }

    @Override
    protected void init() {
        int[] cover = coverRect();
        int x0 = cover[0] + Math.round(BTN_X0 * cover[2] / (float) TEX_W);
        int x1 = cover[0] + Math.round(BTN_X1 * cover[2] / (float) TEX_W);
        int y0 = cover[1] + Math.round(BTN_TOP * cover[3] / (float) TEX_H);
        int pitch = Math.round(BTN_PITCH * cover[3] / (float) TEX_H);
        int h = Math.round(BTN_H * cover[3] / (float) TEX_H);
        int w = Math.max(40, x1 - x0);
        AbstractWidget first = new DoomButton(x0, y0, w, h, 0,
                Component.translatable("menu.apocalypse_zombies.singleplayer"),
                () -> this.minecraft.setScreen(new SelectWorldScreen(this)));
        addRenderableWidget(first);
        addRenderableWidget(new DoomButton(x0, y0 + pitch, w, h, 1,
                Component.translatable("menu.apocalypse_zombies.multiplayer"),
                () -> this.minecraft.setScreen(new JoinMultiplayerScreen(this))));
        addRenderableWidget(new DoomButton(x0, y0 + 2 * pitch, w, h, 2,
                Component.translatable("menu.apocalypse_zombies.options"),
                () -> this.minecraft.setScreen(new OptionsScreen(this, this.minecraft.options))));
        addRenderableWidget(new DoomButton(x0, y0 + 3 * pitch, w, h, 3,
                Component.translatable("menu.apocalypse_zombies.quit"),
                () -> this.minecraft.stop()));
        // 打开就聚焦第一项：与参考图里 SINGLEPLAYER 的亮紫框一致（键盘操作也顺手）
        setInitialFocus(first);
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        drawCoverBackground(graphics);
        super.render(graphics, mouseX, mouseY, partialTick);

        // 底部信息条：只盖住图里那行版本占位文字（右下 MOJANG 标志保持可见）
        int[] cover = coverRect();
        int bakedRight = cover[0] + Math.round(BOTTOM_TEXT_RIGHT * cover[2] / (float) TEX_W);
        String version = ModList.get().getModContainerById(ApocalypseZombies.MOD_ID)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("?");
        String player = this.minecraft.getUser().getName();
        String left = "Apocalypse Zombies  |  Ver " + version + "  |  " + player;
        int barRight = Math.max(bakedRight, 6 + this.font.width(left) + 8);
        graphics.fill(0, this.height - 22, barRight, this.height, 0xE6000000);
        graphics.drawString(this.font, left, 6, this.height - 15, LINK_COLOR, false);

        drawLinks(graphics, mouseX, mouseY);
    }

    /** cover 铺满后的绘制矩形：[x, y, w, h]。 */
    private int[] coverRect() {
        float scale = Math.max(this.width / (float) TEX_W, this.height / (float) TEX_H);
        int w = Math.round(TEX_W * scale);
        int h = Math.round(TEX_H * scale);
        return new int[]{(this.width - w) / 2, (this.height - h) / 2, w, h};
    }

    /** 把 1408×768 的背景按 cover 方式铺满窗口（超出部分居中裁掉）。 */
    private void drawCoverBackground(GuiGraphics graphics) {
        int[] c = coverRect();
        graphics.blit(BACKGROUND, c[0], c[1], c[2], c[3], 0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
    }

    /** 两个链接的布局：[x, y, githubWidth, gapWidth, teamWidth]。 */
    private int[] linkLayout() {
        boolean wide = this.width >= 720;
        String github = wide ? "GitHub · SevenZeroMeowTeam/apocalypse_zombies" : "GitHub";
        String team = wide ? "团队 · team.qlm.org.cn" : "Team";
        String gap = "    ";
        int gw = this.font.width(github);
        int gapW = this.font.width(gap);
        int tw = this.font.width(team);
        int total = gw + gapW + tw;
        int x = (this.width - total) / 2;
        int y = this.height - 15;
        return new int[]{x, y, gw, gapW, tw, wide ? 1 : 0};
    }

    private void drawLinks(GuiGraphics graphics, int mouseX, int mouseY) {
        int[] l = linkLayout();
        boolean wide = l[5] == 1;
        String github = wide ? "GitHub · SevenZeroMeowTeam/apocalypse_zombies" : "GitHub";
        String team = wide ? "团队 · team.qlm.org.cn" : "Team";
        int y = l[1];
        boolean hoverGithub = inLink(mouseX, mouseY, l[0], y, l[2]);
        boolean hoverTeam = inLink(mouseX, mouseY, l[0] + l[2] + l[3], y, l[4]);
        graphics.drawString(this.font, github, l[0], y, hoverGithub ? LINK_HOVER : LINK_COLOR, true);
        if (hoverGithub) {
            graphics.fill(l[0], y + 9, l[0] + l[2], y + 10, LINK_UNDERLINE);
        }
        graphics.drawString(this.font, team, l[0] + l[2] + l[3], y,
                hoverTeam ? LINK_HOVER : LINK_COLOR, true);
        if (hoverTeam) {
            int tx = l[0] + l[2] + l[3];
            graphics.fill(tx, y + 9, tx + l[4], y + 10, LINK_UNDERLINE);
        }
    }

    private static boolean inLink(int mx, int my, int x, int y, int w) {
        return mx >= x && mx <= x + w && my >= y - 2 && my <= y + 11;
    }

    @Override
    public boolean mouseClicked(double mouseX, double mouseY, int button) {
        if (super.mouseClicked(mouseX, mouseY, button)) {
            return true;
        }
        if (button != 0) {
            return false;
        }
        int[] l = linkLayout();
        if (inLink((int) mouseX, (int) mouseY, l[0], l[1], l[2])) {
            openLink(GITHUB_URL);
            return true;
        }
        int tx = l[0] + l[2] + l[3];
        if (inLink((int) mouseX, (int) mouseY, tx, l[1], l[4])) {
            openLink(TEAM_URL);
            return true;
        }
        return false;
    }

    private void openLink(String url) {
        this.minecraft.setScreen(new ConfirmLinkScreen(confirmed -> {
            if (confirmed) {
                Util.getPlatform().openUri(url);
            }
            this.minecraft.setScreen(this);
        }, url, true));
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
