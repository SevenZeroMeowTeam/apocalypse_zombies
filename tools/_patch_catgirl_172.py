# -*- coding: utf-8 -*-
"""1.1.72：她自己干活 —— 拾取 / 自制 / 按工种自动换装（含盔甲）/ 无耐久 / 砸矿必掉。"""
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'

# ============================================================ ① 自制（新文件）
Path(J + 'entity/CatGirlCrafting.java').write_text('''package com.apocalypse.zombies.entity;

import net.minecraft.core.RegistryAccess;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.BowItem;
import net.minecraft.world.item.CrossbowItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.ShieldItem;
import net.minecraft.world.item.TieredItem;
import net.minecraft.world.item.TridentItem;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.RecipeType;

import java.util.ArrayList;
import java.util.List;

/**
 * 猫耳娘自己动手做装备：从她的库存（{@code goods}）里凑材料，按**原版配方表**做出东西，
 * 做完放进库存 —— 也就是摆上她的货架，玩家用爱心币就能换走。
 *
 * <p>只做「她自己的装备」：工具（剑/镐/斧/锹/锄）、弓弩、盔甲、箭、盾、三叉戟。
 * 不设这个白名单的话，她会把玩家交给她的一堆材料做成木棍、台阶之类，库存立刻变垃圾场。</p>
 *
 * <p>判定用**材料多重集**而不是 3x3 摆放（她不像玩家那样有格子摆位），
 * 所以同材料的形状配方可能挑中其中一个 —— 对「她自己做」这件事够用，
 * 要精确摆放走她的界面里那套原版 3x3。</p>
 */
public final class CatGirlCrafting {

    private CatGirlCrafting() {
    }

    /** 候选配方缓存：工程里一千多条配方，每 40 tick 全遍历一遍会把服务端拖慢。 */
    private static List<CraftingRecipe> candidates;

    /** 配方表变了（数据包重载）就清缓存。 */
    public static void invalidate() {
        candidates = null;
    }

    /** 她「该做」的产物。 */
    public static boolean isHerCraftable(ItemStack result) {
        if (result.isEmpty()) {
            return false;
        }
        Item item = result.getItem();
        return item instanceof TieredItem
                || item instanceof BowItem
                || item instanceof CrossbowItem
                || item instanceof ArmorItem
                || item instanceof ArrowItem
                || item instanceof ShieldItem
                || item instanceof TridentItem;
    }

    /** 做多少才算够：装备一件就够，箭攒一叠。 */
    private static int desiredCount(ItemStack result) {
        return result.getItem() instanceof ArrowItem ? Math.min(64, result.getMaxStackSize()) : 1;
    }

    private static List<CraftingRecipe> candidates(ServerLevel level) {
        if (candidates == null) {
            RegistryAccess access = level.registryAccess();
            List<CraftingRecipe> list = new ArrayList<>();
            for (CraftingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)) {
                if (isHerCraftable(recipe.getResultItem(access))) {
                    list.add(recipe);
                }
            }
            candidates = List.copyOf(list);
        }
        return candidates;
    }

    private static int countIn(SimpleContainer goods, ItemStack like) {
        int n = 0;
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack s = goods.getItem(i);
            if (!s.isEmpty() && ItemStack.isSameItemSameTags(s, like)) {
                n += s.getCount();
            }
        }
        return n;
    }

    /**
     * 试着做一件：材料齐就扣材料、产物进她库存。返回做出来的那件，没做返回空。
     */
    public static ItemStack craftOne(CatGirlEntity cat, ServerLevel level) {
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        for (CraftingRecipe recipe : candidates(level)) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty() || countIn(goods, result) >= desiredCount(result)) {
                continue;
            }
            // 逐条材料在库存里找：take[i] 记这个格子被占用几个（同一格不许超发）
            int[] take = new int[goods.getContainerSize()];
            boolean ok = true;
            for (Ingredient ingredient : recipe.getIngredients()) {
                if (ingredient.isEmpty()) {
                    continue;
                }
                boolean found = false;
                for (int i = 0; i < goods.getContainerSize(); i++) {
                    ItemStack s = goods.getItem(i);
                    if (s.getCount() > take[i] && ingredient.test(s)) {
                        take[i]++;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    ok = false;
                    break;
                }
            }
            if (!ok) {
                continue;
            }
            for (int i = 0; i < take.length; i++) {
                if (take[i] > 0) {
                    goods.removeItem(i, take[i]);
                }
            }
            ItemStack out = result.copy();
            ItemStack leftover = goods.addItem(out.copy());
            if (!leftover.isEmpty()) {
                net.minecraft.world.level.block.Block.popResource(level, cat.blockPosition(), leftover);
            }
            goods.setChanged();
            return out;
        }
        return ItemStack.EMPTY;
    }
}
''', encoding='utf-8')
print('(1) entity/CatGirlCrafting.java 新建：材料多重集 → 原版配方 → 产物进她货架')

