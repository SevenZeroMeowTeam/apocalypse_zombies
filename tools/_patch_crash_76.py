# -*- coding: utf-8 -*-
"""1.1.76 崩溃修复：TransientCraftingContainer 传 null 菜单 → setItem 立刻 NPE。

崩溃原文（F:/.minecraft/.../crash-reports/crash-2026-10-10_10.32.00-server.txt）：
    java.lang.NullPointerException: Cannot invoke "AbstractContainerMenu.m_6199_(Container)"
        because "this.f_286998_" is null
      at TransientCraftingContainer.m_6836_
      at CatGirlCrafting.layOut(CatGirlCrafting.java:162)
      at CatGirlCrafting.craftOrder(CatGirlCrafting.java:345)
      at CatGirlTradeMenu.updateOrder(CatGirlTradeMenu.java:232)
      at CatGirlTradeMenu.m_38946_ → ServerPlayer.m_8119_   ← 服务端 tick，整局崩

根因：grid() 故意 `new TransientCraftingContainer(null, 3, 3)`，但 setItem 内部就会回调
menu.slotsChanged(this)，菜单是 null 就 NPE。原注释以为「不调 setChanged 就没事」——错的。

另外两条兜底：订单路径跑在服务器 tick 里、自动制作跑在实体 tick 里，异常逃出去都会崩档，
所以各自加一层 try/catch + ERROR 日志。
"""
from pathlib import Path

NL = chr(10)
ROOT = Path("F:/mcmod/src/main/java/com/apocalypse/zombies")
CRAFT = ROOT / "entity/CatGirlCrafting.java"
MENU = ROOT / "entity/menu/CatGirlTradeMenu.java"
fails = []


def edit(path, pairs):
    s = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            fails.append("%s | no anchor: %s" % (path.name, old.strip().splitlines()[0][:70]))
            continue
        if s.count(old) != 1:
            fails.append("%s | anchor x%d: %s" % (path.name, s.count(old), old.strip().splitlines()[0][:70]))
            continue
        s = s.replace(old, new, 1)
    path.write_text(s, encoding="utf-8")
    print("  [OK] " + path.name)


# ------------------------------------------------------------------ CatGirlCrafting
OLD_GRID = NL.join([
    "    /**",
    "     * 她那张 3x3。<b>故意传 null 菜单</b>：{@code TransientCraftingContainer.setChanged()} 会回调",
    "     * {@code menu.slotsChanged}，所以下面一处都不调 {@code setChanged()} —— 只借它的 {@code getWidth/getHeight}。",
    "     */",
    "    private static TransientCraftingContainer grid() {",
    "        return new TransientCraftingContainer(null, 3, 3);",
    "    }",
])

NEW_GRID = NL.join([
    "    /**",
    "     * 她那张 3x3。<b>必须配一张菜单</b>：{@code TransientCraftingContainer.setItem()} 内部**就会**回调",
    "     * {@code menu.slotsChanged(this)}，菜单为 {@code null} 时第一次 {@code setItem} 立刻 NPE",
    "     * （1.1.75 就这么把服务端崩了：{@code layOut → TransientCraftingContainer.setItem}）。",
    "     * 所以这里给一张空壳菜单：它的 {@code slotsChanged} 走默认空实现，永远不碰真实窗口。",
    "     */",
    "    private static TransientCraftingContainer grid() {",
    "        return new TransientCraftingContainer(new GridMenu(), 3, 3);",
    "    }",
    "",
    "    /**",
    "     * 只为了满足 {@link TransientCraftingContainer} 的菜单回调契约而存在的假菜单：",
    "     * 不打开、不渲染、不持有玩家；{@code slotsChanged} 用默认空实现（这正是我们要的）。",
    "     */",
    "    private static final class GridMenu extends AbstractContainerMenu {",
    "",
    "        GridMenu() {",
    "            super(null, -1);",
    "        }",
    "",
    "        @Override",
    "        public ItemStack quickMoveStack(Player player, int index) {",
    "            return ItemStack.EMPTY;",
    "        }",
    "",
    "        @Override",
    "        public boolean stillValid(Player player) {",
    "            return true;",
    "        }",
    "    }",
])

