# -*- coding: utf-8 -*-
"""由 _deploy_193.py 生成 _deploy_194.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 13→14 /
新增一节「铜装备补齐铜斧」）。

只定点改写、不全局替换 —— _deploy_193.py 里出现的 1.1.93 / 1.1.92 有些是历史引用，
一起改就把历史抹了。1.1.94 的断言段放在 tools/_assert_194.py，直接读进来。
"""
import io

P193 = 'F:/mcmod/tools/_deploy_193.py'
P194 = 'F:/mcmod/tools/_deploy_194.py'
A194 = 'F:/mcmod/tools/_assert_194.py'

s = io.open(P193, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.93'" + CR + "PREV = '1.1.92'", "VER = '1.1.94'" + CR + "PREV = '1.1.93'")
rep("# 认三版：1.1.91（GitHub 正式版，没装机）、1.1.92（装机在册的上一版）、本版。",
    "# 认三版：1.1.92（GitHub 上没有独立正式版）、1.1.93（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.91', PREV, VER)", "ACCEPT = ('1.1.92', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.94 出货：铜装备**补齐铜斧**。',
    '',
    '本版内容：一件物品（注册 / 模型 / 贴图 / 中英文案 / 配方）+ 生成器映射表加一行 + 文档同步。',
    '  * 1.1.92 那批铜装备是按玩家点名列的（剑 / 镐 / 锄 + 四件甲），漏了斧 —— 而斧在原版是与镐',
    '    并肩的第二把「主力工具」（砍木、破盾、当近战武器），缺了它这一档不成套。',
    '  * **数值照石斧，不是石剑**：斧头在 1.20.1 的伤害本来就比剑高一大截（石斧 9 点 vs 石剑 5 点），',
    '    所以照抄的是 STONE_AXE 的 AxeItem(7.0F, -3.2F)（1 + 7 + 1 = 9），不是石剑的 SwordItem(3, -2.4F)。',
    '    耐久 200 / 效率 5.0 / 挖掘等级同石都跟着 ModTiers.COPPER 走，与另三件铜工具同档。',
    '  * 贴图沿用「原版铁质 → 铜色」那套映射（copper_gear_art.py 的映射表加一行，现在 10 张）；',
    '    配方照原版斧形（三个铜锭 + 两根木棍），创造模式进工具页。',
    '  * 不回归：1.1.92 那七件铜装备（三条口径 + 五件套）、1.1.93 的音效换源、1.1.91 的爆炸弹与',
    '    十字弩弦姿态、1.1.90 的 BulletRay、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_194.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_194.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_194.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.94；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.94 本体：铜斧的数值（7.0F / -3.2F，同石斧）+ 五件套 + 生成器映射表有它 + 全库八件',
    '     铜装备都在册且都进了创造页；',
    '  5. 不回归：1.1.93 的音效（guns/ 17 个、sounds.json 键全指 guns/、borrowedEntries 不含音效）、',
    '     1.1.92 的铜装备三条口径、1.1.91 的 AmmoEffects 与十字弩弦姿态、1.1.90 的 BulletRay、',
    '     1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.94 条目与头表、wiki 02/06/07 同步、gradle.properties == 1.1.94；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号：只换分母 13 → 14，**不挪号** ----
# 早几版插入新段时只把「比新段更大的号」整体 +1，却没有给新段自己腾出号 —— 于是编号早就有
# 缺号（根本没有 8/13）与重号（9/13 同时是 192 段和 193 段）。编号纯粹是进度显示、不参与任何
# 判据，所以这里不去重构它：只把分母统一换掉，谁在就是谁，免得再因为「某个号不存在」而 assert 死。
for n in range(14):
    s = s.replace('=== %d/13 ' % n, '=== %d/14 ' % n)

# ---- 4) 文档断言改到 1.1.94 ----
rep("check('### 1.1.93 —' in rd, 'readme 有 1.1.93 条目')",
    "check('### 1.1.94 —' in rd, 'readme 有 1.1.94 条目')")
rep("check('| **当前版本** | `1.1.93` |' in rd, 'readme 头表 == 1.1.93')",
    "check('| **当前版本** | `1.1.94` |' in rd, 'readme 头表 == 1.1.94')")
# 190 / 191 / 192 三段各有一条读头表的断言（变量名是 _rd）；193 段用的是「路径 + needle」元组。
# 头表全库只有一个值，升版后它们必然变红，所以照样换到 1.1.94（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.93` |' in _rd, 'readme 头表 == 1.1.93')",
    "check('| **当前版本** | `1.1.94` |' in _rd, 'readme 头表 == 1.1.94')", n=3)
rep("('F:/mcmod/readme.md', '| **当前版本** | `1.1.93` |', 'readme 头表 == 1.1.93')",
    "('F:/mcmod/readme.md', '| **当前版本** | `1.1.94` |', 'readme 头表 == 1.1.94')")
rep("check('mod_version=1.1.93' in gp, 'gradle.properties mod_version=1.1.93')",
    "check('mod_version=1.1.94' in gp, 'gradle.properties mod_version=1.1.94')")

# ---- 5) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_193.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_194.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.94 那一节（正文读 _assert_194.py，整段缩进 4 格）----
body = io.open(A194, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/14 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P194, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P194, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
