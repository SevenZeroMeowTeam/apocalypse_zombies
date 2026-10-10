# -*- coding: utf-8 -*-
"""1.1.70：配方表接进游戏 —— 猫耳娘能读到「游戏里所有能做的配方」+ /apocalypse catgirl recipes。"""
import re
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'
ROOT = Path('.')

# ---------- ① 配方表读取器 ----------
Path(J + 'entity/CatGirlRecipeTable.java').write_text('''package com.apocalypse.zombies.entity;

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
''', encoding='utf-8')
print('(1) entity/CatGirlRecipeTable.java 新建')

# ---------- ② 命令：/apocalypse catgirl recipes ----------
p = Path(J + 'command/ApocalypseCommand.java')
s = p.read_text(encoding='utf-8')
anchor = '        dispatcher.register(root);'
assert anchor in s, '命令注册入口没找到'
block = '''        root.then(Commands.literal("catgirl")
                .then(Commands.literal("recipes")
                        .executes(context -> recipeReport(context.getSource(), null))
                        .then(Commands.argument("namespace", StringArgumentType.string())
                                .executes(context -> recipeReport(context.getSource(),
                                        StringArgumentType.getString(context, "namespace"))))));

''' + anchor
s = s.replace(anchor, block, 1)

# 实现体：追加到类尾（最后一个 } 之前）
impl = '''
    /** 猫耳娘配方表：总数 / 来源 / 命名空间；给了命名空间就列出它名下的配方。 */
    private static int recipeReport(CommandSourceStack source, String namespace) {
        CatGirlRecipeTable.ensureLoaded(source.getServer());
        if (!CatGirlRecipeTable.isPresent()) {
            source.sendFailure(Component.literal(
                    "配方表没载入 —— 跑 py tools/cat_girl_recipes_sync.py 同步后再重进世界"));
            return 0;
        }
        if (namespace != null) {
            List<CatGirlRecipeTable.Entry> hits = CatGirlRecipeTable.all().stream()
                    .filter(e -> e.namespace().equalsIgnoreCase(namespace))
                    .toList();
            source.sendSuccess(() -> Component.literal(
                    "命名空间 " + namespace + "： " + hits.size() + " 条配方"), false);
            for (CatGirlRecipeTable.Entry e : hits.stream().limit(20).toList()) {
                source.sendSuccess(() -> Component.literal(
                        "  " + e.output() + "  <- " + String.join(", ", e.ingredients())
                                + "   [" + e.type() + "]"), false);
            }
            if (hits.size() > 20) {
                source.sendSuccess(() -> Component.literal("  … 另有 " + (hits.size() - 20) + " 条"), false);
            }
            return hits.size();
        }

        StringBuilder sb = new StringBuilder();
        sb.append("猫耳娘配方表：").append(CatGirlRecipeTable.size()).append(" 条");
        sb.append("，指纹 ").append(CatGirlRecipeTable.digest());
        source.sendSuccess(() -> Component.literal(sb.toString()), false);

        var bySource = CatGirlRecipeTable.bySource();
        source.sendSuccess(() -> Component.literal("来源 " + bySource.size() + " 个："), false);
        bySource.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(12)
                .forEach(e -> source.sendSuccess(() -> Component.literal(
                        "  " + e.getKey() + " —— " + e.getValue() + " 条"), false));

        var byNs = CatGirlRecipeTable.byNamespace();
        source.sendSuccess(() -> Component.literal("命名空间 " + byNs.size() + " 个："), false);
        byNs.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(20)
                .forEach(e -> source.sendSuccess(() -> Component.literal(
                        "  " + e.getKey() + " —— " + e.getValue() + " 条"), false));
        source.sendSuccess(() -> Component.literal(
                "  /apocalypse catgirl recipes <命名空间> 看明细"), false);
        return CatGirlRecipeTable.size();
    }
'''
idx = s.rstrip().rfind('}')
s = s[:idx] + impl + s[idx:]
if 'import com.apocalypse.zombies.entity.CatGirlRecipeTable;' not in s:
    s = s.replace('import com.apocalypse.zombies.entity.HordeOverlord;',
                  'import com.apocalypse.zombies.entity.CatGirlRecipeTable;\nimport com.apocalypse.zombies.entity.HordeOverlord;', 1)
p.write_text(s, encoding='utf-8')
print('(2) ApocalypseCommand：/apocalypse catgirl recipes 已挂')

# ---------- ③ 版本 ----------
g = Path('gradle.properties'); t = g.read_text(encoding='utf-8')
assert 'mod_version=1.1.69' in t
g.write_text(t.replace('mod_version=1.1.69', 'mod_version=1.1.70'), encoding='utf-8')
print('(3) mod_version=1.1.70')

