package com.apocalypse.zombies.client.renderer;

import java.util.List;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraftforge.client.event.RenderLevelStageEvent;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.event.PlayerTreeFell;

/**
 * 斧子一键砍伐的<b>客户端观感</b>：瞄着一棵树时，把「这一斧头下去会跟着下来」的那些方块描上边，
 * 并在准星下方报一句「这棵会砍下多少格」。
 *
 * <p><b>画的一定是真会砍的。</b>选块用的是服务端同一个 {@link PlayerTreeFell#preview}（同一份配置 +
 * 同一套安全判定），所以不会出现「画了一棵树却没砍」或者相反。它是<b>纯观感</b>：不改任何判定，
 * 关掉（{@code player_fell.highlight} / {@code player_fell.count}）也照样一键砍伐。</p>
 *
 * <p><b>笔画与 {@link VeinMineHighlighter} 同一套</b>（{@link VeinMineHighlighter#paintOutlines}），
 * 只是换了一身树皮绿的配色 —— 瞄矿石是青蓝，瞄树是绿色，一眼就知道这一下走的是哪套规则。
 * 缓存键也只含砍树自己的配置：两套观感互不干扰，各画各的。</p>
 */
public final class TreeFellHighlighter {

    private TreeFellHighlighter() {
    }

    /** 描边颜色：树皮绿（叶绿偏黄），A=0.85 —— 与连挖的青蓝区分开。 */
    private static final float RED = 0.42F;
    private static final float GREEN = 0.87F;
    private static final float BLUE = 0.35F;
    private static final float ALPHA = 0.85F;

    /** 数字的颜色（不透明），与描边同色系。 */
    private static final int COUNT_COLOR = 0xFF8BC34A;

    private static BlockPos cachedPos;
    private static String cachedKey = "";
    private static List<BlockPos> cached = List.of();

    /**
     * 方块描边，由 {@link com.apocalypse.zombies.client.ClientEvents} 每帧调用一次（级别渲染阶段）。
     */
    public static void render(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (!ensureCache(minecraft) || !Config.PLAYER_FELL_HIGHLIGHT.get()) {
            return;
        }
        if (cached.size() <= 1) {
            return;   // 只有瞄准的那一格（孤零零的原木桩）—— 原版自己画，不用我们插嘴
        }
        VeinMineHighlighter.paintOutlines(event, cached, cachedPos, RED, GREEN, BLUE, ALPHA);
    }

    /**
     * 准星下方那行「这棵会砍下 N 格」，由 {@link com.apocalypse.zombies.client.ClientEvents}
     * 每帧调用一次（HUD 阶段）。数字含你瞄的那一根。到了 {@code max_blocks} 上限就补一句
     * 「已到上限」，免得你以为是眼前这棵树的全貌。
     */
    public static void renderCount(GuiGraphics graphics, Minecraft minecraft) {
        if (!Config.PLAYER_FELL_COUNT.get()) {
            return;
        }
        if (minecraft.screen != null) {
            return;   // 开着背包 / 箱子的时候别往准星上贴字
        }
        if (!ensureCache(minecraft) || cached.size() <= 1) {
            return;
        }
        int count = cached.size();
        boolean capped = count >= Math.min(Config.PLAYER_FELL_MAX_BLOCKS.get(), 256);
        Component text = Component.translatable(
                capped ? "hud.apocalypse_zombies.fell_count_capped" : "hud.apocalypse_zombies.fell_count",
                count);
        int x = graphics.guiWidth() / 2 - minecraft.font.width(text) / 2;
        int y = graphics.guiHeight() / 2 + VeinMineHighlighter.COUNT_OFFSET_Y;
        graphics.drawString(minecraft.font, text, x, y, COUNT_COLOR, true);
    }

    /**
     * 把「瞄准格 + 配置 + 潜行 + 手上是不是斧头」对一遍缓存，需要就重算。返回 false 表示这一帧
     * 没有可用结果 —— 描边和数字都据此早退。
     */
    private static boolean ensureCache(Minecraft minecraft) {
        LocalPlayer player = minecraft.player;
        Level level = minecraft.level;
        if (player == null || level == null || minecraft.options.hideGui) {
            forget();
            return false;
        }
        if (!Config.PLAYER_FELL_ENABLED.get()) {
            forget();
            return false;
        }
        if (!(minecraft.hitResult instanceof BlockHitResult hit) || hit.getType() != HitResult.Type.BLOCK) {
            forget();
            return false;
        }
        BlockPos pos = hit.getBlockPos();
        String key = cacheKey(player.isShiftKeyDown());
        if (!pos.equals(cachedPos) || !key.equals(cachedKey)) {
            cachedPos = pos.immutable();
            cachedKey = key;
            // 潜行要一起传进去 —— 潜行时服务端只砍一格，这里也得算成一格，否则就是画谎。
            cached = PlayerTreeFell.preview(level, pos, player.getMainHandItem(), player.isShiftKeyDown());
        }
        return true;
    }

    /** 影响砍树 preview 结果的那一小撮配置 —— 它们一变就重算。潜行也在内。 */
    private static String cacheKey(boolean sneaking) {
        return Config.PLAYER_FELL_LEAVES.get() + "/" + Config.PLAYER_FELL_MAX_BLOCKS.get() + "/"
                + Config.PLAYER_FELL_SNEAK_DISABLES.get() + "/" + sneaking + "/"
                + (Minecraft.getInstance().player == null ? "" : Minecraft.getInstance().player.getMainHandItem().getItem());
    }

    private static void forget() {
        cachedPos = null;
        cachedKey = "";
        cached = List.of();
    }
}