# ============================================================ ② Config：五个开关
p = Path(J + 'Config.java')
s = p.read_text(encoding='utf-8')
old = '    /** 全无敌：任何来源都不掉血、也不会死（敌对生物、玩家、爆炸、虚空都免）。 */'
assert old in s, 'Config 锚点'
s = s.replace(old, '''    /** 她会捡地上的东西塞进自己库存（捡到的东西就是她的货架）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_PICKUP;

    /** 她按工种自己换主手：伐木拿斧、挖矿拿镐、战斗拿剑（没剑就弓弩），并把库存里更好的盔甲穿上。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_EQUIP;

    /** 她自己动手把库存材料做成装备（工具 / 武器 / 盔甲 / 箭）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AUTO_CRAFT;

    /** 她的装备不吃耐久（主手、盔甲、库存里的可损物品一律修满）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_NO_DURABILITY;

    /** 无视原版工具等级限制：她砸的方块一律有产物（用最高等级工具兜底取掉落）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ALWAYS_DROPS;

''' + old, 1)
old = '''        CAT_GIRL_INVULNERABLE = b.comment("全无敌：任何来源都不掉血、也不会死（连 /kill 也伤不到她）。")'''
assert old in s, 'Config 定义锚点'
s = s.replace(old, '''        CAT_GIRL_PICKUP = b.comment("她会捡地上的东西收进自己库存（捡到的就是她的货架）。")
                .define("pickup", true);
        CAT_GIRL_AUTO_EQUIP = b.comment("她按工种自己换装备：伐木拿斧、挖矿拿镐、战斗拿剑（没剑用弓弩），顺手穿库存里更好的盔甲。")
                .define("auto_equip", true);
        CAT_GIRL_AUTO_CRAFT = b.comment("她自己把库存材料做成装备（工具 / 武器 / 盔甲 / 箭）。")
                .define("auto_craft", true);
        CAT_GIRL_NO_DURABILITY = b.comment("她的装备不吃耐久。")
                .define("no_durability", true);
        CAT_GIRL_ALWAYS_DROPS = b.comment("无视原版工具等级限制：她砸什么都有产物。")
                .define("always_drops", true);
''' + old, 1)
p.write_text(s, encoding='utf-8')
print('(2) Config：+ pickup / auto_equip / auto_craft / no_durability / always_drops')

# ============================================================ ③ 实体：拾取 / 自动换装 / 无耐久 / 自制
p = Path(J + 'entity/CatGirlEntity.java')
s = p.read_text(encoding='utf-8')

old = '    private final SimpleContainer goods = new SimpleContainer(GOODS_SIZE);'
assert old in s, '库存字段锚点'
s = s.replace(old, old + '''

    /** 日常维护（换装 / 修耐久 / 自制品）的节拍计数。 */
    private int maintenanceTicks = 20;
    private int craftTicks = 40;
    private int pickupTicks = 5;

    /** 盔甲四个槽（她自己穿）。 */
    private static final net.minecraft.world.entity.EquipmentSlot[] ARMOR_SLOTS = {
            net.minecraft.world.entity.EquipmentSlot.HEAD,
            net.minecraft.world.entity.EquipmentSlot.CHEST,
            net.minecraft.world.entity.EquipmentSlot.LEGS,
            net.minecraft.world.entity.EquipmentSlot.FEET};''', 1)

