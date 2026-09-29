package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.EliteAbility;
import com.apocalypse.zombies.entity.ScreamerZombie;

import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.resources.ResourceLocation;

/**
 * 尖啸者：仰头长啸。
 *
 * <p>前摇把上身往后掰、双臂张开上抬，命中那一下全身往外甩一记，收招慢慢落回原版姿态。
 * 蓄力期间给头部加了高频抖，读起来是「绷住了」而不是纯粹静止。</p>
 */
public class ScreamerModel extends AbstractEliteZombieModel<ScreamerZombie> {

    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "screamer_zombie"), "main");

    public ScreamerModel(ModelPart root) {
        super(root);
    }

    /**
     * 和原版僵尸完全同构的人形网格（{@code ModelLayers.ZOMBIE} 就是这个定义，64×64）。
     *
     * <p>必须挂在独立层上：共用 {@code ModelLayers.ZOMBIE} 会让四个模型拿到同一个
     * {@code ModelPart} 实例，摆姿势时互相打架。</p>
     */
    public static LayerDefinition createBodyLayer() {
        return LayerDefinition.create(HumanoidModel.createMesh(CubeDeformation.NONE, 0.0F), 64, 64);
    }

    @Override
    protected void applyCastPose(EliteAbility ability, float hold, float strike, float pulse,
                                 float ageInTicks) {
        float weight = this.castWeight(hold, pulse);

        this.headTilt(-0.55F * hold - 0.32F * pulse);
        this.headRoll(ElitePose.tremble(ageInTicks, 1.3F, 0.04F) * hold);
        this.bodyPose(weight, -0.18F * hold - 0.12F * pulse, 0.0F);

        // xRot 负 = 往前上方甩（原版僵尸手臂 -PI/2 就是平举），-2.3 差不多是举过头顶
        this.armsPose(weight,
                -2.30F * hold + 0.30F * pulse,
                -0.18F * hold - 0.55F * pulse,
                0.28F * hold + 0.50F * pulse,
                -2.30F * hold + 0.30F * pulse,
                0.18F * hold + 0.55F * pulse,
                -0.28F * hold - 0.50F * pulse);

        this.legsPose(weight, 0.14F * hold, -0.10F * hold);
    }
}
