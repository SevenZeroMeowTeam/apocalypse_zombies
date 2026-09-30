package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.item.AWMItem;
import com.apocalypse.zombies.item.CrossbowItem;
import com.apocalypse.zombies.item.M1GarandItem;
import com.apocalypse.zombies.item.MosinNagantItem;
import com.apocalypse.zombies.item.UziItem;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraftforge.common.ForgeSpawnEggItem;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * Item registry for the mod. The guns stack to one and go in the vanilla Combat tab; the
 * special-mob spawn eggs go in the vanilla Spawn Eggs tab.
 *
 * <p>刷怪蛋的 id 一律是 {@code <entity>_spawn_egg}；但别指望 Forge 靠这个后缀配模型 ——
 * 它只为 {@link ForgeSpawnEggItem} 自动注册染色（{@code ItemColors}），模型仍要自己写在
 * {@code models/item/<id>.json}（{@code {"parent": "minecraft:item/template_spawn_egg"}}）。
 * 漏掉的表现是物品栏里一个紫黑 missing 方块加一行 {@code Unable to load model} 警告。</p>
 */
public final class ModItems {

    public static final DeferredRegister<Item> ITEMS =
            DeferredRegister.create(ForgeRegistries.ITEMS, ApocalypseZombies.MOD_ID);

    public static final RegistryObject<Item> AWM =
            ITEMS.register("awm", () -> new AWMItem(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> M1_GARAND =
            ITEMS.register("m1_garand", () -> new M1GarandItem(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> MOSIN_NAGANT =
            ITEMS.register("mosin_nagant", () -> new MosinNagantItem(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> CROSSBOW =
            ITEMS.register("crossbow", () -> new CrossbowItem(new Item.Properties().stacksTo(1)));

    /** Uzi 冲锋枪：32 发匣、600 rpm 全自动、铁瞄。 */
    public static final RegistryObject<Item> UZI =
            ITEMS.register("uzi", () -> new UziItem(new Item.Properties().stacksTo(1)));

    /** 美女僵尸远程技能「抛花刺」甩出去的那束花。不是武器，只是投射物的载体（自带 16×16 贴图）。 */
    public static final RegistryObject<Item> BOUQUET_DART =
            ITEMS.register("bouquet_dart", () -> new Item(new Item.Properties()));

    public static final RegistryObject<Item> SCREAMER_SPAWN_EGG =
            ITEMS.register("screamer_zombie_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.SCREAMER, 0x2E4A2E, 0x8BC34A, new Item.Properties()));

    public static final RegistryObject<Item> CRUSHER_SPAWN_EGG =
            ITEMS.register("crusher_zombie_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.CRUSHER, 0x3A3A3A, 0xB0BEC5, new Item.Properties()));

    public static final RegistryObject<Item> CORRODER_SPAWN_EGG =
            ITEMS.register("corroder_zombie_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.CORRODER, 0x2B3A1F, 0xAEEA00, new Item.Properties()));

    public static final RegistryObject<Item> MARKSMAN_SPAWN_EGG =
            ITEMS.register("marksman_skeleton_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.MARKSMAN, 0xD7D7D7, 0x2F3B2F, new Item.Properties()));

    public static final RegistryObject<Item> BRIDE_SPAWN_EGG =
            ITEMS.register("bride_zombie_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.BRIDE, 0xE8DCC8, 0x8E1B2E, new Item.Properties()));

    public static final RegistryObject<Item> SOLDIER_SPAWN_EGG =
            ITEMS.register("soldier_zombie_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.SOLDIER, 0x46523A, 0xE0B23C, new Item.Properties()));

    /** 尸潮之主：白骨 + 凝血红，一眼能从僵尸堆里认出来。 */
    public static final RegistryObject<Item> OVERLORD_SPAWN_EGG =
            ITEMS.register("horde_overlord_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.OVERLORD, 0xD8D2C0, 0x7A1220, new Item.Properties()));

    private ModItems() {
    }

    /** Wires the registry and its creative-tab hook onto the mod event bus. */
    public static void register(IEventBus modBus) {
        ITEMS.register(modBus);
        modBus.addListener(ModItems::addToCreativeTabs);
    }

    private static void addToCreativeTabs(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.COMBAT) {
            event.accept(AWM);
            event.accept(M1_GARAND);
            event.accept(MOSIN_NAGANT);
            event.accept(CROSSBOW);
            event.accept(UZI);
        }
        if (event.getTabKey() == CreativeModeTabs.SPAWN_EGGS) {
            event.accept(SCREAMER_SPAWN_EGG);
            event.accept(CRUSHER_SPAWN_EGG);
            event.accept(CORRODER_SPAWN_EGG);
            event.accept(MARKSMAN_SPAWN_EGG);
            event.accept(BRIDE_SPAWN_EGG);
            event.accept(SOLDIER_SPAWN_EGG);
            event.accept(OVERLORD_SPAWN_EGG);
        }
    }
}
