package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.advancements.AdvancementsScreen;
import net.minecraft.client.gui.screens.OptionsScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.ShareToLanScreen;
import net.minecraft.client.gui.screens.achievement.StatsScreen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;

/**
 * 末日风的暂停界面（替换原版 {@code PauseScreen}）。
 *
 * <p>按用户要求「只保留背景图，不要原版文字」：背景换成专门的末日废土插画
 * （{@code gui/pause_background.png}，与标题图分开：这张图上没有任何烤死的按钮/标题），
 * <b>不画 "Game Menu" 标题</b>，只保留一列末日石质按钮（{@link DoomButton}）：
 * 回到游戏 / 进度 / 统计 / 选项 / 对局域网开放（条件出现）/ 保存并退出。</p>
 *
 * <p>行为与原版暂停一致：{@link #isPauseScreen()} 返回 true（单人游戏暂停），
 * ESC 关闭即回到游戏；退出按钮走原版的「先断开世界再回标题」路径。</p>
 */
public final class ApocalypsePauseScreen extends Screen {

    private static final ResourceLocation BACKGROUND = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/gui/pause_background.png");
    private static final int TEX_W = 1408;
    private static final int TEX_H = 768;

    public ApocalypsePauseScreen() {
        super(Component.empty());
    }

    @Override
    protected void init() {
        int bw = Math.min(260, Math.max(190, this.width / 4));
        int bh = 24;
        int gap = 8;
        boolean lan = this.minecraft != null && this.minecraft.hasSingleplayerServer()
                && !this.minecraft.getSingleplayerServer().isPublished();
        int rows = lan ? 6 : 5;
        int total = rows * bh + (rows - 1) * gap;
        int x = (this.width - bw) / 2;
        int y = (this.height - total) / 2 + 14;
        int seed = 0;

        addRenderableWidget(new DoomButton(x, y, bw, bh, seed++,
                Component.translatable("menu.returnToGame"),
                () -> this.minecraft.setScreen(null)));
        addRenderableWidget(new DoomButton(x, y + (bh + gap), bw, bh, seed++,
                Component.translatable("gui.advancements"),
                () -> this.minecraft.setScreen(new AdvancementsScreen(this.minecraft.getConnection().getAdvancements()))));
        addRenderableWidget(new DoomButton(x, y + 2 * (bh + gap), bw, bh, seed++,
                Component.translatable("gui.stats"),
                () -> this.minecraft.setScreen(new StatsScreen(this, this.minecraft.player.getStats()))));
        addRenderableWidget(new DoomButton(x, y + 3 * (bh + gap), bw, bh, seed++,
                Component.translatable("options"),
                () -> this.minecraft.setScreen(new OptionsScreen(this, this.minecraft.options))));
        if (lan) {
            addRenderableWidget(new DoomButton(x, y + 4 * (bh + gap), bw, bh, seed++,
                    Component.translatable("menu.shareToLan"),
                    () -> this.minecraft.setScreen(new ShareToLanScreen(this))));
        }
        addRenderableWidget(new DoomButton(x, y + (rows - 1) * (bh + gap), bw, bh, seed,
                Component.translatable("menu.returnToMenu"),
                this::quitToTitle));
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        // cover 铺满 + 全屏压暗：暂停时底下的世界要透不出来，按钮也要在插画上读得清。
        // 暗化比早期版本轻两档（0x80），新插画本身的末日天空和废墟能完整看见。
        float scale = Math.max(this.width / (float) TEX_W, this.height / (float) TEX_H);
        int w = Math.round(TEX_W * scale);
        int h = Math.round(TEX_H * scale);
        graphics.blit(BACKGROUND, (this.width - w) / 2, (this.height - h) / 2, w, h,
                0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
        graphics.fill(0, 0, this.width, this.height, 0x80000000);
        graphics.fill(0, 0, this.width, this.height, 0x2A1A0A28);
        // 注意：不画标题 —— 按需求「只要背景图与按钮」
        super.render(graphics, mouseX, mouseY, partialTick);
    }

    /** 回标题：单人先停集成服务器（原版同一路径），多人直接断开连接。 */
    private void quitToTitle() {
        boolean local = this.minecraft.hasSingleplayerServer();
        if (this.minecraft.level != null) {
            this.minecraft.level.disconnect();
        }
        if (local) {
            this.minecraft.getSingleplayerServer().halt(false);
        } else if (this.minecraft.getConnection() != null) {
            this.minecraft.getConnection().getConnection()
                    .disconnect(Component.translatable("menu.disconnect"));
        }
    }

    @Override
    public boolean isPauseScreen() {
        return true;
    }

    @Override
    public boolean shouldCloseOnEsc() {
        return true;
    }

    @Override
    public void onClose() {
        this.minecraft.setScreen(null);
    }
}
