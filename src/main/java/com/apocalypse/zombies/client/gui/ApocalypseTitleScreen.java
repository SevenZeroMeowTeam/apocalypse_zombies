package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.Util;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.events.GuiEventListener;
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
 * <p>背景图是项目里自带的 {@code textures/gui/apocalypse_title.png}（紫电、浮空岛、末地废墟），
 * 四个按钮用代码画成「裂纹石块 + 紫色描边」：悬停时外圈亮紫、内层提亮、文字转紫白。
 * 底部左侧是模组名/版本/玩家名，中间是两个可点击链接（GitHub 与团队站），
 * 点击会先经过原版的 {@link ConfirmLinkScreen} 确认再打开浏览器。</p>
 *
 * <p>替换入口在 {@code ClientEvents#onScreenOpening}：只要原版要打开 {@link TitleScreen}，
 * 就把新屏幕换成本类。纯客户端，专用服务器不加载。</p>
 */
public final class ApocalypseTitleScreen extends Screen {

    private static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/apocalypse_title.png");
    /** 背景图的原始尺寸（cover 缩放用）。 */
    private static final int TEX_W = 1408;
    private static final int TEX_H = 768;
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
        int cx = this.width / 2;
        int bw = Math.min(300, Math.max(210, this.width / 4));
        int bh = 28;
        int gap = 10;
        int total = 4 * bh + 3 * gap;
        // 图片里按钮组中心略低于画面中线
        int y = this.height / 2 - total / 2 + 12;
        addRenderableWidget(new MenuButton(cx - bw / 2, y, bw, bh, 0,
                Component.translatable("menu.apocalypse_zombies.singleplayer"),
                () -> this.minecraft.setScreen(new SelectWorldScreen(this))));
        addRenderableWidget(new MenuButton(cx - bw / 2, y + (bh + gap), bw, bh, 1,
                Component.translatable("menu.apocalypse_zombies.multiplayer"),
                () -> this.minecraft.setScreen(new JoinMultiplayerScreen(this))));
        addRenderableWidget(new MenuButton(cx - bw / 2, y + 2 * (bh + gap), bw, bh, 2,
                Component.translatable("menu.apocalypse_zombies.options"),
                () -> this.minecraft.setScreen(new OptionsScreen(this, this.minecraft.options))));
        addRenderableWidget(new MenuButton(cx - bw / 2, y + 3 * (bh + gap), bw, bh, 3,
                Component.translatable("menu.apocalypse_zombies.quit"),
                () -> this.minecraft.stop()));
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        drawCoverBackground(graphics);
        super.render(graphics, mouseX, mouseY, partialTick);

        // 底部信息条：盖住原图自带的那行版本文字
        graphics.fill(0, this.height - 22, this.width, this.height, 0xE6000000);
        String version = ModList.get().getModContainerById(ApocalypseZombies.MOD_ID)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("?");
        String player = this.minecraft.getUser().getName();
        String left = "Apocalypse Zombies  |  Ver " + version + "  |  " + player;
        graphics.drawString(this.font, left, 6, this.height - 15, LINK_COLOR, false);

        drawLinks(graphics, mouseX, mouseY);
    }

    /** 把 1408×768 的背景按 cover 方式铺满窗口（超出部分居中裁掉）。 */
    private void drawCoverBackground(GuiGraphics graphics) {
        float scale = Math.max(this.width / (float) TEX_W, this.height / (float) TEX_H);
        int w = Math.round(TEX_W * scale);
        int h = Math.round(TEX_H * scale);
        int x = (this.width - w) / 2;
        int y = (this.height - h) / 2;
        graphics.blit(BACKGROUND, x, y, w, h, 0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
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
        graphics.drawString(this.font, github, l[0], y, hoverGithub ? LINK_HOVER : LINK_COLOR, false);
        if (hoverGithub) {
            graphics.fill(l[0], y + 9, l[0] + l[2], y + 10, LINK_UNDERLINE);
        }
        graphics.drawString(this.font, team, l[0] + l[2] + l[3], y,
                hoverTeam ? LINK_HOVER : LINK_COLOR, false);
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

    /**
     * 裂纹石块按钮：深紫描边 + 灰色石面 + 顶面高光 + 几道裂纹；悬停时紫色泛光、文字变紫白。
     * 索引只用来让每个按钮的裂纹位置不同。
     */
    private static final class MenuButton extends AbstractWidget {
        private final Runnable action;
        private final int seed;

        private MenuButton(int x, int y, int w, int h, int seed, Component message, Runnable action) {
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
                graphics.fill(x - 2, y - 2, x + w + 2, y + h + 2, 0x40B44BFF);
                graphics.fill(x - 1, y - 1, x + w + 1, y + h + 1, 0x90B44BFF);
            }
            graphics.fill(x, y, x + w, y + h, 0xFF2A1B33);
            graphics.fill(x + 1, y + 1, x + w - 1, y + h - 1,
                    hover ? 0xFFB9A6C6 : 0xFF9A939C);
            graphics.fill(x + 1, y + 1, x + w - 1, y + h / 2,
                    hover ? 0xFFD3C1E0 : 0xFFAAA3AC);
            // 裂纹（每个按钮位置不同，颜色很淡）
            int c = 0x33000000;
            int cx = x + 16 + seed * 37 % Math.max(1, w - 60);
            graphics.fill(cx, y + 5, cx + 22 + seed * 9, y + 6, c);
            graphics.fill(cx + 14, y + 5, cx + 15, y + 14, c);
            int cx2 = x + w - 30 - seed * 23 % 60;
            graphics.fill(cx2, y + h - 8, cx2 + 18, y + h - 7, c);
            graphics.fill(cx2 + 6, y + h - 14, cx2 + 7, y + h - 8, c);

            int color = hover ? 0xFFE6CCFF : 0xFF2B2330;
            Component msg = getMessage();
            int tx = x + (w - MenuButton.font().width(msg)) / 2;
            int ty = y + (h - 8) / 2;
            graphics.drawString(MenuButton.font(), msg, tx, ty, color, false);
        }

        private static net.minecraft.client.gui.Font font() {
            return net.minecraft.client.Minecraft.getInstance().font;
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
}
