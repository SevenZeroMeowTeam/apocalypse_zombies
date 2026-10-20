package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.EffectInstance;
import net.minecraft.client.renderer.PostPass;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import org.joml.Matrix4f;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL30;
import org.lwjgl.opengl.GL13;

/**
 * 轨道打击用的 bloom 金字塔（参考 The Shooting Star 的分层实现）。
 *
 * <p><b>做什么</b>：把一帧画面喂进一条 5 级降采样 + 4 级升采样的金字塔，
 * 最后把辉光加回画面里。链路上全部是自己的 FBO（{@link TextureTarget}），
 * 和主画面、和后处理用的 swap 目标都不共享。</p>
 *
 * <p><b>金字塔</b>：</p>
 * <pre>
 *   降采样（每级一半）：scene → D0 → D1 → D2 → D3 → D4
 *   升采样（加到下面一级）：U3 = D3 + tent(D4)
 *                          U2 = D2 + tent(U3)
 *                          U1 = D1 + tent(U2)
 *                          U0 = D0 + tent(U1)      ← 最终 bloom 纹理
 *   合成：output = scene + U0 × strength
 * </pre>
 *
 * <p><b>加法在哪</b>：在 shader 里做（和参考实现一致），不用 GL 加法混合。
 * {@code orbit_bloom_up} 的 {@code AuxSampler} 拿的是「下面一级」的纹理，
 * {@code fragColor = tent(DiffuseSampler) + AuxSampler}；
 * 最后一步合成也复用同一个 program：把 {@code Radius} 设成 0，tent 的 9 个抽样
 * 全部落在同一个点上、权重塌缩成 1.0，于是
 * {@code fragColor = 最终bloom × Strength + 场景}。</p>
 *
 * <p><b>怎么用</b>（接在现有后处理链后面）：</p>
 * <pre>{@code
 * // OrbitalPostFx.process() 里：
 * effectPass.process(time);                                   // main → swap（打击特效）
 * OrbitalBloomChain.render(swap, main, strength, threshold);   // swap + bloom → main
 * // 原来的 blitPass（swap → main）必须去掉，否则会把加了 bloom 的 main 覆盖回 swap
 * }</pre>
 * 或者反过来，让 bloom 先进 swap、打击特效再从 swap 读：
 * <pre>{@code
 * OrbitalBloomChain.render(main, swap, strength, threshold);   // main + bloom → swap
 * effectPass.process(time);                                   // swap → main（特效）
 * }</pre>
 *
 * <p><b>失败即回退</b>：任何异常（program 加载不了、FBO 建不出来、GL 报错）都会把
 * {@link #failed} 置真并永久关闭这条链；调用方拿 {@code false}，画面退回没有 bloom 的
 * 版本，绝不会把异常抛进渲染循环。GL 状态（framebuffer、viewport、混合、激活纹理单元）
 * 在返回前都会还原。</p>
 *
 * <p>只在打击演出期间被调用；没有打击时这条链完全不参与，零常态开销。</p>
 */
@OnlyIn(Dist.CLIENT)
public final class OrbitalBloomChain {

    /** 降采样级数：第 0 级是场景的 1/2 分辨率，之后每级再减半。 */
    public static final int DOWN_LEVELS = 5;
    /** 升采样次数：把第 1 级一路加回第 0 级，4 次刚好补齐 5 级金字塔。 */
    public static final int UP_PASSES = 4;

    private static final String DOWN_PROGRAM = "apocalypse_zombies:orbit_bloom_down";
    private static final String UP_PROGRAM = "apocalypse_zombies:orbit_bloom_up";
    private static final String DEPTH_PROGRAM = "apocalypse_zombies:orbit_depth_copy";

    /** GL_LINEAR：金字塔内部必须双线性采样，否则放大时全是马赛克。 */
    private static final int GL_LINEAR = 9729;

    private static final TextureTarget[] DOWN = new TextureTarget[DOWN_LEVELS];
    private static final TextureTarget[] UP = new TextureTarget[UP_PASSES];
    private static final PostPass[] DOWN_PASS = new PostPass[DOWN_LEVELS];
    private static final PostPass[] UP_PASS = new PostPass[UP_PASSES];

    private static TextureTarget depthSnapshot;
    private static PostPass depthPass;
    private static PostPass compositePass;
    private static RenderTarget compositeOutput;

    private static int sceneWidth = -1;
    private static int sceneHeight = -1;
    private static boolean failed;
    private static boolean announced;
    private static boolean sameTargetWarned;
    private static boolean depthCapture;