old = '''    @Override
    public void aiStep() {
        super.aiStep();
        this.guardImmortal();
    }'''
assert old in s, 'aiStep 锚点'
s = s.replace(old, '''    @Override
    public void aiStep() {
        super.aiStep();
        if (this.level().isClientSide) {
            return;
        }
        this.guardImmortal();
        if (Config.CAT_GIRL_PICKUP.get()) {
            this.pickupNearby();
        }
        if (--this.maintenanceTicks > 0) {
            return;
        }
        this.maintenanceTicks = 20;
        if (Config.CAT_GIRL_NO_DURABILITY.get()) {
            this.keepGearPristine();
        }
        if (Config.CAT_GIRL_AUTO_EQUIP.get()) {
            this.ensureMainHand(this.getJob());
            this.ensureArmor();
        }
        if (Config.CAT_GIRL_AUTO_CRAFT.get() && this.level() instanceof ServerLevel server
                && --this.craftTicks <= 0) {
            this.craftTicks = 40;
            CatGirlCrafting.craftOne(this, server);
        }
    }

    // ------------------------------------------------------------ 拾取

    /** 不用原版那套（它要 mobGriefing 开着）：自己扫身边 1.5 格捡。 */
    private void pickupNearby() {
        if (--this.pickupTicks > 0) {
            return;
        }
        this.pickupTicks = 5;
        net.minecraft.world.phys.AABB box = this.getBoundingBox().inflate(1.5D, 0.5D, 1.5D);
        for (net.minecraft.world.entity.item.ItemEntity item :
                this.level().getEntitiesOfClass(net.minecraft.world.entity.item.ItemEntity.class, box)) {
            if (item.isRemoved() || item.hasPickUpDelay() || item.getItem().isEmpty()) {
                continue;
            }
            if (this.wantsToPickUp(item.getItem())) {
                this.pickUpItem(item);
            }
        }
    }

    @Override
    public boolean canPickUpLoot() {
        return false; // 走自己的扫描，不受 mobGriefing 影响
    }

    @Override
    public boolean wantsToPickUp(ItemStack stack) {
        if (stack.isEmpty()) {
            return false;
        }
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty()) {
                return true;
            }
            if (ItemStack.isSameItemSameTags(s, stack) && s.getCount() < s.getMaxStackSize()) {
                return true;
            }
        }
        return false;
    }

    @Override
    protected void pickUpItem(net.minecraft.world.entity.item.ItemEntity entity) {
        ItemStack stack = entity.getItem();
        ItemStack leftover = this.goods.addItem(stack.copy());
        if (leftover.getCount() == stack.getCount()) {
            return; // 一点也塞不进去，别动它
        }
        this.goods.setChanged();
        this.take(entity, leftover.getCount());
        stack.setCount(leftover.getCount());
        if (stack.isEmpty()) {
            entity.discard();
        }
    }

    // ------------------------------------------------------------ 按工种换装

    /** 工具打分：先看材质等级（木/金 0 < 石 1 < 铁 2 < 钻 3 < 下界 4），再看耐久上限。 */
    private static int gearRank(ItemStack stack) {
        int tier = stack.getItem() instanceof net.minecraft.world.item.TieredItem tiered
                ? tiered.getTier().getLevel() : 0;
        return tier * 10000 + stack.getMaxDamage();
    }

    /** 从库存里取出一件指定物品（真取走）。 */
    private ItemStack takeFirst(net.minecraft.world.item.Item... items) {
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty()) {
                continue;
            }
            for (net.minecraft.world.item.Item item : items) {
                if (s.is(item)) {
                    return this.goods.removeItem(i, 1);
                }
            }
        }
        return ItemStack.EMPTY;
    }

    /** 从库存里取出一把最合适的（真取走，不是复制）。 */
    private ItemStack takeBest(net.minecraft.tags.TagKey<net.minecraft.world.item.Item> tag) {
        int bestIdx = -1;
        int best = -1;
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty() || !s.is(tag)) {
                continue;
            }
            int rank = gearRank(s);
            if (rank > best) {
                best = rank;
                bestIdx = i;
            }
        }
        return bestIdx < 0 ? ItemStack.EMPTY : this.goods.removeItem(bestIdx, 1);
    }

    private void ensureMainHand(Job job) {
        ItemStack held = this.getMainHandItem();
        ItemStack want;
        switch (job) {
            case LUMBER -> {
                if (held.is(net.minecraft.tags.ItemTags.AXES)) {
                    return; // 手上就是斧子（比如玩家刚给她的），别动
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.AXES);
            }
            case MINE -> {
                if (held.is(net.minecraft.tags.ItemTags.PICKAXES)) {
                    return;
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.PICKAXES);
            }
            case FIGHT -> {
                if (held.is(net.minecraft.tags.ItemTags.SWORDS)) {
                    return;
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.SWORDS);
                if (want.isEmpty()) {
                    if ((held.is(Items.BOW) || held.is(Items.CROSSBOW)) && this.countArrows() > 0) {
                        return; // 没剑但有弓且有箭，就这么打
                    }
                    if (want.isEmpty()) {
                        want = this.takeFirst(Items.BOW, Items.CROSSBOW);
                    }
                }
            }
            default -> want = ItemStack.EMPTY; // 跟随 / 没事干：收起工具
        }
        if (ItemStack.isSameItemSameTags(held, want)) {
            return;
        }
        if (!held.isEmpty()) {
            this.goods.addItem(held.copy()); // 换下来的收回库存，不丢
        }
        this.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, ItemStack.EMPTY);
        if (!want.isEmpty()) {
            this.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, want);
        }
    }

    private static int armorValue(ItemStack stack) {
        return stack.getItem() instanceof net.minecraft.world.item.ArmorItem armor ? armor.getDefense() : -1;
    }

    /** 库存里有更好的盔甲就换上（换下来的回库存）。 */
    private void ensureArmor() {
        for (net.minecraft.world.entity.EquipmentSlot slot : ARMOR_SLOTS) {
            ItemStack worn = this.getItemBySlot(slot);
            int bestIdx = -1;
            int best = armorValue(worn);
            for (int i = 0; i < this.goods.getContainerSize(); i++) {
                ItemStack s = this.goods.getItem(i);
                if (s.isEmpty() || !(s.getItem() instanceof net.minecraft.world.item.ArmorItem armor)) {
                    continue;
                }
                if (armor.getEquipmentSlot() != slot) {
                    continue;
                }
                if (armorValue(s) > best) {
                    best = armorValue(s);
                    bestIdx = i;
                }
            }
            if (bestIdx < 0) {
                continue;
            }
            ItemStack take = this.goods.removeItem(bestIdx, 1);
            if (!worn.isEmpty()) {
                this.goods.addItem(worn.copy());
            }
            this.setItemSlot(slot, take);
        }
    }

    /** 她的装备不吃耐久：主手、盔甲、库存里的可损物品一律修满。 */
    private void keepGearPristine() {
        ItemStack held = this.getMainHandItem();
        if (held.isDamageableItem() && held.getDamageValue() > 0) {
            held.setDamageValue(0);
        }
        for (net.minecraft.world.entity.EquipmentSlot slot : ARMOR_SLOTS) {
            ItemStack s = this.getItemBySlot(slot);
            if (s.isDamageableItem() && s.getDamageValue() > 0) {
                s.setDamageValue(0);
            }
        }
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isDamageableItem() && s.getDamageValue() > 0) {
                s.setDamageValue(0);
            }
        }
    }''', 1)
