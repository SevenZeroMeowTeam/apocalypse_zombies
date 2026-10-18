package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.screens.OptionsScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.ShareToLanScreen;
import net.minecraft.client.gui.screens.achievement.StatsScreen;
import net.minecraft.client.gui.screens.advancements.AdvancementsScreen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;

import java.util.ArrayList;
import java.util.List;

/**
 * 末日风的暂停界面（替换原版 {@code PauseScreen}）。
 *
 * <p>按用户要求「只保留背景图，不要原版文字」：背景铺专门的末日废土插画
 * （{@code gui/pause_background.png}），<b>不画 "Game Menu" 标题</b>。3.5.0 起菜单改为
 * <b>横向工具栏</b>：按钮排成一行停在屏幕底部，布局/短标签/间距由
 * {@code assets/apocalypse_zombies/ui/pause_menu.xml} 描述（见 {@link PauseMenuLayout}），
 * 资源包可以覆盖 XML 改顺序和文案，不用重新编译。</p>
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
        PauseMenuLayout.Loaded loaded = PauseMenuLayout.load();
        boolean lan = this.minecraft != null && this.minecraft.hasSingleplayerServer()
                && !this.minecraft.getSingleplayerServer().isPublished();

        List<PauseMenuLayout.Spec> specs = new ArrayList<>();
        for (PauseMenuLayout.Spec spec : loaded.buttons()) {
            if ("lan".equals(spec.condition()) && !lan) {
                continue;
            }
            specs.add(spec);
        }
        if (specs.isEmpty()) {
            // XML 被资源包改成空文件时的最后兜底：至少留一个「回到游戏」。
            specs.add(new PauseMenuLayout.Spec("resume", "menu.returnToGame", "回到游戏", ""));
        }

        int count = specs.size();
        int height = loaded.layout().buttonHeight();
        int gap = loaded.layout().gap();
        int margin = loaded.layout().margin();
        int width = Math.max(40, (this.width - 2 * margin - (count - 1) * gap) / count);
        int total = count * width + (count - 1) * gap;
        int x = (this.width - total) / 2;
        int y = this.height - margin - height - 6;

        AbstractWidget first = null;
        for (int i = 0; i < count; i++) {
            PauseMenuLayout.Spec spec = specs.get(i);
            Component text = spec.shortLabel().isEmpty()
                    ? Component.translatable(spec.label())
                    : Component.literal(spec.shortLabel());
            DoomButton button = new DoomButton(x + i * (width + gap), y, width, height, i, text,
                    () -> runAction(spec.action()));
            if (!spec.label().isEmpty()) {
                button.setTooltip(Tooltip.create(Component.translatable(spec.label())));
            }
            addRenderableWidget(button);
            if (first == null) {
                first = button;
            }
        }
        if (first != null) {
            setInitialFocus(first);
        }
    }

    /** XML 里的 action 在这里分发；未知 action 静默忽略，不会把界面弄崩。 */
    private void runAction(String action) {
        switch (action) {
            case "resume" -> this.minecraft.setScreen(null);
            case "advancements" -> this.minecraft.setScreen(
                    new AdvancementsScreen(this.minecraft.getConnection().getAdvancements()));
            case "stats" -> this.minecraft.setScreen(
                    new StatsScreen(this, this.minecraft.player.getStats()));
            case "options" -> this.minecraft.setScreen(
                    new OptionsScreen(this, this.minecraft.options));
            case "lan" -> this.minecraft.setScreen(new ShareToLanScreen(this));
            case "quit" -> quitToTitle();
            default -> {
            }
        }
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        // cover 铺满 + 全屏压暗：暂停时底下的世界要透不出来，按钮也要在插画上读得清。
        float scale = Math.max(this.width / (float) TEX_W, this.height / (float) TEX_H);
        int w = Math.round(TEX_W * scale);
        int h = Math.round(TEX_H * scale);
        graphics.blit(BACKGROUND, (this.width - w) / 2, (this.height - h) / 2, w, h,
                0.0F, 0.0F, TEX_W, TEX_H, TEX_W, TEX_H);
        graphics.fill(0, 0, this.width, this.height, 0x80000000);
        graphics.fill(0, 0, this.width, this.height, 0x2A1A0A28);
        // 不画标题 —— 按需求「只要背景图与横向按钮」。
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