    private OrbitalBloomChain() {
    }

    /** 这条链现在还能用吗（没失败过）。 */
    public static boolean available() {
        return !failed;
    }

    /** 是否在每次 render 时顺手把场景深度拷进快照（默认关，开着多一次全屏 pass）。 */
    public static void setDepthCaptureEnabled(boolean enabled) {
        depthCapture = enabled;
    }

    /** 最终 bloom 纹理（金字塔第 0 级）。调用方自己的合成 shader 可以直接拿它当 sampler。 */
    public static RenderTarget bloomTarget() {
        return DOWN.length > 0 ? UP[0] : null;
    }

    /** 最终 bloom 纹理的 GL 纹理 id（0 = 还没有建起来）。 */
    public static int bloomTextureId() {
        return UP[0] == null ? 0 : UP[0].getColorTextureId();
    }

    /**
     * 跑一遍 bloom 金字塔，把结果合成进 {@code output}。
     *
     * @param scene     输入画面（会被降采样、也会作为合成时的底图）
     * @param output    合成目标：{@code output = scene + bloom × strength}
     * @param strength  bloom 强度（0 = 不加辉光）
     * @param threshold 亮部阈值（>= threshold 的像素才进金字塔）
     * @return 成功返回 true；失败/被关掉返回 false（画面保持调用方原样，不会抛异常）
     *
     * <p><b>线程</b>：必须在渲染线程调用（要建 FBO 和 GL program）。</p>
     */
    public static boolean render(RenderTarget scene, RenderTarget output, float strength, float threshold) {
        return render(scene, output, strength, threshold, null);
    }

    /**
     * 跑一遍 bloom 金字塔（带差分）。
     *
     * @param original 「特效之前」的那张画面。给了的话，首级降采样会拿它做差分：
     *                只有打击特效**新加上去的光**会发光，原版天空/雪地不会整片糊掉
     *                （这是参考包 bloom_down.fsh 的 Prefilter 分支做的事）。
     *                传 null 就退化成普通阈值提取。
     */
    public static boolean render(RenderTarget scene, RenderTarget output, float strength,
                                 float threshold, RenderTarget original) {
        if (failed) {
            return false;
        }
        if (scene == null || output == null) {
            return false;
        }
        if (scene == output) {
            if (!sameTargetWarned) {
                sameTargetWarned = true;
                ApocalypseZombies.LOGGER.warn("[天陨] bloom 金字塔：scene 与 output 不能是同一个目标（会形成读写反馈），已跳过。");
            }
            return false;
        }
        try {
            Minecraft minecraft = Minecraft.getInstance();
            if (!ensure(minecraft, scene)) {
                return false;
            }
            if (depthCapture) {
                copyDepth(scene);
            }
            float time = time(minecraft);
            // 调用方可能留了别的 GL 错误，先排干净，后面只看我们自己造成的
            while (GL11.glGetError() != 0) {
                // drain
            }

            // —— 1) 降采样：5 级，每级一半；首级先做亮部提取 ——
            //     差分提取：首级拿「特效之前」的画面相减，只让特效新加的光发光
            //     （参考包 bloom_down.fsh 的 Prefilter 分支）；没给 original 就退回阈值提取。
            //     AuxSampler 每帧现绑（不写死在 PostPass 的 aux 资源里），
            //     这样调用方换一张「特效前的画面」也不用重建整条链。
            RenderTarget input = scene;
            for (int i = 0; i < DOWN_LEVELS; i++) {
                EffectInstance effect = DOWN_PASS[i].getEffect();
                effect.safeGetUniform("Threshold").set(threshold);
                effect.safeGetUniform("Prefilter").set(i == 0 ? 1.0F : 0.0F);
                boolean diff = i == 0 && original != null && original != scene;
                effect.safeGetUniform("DiffPrefilter").set(diff ? 1.0F : 0.0F);
                final RenderTarget aux = diff ? original : input;
                effect.setSampler("AuxSampler", aux::getColorTextureId);
                DOWN_PASS[i].process(time);
                input = DOWN[i];
            }

            // —— 2) 升采样：4 次，每次把更小的一级 tent 滤波后加到下面一级上 ——
            for (int i = UP_PASSES - 1; i >= 0; i--) {
                EffectInstance effect = UP_PASS[i].getEffect();
                effect.safeGetUniform("Radius").set(1.0F);
                effect.safeGetUniform("Strength").set(1.0F);
                UP_PASS[i].process(time);
            }

            // —— 3) 合成：output = scene + bloom × strength ——
            PostPass composite = composite(minecraft, output);
            EffectInstance effect = composite.getEffect();
            effect.safeGetUniform("Radius").set(0.0F);
            effect.safeGetUniform("Strength").set(strength);
            effect.setSampler("AuxSampler", scene::getColorTextureId);
            composite.process(time);

            // —— 状态还原：PostPass 结束时 FBO 已经被解绑、viewport 停在输出尺寸，
            //    这里把混合、激活纹理单元再摆正，别影响后面的 GUI 绘制 ——
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
            RenderSystem.activeTexture(GL13.GL_TEXTURE0);
            output.bindWrite(false);
            RenderSystem.viewport(0, 0, output.width, output.height);

            int error = GL11.glGetError();
            if (error != 0) {
                fail(null);
                ApocalypseZombies.LOGGER.warn("[天陨] bloom 金字塔 GL 错误 0x{}，已关闭 bloom。",
                        Integer.toHexString(error));
                return false;
            }
            return true;
        } catch (Throwable error) {
            fail(error);
            return false;
        }
    }