p.write_text(s, encoding='utf-8')
print('(3) CatGirlEntity：拾取扫描 + ensureMainHand/ensureArmor + 无耐久 + 自制节拍')

# ============================================================ ④ 劳作：砸矿必掉（无视等级）
p = Path(J + 'entity/ai/WorkBlockGoal.java')
s = p.read_text(encoding='utf-8')
old = '''        List<ItemStack> drops = Block.getDrops(state, server, pos, entity, this.cat, this.cat.getMainHandItem());
        server.destroyBlock(pos, false);'''
assert old in s, 'breakBlock 锚点'
s = s.replace(old, '''        List<ItemStack> drops = Block.getDrops(state, server, pos, entity, this.cat, this.cat.getMainHandItem());
        if (drops.isEmpty() && state.requiresCorrectToolForDrops()
                && Config.CAT_GIRL_ALWAYS_DROPS.get()) {
            // 「无视原版规则限制」：原版卡掉落的是 playerDestroy 里的 canHarvestBlock（工具等级），
            // 不是掉落表本身 —— 这里用最高等级工具再取一次，保证她砸什么都有产物。
            ItemStack cheat = new ItemStack(this.job == Job.LUMBER
                    ? net.minecraft.world.item.Items.NETHERITE_AXE
                    : net.minecraft.world.item.Items.NETHERITE_PICKAXE);
            drops = Block.getDrops(state, server, pos, entity, this.cat, cheat);
        }
        server.destroyBlock(pos, false);''', 1)
