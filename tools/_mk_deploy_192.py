# -*- coding: utf-8 -*-
"""由 _deploy_191.py 生成 _deploy_192.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 11→12 /
新增一节「一整套铜装备」）。

只定点改写、不全局替换 —— _deploy_191.py 里出现的 1.1.91 / 1.1.90 有些是历史引用，
一起改就把历史抹了。1.1.92 的断言段放在 tools/_assert_192.py，直接读进来（不在生成器里写转义）。
"""
import io

P191 = 'F:/mcmod/tools/_deploy_191.py'
P192 = 'F:/mcmod/tools/_deploy_192.py'
A192 = 'F:/mcmod/tools/_assert_192.py'

s = io.open(P191, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.91'" + CR + "PREV = '1.1.90'", "VER = '1.1.92'" + CR + "PREV = '1.1.91'")
rep("# 认三版：1.1.89（只在 GitHub 上，没装机）、1.1.90（装机在册的上一版）、本版。",
    "# 认三版：1.1.90（GitHub 正式版，没装机）、1.1.91（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.89', PREV, VER)", "ACCEPT = ('1.1.90', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.92 出货：新增一整套**铜装备**（铜剑 / 铜镐 / 铜锄 / 铜头盔 / 铜胸甲 / 铜护腿 / 铜靴）。',
    '',
    '本版内容：两个新注册表 + 七件物品 + 九张贴图 + 七个配方 + 中英文案。',
    '  * **定位**：原版五档之间没有铜这一层 —— 石（耐久 131、攻击 +1、石级挖掘）上去直接是铁',
    '    （250、+2、铁级）。铜补的是**石与铁之间**那一格，三条口径都是玩家点名要的：',
    '    · 工具耐久 200（石 131 → 高）；',
    '    · 武器攻击加成 +1（与石**齐平** ⇒ 铜剑与石剑同为 5 点）；',
    '    · 护甲值 2/4/3/1 合计 10（皮革 7 → 高，铁 15 → 低；头盔单件与铁同为 2 —— 原版护甲值是',
    '      整数，皮革的 1 与铁的 2 之间没有第三个数，所以这条落在整套总和上）。',
    '  * **其余口径**：挖掘等级同石；效率 5.0（石 4.0 / 铁 6.0）；附魔性 12（石 5 / 铁 14）；',
    '    护甲耐久系数 11（皮革 5 / 铁 15）。修复材料一律铜锭，穿戴音借铁的。',
    '  * **注册表**：`registry/ModTiers`（ForgeTier）+ `registry/ModArmorMaterials`（枚举实现',
    '    ArmorMaterial，护甲值按 ArmorItem.Type 逐个写明 —— 原版那个数组的顺序在版本间换过）。',
    '  * **贴图**：`tools/copper_gear_art.py` 把原版铁质装备贴图做「铁 → 铜」色调映射，',
    '    含穿在身上的两层 copper_layer_1/2.png。',
    '  * **配方**：与原版石/铁装备同形，材料换铜锭（工具另加木棍）—— 本模组第一批标准合成配方。',
    '  * 不回归：1.1.91 的爆炸弹修复与十字弩三处姿态、1.1.90 的 BulletRay 与七把枪、',
    '    1.1.89 的 AI 端点迁移、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_192.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_192.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_192.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.92；',
    '  2. 包内 RSC 资产齐全且规格正确（19 骨 / 577 方块 / 512² / 8 条片段长度逐条对得上 Java 常量），',
    '     且剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.92 本体：铜的三条口径（耐久 > 石 / 攻击加成 == 石 / 护甲合计介于皮革与铁之间）',
    '     + 七件物品的注册·模型·贴图·lang·配方五件套 + 两个穿戴图层；',
    '  5. 不回归：1.1.91 的 AmmoEffects 合闸与十字弩弦姿态、1.1.90 的 BulletRay 与七把枪、',
    '     1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.92 条目与头表、wiki 02/06/07 同步、gradle.properties == 1.1.92；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号 11 → 12（先高后低：8~11 各往后挪一格，0~7 只换分母，免得级联替换）----
for n in (11, 10, 9, 8):
    rep('=== %d/11 ' % n, '=== %d/12 ' % (n + 1))
for n in (7, 6, 5, 4, 3, 2, 1, 0):
    rep('=== %d/11 ' % n, '=== %d/12 ' % n)

# ---- 4) 文档断言改到 1.1.92 ----
rep("check('### 1.1.91 —' in rd, 'readme 有 1.1.91 条目')",
    "check('### 1.1.92 —' in rd, 'readme 有 1.1.92 条目')")
rep("check('| **当前版本** | `1.1.91` |' in rd, 'readme 头表 == 1.1.91')",
    "check('| **当前版本** | `1.1.92` |' in rd, 'readme 头表 == 1.1.92')")
# 1.1.90 与 1.1.91 两段各有一条读头表的断言（变量名是 _rd）—— 头表全库只有一个值，
# 升版后它们必然变红，所以照样换到 1.1.92（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.91` |' in _rd, 'readme 头表 == 1.1.91')",
    "check('| **当前版本** | `1.1.92` |' in _rd, 'readme 头表 == 1.1.92')", n=2)
rep("check('mod_version=1.1.91' in gp, 'gradle.properties mod_version=1.1.91')",
    "check('mod_version=1.1.92' in gp, 'gradle.properties mod_version=1.1.92')")

# ---- 5) 189 段里那条「读门禁脚本自己」的自检，路径得跟着走（不改就永远在查上一版）----
rep("open('F:/mcmod/tools/_deploy_191.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_192.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.92 那一节（正文读 _assert_192.py，整段缩进 4 格）----
body = io.open(A192, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 10/12 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P192, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P192, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
