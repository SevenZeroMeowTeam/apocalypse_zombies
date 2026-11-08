package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import com.mojang.blaze3d.systems.RenderSystem;
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
 * 《末日菜单》原图：紫电、末地废墟、标题字与四个石质按钮全都画在图里）。6.4.1 起四个按钮
 * 改成 <b>2×2 网格</b>，四块实心石面正好把图里烤死的四个竖排按钮（含第一项的紫色饰框和那只
 * 烤进图里的手形光标）整片盖住 —— 区域取 x 486..921、y 344..614（图内像素，cover 变换同一套
 * 缩放），中间留 12 图素缝，悬停高亮不会咬到邻格。</p>
 *
 * <p>按钮样式对齐参考图：中性灰石面 + 顶面高光 + 深色描边 + 白字；悬停/键盘聚焦时外圈亮紫、
 * 文字转紫白（第一项在打开时默认聚焦）。底部左侧的版本/玩家名是动态绘制的（图上那行是
 * 占位符），只盖住文字那一段，右侧的 MOJANG 标志保持可见；GitHub / 团队站两个链接
 * <b>紧跟在信息条右侧</b>排开（不再居中 —— 居中时会压到左侧那行字），GitHub 链接带
 * octocat 图标（{@code textures/gui/github_mark.png}，tools/gen_github_mark.py 烘焙），
 * 点击前走原版 {@link ConfirmLinkScreen} 确认。</p>
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

    /** GitHub octocat 图标（16×16 烘焙，按 8×8 GUI 单位 blit；GUI scale 2 时 1:1 像素）。 */
    private static final ResourceLocation GITHUB_ICON = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/github_mark.png");
    private static final int ICON_SIZE = 8;

    // ---- 图里烤死的四个按钮占用的区域（用 PIL 从 末日菜单.png 量出来的）----
    /** 区域左/右边界（图内像素；含第一项紫色饰框与手形光标的横向范围）。 */
    private static final int GRID_X0 = 486;
    private static final int GRID_X1 = 921;
    /** 区域上/下边界（四行按钮从 y 344 到 614）。 */
    private static final int GRID_Y0 = 344;
    private static final int GRID_Y1 = 614;
    /** 2×2 格子之间的缝（图内像素），映射到屏幕后至少 4 GUI px。 */
    private static final int GRID_GAP = 12;

    /** 参考图底部版本占位文字的右边界（图内像素）—— 只盖到这里，让右下 MOJANG 标志留着。 */
    private static final int BOTTOM_TEXT_RIGHT = 640;
    /** 图里烤死的 MOJANG 标志左缘（红色方块起点，实测 1276；链接不得压进去）。 */
    private static final int BAKED_MOJANG_LEFT = 1272;

    private static final String GITHUB_URL = "https://github.com/SevenZeroMeowTeam/apocalypse_zombies";
    private static final String TEAM_URL = "https://team.qlm.org.cn";

    /** GitHub 身份由 octocat 图标承担，文字只留仓库路径 —— 底部一行才放得下两个地址。 */
    private static final String GITHUB_LABEL = "SevenZeroMeowTeam/apocalypse_zombies";
    private static final String TEAM_LABEL = "团队 · team.qlm.org.cn";
    private static final String GITHUB_LABEL_SHORT = "GitHub";
    private static final String TEAM_LABEL_SHORT = "Team";

    private static final int LINK_COLOR = 0xFFB9A8D0;
    private static final int LINK_HOVER = 0xFFE6CCFF;
    private static final int LINK_UNDERLINE = 0xFFB44BFF;

    public ApocalypseTitleScreen() {
        super(Component.empty());
    }

    @Override
    protected void init() {
        // 2×2 网格：整片铺满图里烤死的四个竖排按钮，一像素都不露出来
        int[] cover = coverRect();
        int x0 = cover[0] + Math.round(GRID_X0 * cover[2] / (float) TEX_W);
        int x1 = cover[0] + Math.round(GRID_X1 * cover[2] / (float) TEX_W);
        int y0 = cover[1] + Math.round(GRID_Y0 * cover[3] / (float) TEX_H);
        int y1 = cover[1] + Math.round(GRID_Y1 * cover[3] / (float) TEX_H);
        int gapX = Math.max(4, Math.round(GRID_GAP * cover[2] / (float) TEX_W));
        int gapY = Math.max(4, Math.round(GRID_GAP * cover[3] / (float) TEX_H));
        int bw = Math.max(40, (x1 - x0 - gapX) / 2);
        int bh = Math.max(30, (y1 - y0 - gapY) / 2);
        int colL = x0;
        int colR = x1 - bw;
        int rowT = y0;
        int rowB = y1 - bh;

        AbstractWidget first = new DoomButton(colL, rowT, bw, bh, 0,
                Component.translatable("menu.apocalypse_zombies.singleplayer"),
                () -> this.minecraft.setScreen(new SelectWorldScreen(this)));
        addRenderableWidget(first);
        addRenderableWidget(new DoomButton(colR, rowT, bw, bh, 1,
                Component.translatable("menu.apocalypse_zombies.multiplayer"),
                () -> this.minecraft.setScreen(new JoinMultiplayerScreen(this))));
        addRenderableWidget(new DoomButton(colL, rowB, bw, bh, 2,
                Component.translatable("menu.apocalypse_zombies.options"),
                () -> this.minecraft.setScreen(new OptionsScreen(this, this.minecraft.options))));
        addRenderableWidget(new DoomButton(colR, rowB, bw, bh, 3,
                Component.translatable("menu.apocalypse_zombies.quit"),
                () -> this.minecraft.stop()));
        // 打开就聚焦第一项：与参考图里 SINGLEPLAYER 的亮紫框一致（键盘操作也顺手）
        setInitialFocus(first);
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        drawCoverBackground(graphics);
        // 2×2 底板：垫在按钮后面，把格缝切过的烤死按钮文字/紫框 fringe 盖掉（只露深色缝）
        int[] cover = coverRect();
        int px0 = cover[0] + Math.round((GRID_X0 - 3) * cover[2] / (float) TEX_W);
        int px1 = cover[0] + Math.round((GRID_X1 + 3) * cover[2] / (float) TEX_W);
        int py0 = cover[1] + Math.round((GRID_Y0 - 3) * cover[3] / (float) TEX_H);
        int py1 = cover[1] + Math.round((GRID_Y1 + 3) * cover[3] / (float) TEX_H);
        graphics.fill(px0, py0, px1, py1, 0xFF1A1420);
        super.render(graphics, mouseX, mouseY, partialTick);

        // 底部信息条：只盖住图里那行版本占位文字（右下 MOJANG 标志保持可见）
        int barRight = leftBarRight();
        graphics.fill(0, this.height - 22, barRight, this.height, 0xE6000000);
        graphics.drawString(this.font, leftText(), 6, this.height - 15, LINK_COLOR, false);

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

    /** 底部左侧那行动态文字（模组名 | 版本 | 玩家名）。 */
    private String leftText() {
        String version = ModList.get().getModContainerById(ApocalypseZombies.MOD_ID)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("?");
        String player = this.minecraft.getUser().getName();
        return "Apocalypse Zombies  |  Ver " + version + "  |  " + player;
    }

    /** 左侧信息条的右缘（黑条画到这里为止）。 */
    private int leftBarRight() {
        return Math.max(
                coverRect()[0] + Math.round(BOTTOM_TEXT_RIGHT * coverRect()[2] / (float) TEX_W),
                6 + this.font.width(leftText()) + 8);
    }

    /**
     * 底部链接布局：[x, y, githubW, teamW, gap, wide]。
     * githubW 含 octocat 图标；链接一律跟在信息条右侧（不居中、不右靠，
     * 既不压左侧那行字也不压烤死的 MOJANG 标志）。宽标签放不下时退短标签。
     */
    private int[] linkLayout() {
        int x = leftBarRight() + 16;
        int gap = 20;
        int wideGw = ICON_SIZE + 3 + this.font.width(GITHUB_LABEL);
        int wideTw = this.font.width(TEAM_LABEL);
        int mojangLeft = coverRect()[0] + Math.round(BAKED_MOJANG_LEFT * coverRect()[2] / (float) TEX_W);
        boolean wide = x + wideGw + gap + wideTw <= Math.min(this.width - 4, mojangLeft - 8);
        String github = wide ? GITHUB_LABEL : GITHUB_LABEL_SHORT;
        String team = wide ? TEAM_LABEL : TEAM_LABEL_SHORT;
        int gw = wide ? wideGw : ICON_SIZE + 3 + this.font.width(github);
        int tw = this.font.width(team);
        int y = this.height - 15;
        return new int[]{x, y, gw, tw, gap, wide ? 1 : 0};
    }

    private void drawLinks(GuiGraphics graphics, int mouseX, int mouseY) {
        int[] l = linkLayout();
        String github = l[5] == 1 ? GITHUB_LABEL : GITHUB_LABEL_SHORT;
        String team = l[5] == 1 ? TEAM_LABEL : TEAM_LABEL_SHORT;
        int x = l[0];
        int y = l[1];
        int iconX = x;
        int textX = x + ICON_SIZE + 3;
        int teamX = x + l[2] + l[4];

        boolean hoverGithub = inLink(mouseX, mouseY, x, y, l[2]);
        boolean hoverTeam = inLink(mouseX, mouseY, teamX, y, l[3]);

        // octocat 图标：悬停时染紫（blit 前后换 shader 颜色，只影响这一张）
        RenderSystem.setShaderColor(1.0F, hoverGithub ? 0.72F : 1.0F, 1.0F, 1.0F);
        graphics.blit(GITHUB_ICON, iconX, y, ICON_SIZE, ICON_SIZE, 0.0F, 0.0F, 16, 16, 16, 16);
        RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);

        graphics.drawString(this.font, github, textX, y, hoverGithub ? LINK_HOVER : LINK_COLOR, true);
        if (hoverGithub) {
            graphics.fill(textX, y + 9, textX + this.font.width(github), y + 10, LINK_UNDERLINE);
        }
        graphics.drawString(this.font, team, teamX, y, hoverTeam ? LINK_HOVER : LINK_COLOR, true);
        if (hoverTeam) {
            graphics.fill(teamX, y + 9, teamX + l[3], y + 10, LINK_UNDERLINE);
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
        int mx = (int) mouseX;
        int my = (int) mouseY;
        if (inLink(mx, my, l[0], l[1], l[2])) {
            openLink(GITHUB_URL);
            return true;
        }
        int teamX = l[0] + l[2] + l[4];
        if (inLink(mx, my, teamX, l[1], l[3])) {
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
