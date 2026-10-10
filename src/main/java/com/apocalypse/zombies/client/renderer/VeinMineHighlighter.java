package com.apocalypse.zombies.client.renderer;

import java.util.List;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;

import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.event.PlayerVeinMine;

/**
 * 玩家一键挖掘的<b>客户端高亮</b>：瞄着矿石时，把「左键会一起下来」的那些方块描上边。
 *
 * <p><b>画的一定是真会砸的。</b>选块用的是服务端同一个 {@link PlayerVeinMine#preview}（同一份配置 +
 * 同一套安全判定），所以不会出现「画了框却没砸」或者相反。它是<b>纯观感</b>：不改任何判定，
 * 关掉（{@code player_mine.highlight = false}）也照样能一键挖掘。</p>
 *
 * <p><b>为什么不每帧重算：</b>瞄准的那一格没变就不重算 —— 一次 {@code preview} 要读几十个方块的
 * 状态，60 帧每秒都算没必要。缓存键 = 瞄准格 + 那一小撮会影响结果的配置（半径 / 上限 / 目标集合 /
 * 是否只认连通 / 是否要求工具），配置一改立刻重算。</p>
 *
 * <p><b>为什么不画瞄准的那一格：</b>原版已经给它画了黑框（{@code renderHitOutline}），
 * 再叠一层青色会在同一批像素上闪烁。所以只画「会连带下来的那些」。</p>
 */
public final class VeinMineHighlighter {

    private VeinMineHighlighter() {
    }

    /** 描边颜色：亮青蓝，A=0.85 —— 比原版黑框醒目，又不至于盖住方块本身的颜色。 */
    private static final float RED = 0.31F;
    private static final float GREEN = 0.76F;
    private static final float BLUE = 0.97F;
    private static final float ALPHA = 0.85F;

    /** 线框外扩一点点，免得与方块表面共面打架（z-fighting）。 */
    private static final double INFLATE = 0.002D;

    private static BlockPos cachedPos;
    private static String cachedKey = "";
    private static List<BlockPos> cached = List.of();

    /** 由 {@link com.apocalypse.zombies.client.ClientEvents} 每帧调用一次。 */
    public static void render(RenderLevelStageEvent event) {
        // 方块阶段画完、半透明还没画 —— 这时深度缓冲已经就位，描边会被地形正确遮挡。
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        LocalPlayer player = minecraft.player;
        Level level = minecraft.level;
        if (player == null || level == null || minecraft.options.hideGui) {
            return;
        }
        if (!Config.PLAYER_MINE_ENABLED.get() || !Config.PLAYER_MINE_HIGHLIGHT.get()) {
            forget();
            return;
        }
        if (!(minecraft.hitResult instanceof BlockHitResult hit) || hit.getType() != HitResult.Type.BLOCK) {
            forget();
            return;
        }
        BlockPos pos = hit.getBlockPos();
        String key = cacheKey();
        if (!pos.equals(cachedPos) || !key.equals(cachedKey)) {
            cachedPos = pos.immutable();
            cachedKey = key;
            cached = PlayerVeinMine.preview(level, pos, player.getMainHandItem());
        }
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

    /** 影响 preview 结果的那一小撮配置 —— 它们一变就重算。 */
    private static String cacheKey() {
        return Config.PLAYER_MINE_RADIUS.get() + "/" + Config.PLAYER_MINE_MAX_BLOCKS.get() + "/"
                + Config.PLAYER_MINE_TARGETS.get() + "/" + Config.PLAYER_MINE_VEIN_ONLY.get() + "/"
                + Config.PLAYER_MINE_REQUIRE_TOOL.get() + "/" + Config.PLAYER_MINE_PROTECTED.get();
    }

    private static void forget() {
        cachedPos = null;
        cachedKey = "";
        cached = List.of();
    }
}
