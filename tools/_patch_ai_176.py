# -*- coding: utf-8 -*-
"""1.1.76 接线：Config 加 AI 段；ApocalypseCommand 加 `/apocalypse catgirl ai ...`。

用法：py tools/_patch_ai_176.py
"""
from pathlib import Path

NL = chr(10)
ROOT = Path("F:/mcmod/src/main/java/com/apocalypse/zombies")
CFG = ROOT / "Config.java"
CMD = ROOT / "command/ApocalypseCommand.java"
fails = []


def replace_once(path, old, new, tag):
    s = path.read_text(encoding="utf-8")
    if s.count(old) != 1:
        fails.append("%s | %s（命中 %d 次）" % (path.name, tag, s.count(old)))
        return
    path.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("  [OK] %s ← %s" % (path.name, tag))


def insert_after_last_import(path, prefix, lines, tag):
    src = path.read_text(encoding="utf-8").splitlines()
    idx = [i for i, l in enumerate(src) if l.startswith(prefix)]
    if not idx:
        fails.append("%s | %s：找不到 import 前缀 %s" % (path.name, tag, prefix))
        return
    at = idx[-1] + 1
    src[at:at] = lines
    path.write_text(NL.join(src) + NL, encoding="utf-8")
    print("  [OK] %s ← %s" % (path.name, tag))


# ------------------------------------------------------------------ Config：字段
CFG_FIELDS_OLD = NL.join([
    "    /** 护卫：主人挨打时贴过去站位。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ESCORT;",
])
CFG_FIELDS_NEW = CFG_FIELDS_OLD + NL + NL + NL.join([
    "    /** 本地 AI 助理：用本机的 Ollama 给她一张嘴（默认 qwen2 1.5B）。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AI_ENABLED;",
    "    /** 允许她把模型的话落地（切工种 / 下单做东西）。关掉就只剩聊天。 */",
    "    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_AI_ACTIONS;",
    "    /** Ollama 的地址（默认本机）。 */",
    "    public static final ForgeConfigSpec.ConfigValue<String> CAT_GIRL_AI_ENDPOINT;",
    "    /** 模型名，写 `ollama list` 里那个全名。 */",
    "    public static final ForgeConfigSpec.ConfigValue<String> CAT_GIRL_AI_MODEL;",
    "    /** 一轮最多等多久（毫秒）；超时不会崩游戏，只当她没听懂。 */",
    "    public static final ForgeConfigSpec.IntValue CAT_GIRL_AI_TIMEOUT_MS;",
    "    /** 上下文长度：KV 缓存越大越吃显存，4096 够她记住你说过的话和现状。 */",
    "    public static final ForgeConfigSpec.IntValue CAT_GIRL_AI_NUM_CTX;",
])

# ------------------------------------------------------------------ Config：定义
CFG_DEF_OLD = NL.join([
    "        CAT_GIRL_ESCORT = b.comment(\"护卫：主人被攻击时她会贴到主人与攻击者之间站住（打谁仍由目标选择器决定）。\")",
    "                .define(\"escort\", true);",
])
CFG_DEF_NEW = CFG_DEF_OLD + NL + NL + NL.join([
    "        b.comment(\"本地 AI 助理：用你机器上的 Ollama 让她听懂人话（/apocalypse catgirl ai <一句话>）。\",",
    "                        \"不联网、不花钱、离线也能用；连不上就当她没听懂，绝不会因此崩游戏。\")",
    "                .push(\"ai\");",
    "        CAT_GIRL_AI_ENABLED = b.comment(\"总开关。关掉后这个命令只会回一句「脑子关着」。\")",
    "                .define(\"enabled\", true);",
    "        CAT_GIRL_AI_ACTIONS = b.comment(\"允许她动手：把模型的提议落成「切工种 / 用她的材料下单做东西」。\",",
    "                        \"关掉 = 只能陪你说话，游戏状态一点不改（想先看看她怎么说话就关这个）。\")",
    "                .define(\"actions\", true);",
    "        CAT_GIRL_AI_ENDPOINT = b.comment(\"Ollama 地址。默认本机；指向别的机器前想清楚那是谁在替你算。\")",
    "                .define(\"endpoint\", \"http://127.0.0.1:11434\");",
    "        CAT_GIRL_AI_MODEL = b.comment(\"模型名，和 `ollama list` 里的一字不差。默认是 qwen2 1.5B。\")",
    "                .define(\"model\", \"fableforge-ai/nexus-coder:q4_k_m\");",
    "        CAT_GIRL_AI_TIMEOUT_MS = b.comment(\"一轮最多等多久（毫秒）。小模型一般 0.2~1 秒就回；等太久说明机器忙。\")",
    "                .defineInRange(\"timeout_ms\", 20000, 1000, 120000);",
    "        CAT_GIRL_AI_NUM_CTX = b.comment(\"上下文长度（KV 缓存）。4096 够用；显存紧就调小，别指望它能读完你的书。\")",
    "                .defineInRange(\"num_ctx\", 4096, 512, 32768);",
    "        b.pop();",
])

