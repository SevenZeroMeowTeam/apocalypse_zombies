package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.core.particles.ParticleType;
import net.minecraft.core.particles.SimpleParticleType;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * 自定义粒子类型。
 *
 * <p>轨道打击的「能量火花」：锁定阶段向目标聚拢、落地时四散炸开的青白色发光小点。
 * 贴图复用原版 {@code minecraft:glow}（烟花星火的辉光点），不需要新增美术资产；
 * 渲染走 {@code PARTICLE_SHEET_ADDITIVE}（加色混合），叠在一起会真的发亮。</p>
 */
public final class ModParticles {

    public static final DeferredRegister<ParticleType<?>> PARTICLES =
            DeferredRegister.create(ForgeRegistries.PARTICLE_TYPES, ApocalypseZombies.MOD_ID);

    /** 能量火花。速度由发送方决定：锁定阶段给负速度（向内聚），落地给正速度（向外炸）。 */
    public static final RegistryObject<SimpleParticleType> ORBITAL_SPARK =
            PARTICLES.register("orbital_spark", () -> new SimpleParticleType(false));

    private ModParticles() {
    }

    public static void register(IEventBus modBus) {
        PARTICLES.register(modBus);
    }
}
