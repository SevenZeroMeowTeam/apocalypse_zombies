package com.apocalypse.zombies.client.renderer;

import java.util.List;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.event.PlayerVeinMine;

/**
 * 玩家一键挖掘的<b>客户端观感</b>：瞄着矿石时，把「左键会一起下来」的那些方块描上边，
 * 并在准星下方报一句「这次会连挖几格」。
 *
 * <p><b>画的一定是真会砸的。</b>选块用的是服务端同一个 {@link PlayerVeinMine#preview}（同一份配置 +
 * 同一套安全判定），所以不会出现「画了框却没砸」或者相反。它是<b>纯观感</b>：不改任何判定，
 * 关掉（{@code player_mine.highlight} / {@code player_mine.count}）也照样能一键挖掘。</p>
 *
 * <p><b>描边与数字各管各的：</b>两个开关彼此独立 —— 可以只要框、只要数字，或者都要。
 * 份数取自同一份缓存，不会出现「框画了 12 个、数字却说 11」。</p>
 *
 * <p><b>为什么不每帧重算：</b>瞄准的那一格没变就不重算 —— 一次 {@code preview} 要读几十个方块的
 * 状态，60 帧每秒都算没必要。缓存键 = 瞄准格 + 那一小撮会影响结果的配置（半径 / 上限 / 目标集合 /
 * 是否只认连通 / 是否要求工具 / 是否潜行），任何一项一变立刻重算。潜行要进键：潜行时只砸一格。</p>
 *
 * <p><b>为什么不画瞄准的那一格：</b>原版已经给它画了黑框（{@code renderHitOutline}），
 * 再叠一层青色会在同一批像素上闪烁。所以只画「会连带下来的那些」，数字则含它自己（那是这次总账）。</p>
 */
public final class VeinMineHighlighter {

    private VeinMineHighlighter() {
    }

    /** 描边颜色：亮青蓝，A=0.85 —— 比原版黑框醒目，又不至于盖住方块本身的颜色。 */
    private static final float RED = 0.31F;
    private static final float GREEN = 0.76F;
    private static final float BLUE = 0.97F;
    private static final float ALPHA = 0.85F;

    /** 数字的颜色（不透明），与描边同色系。 */
    private static final int COUNT_COLOR = 0xFF4FC2F7;

    /** 线框外扩一点点，免得与方块表面共面打架（z-fighting）。 */
    private static final double INFLATE = 0.002D;

    /** 数字画在准星下方多少像素 —— 贴着准星，又不压在它上面。 */
    private static final int COUNT_OFFSET_Y = 14;

    private static BlockPos cachedPos;
    private static String cachedKey = "";
    private static List<BlockPos> cached = List.of();

    /**
     * 方块描边，由 {@link com.apocalypse.zombies.client.ClientEvents} 每帧调用一次（级别渲染阶段）。
     *
     * <p>挂在「半透明方块画完」之后：这时深度缓冲已经就位，描边会被地形正确遮挡。</p>
     */
    public static void render(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (!ensureCache(minecraft) || !Config.PLAYER_MINE_HIGHLIGHT.get()) {
            return;
        }
        BlockPos pos = cachedPos;
        if (cached.size() <= 1) {
            return;   // 只有瞄准的那一格 —— 原版自己画，不用我们插嘴
        }

        Vec3 camera = event.getCamera().getPosition();
        PoseStack pose = event.getPoseStack();
        // 1.20.1 的 RenderLevelStageEvent 不带 MultiBufferSource（那是更晚的版本才有的），
        // 所以借用主渲染缓冲 —— 与 LevelRenderer 画原版黑框用的是同一个。
        MultiBufferSource.BufferSource buffers = minecraft.renderBuffers().bufferSource();
        VertexConsumer buffer = buffers.getBuffer(RenderType.lines());
        pose.pushPose();
        pose.translate(-camera.x, -camera.y, -camera.z);
        for (BlockPos target : cached) {
            if (target.equals(pos)) {
                continue;   // 那一格留给原版的黑框
            }
            outline(pose, buffer, target);
        }
        pose.popPose();
        buffers.endBatch(RenderType.lines());
    }

    /**
     * 准星下方那行「会连挖 N 格」，由 {@link com.apocalypse.zombies.client.ClientEvents} 每帧调用一次
     * （HUD 阶段）。数字含你瞄的那一格 —— 那是这一下左键的总账。
     *
     * <p>只显示 2 格以上：只砸一格时原版本来就是这样，没必要在准星底下常驻一行字。
     * 到了 {@code max_blocks} 上限就补一句「已到上限」，免得你以为是眼前这一簇的全部。</p>
     */
    public static void renderCount(GuiGraphics graphics, Minecraft minecraft) {
        if (!Config.PLAYER_MINE_COUNT.get()) {
            return;
        }
        if (minecraft.screen != null) {
            return;   // 开着背包 / 箱子的时候别往准星上贴字
        }
        if (!ensureCache(minecraft) || cached.size() <= 1) {
            return;
        }
        int count = cached.size();
        boolean capped = count >= Math.min(Config.PLAYER_MINE_MAX_BLOCKS.get(), 64);
        Component text = Component.translatable(
                capped ? "hud.apocalypse_zombies.vein_count_capped" : "hud.apocalypse_zombies.vein_count",
                count);
        int x = graphics.guiWidth() / 2 - minecraft.font.width(text) / 2;
        int y = graphics.guiHeight() / 2 + COUNT_OFFSET_Y;
        graphics.drawString(minecraft.font, text, x, y, COUNT_COLOR, true);
    }

