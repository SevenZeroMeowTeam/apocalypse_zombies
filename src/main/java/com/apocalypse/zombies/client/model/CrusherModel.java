package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.CrusherZombie;
import com.apocalypse.zombies.entity.EliteAbility;

import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

/**
 * 碎颅者：双臂过顶蓄力 → 砸地。
 *
 * <p>前摇把双臂一路抬到头顶（{@code -2.95} 差不多是竖直向上偏后），命中瞬间在收招的前三分之一里
 * 一口气砸到身前 {@code 0.70}，同时躯干下沉、双腿蹬开，读起来是整个人往下压。</p>
 */
public class CrusherModel extends AbstractEliteZombieModel<CrusherZombie> {

    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "crusher_zombie"), "main");

    /** 砸下去的终点角度。 */
    private static final float SLAM_ARM_X = 0.70F;
    /** 躯干在砸击时的下沉量（模型单位，1 = 1 像素）。 */
    private static final float SLAM_BODY_DROP = -2.4F;

    public CrusherModel(ModelPart root) {
        super(root);
    }

    public static LayerDefinition createBodyLayer() {
        return LayerDefinition.create(HumanoidModel.createMesh(CubeDeformation.NONE, 0.0F), 64, 64);
    }

    @Override
    protected void applyCastPose(EliteAbility ability, float hold, float strike, float pulse,
                                 float ageInTicks) {
        float weight = this.castWeight(hold, pulse);

        // 抬臂只跟 hold 走；strike 一到 1 就落到位。两段用一次 lerp 串起来，不会出现回摆
        float armX = Mth.lerp(strike, -2.95F * hold, SLAM_ARM_X);

        this.headTilt(-0.22F * hold + 0.30F * strike);
        this.bodyPose(weight, -0.14F * hold + 0.40F * strike, SLAM_BODY_DROP * strike);

        this.armsPose(weight,
                armX, -0.16F * hold, 0.20F * hold,
                armX, 0.16F * hold, -0.20F * hold);

        this.legsPose(weight, 0.55F * strike, 0.55F * strike);
    }
}
