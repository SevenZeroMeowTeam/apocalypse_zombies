package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.util.GeckoLibUtil;

/**
 * 轨道设施展示实体（v4.1.0 第一弹）：纯视觉，把方块搭的卫星换成 GeckoLib 模型。
 *
 * <p><b>刻意不继承 Mob</b>：没有 AI、没有目标选择、不会被推、不会摔 ——
 * {@link #isPushable()} 关掉碰撞响应，玩家从它中间穿过去都行；它是“场景道具”，
 * 不是“生物”。唯一的行为是每 tick 把速度清零、贴回出生点（防止爆炸冲量带跑）。</p>
 *
 * <p>持久化靠 NBT 里的 {@code home}：服务端重建平台时如果家里已有实体就不重复生成，
 * 这样 {@code OrbitFacilities.ensure} 天然去重。</p>
 *
 * <p>贴图里的青色/橙色块用「自发光」样式画进图集；GeckoLib 实体无动画骨骼，用一个
 * 永远 STOP 的空控制器即可（模型静态，但相机移动/世界光照仍在变化）。</p>
 */
public class OrbitSatellite extends Entity implements GeoEntity {

    private static final EntityDataAccessor<String> MODE =
            SynchedEntityData.defineId(OrbitSatellite.class, EntityDataSerializers.STRING);

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    // 出生点（用于贴回与去重）
    private double homeX;
    private double homeY;
    private double homeZ;
    private boolean homeSet;

    public OrbitSatellite(EntityType<?> type, Level level) {
        super(type, level);
        this.noPhysics = true;
        this.setInvulnerable(true);
        this.setNoGravity(true);
    }

    /** 服务端生成时调用：设置模式（决定贴图/模型参数）并记录出生点。 */
    public void setup(OrbitalStrikeMode mode, double x, double y, double z) {
        this.entityData.set(MODE, mode.id());
        this.setPos(x, y, z);
        this.homeX = x;
        this.homeY = y;
        this.homeZ = z;
        this.homeSet = true;
    }

    public OrbitalStrikeMode mode() {
        return OrbitalStrikeMode.byId(this.entityData.get(MODE));
    }

    @Override
    protected void defineSynchedData() {
        this.entityData.define(MODE, OrbitalStrikeMode.LASER.id());
    }

    @Override
    public void tick() {
        super.tick();
        // 场景道具：任何外部冲量都当没发生过，每 tick 贴回出生点
        this.setDeltaMovement(0, 0, 0);
        if (homeSet) {
            this.setPos(homeX, homeY, homeZ);
        }
    }

    @Override
    public boolean isPushable() {
        return false;
    }

    @Override
    public boolean isInvulnerableTo(net.minecraft.world.damagesource.DamageSource source) {
        return true;
    }

    @Override
    public boolean shouldBeSaved() {
        return true;
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag) {
        tag.putBoolean("homeSet", homeSet);
        tag.putDouble("homeX", homeX);
        tag.putDouble("homeY", homeY);
        tag.putDouble("homeZ", homeZ);
        tag.putString("mode", entityData.get(MODE));
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag) {
        homeSet = tag.getBoolean("homeSet");
        homeX = tag.getDouble("homeX");
        homeY = tag.getDouble("homeY");
        homeZ = tag.getDouble("homeZ");
        entityData.set(MODE, tag.getString("mode"));
    }

    // ------------------------------------------------------------------ GeoEntity

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return geoCache;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        // 静态展示：一个永远不播任何动画的控制器即可
        controllers.add(new AnimationController<>(this, "idle", 0, state -> state.setAndContinue(
                software.bernie.geckolib.core.animation.RawAnimation.begin())));
    }

    @OnlyIn(Dist.CLIENT)
    public static boolean isNearbyOrbitSatellite(net.minecraft.client.Minecraft mc) {
        // 保留：渲染器隐藏方块卫星时用（见 OrbitFacilities.laser 的 client 分支）
        return false;
    }
}
