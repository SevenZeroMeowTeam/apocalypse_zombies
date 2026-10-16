package com.apocalypse.zombies.compat;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import net.minecraft.core.NonNullList;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.ReloadableServerResources;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Unit;
import net.minecraft.util.profiling.ProfilerFiller;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeManager;
import net.minecraft.world.item.crafting.ShapedRecipe;
import net.minecraft.world.item.crafting.ShapelessRecipe;
import net.minecraftforge.event.AddReloadListenerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 铜装备配方去重：让本模组的铜装备在「硬核生存」（{@code hcsurvival}）在场时仍然合得出来。
 *
 * <p><b>病根</b>：{@code hcsurvival} 用<b>同一套原版图案 + 同一材料（{@code minecraft:copper_ingot}）</b>
 * 注册了同名的九件铜装备（{@code hcsurvival:copper_helmet} …），与本模组那九件的 canonical 图案
 * 逐格等价。1.20.1 的 {@code RecipeManager.getRecipeFor} 是「按内部 Map 的迭代顺序取第一条命中」
 * （{@code findFirst}，HashMap 顺序，跟谁先加载无关）—— 两条一模一样的配方里<b>永远只有一条能被
 * 合成台用到</b>，另一条等于不存在。玩家于是看到：配方书 / REI 里两套同名铜装备并列，
 * 摆出图案却可能什么都拿不到（或拿到硬核生存那件）。</p>
 *
 * <p><b>做法</b>：配方加载完成后（{@link AddReloadListenerEvent} 加进来的监听器排在原版
 * {@code RecipeManager} 之后，再由 barrier 保证等地到全部 prepare 结束），把「与本模组铜装备配方
 * <b>抢同一批网格</b>（类型 / 尺寸相同、逐格材料集合有交集，shaped 连镜像摆法一起比）、产物却不是
 * 本模组物品」的配方从 {@code RecipeManager} 里剔除。</p>
 *
 * <p><b>手柄槽是物品标签</b>：本模组铜装备的 {@code S} 槽用的是
 * {@code #apocalypse_zombies:copper_handles}（= 原版木棍 + 硬核生存的 {@code short_stick} 短木棍）。
 * 硬核生存把原版木/石工具配方整个换成「1 个屏障」（= 禁用），把玩家推向它自己的硬核工具链，
 * 那条链的「棍」正是短木棍；两种棍在背包里长得几乎一样，玩家极易拿错 —— 认标签就不会白摆。</p>
 *
 * <p><b>为什么不写死 hcsurvival 的配方 id</b>：判定是结构化的（配方类型 + 宽高 + 逐格材料集合），
 * 换个同形冲突的模组照样拦得住；而且只对<b>本模组那九件铜装备的指纹</b>建表 —— 别的配方（包括
 * 硬核生存的其余内容）一概不碰。想关掉：配置 {@code compat.copper_recipe_dedup=false}，
 * 行为立刻回到原样。</p>
 *
 * <p><b>接线</b>：主类构造里显式 {@code MinecraftForge.EVENT_BUS.register}（与 {@code CommonEvents}
 * 同一条路 —— 本模组的 FORGE 总线处理器都这么挂），不依赖注解扫描。</p>
 */
public final class CopperGearRecipeCompat {

    /** 本模组的九件铜装备（物品注册名）。指纹只对这九件建表，其余配方一律不认。 */
    private static final Set<String> COPPER_GEAR = Set.of(
            "copper_sword", "copper_pickaxe", "copper_axe", "copper_hoe", "copper_shovel",
            "copper_helmet", "copper_chestplate", "copper_leggings", "copper_boots");

    private CopperGearRecipeCompat() {
    }

    /** 主类构造里调用：把本类挂到 FORGE 总线上（静态 {@code @SubscribeEvent} 处理器）。 */
    public static void register() {
        net.minecraftforge.common.MinecraftForge.EVENT_BUS.register(CopperGearRecipeCompat.class);
    }

    @SubscribeEvent
    public static void onAddReloadListeners(AddReloadListenerEvent event) {
        // 拿的是同一个 ReloadableServerResources：监听器排在原版最后一个（ServerAdvancementManager）
        // 之后，所以我们 apply 的时候 RecipeManager 已经是最终内容了。
        ReloadableServerResources resources = event.getServerResources();
        event.addListener(new PreparableReloadListener() {
            @Override
            public CompletableFuture<Void> reload(PreparableReloadListener.PreparationBarrier barrier,
                                                  ResourceManager resourceManager,
                                                  ProfilerFiller preparationsProfiler,
                                                  ProfilerFiller reloadProfiler,
                                                  Executor backgroundExecutor,
                                                  Executor gameExecutor) {
                // 必须等 barrier：直接在 reload() 里改配方表会跑在 RecipeManager.apply **之前**
                // （那时配方还是空的）。barrier 之后回到主线程再动手。
                return barrier.wait(Unit.INSTANCE)
                        .thenRunAsync(() -> prune(resources.getRecipeManager()), gameExecutor);
            }
        });
    }

    /** 现场重铺配方表：剔掉「同形、产物却不是本模组」的重复铜装备配方。 */
    private static void prune(RecipeManager manager) {
        try {
            if (!Config.COPPER_RECIPE_DEDUP.get()) {
                return;
            }
            Collection<Recipe<?>> recipes = manager.getRecipes();

            // 第一步：本模组那九件的配方（含 axe / hoe 的镜像变体）——外家笔记只要与其中任意一条
            // 「抢同一批网格」就退场。
            List<Recipe<?>> ours = new ArrayList<>();
            for (Recipe<?> recipe : recipes) {
                if (isOurCopperGear(recipe)) {
                    ours.add(recipe);
                }
            }
            ApocalypseZombies.LOGGER.info("[铜装备兼容] 扫描配方 {} 条 → 本模组铜装备配方 {} 条",
                    recipes.size(), ours.size());
            if (ours.isEmpty()) {
                // 本模组的铜装备配方一条都没上桌（被数据包整个顶掉之类）：绝不多手。
                return;
            }

            // 第二步：与外家配方逐条比「是否抢同一次命中」，抢就走。
            List<Recipe<?>> kept = new ArrayList<>(recipes.size());
            List<String> dropped = new ArrayList<>();
            for (Recipe<?> recipe : recipes) {
                if (!isOurCopperGear(recipe) && competesWithAny(recipe, ours)) {
                    dropped.add(recipe.getId().toString());
                } else {
                    kept.add(recipe);
                }
            }
            if (dropped.isEmpty()) {
                return;
            }
            manager.replaceRecipes(kept);
            ApocalypseZombies.LOGGER.info(
                    "[铜装备兼容] 剔除 {} 条与本模组铜装备抢同一批网格的重复配方（摆对图案必定出本模组的产物）：{}",
                    dropped.size(), dropped);
        } catch (Exception e) {
            // 配方表是游戏的地基，这里任何意外都不该把世界加载搞崩：记一行，照常继续。
            ApocalypseZombies.LOGGER.warn("[铜装备兼容] 配方去重未完成，配方表保持原样。", e);
        }
    }

    /** 本模组的铜装备配方：配方 id 在我们的命名空间，且产的是那九件之一。 */
    private static boolean isOurCopperGear(Recipe<?> recipe) {
        if (!ApocalypseZombies.MOD_ID.equals(recipe.getId().getNamespace())) {
            return false;
        }
        Item item = recipe.getResultItem(RegistryAccess.EMPTY).getItem();
        ResourceLocation key = BuiltInRegistries.ITEM.getKey(item);
        return key != null && COPPER_GEAR.contains(key.getPath());
    }

    private static boolean competesWithAny(Recipe<?> recipe, List<Recipe<?>> ours) {
        for (Recipe<?> mine : ours) {
            if (competes(recipe, mine)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 两条配方是否「抢同一次命中」：存在一张两边都认的网格 ⟺ 配方类型相同、尺寸相同，
     * 且<b>逐格材料集合两两有交集</b>（空槽要求两边都空）。
     *
     * <p>为什么不是「指纹完全相等」：本模组的手柄槽已经换成物品标签
     * （{@code #apocalypse_zombies:copper_handles} = 原版木棍 + 硬核生存的短木棍），
     * 与硬核生存那条只用 {@code minecraft:stick} 的同形配方<b>不再逐字相等，却仍然抢同一批网格</b>
     * —— 只要两格的材料集合有交集（{@code {stick, short_stick} ∩ {stick} ≠ ∅}）就是竞争者。
     * 这条口径同时泛化了 tag 对 item 的覆盖：谁的材料集合更宽都不会漏判。</p>
     *
     * <p><b>shaped 要连镜像摆法一起比</b>：{@code ShapedRecipe.matches} 对同一个图案会同时试正摆与
     * 镜像摆（{@code m_44170_(..., true/false)}），所以图案 P 与镜像(P) 的两条配方接受的是同一批
     * 网格 —— 它们互为竞争者。（铜斧 / 铜锄的镜像变体正是为这件事而存在，硬核生存那边同样是
     * {@code _1/_2} 一对。）</p>
     */
    private static boolean competes(Recipe<?> a, Recipe<?> b) {
        if (a instanceof ShapedRecipe sa && b instanceof ShapedRecipe sb) {
            int width = sa.getRecipeWidth();
            int height = sa.getRecipeHeight();
            if (width != sb.getRecipeWidth() || height != sb.getRecipeHeight()) {
                return false;
            }
            List<Set<String>> ca = cells(sa.getIngredients());
            List<Set<String>> cb = cells(sb.getIngredients());
            if (ca.size() != cb.size()) {
                return false;
            }
            return cellsOverlap(ca, cb, width, height, false)
                    || cellsOverlap(ca, cb, width, height, true);
        }
        if (a instanceof ShapelessRecipe la && b instanceof ShapelessRecipe lb) {
            // shapeless 与顺序无关：按材料集合的「多重集重叠」判（排序后逐位比）。
            List<Set<String>> ca = cells(la.getIngredients());
            List<Set<String>> cb = cells(lb.getIngredients());
            if (ca.size() != cb.size()) {
                return false;
            }
            ca.sort(java.util.Comparator.comparing(Object::toString));
            cb.sort(java.util.Comparator.comparing(Object::toString));
            for (int i = 0; i < ca.size(); i++) {
                if (Collections.disjoint(ca.get(i), cb.get(i))) {
                    return false;
                }
            }
            return true;
        }
        return false;
    }

    /**
     * 逐格比材料集合：{@code mirror} = 拿 a 的镜像摆法去对 b 的正摆法（镜像只作用在一侧 ——
     * 两侧同时镜像等于没镜像）。两边都空 = 一致；一边空一边有 = 不一致；都有则要求有交集
     * （注意 {@code Set.of().isEmpty()} 的空集与任何集合都 disjoint，"空集对空集"必须单独判，
     * 否则头盔 / 胸甲这类带空格的图案会被整条判成不抢同一批网格）。
     */
    private static boolean cellsOverlap(List<Set<String>> a, List<Set<String>> b,
                                        int width, int height, boolean mirror) {
        for (int row = 0; row < height; row++) {
            for (int col = 0; col < width; col++) {
                int i = row * width + (mirror ? width - 1 - col : col);
                int j = row * width + col;
                if (i >= a.size() || j >= b.size()) {
                    return false;
                }
                Set<String> x = a.get(i);
                Set<String> y = b.get(j);
                if (x.isEmpty() || y.isEmpty()) {
                    if (x.isEmpty() != y.isEmpty()) {
                        return false;
                    }
                    continue;
                }
                if (Collections.disjoint(x, y)) {
                    return false;
                }
            }
        }
        return true;
    }

    /** 逐格材料集合：该格子能接受的物品 id（{@code Ingredient.getItems()} 归一；空 = 空槽）。 */
    private static List<Set<String>> cells(NonNullList<Ingredient> ingredients) {
        List<Set<String>> out = new ArrayList<>(ingredients.size());
        for (Ingredient ingredient : ingredients) {
            out.add(ingredientItems(ingredient));
        }
        return out;
    }

    private static Set<String> ingredientItems(Ingredient ingredient) {
        ItemStack[] items = ingredient.getItems();
        if (items.length == 0) {
            return Set.of();
        }
        Set<String> ids = new HashSet<>();
        for (ItemStack stack : items) {
            ResourceLocation key = BuiltInRegistries.ITEM.getKey(stack.getItem());
            ids.add(key == null ? "?" : key.toString());
        }
        return ids;
    }
}
