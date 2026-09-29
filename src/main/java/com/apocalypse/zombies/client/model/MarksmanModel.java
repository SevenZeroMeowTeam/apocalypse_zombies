package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.EliteAbility;
import com.apocalypse.zombies.entity.MarksmanSkeleton;

import net.minecraft.client.model.SkeletonModel;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

/**
 * 骸骨射手：拉满弓 → 释放穿透箭。
 *
 * <p>继承 {@link SkeletonModel} 而不是 {@code HumanoidModel}：它的泛型上界是
 * {@code T extends Mob & RangedAttackMob}，不绑死 {@code Skeleton}，所以骸骨射手能直接复用，
 * 白拿「手持弓且处于敌对状态时端弓瞄准」的 {@code prepareMobModel} 姿态和骨架的 64×32 网格。</p>
 *
 * <p>施法时在端弓姿态之上再拉满：左手拉到脸侧、右手（持弓手）推得更前更稳，
 * 命中瞬间左手弹开、头部后坐。整套动作幅度不大——它是远程单位，在 16 格外不该一眼看出要放技能。</p>
 */
public class MarksmanModel extends SkeletonModel<MarksmanSkeleton> {

    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "marksman_skeleton"), "main");

    private final CastPoseBlender blender;

    public MarksmanModel(ModelPart root) {
        super(root);
        this.blender = new CastPoseBlender(root.getChild("head"), root.getChild("body"),
                root.getChild("right_arm"), root.getChild("left_arm"),
                root.getChild("right_leg"), root.getChild("left_leg"));
    }

    /** 和原版骷髅完全同构（64×32 网格，贴图也是 64×32），只是挂在独立层上。 */
    public static LayerDefinition createBodyLayer() {
        return SkeletonModel.createBodyLayer();
    }

    @Override
    public void setupAnim(MarksmanSkeleton entity, float limbSwing, float limbSwingAmount,
                          float ageInTicks, float netHeadYaw, float headPitch) {
        super.setupAnim(entity, limbSwing, limbSwingAmount, ageInTicks, netHeadYaw, headPitch);

        EliteAbility ability = entity.getAbility();
        if (ability.isIdle()) {
            return;
        }
        this.blender.capture();

        float hold = ElitePose.hold(entity, ability, ageInTicks, entity.tickCount);
        float strike = ElitePose.strike(entity, ability, ageInTicks, entity.tickCount);
        float pulse = ElitePose.pulse(entity, ability, ageInTicks, entity.tickCount);
        float weight = CastPoseBlender.weight(hold, pulse);

        this.blender.headTilt(-0.10F * hold + 0.14F * strike);
        this.blender.body(weight, -0.06F * hold + 0.10F * strike, 0.0F);

        // -PI/2 是平举：右手（持弓）再抬高一点稳住，左手拉到 -1.35 并往内侧收，就是拉满弓
        float bowX = Mth.lerp(strike, -1.62F * hold, -1.80F);
        this.blender.arms(weight,
                bowX, -0.12F * hold, 0.0F,
                Mth.lerp(strike, -1.35F * hold, -0.92F),
                Mth.lerp(strike, -0.72F * hold, -0.18F),
                -0.12F * hold);

        this.blender.legs(weight, 0.16F * hold, -0.14F * hold);
    }
}
