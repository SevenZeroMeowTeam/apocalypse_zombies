# -*- coding: utf-8 -*-
"""由 _deploy_195.py 生成 _deploy_196.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 15→16 /
新增一节「村民自己管门与种地」）。

只定点改写、不全局替换 —— _deploy_195.py 里出现的 1.1.95 / 1.1.94 有些是历史引用，
一起改就把历史抹了。1.1.96 的断言段放在 tools/_assert_196.py，直接读进来。
"""
import io

P195 = 'F:/mcmod/tools/_deploy_195.py'
P196 = 'F:/mcmod/tools/_deploy_196.py'
A196 = 'F:/mcmod/tools/_assert_196.py'

s = io.open(P195, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.95'" + CR + "PREV = '1.1.94'", "VER = '1.1.96'" + CR + "PREV = '1.1.95'")
rep("# 认三版：1.1.93（正式版，未装机）、1.1.94（装机在册的上一版）、本版。",
    "# 认三版：1.1.94（正式版，未装机）、1.1.95（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.93', PREV, VER)", "ACCEPT = ('1.1.94', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.96 出货：村民自己管门与种地。',
    '',
    '本版内容：一个新文件（VillagerChores）+ 村民 tick 挂一行 + 三个配置项 + 文档同步。',
    '  * **两件事**：白天把门打开 / 夜里关上；成熟的作物（小麦 / 胡萝卜 / 马铃薯 / 甜菜）当轮收掉',
    '    并补种 —— 先用一颗当种子补上，其余进村民自己的背包，满了丢在脚边。',
    '  * **为什么不做成 Goal**：村民的日程走 Brain 的活动系统（WORK / IDLE / PANIC），移动由',
    '    MoveToTargetSink 下发，自己往 goalSelector 里挂 Goal 会和它抢 Flag.MOVE；而这两件事都',
    '    **不需要移动**（站在原地就能干完），所以挂在 MobAiEnhanced 的村民 tick 那一支上，',
    '    与「恐慌 + 呼救铁傀儡」共用同一个节流（villager_interval，默认 20 tick）与相位打散。',
    '  * **门的三条规矩**（最容易写漏的地方）：铁门不碰（那是玩家上锁用的）；两半必须手动同步',
    '    （setBlock 不会像玩家交互那样联动另一半，只改一半会得到一扇错开的门）；门 1.5 格内有',
    '    活物就这一轮不动手，免得把谁夹在门里。',
    '  * **开销**：一轮是 半径 × 5 × 半径 的方块带（y 只上下探 2 格），默认半径 6 → 约 845 格，',
    '    同屏 N 个村民摊到每 tick 上是 N/20 轮。',
    '  * **新配置 3 项**：villager_door_enabled / villager_farm_enabled / villager_chore_radius',
    '    （默认 6，域 2~24）。配置总数 151 → 154，图形界面是反射列的会自动多三行，但两处写死的',
    '    「151 项」注释与两份文档要跟着改。',
    '  * 不回归：1.1.95 的枪械物品栏缩放、1.1.94 的铜斧、1.1.93 的音效换源、1.1.92 的七件铜装备、',
    '    1.1.91 的爆炸弹与十字弩弦姿态、1.1.90 的 BulletRay、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_196.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_196.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_196.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.96；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.96 本体：VillagerChores 在（门的三条规矩 + 四种作物的种子映射 + 不用 getBaseSeedId）、',
    '     挂载点是村民 tick 且排在恐慌判定之前、没进 goalSelector、配置三项到位且被读上、',
    '     两处「151 项」已改成 154；',
    '  5. 不回归：1.1.95 的八把枪 gui.scale、1.1.94 的铜斧（7.0F/-3.2F）、1.1.93 的音效（guns/ 17 个）、',
    '     1.1.92 的铜装备三条口径、1.1.91 的 AmmoEffects 与十字弩弦姿态、1.1.90 的 BulletRay、',
    '     1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.96 条目与头表、wiki 02/07 同步、gradle.properties == 1.1.96；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号：只换分母 15 → 16，不挪号 ----
# 编号早就有缺号与重号（每版插新段时没给新段自己腾号），它只是进度显示、不参与任何判据，
# 所以这里只换分母，谁在就是谁，免得再因为「某个号不存在」而 assert 死。
for n in range(16):
    s = s.replace('=== %d/15 ' % n, '=== %d/16 ' % n)

# ---- 4) 文档断言改到 1.1.96 ----
rep("check('### 1.1.95 —' in rd, 'readme 有 1.1.95 条目')",
    "check('### 1.1.96 —' in rd, 'readme 有 1.1.96 条目')")
rep("check('| **当前版本** | `1.1.95` |' in rd, 'readme 头表 == 1.1.95')",
    "check('| **当前版本** | `1.1.96` |' in rd, 'readme 头表 == 1.1.96')")
# 前面几段里读头表的断言（变量名 _rd）与 193 段的元组写法，一并换到 1.1.96 ——
# 头表全库只有一个值，升版后它们必然变红（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.95` |' in _rd, 'readme 头表 == 1.1.95')",
    "check('| **当前版本** | `1.1.96` |' in _rd, 'readme 头表 == 1.1.96')", n=5)
rep("('F:/mcmod/readme.md', '| **当前版本** | `1.1.95` |', 'readme 头表 == 1.1.95')",
    "('F:/mcmod/readme.md', '| **当前版本** | `1.1.96` |', 'readme 头表 == 1.1.96')")
rep("check('mod_version=1.1.95' in gp, 'gradle.properties mod_version=1.1.95')",
    "check('mod_version=1.1.96' in gp, 'gradle.properties mod_version=1.1.96')")

# ---- 5) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_195.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_196.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.96 那一节（正文读 _assert_196.py，整段缩进 4 格）----
body = io.open(A196, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/16 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P196, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P196, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
