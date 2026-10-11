# -*- coding: utf-8 -*-
"""由 _deploy_192.py 生成 _deploy_193.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 12→13 /
新增一节「枪械音效换成项目自备录音」）。

只定点改写、不全局替换 —— _deploy_192.py 里出现的 1.1.92 / 1.1.91 有些是历史引用，
一起改就把历史抹了。1.1.93 的断言段放在 tools/_assert_193.py，直接读进来。
"""
import io

P192 = 'F:/mcmod/tools/_deploy_192.py'
P193 = 'F:/mcmod/tools/_deploy_193.py'
A193 = 'F:/mcmod/tools/_assert_193.py'

s = io.open(P192, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.92'" + CR + "PREV = '1.1.91'", "VER = '1.1.93'" + CR + "PREV = '1.1.92'")
rep("# 认三版：1.1.90（GitHub 正式版，没装机）、1.1.91（装机在册的上一版）、本版。",
    "# 认三版：1.1.91（GitHub 正式版，没装机）、1.1.92（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.90', PREV, VER)", "ACCEPT = ('1.1.91', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')
te = s.index('"""', i + 3)
head = L(
    '"""1.1.93 出货：枪械音效全部换成**项目自备的录音**（顺手切掉「纯净包没声音」）。',
    '',
    '本版内容：音效换源 + 两条新事件 + 构建脚本的借用清单收窄 + 一批文档同步。',
    '  * **换掉了什么**：22 条音效事件此前指向 TaCZ 的 AWM 录音（借用，CC BY-NC-ND 4.0），',
    '    文件在 assets/apocalypse_zombies/sounds/awm/（22 个 / 604 KB）。现在整套换成',
    '    sounds/guns/ 里项目自备的 17 个录音，awm/ 目录已删除。',
    '  * **事件名一个没改**：sounds.json 的键、ModSounds 的常量、各枪的 tick→cue 时刻表是同一份',
    '    契约，所以换音源只是把每个键指向的文件重新指一遍，七把枪的时刻表一行未动。',
    '  * **两条新事件**：uzi_shoot（四支 AK 录音）与 crossbow_shoot（三支弩弦）—— 同一条 event',
    '    挂多支，播放时随机挑一支，连发不像复读；这是共用一条 AWM 录音做不到的。',
    '  * **副产品**：build.gradle 的 borrowedEntries 原来整目录排除 sounds/** 与 sounds.json',
    '    （为剥掉 AWM 音效），代价是纯净包连背景音乐一起没了 —— 哑巴包。音源换成自备的之后不必',
    '    再排除，-clean.jar 从这一版起有声音；借用清单只剩 animations/awm.animation.json 一项，',
    '    borrowedPack 也随之只剩动画，cleanMeta 生成的 NOTICE 文案同步改写。',
    '  * crossbow_hit 已注册、素材就位，但当前没有调用点（弩命中沿用原版箭矢声）；',
    '    alarm_siren_a/b 两支警报暂未接入 —— 项目里还没有警报场景。',
    '  * 不回归：1.1.92 的七件铜装备、1.1.91 的爆炸弹修复与十字弩三处姿态、1.1.90 的 BulletRay、',
    '    1.1.89 的 AI 端点迁移、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_193.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_193.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_193.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.93；',
    '  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.93 本体：awm/ 已删、guns/ 17 个自备录音到位、sounds.json 每个键都指到 guns/ 且文件',
    '     真在、事件名未变、两条新事件有人用、build.gradle 不再排除音效；',
    '  5. 不回归：1.1.92 的铜装备（三条口径 + 五件套）、1.1.91 的 AmmoEffects 与十字弩弦姿态、',
    '     1.1.90 的 BulletRay 与七把枪、1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.93 条目与头表、wiki 01/02/03/07/08 同步、NOTICE 记了音效换源、',
    '     gradle.properties == 1.1.93；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号 12 → 13（先高后低：8~12 各往后挪一格，0~7 只换分母）----
for n in (12, 11, 10, 9, 8):
    rep('=== %d/12 ' % n, '=== %d/13 ' % (n + 1))
for n in (7, 6, 5, 4, 3, 2, 1, 0):
    rep('=== %d/12 ' % n, '=== %d/13 ' % n)

# ---- 4) 文档断言改到 1.1.93 ----
rep("check('### 1.1.92 —' in rd, 'readme 有 1.1.92 条目')",
    "check('### 1.1.93 —' in rd, 'readme 有 1.1.93 条目')")
rep("check('| **当前版本** | `1.1.92` |' in rd, 'readme 头表 == 1.1.92')",
    "check('| **当前版本** | `1.1.93` |' in rd, 'readme 头表 == 1.1.93')")
# 190 / 191 / 192 三段各有一条读头表的断言（变量名是 _rd）—— 头表全库只有一个值，
# 升版后它们必然变红，所以照样换到 1.1.93（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.92` |' in _rd, 'readme 头表 == 1.1.92')",
    "check('| **当前版本** | `1.1.93` |' in _rd, 'readme 头表 == 1.1.93')", n=3)
rep("check('mod_version=1.1.92' in gp, 'gradle.properties mod_version=1.1.92')",
    "check('mod_version=1.1.93' in gp, 'gradle.properties mod_version=1.1.93')")

# ---- 5) 上一版门禁脚本里那条「读自己」的自检，路径得跟着走 ----
rep("open('F:/mcmod/tools/_deploy_192.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_193.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.93 那一节（正文读 _assert_193.py，整段缩进 4 格）----
body = io.open(A193, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 11/13 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P193, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P193, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
