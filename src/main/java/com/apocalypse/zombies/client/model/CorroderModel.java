package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.CorroderZombie;
import com.apocalypse.zombies.entity.EliteAbility;

import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

/**
 * 腐蚀者：后仰蓄酸 → 喷出。
 *
 * <p>右手抬到嘴边聚酸、左手在旁边撑住，头部后仰；命中瞬间右手往前推出去、头跟着一甩。
 * 因为它是远程单位，整套姿态幅度比碎颅者小，免得在 8 格外就能一眼看出要放技能。</p>
 */
public class CorroderModel extends AbstractEliteZombieModel<CorroderZombie> {

    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "corroder_zombie"), "main");

    public CorroderModel(ModelPart root) {
        super(root);
    }

    public static LayerDefinition createBodyLayer() {
        return LayerDefinition.create(HumanoidModel.createMesh(CubeDeformation.NONE, 0.0F), 64, 64);
    }

    @Override
    protected void applyCastPose(EliteAbility ability, float hold, float strike, float pulse,
                                 float ageInTicks) {
        float weight = this.castWeight(hold, pulse);

        this.headTilt(-0.45F * hold + 0.55F * strike);
        this.bodyPose(weight, -0.12F * hold + 0.16F * strike, 0.0F);

        // 右手：抬到嘴边（-1.95 高位内收）→ 命中时推到身前（-0.95 略低、略外）
        float rightX = Mth.lerp(strike, -1.95F * hold, -0.95F);
        float rightY = Mth.lerp(strike, 0.45F * hold, -0.10F);
        float rightZ = Mth.lerp(strike, 0.35F * hold, 0.05F);

        this.armsPose(weight,
                rightX, rightY, rightZ,
                -0.55F * hold + 0.15F * strike, 0.25F * hold, -0.10F * hold);

        this.legsPose(weight, 0.10F * hold, -0.06F * hold);
    }
}
