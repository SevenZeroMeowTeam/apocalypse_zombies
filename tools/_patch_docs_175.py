# -*- coding: utf-8 -*-
"""docs/wiki 补 1.1.74 + 1.1.75（台账 / 类地图 / 脚本表 / 过期版本号）。"""
from pathlib import Path

NL = chr(10)
W = Path("F:/mcmod/docs/wiki")
fails = []


def edit(name, pairs):
    p = W / name
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            fails.append("%s | no anchor: %s" % (name, old.strip().splitlines()[0][:60]))
            continue
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("  [OK] " + name)


# ---------------------------------------------------------------- 07 台账
R73 = "| 1.1.73 | 猫耳娘会「接单」了：你说做哪件，她掏自己的料做给你。 |"
ROWS = R73 + NL + NL.join([
    "| 1.1.74 | 她会走路了：开门 / 浮水 / 绕开挡路的 / 自己跨过坑 / 跟着不被甩掉 |",
    "| 1.1.75 | 她有脑子了：自己挑活干（缺木伐木、缺矿挖矿、有敌人在你身边就上）+ 用你绑的箱子 + 挨打时贴过来站位 |",
])

NOTE_TAIL = NL.join([
    "> 无耐久 / 砸矿必掉 → 订做指定物品 / 3×3 摆放 / 盔甲渲染层（`CatGirlArmorLayer`，GeckoLib 的",
    "> `GeoArmorRenderer` 只服务 `GeoArmorItem`，对原版甲无效） / 内部熔炉 / 月亮三项（tint 对齐 CD + 血月主动刷怪）。",
])
NOTE_NEW = NOTE_TAIL + NL + NL.join([
    "> **1.1.74 → 1.1.75 是「像玩家一样操作」两批**：手和脚（自写 `CatGirlNavigation` 玩家式导航 +",
    "> `CatGirlClearWayGoal` 开路 + `CatGirlBridgeGoal` 搭桥 + 扫描半径 + 跟随速度走 Config）→",
    "> 脑子（`CatGirlNeedGoal` 需求调度 + `CatGirlContainerGoal` 用容器 + `CatGirlEscortGoal` 护卫 +",
    "> `/apocalypse catgirl auto|chest` 两个子命令）。**自主 ≠ 抢指挥**：需求 Goal 不带 MOVE/LOOK 标记、",
    "> 只改 `Job`，玩家一动手切工种（给工具 / 空手右键）那个个体就关掉自动模式。",
])

edit("07-出货与版本管理.md", [
    ("一版一个（已有 `_deploy_124.py` … `_deploy_173.py`）", "一版一个（已有 `_deploy_124.py` … `_deploy_175.py`）"),
    (R73, ROWS),
    (NOTE_TAIL, NOTE_NEW),
])

# ---------------------------------------------------------------- 02 类地图
ARMOR_ROW_TAIL = "| `client/renderer/CatGirlArmorLayer` | **1.1.73 新增**：把原版盔甲网格（内/外层 `HumanoidModel`）按骨骼包围盒贴到头部/躯干/四肢 |"
NEW_ROWS = ARMOR_ROW_TAIL + NL + NL.join([
    "| `entity/ai/CatGirlNavigation` | **1.1.74**：玩家式导航（`setCanOpenDoors`/`setCanPassDoors`/`setCanFloat`/`setAvoidSun(false)`）—— 原版跟班把门当墙、水当死路 |",
    "| `entity/ai/CatGirlClearWayGoal` | **1.1.74**：卡住才动手（`STUCK_TICKS`），只砸白名单自然方块（`MAX_HARDNESS` 3.0），绝不碰容器 / 方块实体 / 门 |",
    "| `entity/ai/CatGirlBridgeGoal` | **1.1.74**：垫脚只用背包里已有的实心方块，只铺正前方一格下一层，铺完重算路径 |",
    "| `entity/ai/CatGirlNeedGoal` | **1.1.75**：需求调度（每 40 tick）—— 有敌人在主人身边→`FIGHT` / 原木<8→`LUMBER` / 矿石<8→`MINE` / 都不缺→`FOLLOW`；**不带 MOVE/LOOK 标记**，只改 `Job` 不抢执行权 |",
    "| `entity/ai/CatGirlContainerGoal` | **1.1.75**：只对主人绑定的储物点开箱（没绑一个容器都不碰）；成品每种至少留一件，背包矿石<4 时取一组 |",
    "| `entity/ai/CatGirlEscortGoal` | **1.1.75**：主人被 `getLastHurtByMob` 命中时贴到主人与攻击者之间站住（打谁仍由目标选择器决定） |",
])

CFG_TAIL = NL.join([
    "- 1.1.73：`craft_fee`(2) / `smelt`(true) / `armor_render`(true) / `blood_moon_spawn`(true) /",
    "  `blood_moon_spawn_interval`(200) / `blood_moon_spawn_count`(2)",
])
CFG_NEW = CFG_TAIL + NL + NL.join([
    "- 1.1.74：`autonomy_radius`(32, 8–64) / `clear_way`(true) / `bridge`(true) / `follow_speed`(1.3, 0.5–2.0)",
    "- 1.1.75：`auto_job`(true) / `chest`(true) / `escort`(true)",
]) + NL + NL + "**命令**：`/apocalypse catgirl craft <物品id> [数量]`（订做）· `recipes <命名空间>`（配方表明细）· " + NL + \
    "`auto`（开关自主模式）· `chest [clear]`（绑定 / 解绑她的储物点）。"

edit("02-代码与资源地图.md", [
    (ARMOR_ROW_TAIL, NEW_ROWS),
    (CFG_TAIL, CFG_NEW),
])

# ---------------------------------------------------------------- 06 脚本表
DEPLOY_ROW = "| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_173.py` 是本轮最新） |"
DEPLOY_NEW = NL.join([
    "| `tools/_patch_catgirl_174a.py` | 1.1.74：挂 `CatGirlNavigation` + 三个新 Goal、跟随速度走 Config、`WorkBlockGoal` 半径取 `work_radius`/`autonomy_radius` 较大值 |",
    "| `tools/_prep_174.py` / `_prep_175.py` | 升版号（`gradle.properties` + readme 段 + 头表）+ 从上一版派生 `_deploy_<ver>.py` |",
    "| `tools/_patch_catgirl_175a.py` / `_175b.py` | 1.1.75：自主 / 容器 / 护卫三个 Goal 接线 + `/apocalypse catgirl auto|chest` 两个子命令 |",
    "| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_175.py` 是本轮最新） |",
])

edit("06-工具脚本手册.md", [
    ("## 1.1.66 → 1.1.73 新增/在用的脚本", "## 1.1.66 → 1.1.75 新增/在用的脚本"),
    ("## 5. 门禁（13 个，判据退出码）", "## 5. 门禁（16 个，判据退出码）"),
    (DEPLOY_ROW, DEPLOY_NEW),
])

# ---------------------------------------------------------------- 03 / 05 / 09 过期版本号
edit("03-构建运行与排障.md", [
    ("apocalypse_zombies-1.1.73.jar", "apocalypse_zombies-1.1.75.jar"),
])
edit("05-武器制作流程.md", [
    ("python tools/_deploy_173.py", "python tools/_deploy_175.py"),
])
edit("09-文档状态与待清理.md", [
    ("`mod_version = \"1.1.5\"`（当前 1.1.73）", "`mod_version = \"1.1.5\"`（当前 1.1.75）"),
    ("头表现在每版手升（当前 `1.1.73`）", "头表现在每版手升（当前 `1.1.75`）"),
])

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
