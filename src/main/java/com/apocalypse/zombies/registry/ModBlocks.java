package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.block.SkyfallTerminalBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.material.MapColor;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * 方块注册表（v4.0 才第一次有自定义方块）。
 *
 * <p>目前只有一个：{@code skyfall_terminal}（天陨指挥终端）。方块本身不挖出物品栏掉落以外的东西，
 * 掉落表见 {@code data/apocalypse_zombies/loot_tables/blocks/skyfall_terminal.json}。</p>
 */
public final class ModBlocks {

    public static final DeferredRegister<Block> BLOCKS =
            DeferredRegister.create(ForgeRegistries.BLOCKS, ApocalypseZombies.MOD_ID);

    /** 天陨指挥终端：协议核心插槽 + 充能 + 参数面板的载体。 */
    public static final RegistryObject<Block> SKYFALL_TERMINAL = BLOCKS.register("skyfall_terminal",
            () -> new SkyfallTerminalBlock(BlockBehaviour.Properties.of()
                    .mapColor(MapColor.METAL)
                    .strength(5.0F, 1200.0F)
                    .sound(SoundType.METAL)
                    .lightLevel(state -> 7)
                    .noOcclusion()));

    private ModBlocks() {
    }

    public static void register(IEventBus modBus) {
        BLOCKS.register(modBus);
    }
}
