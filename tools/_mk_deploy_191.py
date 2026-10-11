# -*- coding: utf-8 -*-
"""由 _deploy_190.py 生成 _deploy_191.py（版本号 / 基线 / 头注释 / 文档断言 / 段落编号 10→11 /
新增一节「爆炸弹只有特效没有伤害 —— 防递归闸补齐」）。

只定点改写、不全局替换 —— _deploy_190.py 里出现的 1.1.90 / 1.1.89 有些是历史引用，
一起改就把历史抹了。1.1.91 的断言段放在 tools/_assert_191.py，直接读进来（不在生成器里写转义）。
"""
import io

P190 = 'F:/mcmod/tools/_deploy_190.py'
P191 = 'F:/mcmod/tools/_deploy_191.py'
A191 = 'F:/mcmod/tools/_assert_191.py'

s = io.open(P190, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.90'" + CR + "PREV = '1.1.89'", "VER = '1.1.91'" + CR + "PREV = '1.1.90'")
rep("# 认三版：1.1.88（只在 GitHub 上，没装机）、1.1.89（装机在册的上一版）、本版。",
    "# 认三版：1.1.89（只在 GitHub 上，没装机）、1.1.90（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.88', PREV, VER)", "ACCEPT = ('1.1.89', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')            # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.91 出货：**爆炸弹「只有特效、一点血都不掉」** —— 补上那道只装了一半的防递归闸。',
    '',
    '本版内容：只改一个文件 `event/AmmoEffects.java`，资产与其余 Java 逻辑一行未动。',
    '  * **病根**：防递归的 `detonating` 有声明、`onLivingHurt` 开头也有 `if (detonating) return;`，',
    '    但**全文件没有一处把它设成 `true`** —— 闸只装了一半。爆炸拿 `player` 当伤害来源，于是爆炸',
    '    造成的每一次 `hurt` 都重新走进这个事件、重新满足「手里是爆炸弹」、再引爆一次：自己引爆自己，',
    '    无限递归到 `StackOverflowError`。',
    '  * **为什么看着像「特效正常、伤害消失」**：`detonate()` 一进门就发粒子与音效，而 Forge 的',
    '    `LivingHurtEvent` 触发点在伤害**真正应用之前** —— 栈被打爆时那一发伤害还没落地，于是命中伤害',
    '    与范围伤害一起作废。特效与伤害看着是两件事，其实是同一处的两端。',
    '  * **修法**：`detonate()` 里补合闸（`if (detonating) return;` + `detonating = true;`），整段用',
    '    `try/finally` 收口 —— 用 `finally` 而不是末尾复位，是为了异常路径也把闸放开（锁死 = 连特效都没了）。',
    '  * 口径一字未动：半径 2.5 / 中心 14 点 / 线性衰减 / 引信 6 点 / 只伤 Enemy / 不动地形 / 玩家不在范围内。',
    '  * 不回归：1.1.90 的 BulletRay 三处口径与七把枪、1.1.89 的 AI 端点迁移、猫耳娘 v4、RSC M1917 全套。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_191.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_191.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_191.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.91；',
    '  2. 包内 RSC 资产齐全且规格正确（19 骨 / 577 方块 / 512² / 8 条片段长度逐条对得上 Java 常量），',
    '     且剪影对表过门禁；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 1.1.91 本体：闸的声明 / 检查 / 上锁 / 解锁四件都在且各自唯一、位置对（检查在事件里、上锁在',
    '     `detonate` 里）、`try/finally` 收口、口径未动、与「士兵僵尸免疫爆炸」那个刻意设定分开；',
    '  5. 不回归：1.1.90 的 BulletRay 与七把枪、1.1.89 的迁移、猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；',
    '  6. 文档：readme 有 1.1.91 条目与头表、wiki 02/06/07 同步、gradle.properties == 1.1.91；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号 10 → 11（先高后低：7~10 各往后挪一格，0~6 只换分母，免得级联替换）----
for n in (10, 9, 8, 7):
    rep('=== %d/10 ' % n, '=== %d/11 ' % (n + 1))
for n in (6, 5, 4, 3, 2, 1, 0):
    rep('=== %d/10 ' % n, '=== %d/11 ' % n)

# ---- 4) 文档断言改到 1.1.91 ----
rep("check('### 1.1.90 —' in rd, 'readme 有 1.1.90 条目')",
    "check('### 1.1.91 —' in rd, 'readme 有 1.1.91 条目')")
rep("check('| **当前版本** | `1.1.90` |' in rd, 'readme 头表 == 1.1.90')",
    "check('| **当前版本** | `1.1.91` |' in rd, 'readme 头表 == 1.1.91')")
# 1.1.90 段自己也有一条读 readme 头表的断言（变量名是 _rd，不是上面的 rd）——
# 头表全库只有一个值，升版后它必然变红，所以照样换到 1.1.91（旧断言不是删掉，是换口径）。
rep("check('| **当前版本** | `1.1.90` |' in _rd, 'readme 头表 == 1.1.90')",
    "check('| **当前版本** | `1.1.91` |' in _rd, 'readme 头表 == 1.1.91')")
rep("check('mod_version=1.1.90' in gp, 'gradle.properties mod_version=1.1.90')",
    "check('mod_version=1.1.91' in gp, 'gradle.properties mod_version=1.1.91')")

# ---- 5) 189 段里那条「读门禁脚本自己」的自检，路径得跟着走（不改就永远在查上一版）----
rep("open('F:/mcmod/tools/_deploy_190.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_191.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.91 那一节（正文读 _assert_191.py，整段缩进 4 格）----
body = io.open(A191, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 9/11 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P191, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P191, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))
