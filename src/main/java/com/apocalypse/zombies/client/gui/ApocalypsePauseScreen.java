package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.screens.GenericDirtMessageScreen;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.OptionsScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.ShareToLanScreen;
import net.minecraft.client.gui.screens.TitleScreen;
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
 * <b>横向工具栏</b>；3.10.1 起默认改为<b>两列网格</b>（3 行 × 2 列，底部居中），
 * 布局/短标签/间距/列数由 {@code assets/apocalypse_zombies/ui/pause_menu.xml} 描述
 * （见 {@link PauseMenuLayout}），资源包可以覆盖 XML 改顺序和文案，不用重新编译。</p>
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
        // columns = 1 时就是 3.5.0 的单行横向工具栏；默认 XML 用 2 → 3 行 × 2 列网格，底部居中。
        int columns = Math.max(1, Math.min(loaded.layout().columns(), count));
        int rows = (count + columns - 1) / columns;
        int width = Math.max(40, (this.width - 2 * margin - (columns - 1) * gap) / columns);
        int totalW = columns * width + (columns - 1) * gap;
        int totalH = rows * height + (rows - 1) * gap;
        int x0 = (this.width - totalW) / 2;
        int y0 = this.height - margin - totalH - 6;
        int lastRowCount = count - (rows - 1) * columns;

        AbstractWidget first = null;
        for (int i = 0; i < count; i++) {
            PauseMenuLayout.Spec spec = specs.get(i);
            Component text = spec.shortLabel().isEmpty()
                    ? Component.translatable(spec.label())
                    : Component.literal(spec.shortLabel());
            int column = i % columns;
            int row = i / columns;
            int x = x0 + column * (width + gap);
            int y = y0 + row * (height + gap);
            // 最后一行只剩一个（比如局域网隐藏后剩 5 个）时居中，避免孤零零贴在左列。
            if (row == rows - 1 && lastRowCount == 1) {
                x = (this.width - width) / 2;
            }
            DoomButton button = new DoomButton(x, y, width, height, i, text,
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

    /**
     * 回标题：严格照原版 {@code PauseScreen#onDisconnect} 的路径。
     *
     * <p>关键顺序：{@code level.disconnect()} → 单人 {@code clearLevel(保存中)} / 多人 {@code clearLevel()}
     * → 单人 {@link TitleScreen} / 多人 {@link JoinMultiplayerScreen}。</p>
     *
     * <p><b>4.1.3 修复</b>：旧实现只调 {@code level.disconnect() + halt(false)}，没有
     * {@code clearLevel} 也没有设置标题界面 —— 连接被关闭后客户端自动落到
     * {@code DisconnectedScreen}，就出现「连接已丢失 / 返回到服务器列表」，单人存档也像多人服。
     * 现在补上原版两步，单人会直接回标题，不会再要求点「返回到服务器列表」。</p>
     */
    private void quitToTitle() {
        if (this.minecraft.level == null) {
            return;
        }
        boolean local = this.minecraft.isLocalServer();
        this.minecraft.level.disconnect();
        if (local) {
            this.minecraft.clearLevel(new GenericDirtMessageScreen(
                    Component.translatable("menu.savingLevel")));
        } else {
            this.minecraft.clearLevel();
        }
        TitleScreen title = new TitleScreen();
        this.minecraft.setScreen(local ? title : new JoinMultiplayerScreen(title));
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
