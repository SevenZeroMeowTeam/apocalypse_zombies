package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * Sound events for the weapon layer.
 *
 * <p>The recordings are TaCZ's own AWM set, shipped verbatim (CC BY-NC-ND 4.0) — the 22 files in
 * {@code assets/apocalypse_zombies/sounds/awm/} are byte-identical to the originals, and the attribution
 * lives in {@code art/awm/README.md}. Nothing here is mixed or re-encoded; if that licence ever stops
 * fitting the project, replacing the .ogg files is the whole job, since every id below is also the
 * sounds.json key.</p>
 *
 * <p>Timing of the mechanical sounds is TaCZ's too, but it is not written here: it lives as
 * {@code sound_effects} keyframes in {@code animations/awm.animation.json}, and
 * {@code tools/check_awm_anim.py} keeps the tables in {@code AWMItem} honest against it.</p>
 */
public final class ModSounds {

    public static final DeferredRegister<SoundEvent> SOUNDS =
            DeferredRegister.create(ForgeRegistries.SOUND_EVENTS, ApocalypseZombies.MOD_ID);

    /** The shot, split the way TaCZ splits it: a close mix for the shooter, a distant one for everyone else. */
    public static final RegistryObject<SoundEvent> AWM_SHOOT = sound("awm_shoot");
    public static final RegistryObject<SoundEvent> AWM_SHOOT_3P = sound("awm_shoot_3p");

    /** Bolt cycle — the 打一发拉一下栓 sequence. */
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_OUT = sound("awm_rechamber_out");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_EJECT = sound("awm_rechamber_ejectclick");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_IN = sound("awm_rechamber_in");
    public static final RegistryObject<SoundEvent> AWM_RECHAMBER_END = sound("awm_rechamber_end");

    /** Magazine swap with a round still chambered — no bolt, so no rechamber sounds. */
    public static final RegistryObject<SoundEvent> AWM_RELOAD_RAISE = sound("awm_reload_raise");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_RATTLE = sound("awm_reload_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EJECT = sound("awm_reload_ejectclick");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGOUT = sound("awm_reload_magout");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_FAST_RATTLE = sound("awm_reload_fast_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGHIT = sound("awm_reload_maghit");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_MAGIN = sound("awm_reload_magin");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_END = sound("awm_reload_end");

    /** Empty-magazine reload — the long one, with the bolt cycle on the end. */
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_RAISE = sound("awm_reload_empty_raise");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGOUT = sound("awm_reload_empty_magout");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAG_DROP = sound("awm_reload_empty_mag_drop");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_RATTLE = sound("awm_reload_empty_rattle");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGHIT = sound("awm_reload_empty_maghit");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_MAGIN = sound("awm_reload_empty_magin");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_BOLTCLOSE = sound("awm_reload_empty_boltclose");
    public static final RegistryObject<SoundEvent> AWM_RELOAD_EMPTY_END = sound("awm_reload_empty_end");

    /** 弹夹弹出时的金属碰撞声"叮"。 */
    public static final RegistryObject<SoundEvent> AMMO_CLIP_POP = sound("ammo_clip_pop");

    private ModSounds() {
    }

    /** Wires the sound registry onto the mod event bus. */
    public static void register(IEventBus modBus) {
        SOUNDS.register(modBus);
    }

    private static RegistryObject<SoundEvent> sound(String name) {
        return SOUNDS.register(name, () -> SoundEvent.createVariableRangeEvent(
                new ResourceLocation(ApocalypseZombies.MOD_ID, name)));
    }
}
