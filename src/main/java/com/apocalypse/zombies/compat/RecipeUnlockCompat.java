package com.apocalypse.zombies.compat;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;

import java.util.ArrayList;
import java.util.List;

/**
 * 登录即把本模组的配方写进玩家配方书 —— 「限制合成」世界里的必需品。
 *
 * <p><b>病根</b>：游戏规则 {@code doLimitedCrafting=true}（硬核生存类玩法/整合包的常见设定）下，
 * 原版 {@code CraftingMenu} 算合成结果前要过一道闸：
 * {@code RecipeHolder.setRecipeUsed(Level, ServerPlayer, Recipe)} —— 配方要么是 {@code special} 的
 * （数据驱动的 shaped/shapeless 都不是），要么<b>已经躺在玩家的配方书里</b>，否则直接返回 false、
 * 产物槽留空。玩家看到的现象就是：材料摆得完全正确、服务端也认得这个配方（探针实测可命中、可装配），
 * 但产物槽里什么都没有，点了也取不出来 —— 而原版物品能合，因为它们的配方早就解锁了。</p>
 *
 * <p><b>正规解法是「配方解锁进度」</b>：本模组已在
 * {@code data/apocalypse_zombies/advancements/recipes/} 里给全部 18 条配方配了解锁文件 —— 拿到铜锭
 * （工具另需一根棍）就自动解锁，配方书里会列出，限制合成下即可合成。</p>
 *
 * <p>这个类补的是<b>既有存档</b>：玩家进世界的那一刻就把本模组现有配方一次性写入配方书，
 * 不用等下一次背包变动去触发进度判定。只解锁 {@code apocalypse_zombies} 命名空间下的配方，
 * 原版与其它模组一概不碰；配方书已有的条目由原版自行去重。</p>
 */
public final class RecipeUnlockCompat {

    private RecipeUnlockCompat() {
    }

    /** 主类构造里调用：把本类挂到 FORGE 总线上（与 {@code CopperGearRecipeCompat} 同一条路）。 */
    public static void register() {
        net.minecraftforge.common.MinecraftForge.EVENT_BUS.register(RecipeUnlockCompat.class);
    }

    @SubscribeEvent
    public static void onPlayerLoggedIn(PlayerEvent.PlayerLoggedInEvent event) {
        try {
            if (!(event.getEntity() instanceof ServerPlayer player)) {
                return;
            }
            MinecraftServer server = player.getServer();
            if (server == null) {
                return;
            }
            List<ResourceLocation> ids = new ArrayList<>();
            for (Recipe<?> recipe : server.getRecipeManager().getRecipes()) {
                if (ApocalypseZombies.MOD_ID.equals(recipe.getId().getNamespace())) {
                    ids.add(recipe.getId());
                }
            }
            if (!ids.isEmpty()) {
                player.awardRecipesByKey(ids.toArray(new ResourceLocation[0]));
            }
        } catch (Exception e) {
            // 解锁失败不该拦着玩家进世界：记一行，照常继续。
            ApocalypseZombies.LOGGER.warn("[配方解锁] 登录时写入本模组配方未完成。", e);
        }
    }
}
