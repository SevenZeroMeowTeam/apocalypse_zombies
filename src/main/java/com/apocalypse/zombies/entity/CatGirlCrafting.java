package com.apocalypse.zombies.entity;

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
