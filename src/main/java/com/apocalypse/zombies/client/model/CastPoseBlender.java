package com.apocalypse.zombies.client.model;

import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.util.Mth;

/**
 * 施法姿态混合器：把父类摆好的「常规姿态」记下来，再按权重插值到施法角度。
 *
 * <p>为什么不直接赋值：常规姿态是父类 {@code setupAnim} 摆出来的（僵尸手臂是 {@code -PI/2} 平举，
 * 还会跟着走路摆动和挥击摆动一起动），直接覆盖会让施法结束那一帧「啪」地弹回原状。
 * 权重归零时插值结果正好等于原版角度，过渡是连续的。</p>
 *
 * <p>僵尸系四个模型都能用：{@code ModelPart} 的字段名在人形网格里是固定的，
 * 所以这里收六个部件就能覆盖头 / 躯干 / 双臂 / 双腿。</p>
 */
public final class CastPoseBlender {

    private final ModelPart head;
    private final ModelPart body;
    private final ModelPart rightArm;
    private final ModelPart leftArm;
    private final ModelPart rightLeg;
    private final ModelPart leftLeg;

    private float restHeadX;
    private float restBodyX;
    private float restBodyY;
    private float restRightArmX;
    private float restRightArmY;
    private float restRightArmZ;
    private float restLeftArmX;
    private float restLeftArmY;
    private float restLeftArmZ;
    private float restRightLegX;
    private float restLeftLegX;

    public CastPoseBlender(ModelPart head, ModelPart body, ModelPart rightArm, ModelPart leftArm,
                           ModelPart rightLeg, ModelPart leftLeg) {
        this.head = head;
        this.body = body;
        this.rightArm = rightArm;
        this.leftArm = leftArm;
        this.rightLeg = rightLeg;
        this.leftLeg = leftLeg;
    }

    /** 必须在父类 {@code setupAnim} 之后、摆施法姿态之前调用。 */
    public void capture() {
        this.restHeadX = this.head.xRot;
        this.restBodyX = this.body.xRot;
        this.restBodyY = this.body.y;
        this.restRightArmX = this.rightArm.xRot;
        this.restRightArmY = this.rightArm.yRot;
        this.restRightArmZ = this.rightArm.zRot;
        this.restLeftArmX = this.leftArm.xRot;
        this.restLeftArmY = this.leftArm.yRot;
        this.restLeftArmZ = this.leftArm.zRot;
        this.restRightLegX = this.rightLeg.xRot;
        this.restLeftLegX = this.leftLeg.xRot;
    }

    /** 姿态强度：{@code hold} 与 {@code pulse} 的合成。归零即「完全回到原版姿态」。 */
    public static float weight(float hold, float pulse) {
        return Mth.clamp(hold + pulse, 0.0F, 1.0F);
    }

    /**
     * 头部在常规朝向的基础上追加仰俯。
     *
     * <p>用加法而不是替换：施法期间目标还在动，头仍要跟着 {@code netHeadYaw} / {@code headPitch}
     * 转过去看人。</p>
     */
    public void headTilt(float delta) {
        this.head.xRot = this.restHeadX + delta;
    }

    public void headRoll(float roll) {
        this.head.zRot += roll;
    }

    public void body(float poseWeight, float xRot, float yOffset) {
        this.body.xRot = Mth.lerp(poseWeight, this.restBodyX, xRot);
        this.body.y = Mth.lerp(poseWeight, this.restBodyY, yOffset);
    }

    public void arms(float poseWeight,
                     float rightX, float rightY, float rightZ,
                     float leftX, float leftY, float leftZ) {
        this.rightArm.xRot = Mth.lerp(poseWeight, this.restRightArmX, rightX);
        this.rightArm.yRot = Mth.lerp(poseWeight, this.restRightArmY, rightY);
        this.rightArm.zRot = Mth.lerp(poseWeight, this.restRightArmZ, rightZ);
        this.leftArm.xRot = Mth.lerp(poseWeight, this.restLeftArmX, leftX);
        this.leftArm.yRot = Mth.lerp(poseWeight, this.restLeftArmY, leftY);
        this.leftArm.zRot = Mth.lerp(poseWeight, this.restLeftArmZ, leftZ);
    }

    public void legs(float poseWeight, float rightX, float leftX) {
        this.rightLeg.xRot = Mth.lerp(poseWeight, this.restRightLegX, rightX);
        this.leftLeg.xRot = Mth.lerp(poseWeight, this.restLeftLegX, leftX);
    }
}
