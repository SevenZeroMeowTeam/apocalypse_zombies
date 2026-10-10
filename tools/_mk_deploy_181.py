# -*- coding: utf-8 -*-
"""由 _deploy_180.py 生成 _deploy_181.py（版本号 / 头注释 / 1.1.81 断言段：玩家一键挖掘）。

只定点改写，不全局替换 —— _deploy_180.py 里大量的 1.1.80 是历史引用
（「1.1.80 起：她 36 格在面板内」），一起改就把历史抹了。
"""
import io

P180 = 'F:/mcmod/tools/_deploy_180.py'
P181 = 'F:/mcmod/tools/_deploy_181.py'
CR = '\r\n'


def L(*lines):
    return CR.join(lines) + CR


s = io.open(P180, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号 ----
rep("VER = '1.1.80'\r\nPREV = '1.1.79'", "VER = '1.1.81'\r\nPREV = '1.1.80'")
rep("_deploy_180.py", "_deploy_181.py", s.count("_deploy_180.py"))

# ---- 2) 头注释 ----
i = s.index('"""')  # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.81 出货：**玩家一键挖掘**（左键破坏即连带同种矿石 —— 不设按键 / 不加命令，',
    '全部行为只认配置 `[player_mine]`，默认开启）',
    '（含 1.1.80 的 36 格库存 / 手持物品方向 / 不垂直下钻 + 探矿，全部不回归）',
    '（含 1.1.79 的图形配置界面 / 一键挖掘上限 64 / id 参数修复全部不回归）',
    '（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_181.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_181.py                # 用 build/libs 里已构建好的包',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.81；',
    '  2. 猫耳娘该有的东西：',
    '     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、',
    '       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；',
    '     · textures/entity/cat_girl.png 是 128×128；',
    '     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；',
    '     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；',
    '  3. 1.1.81 本体（源码级 + 包内级）：',
    '     · 玩家一键挖掘：破坏事件（BlockEvent.BreakEvent，FORGE 总线）→ 同种方块 flood fill，',
    '       默认只认矿石（forge:ores）+ 深板岩变种算同一簇；',
    '     · 配置 [player_mine] 十项：enabled(true) / targets(0) / radius(16,4~64) /',
    '       max_blocks(64,1~64) / vein_only(true) / require_correct_tool(true) /',
    '       consume_durability(true) / sneak_disables(true) / to_inventory(true) / protected([])；',
    '       配置项总数 167（反射列给图形界面的那一份，声明顺序）；',
    '     · 安全边界与她那边共用 CatGirlHarvest.isMineable（容器 / 方块实体 / 保护名单 / 流体 /',
    '       火 / 硬度<0 一律不碰）；',
    '  4. **不回归**：1.1.80 的 36 格库存 / 手持物品基准旋转 / mine_depth 与 prospect；',
    '     柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 / 8 条片段长度逐条等于 Java 常量）；',
    '  5. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；',
    '  6. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；',
    '  7. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '',
    '(下面为原文，未改)',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 工具名 / 描述 / readme 版本断言 ----
rep("description='1.1.80 出货：36 格库存 + 手持物品方向'",
    "description='1.1.81 出货：玩家一键挖掘（左键破坏即连带同种矿石）'")
rep("check('| **当前版本** | `1.1.80` |' in _rd, 'readme 头表版本 == 1.1.80')",
    "check('| **当前版本** | `1.1.81` |' in _rd, 'readme 头表版本 == 1.1.81')")

# ---- 4) 新断言段：插在「工程门禁」之前 ----
NEW = L(
    "print('=== 13/9 1.1.81：玩家一键挖掘（破坏即连带同种矿石） ===')",
    "_vm9 = open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read()",
    "check('import net.minecraftforge.event.level.BlockEvent;' in _vm9",
    "      and 'BlockEvent.BreakEvent event' in _vm9,",
    "      '挂在原版破坏事件上（不是按键 / 不是命令）')",
    "check('Bus.FORGE' in _vm9 and '@SubscribeEvent' in _vm9, 'FORGE 总线订阅，服务端判定')",
    "check('Config.PLAYER_MINE_ENABLED.get()' in _vm9, '总开关读配置')",
    "check('player.isShiftKeyDown()' in _vm9 and 'PLAYER_MINE_SNEAK_DISABLES' in _vm9,",
    "      '潜行时只挖一格（经典 veinminer 手感）')",
    "check('CatGirlHarvest.isMineable' in _vm9 and 'CatGirlHarvest.isOre' in _vm9,",
    "      '安全判定与她那边共用一套（容器/方块实体/保护名单一律不碰）')",
    "check('deepslateTwin' in _vm9 and 'deepslate_' in _vm9,",
    "      '深板岩变种算同一簇（iron_ore ↔ deepslate_iron_ore）')",
    "check('tool.isCorrectToolForDrops(origin)' in _vm9, '工具不对口就不连带（require_correct_tool）')",
    "check('hurtAndBreak' in _vm9, '连带出来的每格扣耐久')",
    "check('Block.getDrops(state, level, pos, be, player, tool)' in _vm9,",
    "      '掉落走原版 getDrops（附魔/时运/精准采集都算数）')",
    "check('level.destroyBlock(pos, false)' in _vm9, '销毁时不重复掉东西（我们自己发产物）')",
    "check('getInventory().add' in _vm9 and 'player.drop(drop, false)' in _vm9,",
    "      '产物进背包，塞不下掉在脚下')",
    "check('clampMax' in _vm9 and 'Math.min(value, 64)' in _vm9, '上限硬夹到 64')",
    "",
    "_har9 = open(_p + 'entity/CatGirlHarvest.java', encoding='utf-8').read()",
    "check('public static boolean isOre(BlockState state)' in _har9,",
    "      'CatGirlHarvest 暴露 isOre（forge:ores 标签）给玩家那条链复用')",
    "",
    "_cfg9 = open(_p + 'Config.java', encoding='utf-8').read()",
    "import re as _re9",
    "_n9 = len(_re9.findall(r'public static final ForgeConfigSpec\\.[A-Za-z<>?,\\s\\.]+?\\s+[A-Z_0-9]+\\s*;', _cfg9))",
    "check(_n9 == 167, '配置项总数 167（1.1.80 的 157 + 玩家一键挖掘 10）', '实得 %d' % _n9)",
    "check('\\\"player_mine\\\"' in _cfg9, '新段落 player_mine')",
    "check('define(\\\"enabled\\\", true)' in _cfg9, '玩家一键挖掘默认开启')",
    "check('defineInRange(\\\"targets\\\", 0, 0, 2)' in _cfg9, '默认只连带矿石（targets 0，域 0~2）')",
    "check('defineInRange(\\\"radius\\\", 16, 4, 64)' in _cfg9, '半径默认 16（4~64）')",
    "check('defineInRange(\\\"max_blocks\\\", 64, 1, 64)' in _cfg9, '上限默认 64（1~64，与 1.1.79 同口径）')",
    "check('define(\\\"vein_only\\\", true)' in _cfg9, '默认只连带连通矿脉')",
    "check('define(\\\"require_correct_tool\\\", true)' in _cfg9, '默认要求工具对口')",
    "check('define(\\\"consume_durability\\\", true)' in _cfg9, '默认扣耐久')",
    "check('define(\\\"sneak_disables\\\", true)' in _cfg9, '默认潜行只挖一格')",
    "check('define(\\\"to_inventory\\\", true)' in _cfg9, '默认产物进背包')",
    "check('defineList(\\\"protected\\\", List.of()' in _cfg9, '追加保护名单（默认空）')",
    "for _k9 in ('PLAYER_MINE_ENABLED', 'PLAYER_MINE_TARGETS', 'PLAYER_MINE_RADIUS',",
    "            'PLAYER_MINE_MAX_BLOCKS', 'PLAYER_MINE_VEIN_ONLY', 'PLAYER_MINE_REQUIRE_TOOL',",
    "            'PLAYER_MINE_DURABILITY', 'PLAYER_MINE_SNEAK_DISABLES', 'PLAYER_MINE_TO_INVENTORY',",
    "            'PLAYER_MINE_PROTECTED'):",
    "    check(_k9 in _cfg9, 'Config 有字段 %s' % _k9)",
    "",
    "with zipfile.ZipFile(SRC) as _z9:",
    "    _vmcls = _z9.read('com/apocalypse/zombies/event/PlayerVeinMine.class') \\",
    "        if 'com/apocalypse/zombies/event/PlayerVeinMine.class' in names else b''",
    "    _cfgcls9 = _z9.read('com/apocalypse/zombies/Config.class') \\",
    "        if 'com/apocalypse/zombies/Config.class' in names else b''",
    "check(_vmcls != b'', 'PlayerVeinMine.class 进包了')",
    "for _lit9 in (b'player_mine', b'targets', b'vein_only', b'require_correct_tool',",
    "              b'consume_durability', b'sneak_disables', b'to_inventory'):",
    "    check(_lit9 in _cfgcls9, 'Config.class 内含配置名字面量 %s' % _lit9.decode())",
    "",
    "_rd9 = open('F:/mcmod/readme.md', encoding='utf-8').read()",
    "check('### 1.1.81 —' in _rd9, 'readme 有 1.1.81 更新日志条目')",
    "check('player_mine' in _rd9 and '一键挖掘' in _rd9, 'readme 写明玩家一键挖掘')",
    "check('targets' in _rd9 and 'sneak_disables' in _rd9 and 'deepslate' in _rd9,",
    "      'readme 写明 targets / 潜行 / 深板岩认亲')",
    "check('全部 167 项配置' in _rd9, 'readme 写明图形界面共 167 项')",
    "",
)
rep("print('=== 最后：工程门禁（本机实跑） ===')", NEW + "print('=== 最后：工程门禁（本机实跑） ===')")

io.open(P181, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P181, len(s), 'chars')
