package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.effect.DeathMarkEffect;
import net.minecraft.world.effect.MobEffect;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * 自定义状态效果。
 *
 * <p>图标不是「自己指定路径」，而是按效果的注册名去 {@code textures/mob_effect/<path>.png} 找
 * （见 {@code MobEffectTextureManager}）：所以注册名 {@code death_mark} 与
 * {@code textures/mob_effect/death_mark.png} 必须逐字一致，改名要同时改两处，
 * {@code tools/check_death_mark.py} 会把这条钉住。</p>
 */
public final class ModEffects {

    public static final DeferredRegister<MobEffect> EFFECTS =
            DeferredRegister.create(ForgeRegistries.MOB_EFFECTS, ApocalypseZombies.MOD_ID);

    /** 被远程怪打中时挂上的印记，见 {@link DeathMarkEffect}。 */
    public static final RegistryObject<MobEffect> DEATH_MARK =
            EFFECTS.register("death_mark", DeathMarkEffect::new);

    private ModEffects() {
    }

    public static void register(IEventBus modBus) {
        EFFECTS.register(modBus);
    }
}
