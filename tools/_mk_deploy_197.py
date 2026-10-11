# -*- coding: utf-8 -*-
"""由 _deploy_196.py 生成 _deploy_197.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 16→17 /
新增一节「全部 readme 过一次账」）。

只定点改写、不全局替换 —— _deploy_196.py 里出现的 1.1.96 / 1.1.95 有些是历史引用，
一起改就把历史抹了。1.1.97 的断言段放在 tools/_assert_197.py，直接读进来。
"""
import io

P196 = 'F:/mcmod/tools/_deploy_196.py'
P197 = 'F:/mcmod/tools/_deploy_197.py'
A197 = 'F:/mcmod/tools/_assert_197.py'

s = io.open(P196, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.96'" + CR + "PREV = '1.1.95'", "VER = '1.1.97'" + CR + "PREV = '1.1.96'")
rep("# 认三版：1.1.94（正式版，未装机）、1.1.95（装机在册的上一版）、本版。",
    "# 认三版：1.1.95（正式版，未装机）、1.1.96（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.94', PREV, VER)", "ACCEPT = ('1.1.95', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.97 出货：**全部 readme 过一次账**（只改文档，没碰代码）。',
    '',
    '本版内容：8 份 readme / 台账里的过期描述改成现状 + 版本号与日志。**没有 Java 改动。**',
    '  * **四处实证错误**：',
    '      - art/crossbow/DELIVERY.md 偏差 #9「物品栏图标约 4 px，未修待定」→ 1.1.95 已修（0.30→1.20）；',
    '        紧跟的「待定 #2 是否四把枪一起放大」也随之已决。',
    '      - art/uzi/DELIVERY.md「Java 同步：未做，UziItem 尚未落地」→ 早已落地（八个 clip 五個在用）。',
    '      - art/awm/README.md 与 art/m1garand/README.md 的署名表「22 个 TaCZ 音效 = 未修改副本，',
    '        只留在自用包」→ 1.1.93 已全部换成项目自备录音。',
    '      - art/m1garand/README.md 的 clip 表与待办 4「draw 尚未接线」→ 已接线（M1GarandItem.ANIM_DRAW）。',
    '  * **wiki 索引的数字对不上现状**（docs/wiki/README.md）：_deploy_140.py → 196；readme「514 行」',
    '    → 1975 行；门禁「13 个脚本」→ 18 个；tools「100+ 个脚本」→ 235 个；mod.toml 那条改准确',
    '    （build.gradle 只认 META-INF/mods.toml，根目录这个不参与构建）。',
    '  * **待办列表加了重核结论**（awm / m1garand）：WeaponMount 常量类确实仍未做、AWM 那 5 段 clip',
    '    仍未接线、持枪微动仍缺；但加兰德的 draw 已接线。核过的结论写进待办区顶部，免得照旧结论干活。',
    '  * **顺带记一笔**：art/awm/sounds/*.ogg（22 个 TaCZ 副本）仍在仓库里 —— 模组已不用它们，',
    '    但作为留档没删，所以与 art/awm/awm.animation.json 一样仍在公开仓库中（见 NOTICE.md）。',
    '  * 不回归：1.1.96 的村民管门与种地、1.1.95 的八把枪图标缩放、1.1.94 的铜斧、1.1.93 的音效换源、',
    '    1.1.92 的七件铜装备、1.1.91 的爆炸弹与十字弩弦姿态、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_197.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_197.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_197.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.97；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.97 本体：四处实证错误都改成了现状、wiki 索引的四个数字都对得上实物',
    '     （readme 行数 / tools 脚本数 / check_*.py 数都是**量出来的**）、核过「仍未做」的条目仍在；',
    '  5. 不回归：1.1.96 的 VillagerChores 与三个配置项、1.1.95 的八把枪 gui.scale、1.1.94 的铜斧、',
    '     1.1.93 的音效（guns/ 17 个）、1.1.92 的铜装备、1.1.91 的 AmmoEffects、1.1.90 的 BulletRay、',
    '     猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.97 条目与头表、wiki 07 同步、gradle.properties == 1.1.97；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号：只换分母 16 → 17，不挪号 ----
# 编号早就有缺号与重号（每版插新段时没给新段自己腾号），它只是进度显示、不参与任何判据，
# 所以这里只换分母，谁在就是谁，免得再因为「某个号不存在」而 assert 死。
for n in range(17):
    s = s.replace('=== %d/16 ' % n, '=== %d/17 ' % n)

# ---- 4) 文档断言改到 1.1.97 ----
rep("check('### 1.1.96 —' in rd, 'readme 有 1.1.96 条目')",
    "check('### 1.1.97 —' in rd, 'readme 有 1.1.97 条目')")
rep("check('| **当前版本** | `1.1.96` |' in rd, 'readme 头表 == 1.1.96')",
    "check('| **当前版本** | `1.1.97` |' in rd, 'readme 头表 == 1.1.97')")
# 前面几段里读头表的断言（变量名 _rd）与 193 段的元组写法，一并换到 1.1.97 ——
# 头表全库只有一个值，升版后它们必然变红（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.96` |' in _rd, 'readme 头表 == 1.1.96')",
    "check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')", n=6)
rep("('F:/mcmod/readme.md', '| **当前版本** | `1.1.96` |', 'readme 头表 == 1.1.96')",
    "('F:/mcmod/readme.md', '| **当前版本** | `1.1.97` |', 'readme 头表 == 1.1.97')")
rep("check('mod_version=1.1.96' in gp, 'gradle.properties mod_version=1.1.96')",
    "check('mod_version=1.1.97' in gp, 'gradle.properties mod_version=1.1.97')")

# ---- 5) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_196.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_197.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.97 那一节（正文读 _assert_197.py，整段缩进 4 格）----
body = io.open(A197, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/17 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P197, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P197, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
