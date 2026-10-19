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

    // ---- v4.0.8 轨道设施装饰方块（只用于 orbit 维度，不可破坏、无物品形态） ----
    public static final RegistryObject<Block> FACILITY_HULL = facility("facility_hull", MapColor.COLOR_GRAY, 0);
    public static final RegistryObject<Block> FACILITY_GOLD = facility("facility_gold", MapColor.GOLD, 0);
    public static final RegistryObject<Block> FACILITY_PANEL = facility("facility_panel", MapColor.SNOW, 0);
    public static final RegistryObject<Block> FACILITY_SOLAR = facility("facility_solar", MapColor.COLOR_BLUE, 0);
    public static final RegistryObject<Block> FACILITY_DISH = facility("facility_dish", MapColor.SNOW, 0);
    public static final RegistryObject<Block> FACILITY_GLOW_CYAN = facility("facility_glow_cyan", MapColor.COLOR_CYAN, 15);
    public static final RegistryObject<Block> FACILITY_GLOW_ORANGE = facility("facility_glow_orange", MapColor.COLOR_ORANGE, 15);
    public static final RegistryObject<Block> FACILITY_DARK = facility("facility_dark", MapColor.COLOR_BLACK, 0);

    private static RegistryObject<Block> facility(String name, MapColor color, int light) {
        return BLOCKS.register(name, () -> new Block(BlockBehaviour.Properties.of()
                .mapColor(color)
                .strength(-1.0F, 3600000.0F)
                .sound(SoundType.METAL)
                .lightLevel(state -> light)));
    }

    private ModBlocks() {
    }

    public static void register(IEventBus modBus) {
        BLOCKS.register(modBus);
    }
}
