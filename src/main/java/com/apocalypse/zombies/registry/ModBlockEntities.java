package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.block.SkyfallTerminalBlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * 方块实体注册表。第一个成员就是天陨终端的 {@link SkyfallTerminalBlockEntity}。
 *
 * <p>注意 {@code BlockEntityType.Builder.of(...).build(null)} 的 {@code null} 是 datafixer 类型：
 * 1.20.1 里方块实体不做数据修复，传 null 是官方推荐写法。</p>
 */
public final class ModBlockEntities {

    public static final DeferredRegister<BlockEntityType<?>> BLOCK_ENTITIES =
            DeferredRegister.create(ForgeRegistries.BLOCK_ENTITY_TYPES, ApocalypseZombies.MOD_ID);

    public static final RegistryObject<BlockEntityType<SkyfallTerminalBlockEntity>> SKYFALL_TERMINAL =
            BLOCK_ENTITIES.register("skyfall_terminal", () -> BlockEntityType.Builder
                    .of(SkyfallTerminalBlockEntity::new, ModBlocks.SKYFALL_TERMINAL.get())
                    .build(null));

    private ModBlockEntities() {
    }

    public static void register(IEventBus modBus) {
        BLOCK_ENTITIES.register(modBus);
    }
}
