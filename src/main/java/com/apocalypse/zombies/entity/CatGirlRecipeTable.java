package com.apocalypse.zombies.entity;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.logging.LogUtils;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.packs.resources.Resource;
import org.slf4j.Logger;

import java.io.Reader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * 猫耳娘的配方表：她「会做玩家能做的任何东西」这件事的依据表。
 *
 * <p>表由 {@code tools/cat_girl_recipes_sync.py} 从**原版 client.jar + 游戏实例所有模组 jar +
 * 本模组开发目录**自动抽取并归一化，落在
 * {@code data/apocalypse_zombies/cat_girl/recipes.json}，随 mod 一起打包。这里只负责读它，
 * 并且按服务器实例缓存 —— 换存档/重开服会重新读一次。</p>
 *
 * <p>表里每条只有「id / 来源 / 配方类型 / 产物 / 材料」，不做配方语义解析：判定「她做不做得出
 * 某个东西」用产物反查即可，真正的合成仍然交给原版 {@code RecipeManager}
 * （她的界面里那套 3x3 就是走原版配方，所以模组配方天然支持）。</p>
 */
public final class CatGirlRecipeTable {

    private static final Logger LOGGER = LogUtils.getLogger();
    private static final ResourceLocation TABLE_ID =
            new ResourceLocation("apocalypse_zombies", "cat_girl/recipes.json");

    /** 一条配方的最小信息。 */
    public record Entry(String id, String source, String type, String output, List<String> ingredients) {
        /** 命名空间（id 冒号前那段）。 */
        public String namespace() {
            int i = this.id.indexOf(':');
            return i < 0 ? this.id : this.id.substring(0, i);
        }

        /** 产物物品 id（去掉 xN 数量后缀）。 */
        public String outputItem() {
            int i = this.output.lastIndexOf(" x");
            return i < 0 ? this.output : this.output.substring(0, i);
        }
    }

    private static MinecraftServer cachedServer;
    private static List<Entry> entries = List.of();
    private static String digest = "";
    private static boolean present = false;

    private CatGirlRecipeTable() {
    }

    /** 懒加载 + 按服务器实例缓存。 */
    public static synchronized void ensureLoaded(MinecraftServer server) {
        if (server == null || server == cachedServer) {
            return;
        }
        cachedServer = server;
        entries = List.of();
        digest = "";
        present = false;

        Optional<Resource> resource = server.getResourceManager().getResource(TABLE_ID);
        if (resource.isEmpty()) {
            LOGGER.warn("[cat_girl] 没找到配方表 {}，先跑 py tools/cat_girl_recipes_sync.py 同步", TABLE_ID);
            return;
        }
        try (Reader reader = resource.get().openAsReader()) {
            JsonObject root = JsonParser.parseReader(reader).getAsJsonObject();
            digest = root.has("digest") ? root.get("digest").getAsString() : "";
            List<Entry> list = new ArrayList<>();
            JsonArray array = root.getAsJsonArray("recipes");
            if (array != null) {
                for (JsonElement element : array) {
                    JsonObject o = element.getAsJsonObject();
                    List<String> ingredients = new ArrayList<>();
                    if (o.has("in") && o.get("in").isJsonArray()) {
                        for (JsonElement ing : o.getAsJsonArray("in")) {
                            ingredients.add(ing.getAsString());
                        }
                    }
                    list.add(new Entry(
                            o.get("id").getAsString(),
                            o.has("src") ? o.get("src").getAsString() : "",
                            o.has("type") ? o.get("type").getAsString() : "?",
                            o.has("out") ? o.get("out").getAsString() : "?",
                            List.copyOf(ingredients)));
                }
            }
            entries = List.copyOf(list);
            present = true;
            LOGGER.info("[cat_girl] 配方表已载入：{} 条（指纹 {}）", entries.size(), digest);
        } catch (Exception ex) {
            LOGGER.error("[cat_girl] 配方表读取失败", ex);
        }
    }

    public static boolean isPresent() {
        return present;
    }

    public static String digest() {
        return digest;
    }

    public static List<Entry> all() {
        return entries;
    }

    public static int size() {
        return entries.size();
    }

    /** 按命名空间计数（表里天然知道哪些模组供了多少配方）。 */
    public static Map<String, Integer> byNamespace() {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (Entry e : entries) {
            map.merge(e.namespace(), 1, Integer::sum);
        }
        return map;
    }

    /** 有配方进表的来源 jar 数量（原版算 1）。 */
    public static Map<String, Integer> bySource() {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (Entry e : entries) {
            map.merge(e.source(), 1, Integer::sum);
        }
        return map;
    }

    /** 按产物模糊查：找出所有「能做出这些东西」的配方。 */
    public static List<Entry> find(String outputQuery) {
        String q = outputQuery.toLowerCase(Locale.ROOT);
        List<Entry> hits = new ArrayList<>();
        for (Entry e : entries) {
            if (e.outputItem().toLowerCase(Locale.ROOT).contains(q)) {
                hits.add(e);
            }
        }
        return hits;
    }
}
