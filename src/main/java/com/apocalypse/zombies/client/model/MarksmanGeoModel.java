package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.MarksmanSkeleton;

import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.model.GeoModel;

/**
 * 骸骨射手 —— GeckoLib 骨骼模型绑定。
 *
 * <p>几何、贴图与动画由 {@code tools/marksman_bb_gen.py} 那一系生成：27 根骨头
 * （root / move / hip / spine / chest / neck / head / jaw / 三段披风 / 箭袋 / 双臂两段链 +
 * 手 / 骨弓 / 双腿两段链 + 脚），贴图 128×128、1u = 1px（16u = 1 Block）。</p>
 *
 * <p><b>下面这组常量与设计规格 {@code art/marksman/DESIGN.md} 双向同步</b>：
 * {@code tools/check_marksman.py} 会拿几何文件回来核对脚底与颅顶，对不上就 FAIL。
 * 改模型规格必须同时改生成器、设计与这里。</p>
 *
 * <p><b>这里没有物品层</b>，是刻意的：怪的主手挂着原版弓，只是为了满足
 * {@code RangedBowAttackGoal} 的持物判定；玩家看到的弓是骨骼树里的 {@code bow}。
 * 一旦有人「顺手」加上 {@code BlockAndItemGeoLayer}，手上会多出一把原版弓穿模
 * —— 和 {@code SoldierGeoModel} 同一个坑。</p>
 *
 * <p>贴图必须走 {@code entityCutoutNoCull}：骷髅的肋骨、披风、弓弦都是靠 alpha 镂空
 * 切出来的，不透明管线会把这些洞填成实心块。模型是薄板围出的体块，剔背面还会露出内壁。</p>
 */
public class MarksmanGeoModel extends GeoModel<MarksmanSkeleton> {

    // ---------------------------------------------------------------- 坐标常量（单位 u，16u = 1 Block）

    /** 16u = 1 Block：写模型尺寸时统一除它，别在代码里散落魔法数。 */
    public static final float TEXEL = 1.0F / 16.0F;

    /** 模型总高（u）：脚底 0 → 颅顶 32，正好 2.0 格 —— 命中箱保持原版骷髅尺度不变。 */
    public static final float MODEL_HEIGHT = 32.0F;

    /** 贴图规格：128×128，1u = 1px。 */
    public static final int TEXTURE_SIZE = 128;

    // ---------------------------------------------------------------- 资源路径
    private static final ResourceLocation MODEL = resource("geo/marksman_skeleton.geo.json");
    private static final ResourceLocation TEXTURE = resource("textures/entity/marksman_skeleton.png");
    private static final ResourceLocation ANIMATION = resource("animations/marksman_skeleton.animation.json");

    private static ResourceLocation resource(String path) {
        return new ResourceLocation(ApocalypseZombies.MOD_ID, path);
    }

    @Override
    public ResourceLocation getModelResource(MarksmanSkeleton animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(MarksmanSkeleton animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(MarksmanSkeleton animatable) {
        return ANIMATION;
    }

    @Override
    public RenderType getRenderType(MarksmanSkeleton animatable, ResourceLocation texture) {
        return RenderType.entityCutoutNoCull(texture);
    }
}
