# -*- coding: utf-8 -*-
"""由 _deploy_194.py 生成 _deploy_195.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 14→15 /
新增一节「枪械物品栏显示放大」）。

只定点改写、不全局替换 —— _deploy_194.py 里出现的 1.1.94 / 1.1.93 有些是历史引用，
一起改就把历史抹了。1.1.95 的断言段放在 tools/_assert_195.py，直接读进来。
"""
import io

P194 = 'F:/mcmod/tools/_deploy_194.py'
P195 = 'F:/mcmod/tools/_deploy_195.py'
A195 = 'F:/mcmod/tools/_assert_195.py'

s = io.open(P194, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.94'" + CR + "PREV = '1.1.93'", "VER = '1.1.95'" + CR + "PREV = '1.1.94'")
rep("# 认三版：1.1.92（GitHub 上没有独立正式版）、1.1.93（装机在册的上一版）、本版。",
    "# 认三版：1.1.93（正式版，未装机）、1.1.94（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.92', PREV, VER)", "ACCEPT = ('1.1.93', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.95 出货：枪械**物品栏显示放大**到与金剑相近的比例。',
    '',
    '本版内容：八把枪的 display.gui.scale + 一批文档同步。**没有碰贴图，也没有碰 Java。**',
    '  * **根因**：枪械模型是 "parent": "builtin/entity" —— 真正画它的是 GeckoLib 的',
    '    BlockEntityWithoutLevelRenderer（3D 模型），物品栏里多大**只由 display.gui.scale 决定**，',
    '    而它一直是 0.30~0.36。贴图本身没问题（内容占满画布：awm 100%×88%、mosin 100%×44%），',
    '    所以「放大贴图」是错的解法。',
    '  * **新值怎么来**：读各枪 .geo.json 所有 cube 的联合包围盒得到真实全长，再按',
    '    「枪长 ≈ 格子宽度的 90%（14.5 / 16 像素）」反算 —— 枪长 0.76~1.50 格差一倍，',
    '    所以短枪放得多、长枪放得少，最后八把枪显示出来一样长。',
    '      awm 0.30→0.60   mosin 0.30→0.63   rsc_1917 0.32→0.69   s686 0.30→0.74',
    '      m1_garand 0.32→0.82   uzi 0.36→0.92   colt_1878 0.30→0.97   crossbow 0.30→1.20',
    '  * **只改 gui 一格**：其余槽位（三人称/一人称/ground/fixed/head）是「手里持枪」的构图，',
    '    动了会改坏手感 —— 门禁里因此有一条反向断言：除 gui 外各槽位 scale 必须仍 < 0.95。',
    '  * 不回归：1.1.94 的铜斧、1.1.93 的音效换源、1.1.92 的七件铜装备、1.1.91 的爆炸弹与十字弩弦',
    '    姿态、1.1.90 的 BulletRay、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_195.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_195.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_195.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.95；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.95 本体：八把枪的 gui.scale 等于新值、显示长度验算落在 13.5~15.5 像素、',
    '     其余槽位没被碰（< 0.95）；',
    '  5. 不回归：1.1.94 的铜斧（7.0F/-3.2F）、1.1.93 的音效（guns/ 17 个、键全指 guns/）、',
    '     1.1.92 的铜装备三条口径、1.1.91 的 AmmoEffects 与十字弩弦姿态、1.1.90 的 BulletRay、',
    '     1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.95 条目与头表、wiki 02/07 同步、gradle.properties == 1.1.95；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号：只换分母 14 → 15，不挪号 ----
# 编号早就有缺号与重号（每版插新段时没给新段自己腾号），它只是进度显示、不参与任何判据，
# 所以这里只换分母，谁在就是谁，免得再因为「某个号不存在」而 assert 死。
for n in range(15):
    s = s.replace('=== %d/14 ' % n, '=== %d/15 ' % n)

# ---- 4) 文档断言改到 1.1.95 ----
rep("check('### 1.1.94 —' in rd, 'readme 有 1.1.94 条目')",
    "check('### 1.1.95 —' in rd, 'readme 有 1.1.95 条目')")
rep("check('| **当前版本** | `1.1.94` |' in rd, 'readme 头表 == 1.1.94')",
    "check('| **当前版本** | `1.1.95` |' in rd, 'readme 头表 == 1.1.95')")
# 前面几段里读头表的断言（变量名 _rd）与 194 段的元组写法，一并换到 1.1.95 ——
# 头表全库只有一个值，升版后它们必然变红（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.94` |' in _rd, 'readme 头表 == 1.1.94')",
    "check('| **当前版本** | `1.1.95` |' in _rd, 'readme 头表 == 1.1.95')", n=4)
# 193 段用的是「路径 + needle」元组写法，也得跟着换（否则它指着 1.1.94 的头表必然变红）
rep("('F:/mcmod/readme.md', '| **当前版本** | `1.1.94` |', 'readme 头表 == 1.1.94')",
    "('F:/mcmod/readme.md', '| **当前版本** | `1.1.95` |', 'readme 头表 == 1.1.95')")
rep("check('mod_version=1.1.94' in gp, 'gradle.properties mod_version=1.1.94')",
    "check('mod_version=1.1.95' in gp, 'gradle.properties mod_version=1.1.95')")

# ---- 5) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_194.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_195.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.95 那一节（正文读 _assert_195.py，整段缩进 4 格）----
body = io.open(A195, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/15 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P195, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P195, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
