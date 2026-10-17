package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.item.AWMItem;
import com.apocalypse.zombies.item.CrossbowItem;
import com.apocalypse.zombies.item.M1GarandItem;
import com.apocalypse.zombies.item.MosinNagantItem;
import com.apocalypse.zombies.item.OrbitalStrikeRemoteItem;
import com.apocalypse.zombies.item.Rsc1917Item;
import com.apocalypse.zombies.item.Colt1878Item;
import com.apocalypse.zombies.item.S686Item;
import com.apocalypse.zombies.item.UziItem;
import com.apocalypse.zombies.item.Win94Item;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.AxeItem;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.HoeItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.PickaxeItem;
import net.minecraft.world.item.ShovelItem;
import net.minecraft.world.item.SwordItem;
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

    /** RSC M1917：5 发漏夹从**下方**经弹匣盖压入固定弹匣、半自动、空仓不挂机。 */
    public static final RegistryObject<Item> RSC_1917 =
            ITEMS.register("rsc_1917", () -> new Rsc1917Item(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> MOSIN_NAGANT =
            ITEMS.register("mosin_nagant", () -> new MosinNagantItem(new Item.Properties().stacksTo(1)));

    /**
     * 温彻斯特 M1894（Win94 杠杆狙击枪）：管状弹仓 5 发 .45-70、手动杠杆循环、内置清晰镜（2.5 倍、
     * 透明十字准星、瞄准时枪与手臂均不隐藏）。
     *
     * <p>与莫辛同一类武器（手动循环、固定弹仓、射击后动作自动跟上），差别在几何（杠杆而非枪栓）、
     * 动作时长与 ADS 样式 —— 见 {@link Win94Item}。全长 1.37 格（参考图比例）。</p>
     */
    public static final RegistryObject<Item> WIN94 =
            ITEMS.register("win94", () -> new Win94Item(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> CROSSBOW =
            ITEMS.register("crossbow", () -> new CrossbowItem(new Item.Properties().stacksTo(1)));

    /** Uzi 冲锋枪：32 发匣、600 rpm 全自动、铁瞄。 */
    public static final RegistryObject<Item> UZI =
            ITEMS.register("uzi", () -> new UziItem(new Item.Properties().stacksTo(1)));

    /** 金板 S686：上下双管折开式霰弹枪，2 发、每发 8 颗弹丸、1 秒一发、铁瞄。 */
    public static final RegistryObject<Item> S686 =
            ITEMS.register("s686", () -> new S686Item(new Item.Properties().stacksTo(1)));

    /**
     * 柯尔特 1878 教练枪：**并排**双管折开式霰弹枪，2 发、每发 8 颗弹丸、铁瞄。
     *
     * <p>与 S686 是同一类武器（折开式双管、两发、按枪管折开换弹），差别在几何、动作时长与音效 ——
     * 见 {@link Colt1878Item}。全长 0.93 格（940 mm 教练枪），比 S686 短。</p>
     */
    public static final RegistryObject<Item> COLT_1878 =
            ITEMS.register("colt_1878", () -> new Colt1878Item(new Item.Properties().stacksTo(1)));

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

    /** 猫耳娘：粉发 + 蓝白裙。 */
    public static final RegistryObject<Item> CAT_GIRL_SPAWN_EGG =
            ITEMS.register("cat_girl_spawn_egg", () -> new ForgeSpawnEggItem(
                    ModEntities.CAT_GIRL, 0xE8C8C8, 0x8FB0DC, new Item.Properties()));

    /**
     * 爱心币：猫耳娘交易系统的通货。
     *
     * <p>卖出任意物品（含模组物品）按价值表得币，再用币买下她伐木挖矿攒下的库存。
     * 可堆叠 64 —— 回报格按「价值 × 数量」出币，一叠才对得上大额交易。</p>
     */
    public static final RegistryObject<Item> LOVE_COIN =
            ITEMS.register("love_coin", () -> new Item(new Item.Properties().stacksTo(64)));

    /**
     * 轨道打击遥控器（科幻武器）：手持时准星处画选区立方体，右键触发轨道打击
     * —— 详见 {@link com.apocalypse.zombies.event.OrbitalStrikeManager}。
     * stacksTo(1) + 不可用附魔台。注册在 {@code apocalypse_zombies:item/orbital_strike_remote}。
     */
    public static final RegistryObject<Item> ORBITAL_STRIKE_REMOTE =
            ITEMS.register("orbital_strike_remote",
                    () -> new OrbitalStrikeRemoteItem(new Item.Properties().stacksTo(1).rarity(
                            net.minecraft.world.item.Rarity.RARE)));

    // ------------------------------------------------------------------ 铜装备

    /**
     * 铜剑：伤害与石剑**完全一致** —— 两者 Tier 的攻击加成都是 +1，剑自身 +3、基础 +1，
     * 最终都是 5 点。耐久 200 比石剑的 131 高。
     */
    public static final RegistryObject<Item> COPPER_SWORD =
            ITEMS.register("copper_sword",
                    () -> new SwordItem(ModTiers.COPPER, 3, -2.4F, new Item.Properties()));

    /** 铜镐：挖掘等级同石（挖得动铁矿石、挖不动钻石），效率 5.0 略高于石镐的 4.0。 */
    public static final RegistryObject<Item> COPPER_PICKAXE =
            ITEMS.register("copper_pickaxe",
                    () -> new PickaxeItem(ModTiers.COPPER, 1, -2.8F, new Item.Properties()));

    /** 铜锄：与石锄同一组手感参数（攻击修正 -1 / 攻速 -2.0）。 */
    public static final RegistryObject<Item> COPPER_HOE =
            ITEMS.register("copper_hoe",
                    () -> new HoeItem(ModTiers.COPPER, -1, -2.0F, new Item.Properties()));

    /**
     * 铜斧：伤害与石斧**完全一致**（同样是 {@code 1 + 7 + 1 = 9} 点），耐久 200 比石斧的 131 高。
     *
     * <p>斧头在 1.20.1 的伤害本来就比剑高一大截（石斧 9 点 vs 石剑 5 点），所以这里照抄的是
     * <b>石斧</b>那一组参数（{@code 7.0F / -3.2F}），不是石剑的 —— 「武器伤害和石制一样」对斧的
     * 读法就是这一条。耐久 / 效率 / 挖掘等级都跟着 {@link ModTiers#COPPER} 走，与另三件铜工具同档。</p>
     */
    public static final RegistryObject<Item> COPPER_AXE =
            ITEMS.register("copper_axe",
                    () -> new AxeItem(ModTiers.COPPER, 7.0F, -3.2F, new Item.Properties()));

    /**
     * 铜锹：与石锹同一组手感参数（攻击修正 +1.5 / 攻速 -3.0），挖掘等级 / 耐久 / 效率跟着
     * {@link ModTiers#COPPER} 走，与另四件铜工具同档。
     *
     * <p>1.1.110 同版追加：这套铜装备原先只有剑 / 镐 / 锄 / 斧 —— 玩家在配方书里看到的"铜锹"
     * 其实来自 {@code [硬核生存] hcsurvival}（它的 `hcsurvival:copper_*` 与本模组是两套同名物品），
     * 这里把缺的那一件补进本家，铜套装自此完整（贴图沿用套装同一套铁→铜色板重染）。</p>
     */
    public static final RegistryObject<Item> COPPER_SHOVEL =
            ITEMS.register("copper_shovel",
                    () -> new ShovelItem(ModTiers.COPPER, 1.5F, -3.0F, new Item.Properties()));

    /**
     * 铜甲四件：护甲值 2 / 4 / 3 / 1（合计 <b>10</b>）—— 皮革 7 → 高，铁 15 → 低。
     *
     * <p>单看头盔它与铁同为 2：原版护甲值是整数，皮革的 1 与铁的 2 之间没有第三个数，所以
     * 「比皮革高、比铁低」这条落在整套<b>总和</b>上。耐久系数 11（皮革 5 / 铁 15）。
     * 穿戴贴图名由 {@link ModArmorMaterials#getName()} 决定，与那两张 layer 贴图一一对应。</p>
     */
    public static final RegistryObject<Item> COPPER_HELMET =
            ITEMS.register("copper_helmet",
                    () -> new ArmorItem(ModArmorMaterials.COPPER, ArmorItem.Type.HELMET,
                            new Item.Properties()));

    public static final RegistryObject<Item> COPPER_CHESTPLATE =
            ITEMS.register("copper_chestplate",
                    () -> new ArmorItem(ModArmorMaterials.COPPER, ArmorItem.Type.CHESTPLATE,
                            new Item.Properties()));

    public static final RegistryObject<Item> COPPER_LEGGINGS =
            ITEMS.register("copper_leggings",
                    () -> new ArmorItem(ModArmorMaterials.COPPER, ArmorItem.Type.LEGGINGS,
                            new Item.Properties()));

    public static final RegistryObject<Item> COPPER_BOOTS =
            ITEMS.register("copper_boots",
                    () -> new ArmorItem(ModArmorMaterials.COPPER, ArmorItem.Type.BOOTS,
                            new Item.Properties()));

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
            event.accept(RSC_1917);
            event.accept(MOSIN_NAGANT);
            event.accept(WIN94);
            event.accept(CROSSBOW);
            event.accept(UZI);
            event.accept(S686);
            event.accept(COLT_1878);
            // 铜装备：剑与四件甲归战斗页，与它们要替代的石/铁装备同页
            event.accept(COPPER_SWORD);
            event.accept(COPPER_HELMET);
            event.accept(COPPER_CHESTPLATE);
            event.accept(COPPER_LEGGINGS);
            event.accept(COPPER_BOOTS);
            // 轨道打击遥控器属于「战斗」，和枪械同页 —— 之前误挂在刷怪蛋页
            event.accept(ORBITAL_STRIKE_REMOTE);
        }
        if (event.getTabKey() == CreativeModeTabs.TOOLS_AND_UTILITIES) {
            event.accept(COPPER_PICKAXE);
            event.accept(COPPER_HOE);
            event.accept(COPPER_AXE);
            event.accept(COPPER_SHOVEL);
        }
        if (event.getTabKey() == CreativeModeTabs.SPAWN_EGGS) {
            event.accept(SCREAMER_SPAWN_EGG);
            event.accept(CRUSHER_SPAWN_EGG);
            event.accept(CORRODER_SPAWN_EGG);
            event.accept(MARKSMAN_SPAWN_EGG);
            event.accept(BRIDE_SPAWN_EGG);
            event.accept(SOLDIER_SPAWN_EGG);
            event.accept(OVERLORD_SPAWN_EGG);
            event.accept(CAT_GIRL_SPAWN_EGG);
        }
        if (event.getTabKey() == CreativeModeTabs.INGREDIENTS) {
            event.accept(LOVE_COIN);
        }
    }
}