# ---------- ④ 出货脚本 170 ----------
src = Path('tools/_deploy_169.py').read_text(encoding='utf-8')
src = src.replace('1.1.69', '1.1.70').replace('1.1.68', '1.1.69')
src = src.replace('"""1.1.70 出货：猫耳娘「工具即指令」（斧→伐木 / 镐→挖矿 / 剑·弓→打怪 + 弓会放箭）',
                  '"""1.1.70 出货：猫耳娘配方表（自动同步原版 + 全部模组配方）')
anchor = "print('=== 3/5 不回归：柯尔特 1878（1.1.69 内容不许被冲掉） ===')"
assert anchor in src, '锚点不对（要用替换后的 1.1.69 文案）'
block = r'''# ---- 配方表：表在、与当前游戏一致（真同步）、读取器与命令都进了包 ----
import subprocess
tbl = pathlib.Path('F:/mcmod/src/main/resources/data/apocalypse_zombies/cat_girl/recipes.json')
check(tbl.is_file() and tbl.stat().st_size > 10000, '装机配方表在（%s KB）' % (tbl.stat().st_size // 1024 if tbl.is_file() else 0))
sync = subprocess.run([sys.executable, 'F:/mcmod/tools/cat_girl_recipes_sync.py', '--check'],
                      capture_output=True, text=True, cwd='F:/mcmod')
check(sync.returncode == 0, '配方表与当前游戏一致（--check 通过）—— %s' % (sync.stdout.strip() or sync.stderr.strip())[:120])
cgsrc2 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlRecipeTable.java', encoding='utf-8').read()
check('cat_girl/recipes.json' in cgsrc2, '读取器指向装机配方表')
cmdsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/command/ApocalypseCommand.java', encoding='utf-8').read()
check('"catgirl"' in cmdsrc and 'recipeReport' in cmdsrc, '/apocalypse catgirl recipes 命令在')

'''
src = src.replace(anchor, block + anchor, 1)
if 'import sys' not in src:
    src = 'import sys\n' + src
Path('tools/_deploy_170.py').write_text(src, encoding='utf-8')
import py_compile
py_compile.compile('tools/_deploy_170.py', doraise=True)
print('(4) tools/_deploy_170.py OK')

# ---------- ⑤ readme ----------
p = Path('readme.md'); s = p.read_text(encoding='utf-8')
s = s.replace('| **当前版本** | `1.1.69` |', '| **当前版本** | `1.1.70` |', 1)
entry = """### 1.1.70 — 2026-10-10

**猫耳娘配方表：自动同步游戏里所有能做得出来的东西**

- 新增 `tools/cat_girl_recipes_sync.py`：自动发现并抽取**原版 `client.jar` +
  游戏实例 `mods/` 下每一个 jar + 本模组开发目录**里的配方（`data/<ns>/recipes/**.json`），
  归一化成「id / 来源 / 类型 / 产物 / 材料」四要素，按 id 排序、算内容指纹。
  只认真配方文件，`advancements/recipes/`（进度）与 `datapacks/bundle/`（实验数据包）自动排除。
- 产出三份：主表 `art/cat_girl/recipes_all.json`、汇总 `art/cat_girl/recipes_summary.md`、
  装机副本 `data/apocalypse_zombies/cat_girl/recipes.json`（随 mod 打包，运行时读）。
  幂等可复跑，`--check` 用指纹判定「盘上的表是否还跟游戏一致」（不一致 exit 1，已接入出货门禁）。
- 新增 `CatGirlRecipeTable`：从资源管理器载入装机表，按服务器实例缓存，暴露总数 / 来源 /
  命名空间 / 按产物反查 —— 这是她「会做玩家能做的任何东西」的依据表；
  真正合成仍走原版 `RecipeManager`，所以模组配方天然支持。
- 新增调试命令：`/apocalypse catgirl recipes`（总数 + 内容来源 + 命名空间分布）、
  `/apocalypse catgirl recipes <命名空间>`（列明细，最多 20 条）。

**当前实机数据**：1 433 条配方（原版 1 174 + 模组 259），命名空间 10 个，
供了配方的模组 9 个（sophisticatedbackpacks 84、crafting-dead-core 83、Jennycraft 34、
hexalunar_calamity 24、tacz 11 …）。指纹 `644faf82cd9b7035`。

"""
if '### 1.1.69 — 2026-10-10' in s and '### 1.1.70' not in s:
    s = s.replace('### 1.1.69 — 2026-10-10', entry + '### 1.1.69 — 2026-10-10', 1)
p.write_text(s, encoding='utf-8')
print('(5) readme.md 1.1.70')
