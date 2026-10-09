package com.apocalypse.zombies.event;

import java.util.List;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.registry.ModItems;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraftforge.event.entity.living.LivingDropsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 僵尸掉落：压制 crafting-dead 那份，并按档次补上自己的。
 *
 * <h2>为什么能拦得住 crafting-dead</h2>
 * 它的僵尸（{@code craftingdeadsurvival:weak_zombie} / {@code fast_zombie} / {@code tank_zombie} /
 * {@code police_zombie} / {@code doctor_zombie} / {@code giant_zombie}）掉的是标准的
 * {@code loot_tables/entities/*.json}，走原版的掉落结算路径，所以 {@link LivingDropsEvent} 看得到、也改得动。
 * 反编译它的 {@code ZombieMixin} 确认过：那个 mixin 管的是「水里不转化 / 不在阳光下燃烧 / 幼年体」这些，
 * 掉落没另起炉灶。
 *
 * <p>判定用的是<b>命名空间</b>而不是具体实体类型 —— 它将来加一个新变体，这里不用跟着改。</p>
 *
 * <h2>为什么是「清空」而不是「调低它的表」</h2>
 * 改它的 loot table 等于覆盖别的模组的资源，版本一变就错位。这里改成一次掷骰：没中就把这一次结算出的
 * 掉落整个清掉。效果就是「2% 的僵尸才掉东西」，而且与它内部怎么配表无关。</p>
 *
 * <h2>分档补掉落的设计口径</h2>
 * 参考 Zombie Apocalypse Core 的思路（食物 / 武器 / 装备 / 工具都要有，而不是清一色腐肉），
 * 但用的都是<b>原版物品</b>：这样不引入依赖、掉率好读、玩家一眼认得。
 * 五档独立掷骰，所以一只僵尸可能同时掉好几样，也可能什么都不掉 —— 这是有意为之。
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ZombieLoot {

    /** crafting-dead 的命名空间（core 与 survival 都算）。 */
    private static final String[] CRAFTING_DEAD_NAMESPACES = {"craftingdeadsurvival", "craftingdead"};

    private static final Item[] FOOD = {
            Items.BREAD, Items.COOKED_BEEF, Items.COOKED_CHICKEN, Items.COOKED_PORKCHOP,
            Items.APPLE, Items.CARROT, Items.BAKED_POTATO, Items.COOKIE};

    private static final Item[] TOOLS = {
            Items.IRON_SHOVEL, Items.IRON_PICKAXE, Items.IRON_AXE, Items.STONE_AXE,
            Items.STONE_SHOVEL, Items.SHEARS, Items.FLINT_AND_STEEL};

    private static final Item[] WEAPONS = {
            Items.IRON_SWORD, Items.STONE_SWORD, Items.BOW, Items.CROSSBOW, Items.WOODEN_SWORD};

    private static final Item[] GEAR = {
            Items.LEATHER_HELMET, Items.LEATHER_CHESTPLATE, Items.LEATHER_LEGGINGS,
            Items.LEATHER_BOOTS, Items.CHAINMAIL_HELMET, Items.CHAINMAIL_CHESTPLATE,
            Items.CHAINMAIL_LEGGINGS, Items.CHAINMAIL_BOOTS};

    private ZombieLoot() {
    }

    @SubscribeEvent
    public static void onLivingDrops(LivingDropsEvent event) {
        if (!Config.ZOMBIE_LOOT_ENABLED.get()) {
            return;
        }
        LivingEntity entity = event.getEntity();
        if (!(entity instanceof Monster)) {
            return;
        }

        if (isCraftingDead(entity)) {
            // 它原本必掉：没掷中就整单清掉，掷中则原样保留它自己配的表
            if (entity.getRandom().nextDouble() >= Config.ZOMBIE_LOOT_CRAFTINGDEAD_CHANCE.get()) {
                event.getDrops().clear();
            }
            return;
        }

        if (!Config.ZOMBIE_LOOT_EXTRA_ENABLED.get() || !(entity instanceof Zombie)) {
            return;
        }
        RandomSource random = entity.getRandom();
        roll(event, entity, random, Config.ZOMBIE_LOOT_FOOD_CHANCE.get(), FOOD);
        roll(event, entity, random, Config.ZOMBIE_LOOT_TOOL_CHANCE.get(), TOOLS);
        roll(event, entity, random, Config.ZOMBIE_LOOT_WEAPON_CHANCE.get(), WEAPONS);
        roll(event, entity, random, Config.ZOMBIE_LOOT_GEAR_CHANCE.get(), GEAR);
        if (random.nextDouble() < Config.ZOMBIE_LOOT_RARE_CHANCE.get()) {
            add(event, entity, new ItemStack(pickGun(random)));
        }
    }

    private static boolean isCraftingDead(LivingEntity entity) {
        ResourceLocation key = EntityType.getKey(entity.getType());
        for (String ns : CRAFTING_DEAD_NAMESPACES) {
            if (ns.equals(key.getNamespace())) {
                return true;
            }
        }
        return false;
    }

    /** 掷一次骰：中了就从表里随机挑一样掉出来。 */
    private static void roll(LivingDropsEvent event, LivingEntity entity, RandomSource random,
                             double chance, Item[] table) {
        if (chance <= 0.0D || random.nextDouble() >= chance) {
            return;
        }
        add(event, entity, new ItemStack(table[random.nextInt(table.length)]));
    }

    /** 弓 / 弩带上一小把箭，不然掉出来是块木头。 */
    private static void add(LivingDropsEvent event, LivingEntity entity, ItemStack stack) {
        if (stack.is(Items.BOW) || stack.is(Items.CROSSBOW)) {
            event.getDrops().add(itemEntity(entity, new ItemStack(Items.ARROW, 4 + entity.getRandom().nextInt(9))));
        }
        event.getDrops().add(itemEntity(entity, stack));
    }

    private static ItemEntity itemEntity(LivingEntity entity, ItemStack stack) {
        Level level = entity.level();
        return new ItemEntity(level, entity.getX(), entity.getY() + 0.5D, entity.getZ(), stack);
    }

    /** 本模组六把枪之一 —— 极低概率的那一档。 */
    private static Item pickGun(RandomSource random) {
        List<Item> guns = List.of(
                ModItems.AWM.get(), ModItems.M1_GARAND.get(), ModItems.MOSIN_NAGANT.get(),
                ModItems.UZI.get(), ModItems.S686.get(), ModItems.CROSSBOW.get());
        return guns.get(random.nextInt(guns.size()));
    }
}
