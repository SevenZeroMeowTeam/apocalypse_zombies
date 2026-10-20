package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.BufferUploader;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

import java.io.IOException;

/**
 * 我们自己的 HUD 图形层：一个形状 = 一个四边形，四边形交给 {@code orbit_hud} 着色器去画。
 *
 * <p>为什么这么做：Minecraft 自带的 {@code GuiGraphics.fill} 只能画死板的矩形，
 * 圆角、发光、进度弧、准星这些东西都得自己算；而每个形状单独算一遍顶点又很啰嗦。
 * 这里把「形状」整个交给片元着色器：Java 只负责摆好一个四边形，
 * 形状本身（圆角多大、描不描边、弧填了多少）编码在顶点色里，
 * 抗锯齿由着色器在四边形自己的像素空间里用 {@code fwidth} 算出来，
 * 所以无论外层怎么缩放、怎么旋转，边缘都还是干净的一个像素。</p>
 *
 * <p><b>顶点色的编码（和 {@code shaders/core/orbit_hud.fsh} 一一对应）：</b></p>
 * <pre>
 * R = RGB565 的高字节          G = RGB565 的低字节
 * B = 元素透明度 0..255        A = 0x80 | (参数 &lt;&lt; 4) | 模式
 * </pre>
 * <ul>
 *   <li>{@code A} 的 bit7 恒为 1，标记「这是一个图形四边形」（不是贴图四边形）；</li>
 *   <li>{@code A} 的 bit4-6 是「参数」，3 bit，含义随模式而变，见下面的模式表；</li>
 *   <li>{@code A} 的 bit0-3 是「模式」；</li>
 *   <li>颜色用 RGB565（16 bit）存进 R/G 两个字节，所以只有 5/6/5 的精度，够用且省带宽。</li>
 * </ul>
 *
 * <p><b>模式表：</b></p>
 * <pre>
 * 模式 0 面板   参数 bit0-1 = 圆角档位（0=2px 1=4px 2=8px 3=胶囊），bit2 = 描边
 * 模式 1 投影   参数 bit0-1 = 圆角档位，bit2 = 大模糊；四边形比面板本体大一圈
 * 模式 2 圆盘   参数 = 样式（0 实心 1 细环 2 辉光 3 粗环 4 斜面）
 * 模式 3 进度弧 参数 = 已填充档位 0..7（0 空、7 满），从正上方顺时针
 * 模式 6 准星   参数 = 锁定档位 0..7（越锁越紧）
 * 模式 7 标尺   参数 = 已画出档位 0..7（线头带一小簇火花）
 * </pre>
 *
 * <p><b>最终颜色</b> = 形状覆盖率 × 元素透明度 × {@code ColorModulator}，
 * 颜色本身再乘一遍 {@code ColorModulator}。参考实现漏掉了 {@code ScreenSize}，
 * 导致它的全屏擦除/镜像模式按 1×1 的屏幕去算；这里两个 uniform 都显式写好。</p>
 *
 * <p>用法：</p>
 * <pre>
 * OrbitHudShapes.plate(gui, 10, 10, 120, 40, 0x101820, 0.9F, OrbitHudShapes.CORNER_8, true);
 * OrbitHudShapes.arc(gui, 60, 60, 32, 0x40E0D0, 1.0F, 0.5F);
 * </pre>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitHudShapes {

    // —— 模式号（和着色器里的模式一一对应）——
    /** 面板：圆角矩形，可选描边。 */
    public static final int MODE_PLATE = 0;
    /** 投影：面板底下那团软阴影。 */
    public static final int MODE_SHADOW = 1;
    /** 圆盘：实心 / 细环 / 辉光 / 粗环 / 斜面。 */
    public static final int MODE_DISC = 2;
    /** 进度弧：一段可以只填一部分的环。 */
    public static final int MODE_ARC = 3;
    /** 准星：环 + 刻度 + 中心点。 */
    public static final int MODE_RETICLE = 6;
    /** 标尺：一条横线，画过的那一段更亮，线头带火花。 */
    public static final int MODE_RULE = 7;

    // —— 圆角档位（参数的低两位）——
    public static final int CORNER_2 = 0;
    public static final int CORNER_4 = 1;
    public static final int CORNER_8 = 2;
    public static final int CORNER_PILL = 3;

    // —— 圆盘样式（参数整体）——
    public static final int DISC_FILLED = 0;
    public static final int DISC_RING = 1;
    public static final int DISC_GLOW = 2;
    public static final int DISC_RING_THICK = 3;
    public static final int DISC_FACE = 4;

    /** 投影在面板四周留出的余量（小模糊），必须和着色器里的数值一致。 */
    public static final float SHADOW_MARGIN = 6.0F;
    /** 投影在面板四周留出的余量（大模糊）。 */
    public static final float SHADOW_MARGIN_WIDE = 14.0F;

    private static ShaderInstance shader;

    private OrbitHudShapes() {
    }

    /**
     * 注册 {@code orbit_hud} 核心着色器（Forge 的 {@code RegisterShadersEvent}，
     * 走的和 {@link com.apocalypse.zombies.client.renderer.OrbitSkyShader} 一样的路子）。
     */
    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_hud"),
                DefaultVertexFormat.POSITION_TEX_COLOR);
        event.registerShader(instance, loaded -> shader = loaded);
    }

    // ——————————————————————————————————————————————————————————
    //  对外的绘制接口
    // ——————————————————————————————————————————————————————————

    /**
     * 画一块面板（圆角矩形，可选描边）。
     *
     * @param corner 圆角档位，见 {@link #CORNER_2} 等常量
     * @param border 是否描边
     */
    public static void plate(GuiGraphics graphics, float x, float y, float width, float height,
                             int rgb, float alpha, int corner, boolean border) {
        int param = (corner & 3) | (border ? 4 : 0);
        draw(graphics, x, y, width, height, rgb, alpha, MODE_PLATE, param);
    }

    /**
     * 在一块面板底下垫一层软投影。调用时给的是**面板本体**的位置，
     * 四边形会自动往外扩一圈，模糊就在这一圈里化开。
     *
     * @param wide 是否用大模糊
     */
    public static void shadow(GuiGraphics graphics, float x, float y, float width, float height,
                              int rgb, float alpha, int corner, boolean wide) {
        float m = wide ? SHADOW_MARGIN_WIDE : SHADOW_MARGIN;
        int param = (corner & 3) | (wide ? 4 : 0);
        draw(graphics, x - m, y - m, width + 2.0F * m, height + 2.0F * m,
                rgb, alpha, MODE_SHADOW, param);
    }

    /**
     * 画一个圆盘（或者环、辉光）。
     *
     * @param style 见 {@link #DISC_FILLED} 等常量
     */
    public static void disc(GuiGraphics graphics, float x, float y, float size,
                            int rgb, float alpha, int style) {
        draw(graphics, x, y, size, size, rgb, alpha, MODE_DISC, style & 7);
    }

    /**
     * 画一段进度弧：从正上方开始顺时针，{@code fraction} 是已经画出去的比例（0..1）。
     *
     * <p>注意：比例在顶点色里只有 7 档（0..7 档映射到 0..1），所以这里会就近取整。</p>
     */
    public static void arc(GuiGraphics graphics, float x, float y, float size,
                           int rgb, float alpha, float fraction) {
        draw(graphics, x, y, size, size, rgb, alpha, MODE_ARC, level(fraction));
    }

    /**
     * 画一个准星（环 + 刻度 + 中心点）。
     *
     * @param lock 锁定程度 0..1，越大越收紧
     */
    public static void reticle(GuiGraphics graphics, float x, float y, float size,
                               int rgb, float alpha, float lock) {
        draw(graphics, x, y, size, size, rgb, alpha, MODE_RETICLE, level(lock));
    }

    /**
     * 画一条标尺：一条横线，画过的那一段更亮，线头有一小簇火花。
     *
     * @param fraction 已经画出来的比例（0..1），同样只有 7 档
     */
    public static void rule(GuiGraphics graphics, float x, float y, float width,
                            int rgb, float alpha, float fraction) {
        draw(graphics, x, y, width, 6.0F, rgb, alpha, MODE_RULE, level(fraction));
    }

    // ——————————————————————————————————————————————————————————
    //  内部实现
    // ——————————————————————————————————————————————————————————

    /** 把 0..1 的比例压成 0..7 的档位（0 和 7 分别是空和满）。 */
    private static int level(float fraction) {
        float f = Mth.clamp(fraction, 0.0F, 1.0F);
        return Mth.clamp(Math.round(f * 7.0F), 0, 7);
    }

    /** 0xRRGGBB → RGB565 的两个字节（高字节、低字节）。 */
    private static int[] rgb565(int rgb) {
        int packed = (((rgb >> 19) & 0x1F) << 11) | (((rgb >> 10) & 0x3F) << 5) | ((rgb >> 3) & 0x1F);
        return new int[]{(packed >> 8) & 0xFF, packed & 0xFF};
    }

    /**
     * 摆好一个四边形并画出去。
     *
     * <p>四边形的 UV0 写的是 {@code (宽 + 0.25, 高 + 0.25)}，四个角各差 0.5，
     * 这样着色器里 {@code floor(uv)} 永远是这块四边形自己的像素尺寸，
     * 而 {@code (uv - 尺寸 - 0.25) * 2} 正好还原出 0..1 的局部坐标，
     * 边缘那一像素也不会因为取整而「毛」掉。</p>
     */
    private static void draw(GuiGraphics graphics, float x, float y, float width, float height,
                             int rgb, float alpha, int mode, int param) {
        if (shader == null || width <= 0.0F || height <= 0.0F || alpha <= 0.0F) {
            return;
        }
        int alphaByte = Mth.clamp(Math.round(alpha * 255.0F), 0, 255);
        if (alphaByte <= 0) {
            return;
        }
        int[] packed = rgb565(rgb);
        int state = 0x80 | ((param & 7) << 4) | (mode & 0xF);

        Matrix4f pose = graphics.pose().last().pose();
        float u = width + 0.25F;
        float v = height + 0.25F;

        BufferBuilder builder = Tesselator.getInstance().getBuilder();
        builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_TEX_COLOR);
        builder.vertex(pose, x, y, 0.0F)
                .uv(u, v)
                .color(packed[0], packed[1], alphaByte, state)
                .endVertex();
        builder.vertex(pose, x, y + height, 0.0F)
                .uv(u, v + 0.5F)
                .color(packed[0], packed[1], alphaByte, state)
                .endVertex();
        builder.vertex(pose, x + width, y + height, 0.0F)
                .uv(u + 0.5F, v + 0.5F)
                .color(packed[0], packed[1], alphaByte, state)
                .endVertex();
        builder.vertex(pose, x + width, y, 0.0F)
                .uv(u + 0.5F, v)
                .color(packed[0], packed[1], alphaByte, state)
                .endVertex();

        // uniform：模型/投影矩阵跟着 Minecraft 当前的渲染状态走，
        // ColorModulator 与 ScreenSize 自己写死 —— 参考实现漏了 ScreenSize，
        // 它的全屏效果就按 1×1 的屏幕去算，这里不会。
        Minecraft minecraft = Minecraft.getInstance();
        shader.safeGetUniform("ModelViewMat").set(RenderSystem.getModelViewMatrix());
        shader.safeGetUniform("ProjMat").set(RenderSystem.getProjectionMatrix());
        shader.safeGetUniform("ColorModulator").set(1.0F, 1.0F, 1.0F, 1.0F);
        shader.safeGetUniform("ScreenSize")
                .set((float) minecraft.getWindow().getWidth(), (float) minecraft.getWindow().getHeight());

        // 自己 apply：Minecraft 的 BufferUploader.drawWithShader 会在上传前
        // 用 RenderSystem 的颜色和窗口大小覆盖掉上面两个 uniform。
        shader.apply();
        BufferUploader.draw(builder.end());
    }
}