    /**
     * 把场景深度拷进自己的深度快照（用采样而不是 framebuffer blit，理由见
     * {@code orbit_depth_copy.fsh} 的注释）。失败返回 false，不抛异常。
     */
    public static boolean copyDepth(RenderTarget scene) {
        if (failed || scene == null) {
            return false;
        }
        try {
            Minecraft minecraft = Minecraft.getInstance();
            if (!ensure(minecraft, scene)) {
                return false;
            }
            if (depthSnapshot == null || depthSnapshot.width != scene.width || depthSnapshot.height != scene.height) {
                if (depthPass != null) {
                    depthPass.close();
                    depthPass = null;
                }
                if (depthSnapshot != null) {
                    depthSnapshot.destroyBuffers();
                    depthSnapshot = null;
                }
                depthSnapshot = new TextureTarget(scene.width, scene.height, true, Minecraft.ON_OSX);
                depthPass = new PostPass(minecraft.getResourceManager(), DEPTH_PROGRAM, scene, depthSnapshot);
                depthPass.setOrthoMatrix(ortho(depthSnapshot));
            }
            depthPass.getEffect().setSampler("DepthSampler", scene::getDepthTextureId);
            // gl_FragDepth 只有在深度测试开着的时候才会真的写进深度缓冲
            RenderSystem.enableDepthTest();
            RenderSystem.depthMask(true);
            depthPass.process(time(minecraft));
            RenderSystem.disableDepthTest();
            return true;
        } catch (Throwable error) {
            fail(error);
            return false;
        }
    }

    /** 深度快照（可能是 null）。 */
    public static RenderTarget depthSnapshot() {
        return depthSnapshot;
    }

    /** 立刻释放所有 FBO 和 program（不再需要 bloom 时调用）。 */
    public static void destroyBuffers() {
        release();
    }

    // ————————————————————————————————————————————————————————————
    //  内部
    // ————————————————————————————————————————————————————————————

