package com.apocalypse.zombies.client.particle;

import com.apocalypse.zombies.registry.ModParticles;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.particle.Particle;
import net.minecraft.client.particle.ParticleEngine;
import net.minecraft.client.particle.ParticleProvider;
import net.minecraft.client.particle.ParticleRenderType;
import net.minecraft.client.particle.SpriteSet;
import net.minecraft.client.particle.TextureSheetParticle;
import net.minecraft.core.particles.SimpleParticleType;

/**
 * 轨道打击的「能量火花」。
 *
 * <p>贴图复用原版 {@code minecraft:glow}（烟花星火），全亮光照渲染（1.20.1 没有
 * 加色 sheet，发光感同原版 END_ROD：TRANSLUCENT + 0xF000F0 + 白青亮色）；
 * 不受重力（能量粒子），带一点空气摩擦，生命末期渐隐 + 收缩。</p>
 *
 * <p>颜色在「纯白」与「青蓝」之间随机 —— 和光柱 / 冲击波同色系。
 * 速度由发送方决定：锁定阶段从外圈指向中心（聚拢），落地时向外炸开。
 * {@link ModParticles#ORBITAL_SPARK} 是无参数的 {@link SimpleParticleType}，行为全靠初速度。</p>
 */
public class OrbitalSparkParticle extends TextureSheetParticle {

    OrbitalSparkParticle(ClientLevel level, double x, double y, double z,
                         double vx, double vy, double vz, SpriteSet sprites) {
        super(level, x, y, z, 0.0D, 0.0D, 0.0D);
        this.pickSprite(sprites);
        this.friction = 0.94F;
        this.gravity = 0.0F;
        this.hasPhysics = false;
        this.lifetime = 12 + this.random.nextInt(16);
        this.xd = vx;
        this.yd = vy;
        this.zd = vz;
        float mix = this.random.nextFloat();
        this.rCol = 1.0F - 0.55F * mix;
        this.gCol = 1.0F - 0.12F * mix;
        this.bCol = 1.0F;
        this.quadSize = 0.07F + this.random.nextFloat() * 0.09F;
        this.setAlpha(1.0F);
    }

    @Override
    public void tick() {
        super.tick();
        // 能量耗散：线性渐隐 + 逐 tick 收缩
        float progress = (float) this.age / (float) this.lifetime;
        this.setAlpha(1.0F - progress);
        this.quadSize *= 0.965F;
    }

    /**
     * 1.20.1 只有 OPAQUE / TRANSLUCENT 两种 sheet（没有 PARTICLE_SHEET_ADDITIVE，那是 1.20.4+ 的）。
     * 原版 END_ROD / GLOW 的「发光感」同样用 TRANSLUCENT：靠 {@code SingleQuadParticle}
     * 默认的全亮光照（0xF000F0）+ 亮色，不走 OPAQUE 的不透明混合。
     */
    @Override
    public ParticleRenderType getRenderType() {
        return ParticleRenderType.PARTICLE_SHEET_TRANSLUCENT;
    }

    /** 原版风格的注册工厂：粒子引擎把 glow 贴图的 {@link SpriteSet} 递给我们。 */
    public static final class Provider implements ParticleEngine.SpriteParticleRegistration<SimpleParticleType> {
        @Override
        public ParticleProvider<SimpleParticleType> create(SpriteSet sprites) {
            return (type, level, x, y, z, vx, vy, vz) ->
                    new OrbitalSparkParticle(level, x, y, z, vx, vy, vz, sprites);
        }
    }
}