OLD_TICK = NL.join([
    "    public static void tick(CatGirlEntity cat, ServerLevel level) {",
    "        long time = level.getGameTime();",
    "        if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get() && time % 40L == 0L) {",
    "            craftOne(cat, level);",
    "        }",
    "        if (com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get() && time % 60L == 0L) {",
    "            smeltOne(cat, level);",
    "        }",
    "    }",
])

NEW_TICK = NL.join([
    "    public static void tick(CatGirlEntity cat, ServerLevel level) {",
    "        long time = level.getGameTime();",
    "        try {",
    "            if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get() && time % 40L == 0L) {",
    "                craftOne(cat, level);",
    "            }",
    "            if (com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get() && time % 60L == 0L) {",
    "                smeltOne(cat, level);",
    "            }",
    "        } catch (RuntimeException e) {",
    "            // 这段跑在实体的服务端 tick 里：异常逃出去 = 把服务端一起带走。",
    "            // 记一条日志、这一拍跳过，下一拍再试 —— 别让某个奇怪配方毁掉存档。",
    "            LOGGER.error(\"cat_girl 自动制作/熔炼这一拍失败，跳过\", e);",
    "        }",
    "    }",
])

edit(CRAFT, [
    ("import net.minecraft.world.inventory.TransientCraftingContainer;",
     "import net.minecraft.world.inventory.AbstractContainerMenu;" + NL +
     "import net.minecraft.world.inventory.TransientCraftingContainer;"),
    ("import java.util.ArrayList;",
     "import com.mojang.logging.LogUtils;" + NL + "import org.slf4j.Logger;" + NL + NL +
     "import java.util.ArrayList;"),
    ("public final class CatGirlCrafting {" + NL + NL + "    private CatGirlCrafting() {",
     "public final class CatGirlCrafting {" + NL + NL +
     "    private static final Logger LOGGER = LogUtils.getLogger();" + NL + NL +
     "    private CatGirlCrafting() {"),
    (OLD_GRID, NEW_GRID),
    (OLD_TICK, NEW_TICK),
])

# ------------------------------------------------------------------ CatGirlTradeMenu
OLD_ORDER = NL.join([
    "        CatGirlCrafting.Result result = CatGirlCrafting.craftOrder(",
    "                this.catGirl, server, sample.copyWithCount(1), 1, this.player);",
])

NEW_ORDER = NL.join([
    "        CatGirlCrafting.Result result;",
    "        try {",
    "            result = CatGirlCrafting.craftOrder(this.catGirl, server, sample.copyWithCount(1), 1, this.player);",
    "        } catch (RuntimeException e) {",
    "            // 这条路径跑在服务端每 tick 的 broadcastChanges 里：异常逃出去 = 整个服务端崩",
    "            // （1.1.75 的崩溃就是这么出来的）。记日志、当作这次没做成，绝不带崩存档。",
    "            LOGGER.error(\"cat_girl 下单这一拍失败（样品 {}），跳过\", sample, e);",
    "            return;",
    "        }",
])

edit(MENU, [
    ("import net.minecraft.world.level.Level;",
     "import net.minecraft.world.level.Level;" + NL + NL + "import com.mojang.logging.LogUtils;"),
    ("import com.apocalypse.zombies.registry.ModMenus;",
     "import com.apocalypse.zombies.registry.ModMenus;" + NL + "import org.slf4j.Logger;"),
    ("    private final TransientCraftingContainer craftSlots;",
     "    private static final Logger LOGGER = LogUtils.getLogger();" + NL + NL +
     "    private final TransientCraftingContainer craftSlots;"),
    (OLD_ORDER, NEW_ORDER),
])

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