p.write_text(s, encoding='utf-8')
print('(4) WorkBlockGoal：工具等级不再卡她的掉落')

# ============================================================ ⑤ 版本 + readme
g = Path('gradle.properties'); t = g.read_text(encoding='utf-8')
assert 'mod_version=1.1.71' in t
g.write_text(t.replace('mod_version=1.1.71', 'mod_version=1.1.72'), encoding='utf-8')
print('(5) mod_version=1.1.72')

p = Path('readme.md'); s = p.read_text(encoding='utf-8')
s = s.replace('| **当前版本** | `1.1.71` |', '| **当前版本** | `1.1.72` |', 1)
entry = """### 1.1.72 — 2026-10-10

**猫耳娘自己干活：拾取 → 自制 → 按工种换装备（含盔甲），工具无耐久、砸矿必掉**

- **拾取**（`pickup`，默认开）：她扫身边 1.5 格捡地上的东西塞进自己的库存 ——
  不走原版那套（原版要 `mobGriefing` 开着才捡），5 tick 扫一次，捡到的直接进她的货架。
- **自制**（`auto_craft`，默认开）：新增 `CatGirlCrafting` —— 把她库存里的材料按**原版配方表**
  做成装备，每 40 tick 出一件，产物进库存（也就是摆上货架）。
  只做「她自己的装备」：工具（剑/镐/斧/锹/锄）、弓弩、盔甲、箭、盾、三叉戟 ——
  不设白名单她会把材料做成木棍台阶、把库存变垃圾场。材料判定用多重集（她没格子摆位），
  要精确摆放走她界面里那套原版 3×3。候选配方带缓存，不会被一千多条配方拖慢。
- **自动换装**（`auto_equip`，默认开）：按工种自己换主手 —— 伐木拿斧、挖矿拿镐、
  战斗拿剑（没剑但有弓且有箭就用弓弩），跟随/没事干时把工具收回库存。换装按材质等级
  （木/金 0 < 石 1 < 铁 2 < 钻 3 < 下界 4）挑最好的，**换下来的回库存不丢**；
  手上已经是对口工具时不动（保护玩家刚给她的那把）。同时把库存里防御更高的盔甲穿到
  头/胸/腿/脚四个槽（换下来的同样回库存）。
- **无耐久**（`no_durability`，默认开）：她的主手、盔甲、库存里所有可损物品每 20 tick 修满。
- **砸什么都有掉**（`always_drops`，默认开）：原版卡掉落的是 `playerDestroy` 里的
  `canHarvestBlock`（工具等级），不是掉落表本身 —— 掉落为空且方块要求对口工具时，
  用最高等级工具再取一次，所以木镐砸钻石矿也有钻石。
- **货币交易**：爱心币（`love_coin`）那套原样可用 —— 她做好的东西进她库存即货架，
  从她货架拿东西按 `coinValue` 扣爱心币；不够钱给提示 + 生气粒子。

**闭环**：捡/收下材料 → 她自己做成剑斧镐甲 → 按工种换上 → 你花爱心币从她货架换走成品。

"""
if '### 1.1.71 — 2026-10-10' in s and '### 1.1.72' not in s:
    s = s.replace('### 1.1.71 — 2026-10-10', entry + '### 1.1.71 — 2026-10-10', 1)
p.write_text(s, encoding='utf-8')
print('(6) readme.md 1.1.72')
