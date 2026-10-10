# -*- coding: utf-8 -*-
"""1.1.75：/apocalypse catgirl auto + chest 两个子命令。"""
from pathlib import Path

NL = chr(10)
fails = []


def edit(path, pairs, label):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            fails.append("%s ｜ no anchor: %s" % (label, old.strip().splitlines()[0][:70]))
            continue
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("  [OK] " + label)


CMD = "F:/mcmod/src/main/java/com/apocalypse/zombies/command/ApocalypseCommand.java"

CHAIN_OLD = NL.join([
    "                                .executes(context -> recipeReport(context.getSource(),",
    "                                        StringArgumentType.getString(context, \"namespace\"))))));",
])
CHAIN_NEW = NL.join([
    "                                .executes(context -> recipeReport(context.getSource(),",
    "                                        StringArgumentType.getString(context, \"namespace\")))))",
    "                .then(Commands.literal(\"auto\")",
    "                        .executes(context -> catgirlAuto(context.getSource())))",
    "                .then(Commands.literal(\"chest\")",
    "                        .executes(context -> catgirlChest(context.getSource(), false))",
    "                        .then(Commands.literal(\"clear\")",
    "                                .executes(context -> catgirlChest(context.getSource(), true)))));",
])
# 注意：原来最后是 4 个右括号 + '));' —— 这里把 'recipes' 链的收尾从 4 个括号减到 4 个再挂新链
CHAIN_NEW = CHAIN_NEW.replace("(context, \"namespace\")))))", "(context, \"namespace\"))))")

HELPERS = NL.join([
    "    /**",
    "     * {@code /apocalypse catgirl auto} —— 开关她的自主模式。",
    "     *",
    "     * <p>开着时她自己按需求挑活干（缺木→伐木、缺矿→挖矿、有敌人在主人身边→打）；",
    "     * 你一旦手动给她切过工种（给工具 / 空手右键）这个个体就自动关了，用这条再打开。</p>",
    "     */",
    "    private static int catgirlAuto(CommandSourceStack source) {",
    "        CatGirlEntity girl = nearestOwned(source);",
    "        if (girl == null) {",
    "            return 0;",
    "        }",
    "        boolean next = !girl.isAutoJob();",
    "        girl.setAutoJob(next);",
    "        if (next) {",
    "            source.sendSuccess(() -> Component.literal(",
    "                    \"自动模式：开 —— 她自己按需求挑活干（缺木伐木 / 缺矿挖矿 / 有敌人在你身边就上）。\"), false);",
    "        } else {",
    "            source.sendSuccess(() -> Component.literal(",
    "                    \"自动模式：关 —— 她只干你指定的活（给工具或空手右键切工种；命令切不会关自动模式）。\"), false);",
    "        }",
    "        return 1;",
    "    }",
    "",
    "    /**",
    "     * {@code /apocalypse catgirl chest [clear]} —— 绑定 / 解绑她的储物点。",
    "     *",
    "     * <p>她的「储物点」只能这么绑（原版分不出哪个箱子是玩家的）：绑定后她会把多余的成品",
    "     * 收进去、背包里缺矿石时从那里取一组；<b>没绑她一个容器都不碰</b>。</p>",
    "     */",
    "    private static int catgirlChest(CommandSourceStack source, boolean clear) {",
    "        CatGirlEntity girl = nearestOwned(source);",
    "        if (girl == null) {",
    "            return 0;",
    "        }",
    "        if (clear) {",
    "            girl.setStorage(null);",
    "            source.sendSuccess(() -> Component.literal(\"储物点已解绑 —— 她不会再碰任何容器。\"), false);",
    "            return 1;",
    "        }",
    "        net.minecraft.core.BlockPos found = null;",
    "        for (net.minecraft.core.BlockPos pos : net.minecraft.core.BlockPos.betweenClosed(",
    "                girl.blockPosition().offset(-6, -2, -6), girl.blockPosition().offset(6, 2, 6))) {",
    "            if (girl.level().getBlockEntity(pos) instanceof net.minecraft.world.Container) {",
    "                found = pos.immutable();",
    "                break;",
    "            }",
    "        }",
    "        if (found == null) {",
    "            source.sendFailure(Component.literal(",
    "                    \"她附近 6 格内没有容器（箱子 / 木桶 / 潜影盒……）—— 先把她带到箱子旁边。\"));",
    "            return 0;",
    "        }",
    "        girl.setStorage(found);",
    "        String at = found.getX() + \", \" + found.getY() + \", \" + found.getZ();",
    "        source.sendSuccess(() -> Component.literal(\"储物点已绑定到 \" + at",
    "                + \" —— 她会把多余成品收进去，缺矿石时从那里取；换绑定就再跑一次。\"), false);",
    "        return 1;",
    "    }",
    "",
    "    /** 16 格内最近的、属于命令发起者的猫耳娘；没有就发失败消息并返回 null。 */",
    "    private static CatGirlEntity nearestOwned(CommandSourceStack source) {",
    "        ServerPlayer player;",
    "        try {",
    "            player = source.getPlayerOrException();",
    "        } catch (Exception e) {",
    "            source.sendFailure(Component.literal(\"这个命令要玩家来跑（得认得出哪只是你的）。\"));",
    "            return null;",
    "        }",
    "        CatGirlEntity girl = player.level().getEntitiesOfClass(CatGirlEntity.class,",
    "                        player.getBoundingBox().inflate(16.0D), cat -> cat.isOwnedBy(player))",
    "                .stream()",
    "                .min(java.util.Comparator.comparingDouble(cat -> cat.distanceToSqr(player)))",
    "                .orElse(null);",
    "        if (girl == null) {",
    "            source.sendFailure(Component.literal(\"16 格内没有你的猫耳娘。\"));",
    "        }",
    "        return girl;",
    "    }",
    "",
    "    private static int recipeReport(CommandSourceStack source, String namespace) {",
])

edit(CMD, [
    (CHAIN_OLD, CHAIN_NEW),
    ("    private static int recipeReport(CommandSourceStack source, String namespace) {", HELPERS),
], "ApocalypseCommand")

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