    /**
     * 把「瞄准格 + 配置 + 潜行」对一遍缓存，需要就重算。返回 false 表示这一帧没有可用结果
     * （没瞄方块 / 关了总开关 / 藏了 HUD）—— 描边和数字都据此早退。
     */
    private static boolean ensureCache(Minecraft minecraft) {
        LocalPlayer player = minecraft.player;
        Level level = minecraft.level;
        if (player == null || level == null || minecraft.options.hideGui) {
            forget();
            return false;
        }
        if (!Config.PLAYER_MINE_ENABLED.get()) {
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
            // 潜行要一起传进去 —— 潜行时服务端只砸一格，这里也得算成一格，否则就是画谎。
            cached = PlayerVeinMine.preview(level, pos, player.getMainHandItem(), player.isShiftKeyDown());
        }
        return true;
    }

    /** 画一个方块（整格 1×1×1）的线框。 */
    private static void outline(PoseStack pose, VertexConsumer buffer, BlockPos pos) {
        double minX = pos.getX() - INFLATE;
        double minY = pos.getY() - INFLATE;
        double minZ = pos.getZ() - INFLATE;
        double maxX = pos.getX() + 1.0D + INFLATE;
        double maxY = pos.getY() + 1.0D + INFLATE;
        double maxZ = pos.getZ() + 1.0D + INFLATE;

        // 12 条棱，每条两个顶点；法线随便给个朝外的方向 —— RenderType.lines() 只吃位置 + 颜色。
        edge(pose, buffer, minX, minY, minZ, maxX, minY, minZ, 0.0F, -1.0F, 0.0F);
        edge(pose, buffer, maxX, minY, minZ, maxX, minY, maxZ, 1.0F, 0.0F, 0.0F);
        edge(pose, buffer, maxX, minY, maxZ, minX, minY, maxZ, 0.0F, -1.0F, 0.0F);
        edge(pose, buffer, minX, minY, maxZ, minX, minY, minZ, -1.0F, 0.0F, 0.0F);

        edge(pose, buffer, minX, maxY, minZ, maxX, maxY, minZ, 0.0F, 1.0F, 0.0F);
        edge(pose, buffer, maxX, maxY, minZ, maxX, maxY, maxZ, 1.0F, 0.0F, 0.0F);
        edge(pose, buffer, maxX, maxY, maxZ, minX, maxY, maxZ, 0.0F, 1.0F, 0.0F);
        edge(pose, buffer, minX, maxY, maxZ, minX, maxY, minZ, -1.0F, 0.0F, 0.0F);

        edge(pose, buffer, minX, minY, minZ, minX, maxY, minZ, 0.0F, 0.0F, -1.0F);
        edge(pose, buffer, maxX, minY, minZ, maxX, maxY, minZ, 0.0F, 0.0F, -1.0F);
        edge(pose, buffer, maxX, minY, maxZ, maxX, maxY, maxZ, 0.0F, 0.0F, 1.0F);
        edge(pose, buffer, minX, minY, maxZ, minX, maxY, maxZ, 0.0F, 0.0F, 1.0F);
    }

    private static void edge(PoseStack pose, VertexConsumer buffer,
                             double x1, double y1, double z1, double x2, double y2, double z2,
                             float nx, float ny, float nz) {
        vertex(pose, buffer, x1, y1, z1, nx, ny, nz);
        vertex(pose, buffer, x2, y2, z2, nx, ny, nz);
    }

    private static void vertex(PoseStack pose, VertexConsumer buffer,
                               double x, double y, double z, float nx, float ny, float nz) {
        buffer.vertex(pose.last().pose(), (float) x, (float) y, (float) z)
                .color(RED, GREEN, BLUE, ALPHA)
                .normal(pose.last().normal(), nx, ny, nz)
                .endVertex();
    }

    /** 影响 preview 结果的那一小撮配置 —— 它们一变就重算。潜行也在内（潜行时只砸一格）。 */
    private static String cacheKey(boolean sneaking) {
        return Config.PLAYER_MINE_RADIUS.get() + "/" + Config.PLAYER_MINE_MAX_BLOCKS.get() + "/"
                + Config.PLAYER_MINE_TARGETS.get() + "/" + Config.PLAYER_MINE_VEIN_ONLY.get() + "/"
                + Config.PLAYER_MINE_REQUIRE_TOOL.get() + "/" + Config.PLAYER_MINE_PROTECTED.get() + "/"
                + Config.PLAYER_MINE_SNEAK_DISABLES.get() + "/" + sneaking;
    }

    private static void forget() {
        cachedPos = null;
        cachedKey = "";
        cached = List.of();
    }
}
