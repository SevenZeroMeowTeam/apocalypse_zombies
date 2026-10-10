# -*- coding: utf-8 -*-
"""由 _deploy_179.py 生成 _deploy_180.py（版本号 / 头注释 / 1.1.80 断言段）。"""
import io

P179 = 'F:/mcmod/tools/_deploy_179.py'
P180 = 'F:/mcmod/tools/_deploy_180.py'
CR = '\r\n'


def L(*lines):
    return CR.join(lines) + CR


s = io.open(P179, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号 ----
rep("VER = '1.1.79'\r\nPREV = '1.1.78'", "VER = '1.1.80'\r\nPREV = '1.1.79'")
rep("_deploy_179.py", "_deploy_180.py", s.count("_deploy_179.py"))
rep("1.1.79 出货：配置界面 + 一键挖掘上限 64", "1.1.80 出货：36 格库存 + 手持物品方向")

# ---- 2) 头注释 ----
head = L(
    '"""1.1.80 出货：**她的库存扩到 36 格（背包 27 + 物品栏 9）** + **修「手里的东西方向不对」**',
    '（带上 1.1.80 已批准的另一半：自主挖矿不再垂直下钻 —— `mine_depth` 默认 1 + `prospect` 探矿）',
    '（含 1.1.79 的图形配置界面 / 一键挖掘上限 64 / id 参数修复全部不回归）',
    '（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_180.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_180.py                # 用 build/libs 里已构建好的包',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.80；',
    '  2. 猫耳娘该有的东西：',
    '     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、',
    '       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；',
    '     · textures/entity/cat_girl.png 是 128×128；',
    '     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；',
    '     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；',
    '  3. 1.1.80 本体（源码级 + 包内级）：',
    '     · 库存 36 格：实体 GOODS_HOTBAR / GOODS_BACKPACK / GOODS_SIZE 三件套；菜单槽位坐标',
    '       只有一个算法 goodsSlotX/Y（背包 27 在上三行、物品栏 9 在最下一行）；玩家 27 格移出',
    '       面板（PLAYER_ROW_Y = 10000，仍注册，shift 搬货照旧）；',
    '     · 手持物品：渲染器补上原版 ItemInHandLayer 的手部基准旋转（XP -90° / YP 180°），',
    '       并留 held_item_mirror 开关 —— 缺那两步时平物品会立成一张牌子（就是「方向不对」）；',
    '     · 自主挖矿：mine_depth 默认 1（不许垂直下钻）+ mine_order_depth 默认 6（订单单独算）',
    '       + prospect / prospect_tries / prospect_step 探矿三件套；',
    '  4. **不回归**：柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 /',
    '     8 条片段长度逐条等于 Java 常量）；',
    '  5. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；',
    '  6. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；',
    '  7. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
i = s.index('"""')  # 文件第一个三引号 = 头部 docstring
j = s.index('"""', s.index('\n', i)) + 3
s = s[:i] + head + s[j:]

# ---- 3) 旧布局断言（1.1.72 那两处） ----
rep(L("check('PLAYER_ROW_Y' in menusrc and 'HOTBAR_Y' in menusrc,",
      "      '玩家 27 格回到面板内（原版 9 列布局）')"),
    L("check('PLAYER_ROW_Y' in menusrc and 'HOTBAR_Y' in menusrc and 'goodsSlotY' in menusrc,",
      "      '库存槽位坐标与玩家行常量都在（1.1.80 起：她 36 格在面板内、玩家 27 格在面板外）')"))

rep(L("menusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()",
      "check('PLAYER_ROW_Y = 142' in menusrc and 'PANEL_HEIGHT = 226' in menusrc and 'HIDDEN_PLAYER_Y' not in menusrc,",
      "      '玩家 27 格回到面板内（原版 9 列布局，面板 226）')",
      "scr = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()",
      "check('PLAYER_ROW_Y - 6' in scr, '玩家背包分隔线在')"),
    L("menusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()",
      "check('PANEL_HEIGHT = 226' in menusrc",
      "      and 'GOODS_HOTBAR_Y = GOODS_Y + GOODS_BACKPACK / 9 * SLOT_PITCH + 4' in menusrc,",
      "      '她的 4 行排布在（背包 3 行 + 物品栏 1 行，面板仍 226）')",
      "scr = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()",
      "check('cat_girl.trade.stock' in scr and 'CatGirlTradeMenu.goodsSlotY(i)' in scr,",
      "      '界面按同一个槽位算法标价格（菜单 / 界面同源）')"))

# ---- 4) readme 版本行 ----
rep("check('| **当前版本** | `1.1.79` |' in _rd, 'readme 头表版本 == 1.1.79')",
    "check('| **当前版本** | `1.1.80` |' in _rd, 'readme 头表版本 == 1.1.80')")

# ---- 5) 新段：1.1.80 ----
sec = L(
    "print('=== 12/9 1.1.80：库存 36 格 + 手里的东西方向 ===')",
    "_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'",
    "_ent8 = open(_p + 'entity/CatGirlEntity.java', encoding='utf-8').read()",
    "check('public static final int GOODS_HOTBAR = 9;' in _ent8",
    "      and 'public static final int GOODS_BACKPACK = 27;' in _ent8",
    "      and 'public static final int GOODS_SIZE = GOODS_HOTBAR + GOODS_BACKPACK;' in _ent8,",
    "      '她 36 格 = 物品栏 9 + 背包 27（与玩家同款排布）')",
    "check('new SimpleContainer(GOODS_SIZE)' in _ent8, '库存容器真按 36 格建（不是只改常量）')",
    "_menu8 = open(_p + 'entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()",
    "check('GOODS_COUNT = CatGirlEntity.GOODS_SIZE' in _menu8, '菜单槽位数跟着 36 走')",
    "check('public static int goodsSlotX(int index)' in _menu8",
    "      and 'public static int goodsSlotY(int index)' in _menu8,",
    "      '槽位坐标只有一个算法（菜单与界面共用，不许两份）')",
    "check('if (index < CatGirlEntity.GOODS_HOTBAR)' in _menu8,",
    "      '物品栏 9 格排最后一行（背包 27 在上面三行）')",
    "check('PLAYER_ROW_Y = 10000' in _menu8, '玩家 27 格移出面板（槽位仍注册，shift 搬货照旧）')",
    "_scr8 = open(_p + 'client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()",
    "check('getGoods().getItem(i)' in _scr8 and 'goodsSlotY(i)' in _scr8,",
    "      '界面把价格标在每格右下角（36 格都标）')",
    "check('GOODS_HOTBAR_Y - 3' in _scr8, '背包 / 物品栏之间画了分组细线')",
    "for _lf in ('en_us.json', 'zh_cn.json'):",
    "    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()",
    "    check('cat_girl.trade.stock' in _ls and '%1$s' in _ls and '%2$s' in _ls,",
    "          'lang %s 的库存标题带两个参数（27 / 9）' % _lf)",
    "",
    "_ren8 = open(_p + 'client/renderer/CatGirlGeoRenderer.java', encoding='utf-8').read()",
    "check('poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F))' in _ren8",
    "      and 'poseStack.mulPose(Axis.YP.rotationDegrees(180.0F))' in _ren8,",
    "      '补上原版 ItemInHandLayer 的手部基准旋转（XP -90 / YP 180）—— 缺它就是「方向不对」')",
    "check('renderStackForBone' in _ren8 and 'THIRD_PERSON_RIGHT_HAND' in _ren8",
    "      and 'THIRD_PERSON_LEFT_HAND' in _ren8,",
    "      '物品在手骨骼矩阵里自己画（左右手两条 display 上下文都在）')",
    "check('Config.CAT_GIRL_HELD_ITEM_MIRROR' in _ren8, '镜像开关接在渲染器上')",
    "check('ITEM_BONE = \"item_righthand\"' in _ren8, '挂点骨骼仍是 geo 里的 item_righthand')",
    "",
    "_cfg8 = open(_p + 'Config.java', encoding='utf-8').read()",
    "for _k in ('\"mine_depth\"', '\"mine_order_depth\"', '\"prospect\"', '\"prospect_tries\"',",
    "           '\"prospect_step\"', '\"held_item_mirror\"'):",
    "    check(_k in _cfg8, 'Config 有 1.1.80 项 %s' % _k)",
    "check('defineInRange(\"mine_depth\", 1, 0, 8)' in _cfg8, '自主挖矿默认只下探 1 格（0~8）')",
    "check('defineInRange(\"mine_order_depth\", 6, 0, 16)' in _cfg8, '订单允许下探 6 格（0~16）')",
    "check('define(\"prospect\", true)' in _cfg8, '探矿默认开')",
    "check('defineInRange(\"prospect_tries\", 6, 1, 32)' in _cfg8, '空手 6 次就回主人身边')",
    "check('defineInRange(\"prospect_step\", 8, 2, 32)' in _cfg8, '探点步长 8 格')",
    "check('define(\"held_item_mirror\", false)' in _cfg8, '镜像默认关（= 原版右手拿法）')",
    "",
    "_wb8 = open(_p + 'entity/ai/WorkBlockGoal.java', encoding='utf-8').read()",
    "check('CAT_GIRL_MINE_ORDER_DEPTH.get() : Config.CAT_GIRL_MINE_DEPTH.get()' in _wb8,",
    "      '自主 / 订单两条下探深度分开取（订单是主人点名的活）')",
    "check('Config.CAT_GIRL_PROSPECT.get()' in _wb8 and 'CAT_GIRL_PROSPECT_TRIES' in _wb8",
    "      and 'CAT_GIRL_PROSPECT_STEP' in _wb8, '探矿三件套都接在劳作目标里')",
    "",
    "# —— 包内级：新配置项的字面量必须真进了 Config.class",
    "_cfgcls = z.read('com/apocalypse/zombies/Config.class') if 'com/apocalypse/zombies/Config.class' in names else b''",
    "for _lit in (b'mine_depth', b'mine_order_depth', b'prospect_step', b'held_item_mirror'):",
    "    check(_lit in _cfgcls, 'Config.class 内含配置名字面量 %s' % _lit.decode())",
    "",
    "_rd8 = open('F:/mcmod/readme.md', encoding='utf-8').read()",
    "check('### 1.1.80 —' in _rd8, 'readme 有 1.1.80 更新日志条目')",
    "check('36 格' in _rd8 and '背包 27' in _rd8, 'readme 写明库存 36 格（背包 27 + 物品栏 9）')",
    "check('held_item_mirror' in _rd8, 'readme 写明手持物品镜像开关')",
    "check('mine_depth' in _rd8 and 'prospect' in _rd8, 'readme 写明不垂直下挖 + 探矿两项')",
    "",
)
anchor = "print('=== 最后：工程门禁（本机实跑） ===')"
assert s.count(anchor) == 1
s = s.replace(anchor, sec + anchor, 1)

io.open(P180, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P180, len(s), 'chars')