# ------------------------------------------------------------------ 命令树
CMD_TREE_OLD = NL.join([
    "                .then(Commands.literal(\"chest\")",
    "                        .executes(context -> catgirlChest(context.getSource(), false))",
    "                        .then(Commands.literal(\"clear\")",
    "                                .executes(context -> catgirlChest(context.getSource(), true)))));",
])
CMD_TREE_NEW = NL.join([
    "                .then(Commands.literal(\"chest\")",
    "                        .executes(context -> catgirlChest(context.getSource(), false))",
    "                        .then(Commands.literal(\"clear\")",
    "                                .executes(context -> catgirlChest(context.getSource(), true))))",
    "                .then(Commands.literal(\"ai\")",
    "                        .then(Commands.literal(\"status\")",
    "                                .executes(context -> catgirlAiStatus(context.getSource())))",
    "                        .then(Commands.argument(\"text\", StringArgumentType.greedyString())",
    "                                .executes(context -> catgirlAi(context.getSource(),",
    "                                        StringArgumentType.getString(context, \"text\"))))));",
])

# ------------------------------------------------------------------ 命令实现：挂在 catgirlChest 前面
CMD_METHODS_OLD = "    private static int catgirlChest(CommandSourceStack source, boolean clear) {"
CMD_METHODS_NEW = NL.join([
    "    /** {@code /apocalypse catgirl ai status}：端点、模型、熔断状态。 */",
    "    private static int catgirlAiStatus(CommandSourceStack source) {",
    "        source.sendSuccess(() -> Component.literal(LocalAiClient.statusLine()), false);",
    "        return 1;",
    "    }",
    "",
    "    /**",
    "     * {@code /apocalypse catgirl ai <一句话>}：把话交给本机模型，她回话、必要时动手。",
    "     *",
    "     * <p>这里只负责把话递出去（之后在工作线程上跑，结果用 server.execute 回投主线程），",
    "     * 所以命令本身立刻就返回，不会卡住服务器。</p>",
    "     */",
    "    private static int catgirlAi(CommandSourceStack source, String text) {",
    "        ServerPlayer player;",
    "        try {",
    "            player = source.getPlayerOrException();",
    "        } catch (Exception e) {",
    "            source.sendFailure(Component.literal(\"这个命令要玩家来跑（得认得出哪只是你的）。\"));",
    "            return 0;",
    "        }",
    "        CatGirlEntity cat = nearestOwned(source);",
    "        if (cat == null) {",
    "            source.sendFailure(Component.literal(\"16 格内没有你的猫耳娘。\"));",
    "            return 0;",
    "        }",
    "        LocalAiClient.ask(source.getServer(), player, cat, text.trim());",
    "        return 1;",
    "    }",
    "",
    CMD_METHODS_OLD,
])

replace_once(CFG, CFG_FIELDS_OLD, CFG_FIELDS_NEW, "AI 配置字段")
replace_once(CFG, CFG_DEF_OLD, CFG_DEF_NEW, "AI 配置定义")
replace_once(CMD, CMD_TREE_OLD, CMD_TREE_NEW, "catgirl ai 子命令")
replace_once(CMD, CMD_METHODS_OLD, CMD_METHODS_NEW, "catgirlAi/catgirlAiStatus 实现")
insert_after_last_import(CMD, "import com.apocalypse", ["import com.apocalypse.zombies.ai.LocalAiClient;"], "import LocalAiClient")
insert_after_last_import(CMD, "import net.minecraft.server.MinecraftServer", [], "MinecraftServer 已有则跳过")
# MinecraftServer 不存在时补一个
src = CMD.read_text(encoding="utf-8")
if "import net.minecraft.server.MinecraftServer;" not in src:
    insert_after_last_import(CMD, "import net.minecraft.server", ["import net.minecraft.server.MinecraftServer;"], "import MinecraftServer")
    src = CMD.read_text(encoding="utf-8")
src = CMD.read_text(encoding="utf-8")
if "import net.minecraft.server.level.ServerPlayer;" not in src:
    insert_after_last_import(CMD, "import net.minecraft.server", ["import net.minecraft.server.level.ServerPlayer;"], "import ServerPlayer")

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