    /**
     * 按场景尺寸重建金字塔。尺寸没变就直接复用（每帧重建 FBO 会漏显存）。
     */
    private static boolean ensure(Minecraft minecraft, RenderTarget scene) {
        if (DOWN[0] != null && sceneWidth == scene.width && sceneHeight == scene.height) {
            return true;
        }
        release();
        try {
            ResourceManager resources = minecraft.getResourceManager();
            int width = Math.max(1, (scene.width + 1) >> 1);
            int height = Math.max(1, (scene.height + 1) >> 1);
            for (int i = 0; i < DOWN_LEVELS; i++) {
                TextureTarget target = new TextureTarget(width, height, false, Minecraft.ON_OSX);
                target.setFilterMode(GL_LINEAR);
                DOWN[i] = target;
                width = Math.max(1, (width + 1) >> 1);
                height = Math.max(1, (height + 1) >> 1);
            }
            for (int i = 0; i < UP_PASSES; i++) {
                TextureTarget target = new TextureTarget(DOWN[i].width, DOWN[i].height, false, Minecraft.ON_OSX);
                target.setFilterMode(GL_LINEAR);
                UP[i] = target;
            }
            // 降采样 pass：scene → D0 → D1 → ...
            for (int i = 0; i < DOWN_LEVELS; i++) {
                RenderTarget input = (i == 0) ? scene : DOWN[i - 1];
                PostPass pass = new PostPass(resources, DOWN_PROGRAM, input, DOWN[i]);
                // AuxSampler 不写进 aux 资源：它每帧在 render() 里现绑（可能是「特效前」的画面）
                pass.setOrthoMatrix(ortho(DOWN[i]));
                DOWN_PASS[i] = pass;
            }
            // 升采样 pass：U[i] = D[i] + tent(更小的一级)
            for (int i = 0; i < UP_PASSES; i++) {
                RenderTarget input = (i == UP_PASSES - 1) ? DOWN[DOWN_LEVELS - 1] : UP[i + 1];
                PostPass pass = new PostPass(resources, UP_PROGRAM, input, UP[i]);
                pass.addAuxAsset("AuxSampler", DOWN[i]::getColorTextureId, DOWN[i].width, DOWN[i].height);
                pass.setOrthoMatrix(ortho(UP[i]));
                UP_PASS[i] = pass;
            }
            sceneWidth = scene.width;
            sceneHeight = scene.height;
            // 合成 pass 的输入是 U[0]，U[0] 刚被重建，旧的合成 pass 得扔掉
            compositePass = null;
            compositeOutput = null;
            if (!announced) {
                announced = true;
                ApocalypseZombies.LOGGER.info("[天陨] bloom 金字塔已启用（{} 级降采样 / {} 级升采样，{}x{}）",
                        DOWN_LEVELS, UP_PASSES, scene.width, scene.height);
            }
            return true;
        } catch (Throwable error) {
            fail(error);
            return false;
        }
    }

    /**
     * 合成 pass：输入是最终 bloom（U0），输出是调用方给的目标。
     * 输出目标会变，所以按目标缓存，换目标就重建。
     */
    private static PostPass composite(Minecraft minecraft, RenderTarget output) throws java.io.IOException {
        if (compositePass != null
                && compositeOutput == output
                && compositePass.outTarget.width == output.width
                && compositePass.outTarget.height == output.height) {
            return compositePass;
        }
        if (compositePass != null) {
            compositePass.close();
            compositePass = null;
        }
        compositeOutput = output;
        compositePass = new PostPass(minecraft.getResourceManager(), UP_PROGRAM, UP[0], output);
        compositePass.setOrthoMatrix(ortho(output));
        return compositePass;
    }

    /** 全屏 pass 的正交矩阵：范围就是输出目标的像素尺寸。 */
    private static Matrix4f ortho(RenderTarget target) {
        return new Matrix4f().setOrtho(0.0F, target.width, 0.0F, target.height, 0.1F, 1000.0F);
    }

    private static float time(Minecraft minecraft) {
        if (minecraft.level == null) {
            return 0.0F;
        }
        return (minecraft.level.getGameTime() % 24000L) / 20.0F;
    }

    /** 释放所有资源。关掉链的时候必须调用，否则 FBO 和 program 会一直挂着。 */
    private static void release() {
        if (compositePass != null) {
            compositePass.close();
            compositePass = null;
        }
        compositeOutput = null;
        if (depthPass != null) {
            depthPass.close();
            depthPass = null;
        }
        if (depthSnapshot != null) {
            depthSnapshot.destroyBuffers();
            depthSnapshot = null;
        }
        for (int i = 0; i < DOWN_PASS.length; i++) {
            if (DOWN_PASS[i] != null) {
                DOWN_PASS[i].close();
                DOWN_PASS[i] = null;
            }
        }
        for (int i = 0; i < UP_PASS.length; i++) {
            if (UP_PASS[i] != null) {
                UP_PASS[i].close();
                UP_PASS[i] = null;
            }
        }
        for (int i = 0; i < DOWN.length; i++) {
            if (DOWN[i] != null) {
                DOWN[i].destroyBuffers();
                DOWN[i] = null;
            }
        }
        for (int i = 0; i < UP.length; i++) {
            if (UP[i] != null) {
                UP[i].destroyBuffers();
                UP[i] = null;
            }
        }
        sceneWidth = -1;
        sceneHeight = -1;
    }

    /** 失败即永久关闭：只记一次日志，之后所有调用都是空操作。 */
    private static void fail(Throwable error) {
        if (!failed) {
            failed = true;
            if (error != null) {
                ApocalypseZombies.LOGGER.warn("[天陨] bloom 金字塔失败，已永久关闭（后续调用直接跳过）。", error);
            } else {
                ApocalypseZombies.LOGGER.warn("[天陨] bloom 金字塔失败，已永久关闭（后续调用直接跳过）。");
            }
        }
        release();
    }
}
