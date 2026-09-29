package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.entity.EliteAbility;
import com.apocalypse.zombies.entity.EliteMob;

import net.minecraft.client.model.ZombieModel;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.world.entity.monster.Zombie;

/**
 * 僵尸系精英模型（尖啸者 / 碎颅者 / 腐蚀者）的公共骨架。
 *
 * <p>不施法时完全走原版：父类 {@link ZombieModel} 那套僵尸手臂姿态照旧。一旦进入施法，
 * 就按 {@link ElitePose} 算出的三个量覆盖手臂 / 躯干 / 头部，具体角度由子类实现。</p>
 *
 * <p>姿态一律经 {@code *_pose} 系列方法摆（内部走 {@link CastPoseBlender} 做插值），
 * 不要直接赋值 {@code ModelPart} —— 否则施法结束会弹回原版角度。</p>
 *
 * <p>泛型用 {@code T extends Zombie & EliteMob} 交叉约束：模型侧要拿 {@link EliteMob} 的同步状态，
 * 而 {@link ZombieModel} 要求 {@code T extends Zombie}。</p>
 */
public abstract class AbstractEliteZombieModel<T extends Zombie & EliteMob> extends ZombieModel<T> {

    private final CastPoseBlender blender;

    protected AbstractEliteZombieModel(ModelPart root) {
        super(root);
        this.blender = new CastPoseBlender(root.getChild("head"), root.getChild("body"),
                root.getChild("right_arm"), root.getChild("left_arm"),
                root.getChild("right_leg"), root.getChild("left_leg"));
    }

    @Override
    public void setupAnim(T entity, float limbSwing, float limbSwingAmount, float ageInTicks,
                          float netHeadYaw, float headPitch) {
        super.setupAnim(entity, limbSwing, limbSwingAmount, ageInTicks, netHeadYaw, headPitch);

        EliteAbility ability = entity.getAbility();
        if (ability.isIdle()) {
            return;
        }
        this.blender.capture();
        this.applyCastPose(ability,
                ElitePose.hold(entity, ability, ageInTicks, entity.tickCount),
                ElitePose.strike(entity, ability, ageInTicks, entity.tickCount),
                ElitePose.pulse(entity, ability, ageInTicks, entity.tickCount),
                ageInTicks);
    }

    /**
     * 摆出施法姿态。三个量都是 0..1：
     * {@code hold} 蓄力保持量、{@code strike} 命中后那一下的完成度、{@code pulse} 命中瞬间的冲击。
     */
    protected abstract void applyCastPose(EliteAbility ability, float hold, float strike, float pulse,
                                          float ageInTicks);

    /** 姿态强度：{@code hold} 与 {@code pulse} 的合成。归零即「完全回到原版姿态」。 */
    protected final float castWeight(float hold, float pulse) {
        return CastPoseBlender.weight(hold, pulse);
    }

    protected final void headTilt(float delta) {
        this.blender.headTilt(delta);
    }

    protected final void headRoll(float roll) {
        this.blender.headRoll(roll);
    }

    protected final void bodyPose(float weight, float xRot, float yOffset) {
        this.blender.body(weight, xRot, yOffset);
    }

    protected final void armsPose(float weight,
                                  float rightX, float rightY, float rightZ,
                                  float leftX, float leftY, float leftZ) {
        this.blender.arms(weight, rightX, rightY, rightZ, leftX, leftY, leftZ);
    }

    protected final void legsPose(float weight, float rightX, float leftX) {
        this.blender.legs(weight, rightX, leftX);
    }
}
