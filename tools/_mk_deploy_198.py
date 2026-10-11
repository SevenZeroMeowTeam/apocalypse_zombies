# -*- coding: utf-8 -*-
"""由 _deploy_197.py 生成 _deploy_198.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 17→18 /
新增一节「修 EasyNPC 武器商预设」，并把 197 段里写死的 readme 行数改成现状）。

只定点改写、不全局替换 —— _deploy_197.py 里出现的 1.1.97 / 1.1.96 有些是历史引用，
一起改就把历史抹了。1.1.98 的断言段放在 tools/_assert_198.py，直接读进来。
"""
import io

P197 = 'F:/mcmod/tools/_deploy_197.py'
P198 = 'F:/mcmod/tools/_deploy_198.py'
A198 = 'F:/mcmod/tools/_assert_198.py'

s = io.open(P197, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.97'" + CR + "PREV = '1.1.96'", "VER = '1.1.98'" + CR + "PREV = '1.1.97'")
rep("# 认三版：1.1.95（正式版，未装机）、1.1.96（装机在册的上一版）、本版。",
    "# 认三版：1.1.96（正式版，未装机）、1.1.97（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.95', PREV, VER)", "ACCEPT = ('1.1.96', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.98 出货：修 EasyNPC 武器商预设（原来是个空商店）。',
    '',
    '本版内容：一个预设文件重写（+ 挪到 EasyNPC 认的路径）+ 文档。**没有 Java 改动。**',
    '  * **症状**：摆下武器商，右键能开交易界面但**一件商品都没有**；导入时还打两条',
    '    「limited by server rules」的提示。',
    '  * **提示那条不是问题**：`Owner data was updated` / `Action permission levels were reduced`',
    '    是 EasyNPC 对**每个**预设都做的净化（PresetAccess + sanitize.* 文案），官方内置预设',
    '    welcome_coin_trader 导入时一字不差地打同样两条。第二条是动作权限被夹到 security.cfg 的',
    '    creativePlayerCommandLevel（默认 MODERATORS），抬到 OWNERS 即可。',
    '  * **真问题两个**（都是「按类结构反推 SNBT」的代价）：',
    '      ① TradingDataSet 原来写在 data 顶层，而 EasyNPC 读的是 data.TradingData.TradingDataSet',
    '         —— 层级错 ⇒ 交易设置整段被忽略；',
    '      ② 没有 Offers 段，而商品在 data.Offers.Recipes.Recipes[] —— 整段缺失 ⇒ 空商店。',
    '    javap 能给出字段名，给不出层级，所以正解是**先找一个官方同类预设当模板**。',
    '  * **修完的预设**：七条交易（六把枪 + 十字弩，全装满弹、绿宝石定价、每 30 分钟补货），',
    '    补齐 Offers / PresetUUID / Profession / SkinData / SoundData / EntityAttribute；',
    '    并从 api/preset/apocalypse_zombies/ 挪到 default_preset/villager/（官方 24 个默认预设同级）。',
    '  * 不回归：1.1.97 的 readme 过账、1.1.96 的村民管门与种地、1.1.95 的八把枪图标缩放、',
    '    1.1.94 的铜斧、1.1.93 的音效换源、1.1.92 的七件铜装备、1.1.91 的爆炸弹、猫耳娘 v4、RSC M1917。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_198.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_198.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_198.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.98；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.98 本体：TradingDataSet 嵌在 TradingData 内（不是顶层）、Offers.Recipes.Recipes 有',
    '     恰好七条 sell、六把枪都在且每把的弹量与 Java 的 MAGAZINE_SIZE **逐一相等**、',
    '     官方那六个字段都补齐、旧路径已删除；',
    '  5. 不回归：1.1.97 的文档一致性断言、1.1.96 的 VillagerChores 与三个配置项、',
    '     1.1.95 的八把枪 gui.scale、1.1.94 的铜斧、1.1.93 的音效（guns/ 17 个）、',
    '     猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.98 条目与头表、wiki 07 同步、EasyNPC-武器商.md 写清新结构与根因、',
    '     gradle.properties == 1.1.98；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号：只换分母 17 → 18，不挪号 ----
# 编号早就有缺号与重号（每版插新段时没给新段自己腾号），它只是进度显示、不参与任何判据，
# 所以这里只换分母，谁在就是谁，免得再因为「某个号不存在」而 assert 死。
for n in range(18):
    s = s.replace('=== %d/17 ' % n, '=== %d/18 ' % n)

# ---- 4) 文档断言改到 1.1.98 ----
rep("check('### 1.1.97 —' in rd, 'readme 有 1.1.97 条目')",
    "check('### 1.1.98 —' in rd, 'readme 有 1.1.98 条目')")
rep("check('| **当前版本** | `1.1.97` |' in rd, 'readme 头表 == 1.1.97')",
    "check('| **当前版本** | `1.1.98` |' in rd, 'readme 头表 == 1.1.98')")
# 前面几段里读头表的断言（变量名 _rd）与 193 段的元组写法，一并换到 1.1.98 ——
# 头表全库只有一个值，升版后它们必然变红（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')",
    "check('| **当前版本** | `1.1.98` |' in _rd, 'readme 头表 == 1.1.98')", n=7)
rep("('F:/mcmod/readme.md', '| **当前版本** | `1.1.97` |', 'readme 头表 == 1.1.97')",
    "('F:/mcmod/readme.md', '| **当前版本** | `1.1.98` |', 'readme 头表 == 1.1.98')")
rep("check('mod_version=1.1.97' in gp, 'gradle.properties mod_version=1.1.97')",
    "check('mod_version=1.1.98' in gp, 'gradle.properties mod_version=1.1.98')")

# ---- 5) 197 段里写死的 readme 行数跟着走（写死在门禁里就会漂，这是它的代价）----
rep("check('1975 行' in _wr, 'wiki 索引写的是 readme 的真实行数（1975）')",
    "check('1999 行' in _wr, 'wiki 索引写的是 readme 的真实行数（1999）')")
rep("abs(_lines - 1975) <= 40, 'readme 行数仍与文档里写的 1975 同一量级'",
    "abs(_lines - 1999) <= 60, 'readme 行数仍与文档里写的 1999 同一量级'")

# ---- 6) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_197.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_198.py', encoding='utf-8').read()")

# ---- 7) 插入 1.1.98 那一节（正文读 _assert_198.py，整段缩进 4 格）----
body = io.open(A198, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/18 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P198, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P198, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
